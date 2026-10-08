"""Personal Best Buy 75/85 inch TV deal monitor: API only, no scraping."""
import json
import os
import re
import sys
import time
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

CATEGORY = "abcat0101001"
LIMIT = Decimal("400")
SIZE = re.compile(r'(?<!\d)(75|85)[\s-]*(?:["\u201d\u2033]|inch(?:es)?\b|in\b\.?)', re.I)
MARKER = re.compile(r'<!-- tv-monitor key=([^ ]+) best=([0-9.]+) -->')

def request(url, method="GET", data=None, github=False):
    headers = {"Accept": "application/vnd.github+json" if github else "application/json",
               "User-Agent": "PrivateBestBuyTVDealMonitor/1.0"}
    if github:
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    body = json.dumps(data).encode() if data is not None else None
    for attempt in range(3):
        try:
            with urlopen(Request(url, data=body, headers=headers, method=method), timeout=25) as response:
                return json.load(response)
        except HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError("API returned HTTP " + str(e.code)) from None
        except (URLError, TimeoutError):
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError("API request failed due to network error") from None

def price(value):
    try:
        x = Decimal(str(value))
        return x if x.is_finite() and 0 < x < LIMIT else None
    except (InvalidOperation, ValueError, TypeError):
        return None

def screen_size(name):
    found = {int(x) for x in SIZE.findall(name)}
    return next(iter(found)) if len(found) == 1 else None

def clean_url(raw, sku):
    if isinstance(raw, str):
        u = urlsplit(raw)
        host = (u.hostname or "").lower()
        if u.scheme in ("http", "https") and (host == "bestbuy.com" or host.endswith(".bestbuy.com")):
            clean = [(k, v) for k, v in parse_qsl(u.query) if k.lower() not in ("apikey", "key")]
            return urlunsplit(("https", u.netloc, u.path, urlencode(clean), u.fragment))
    return "https://www.bestbuy.com/site/searchpage.jsp?" + urlencode({"st": sku})

def normalize(product, kind):
    sku = str(product.get("sku", ""))
    name = str((product.get("names") or {}).get("title", "")) if kind == "open" else str(product.get("name", ""))
    size = screen_size(name)
    if not sku.isdigit() or size is None:
        return []
    if kind == "new":
        offers = [("New", product.get("salePrice"))]
        url = product.get("url")
    else:
        offers = [("Open Box " + str(o.get("condition") or "Unknown").title(),
                   (o.get("prices") or {}).get("current")) for o in product.get("offers", [])]
        url = (product.get("links") or {}).get("web")
    result = []
    for condition, amount in offers:
        amount = price(amount)
        if amount is not None:
            result.append({"sku": sku, "name": name, "size": size, "condition": condition,
                           "price": amount, "url": clean_url(url, sku),
                           "key": sku + ":" + condition.lower().replace(" ", "-")})
    return result

def fetch_offers(key, endpoint, kind):
    found = []
    for page in range(1, 26):
        opts = {"apiKey": key, "pageSize": 100, "page": page}
        if kind == "new":
            opts.update({"format": "json", "show": "sku,name,salePrice,url"})
        data = request("https://api.bestbuy.com" + endpoint + "?" + urlencode(opts))
        rows = data.get("results", []) if kind == "open" else data.get("products", [])
        for item in rows:
            found.extend(normalize(item, kind))
        if kind == "open":
            total_pages = int((data.get("metadata") or {}).get("page", {}).get("total") or 1)
        else:
            total_pages = int(data.get("totalPages") or 1)
        if not rows or page >= total_pages:
            break
        if page == 25:
            print("WARNING: API results truncated at 25 pages", file=sys.stderr)
        time.sleep(0.25)
    return found

def find_deals(key):
    offers = fetch_offers(key, "/beta/products/openBox(categoryId=" + CATEGORY + ")", "open")
    try:
        # New offers also catch some advertised sale reductions.
        offers += fetch_offers(key, "/v1/products(categoryPath.id=" + CATEGORY + "&salePrice%3C400)", "new")
    except RuntimeError as exc:
        print("WARNING: Products API unavailable; open-box results still checked: " + str(exc), file=sys.stderr)
    best = {}
    for item in offers:
        if item["key"] not in best or item["price"] < best[item["key"]]["price"]:
            best[item["key"]] = item
    return sorted(best.values(), key=lambda x: (x["price"], -x["size"]))

def gh(path, method="GET", data=None):
    repo = os.environ["GITHUB_REPOSITORY"]
    return request("https://api.github.com/repos/" + repo + path, method, data, github=True)

def previously_alerted():
    found = {}
    for page in range(1, 21):
        issues = gh("/issues?state=all&per_page=100&page=" + str(page))
        for issue in issues:
            if "pull_request" in issue:
                continue
            body = issue.get("body") or ""
            match = MARKER.search(body)
            if match:
                found[match.group(1)] = (int(issue["number"]), Decimal(match.group(2)), body)
        if len(issues) < 100:
            return found
    raise RuntimeError("Too many issues to deduplicate safely")

def issue_body(item):
    return (
        "<!-- tv-monitor key={key} best={price:.2f} -->\n"
        "Size: {size} inches\nModel: {name}\nBest Buy SKU: {sku}\n"
        "Condition: {condition}\nPre-tax price: USD {price:.2f}\n"
        "Link: {url}\n\n"
        "**Store availability NOT verified.** Set pickup ZIP to Gainesville 32608 and "
        "confirm actual price, condition, pickup and delivery. API offers can be nationwide "
        "ship-from-store listings. In-store-only markdowns may not appear in this API."
    ).format(**item)

def send_alerts(items):
    previous = previously_alerted()
    owner = os.environ["GITHUB_REPOSITORY"].split("/")[0]
    for item in items:
        key = item["key"]
        if key not in previous:
            title = '[TV Deal] {size}" | USD {price:.2f} | {condition} | SKU {sku}'.format(**item)
            new = gh("/issues", "POST", {"title": title, "body": issue_body(item), "assignees": [owner]})
            print("New issue alert:", new.get("html_url"))
        else:
            no, best, body = previous[key]
            if item["price"] < best:
                gh("/issues/" + str(no) + "/comments", "POST",
                   {"body": "Price fell from USD {:.2f} to USD {:.2f}. Local pickup not verified.\n{}".format(best, item["price"], item["url"])})
                updated = MARKER.sub("<!-- tv-monitor key={} best={:.2f} -->".format(key, item["price"]), body, count=1)
                gh("/issues/" + str(no), "PATCH", {"body": updated})
                print("Price-drop alert for issue", no)

def main():
    key = os.environ.get("BESTBUY_API_KEY", "").strip()
    if not key:
        print("BESTBUY_API_KEY GitHub Actions secret has not been set. Scan not executed.", file=sys.stderr)
        return 2
    offers = find_deals(key)
    print("Found", len(offers), "qualifying API deals")
    for item in offers:
        print('{size}" USD {price:.2f} {condition} {name} {url}'.format(**item))
    if os.environ.get("DRY_RUN", "").lower() == "true":
        print("Dry run; no alert issues posted.")
        return 0
    if not os.environ.get("GITHUB_TOKEN") or not os.environ.get("GITHUB_REPOSITORY"):
        print("GitHub credentials absent; no alerts posted", file=sys.stderr)
        return 2
    send_alerts(offers)
    return 0

if __name__ == "__main__":
    sys.exit(main())
