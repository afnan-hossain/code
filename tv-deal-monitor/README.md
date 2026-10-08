# Best Buy 75-inch / 85-inch TV deal monitor

Personal deal alerts for **75-inch and 85-inch TVs priced strictly below USD 400 before tax**.

The checker uses Best Buy's official Buying Options (open-box) and Products (new-item prices) APIs. It does not scrape BestBuy.com. GitHub Actions runs it around minute 17 each hour. New qualifying deals create GitHub Issues assigned to the repository owner; subsequent lower prices add an issue comment. Unchanged prices do not send repeated alerts.

## Finish setup (requires account-owner action)

1. Obtain your own developer key from https://developer.bestbuy.com/. Keep it private. Best Buy's registration and API terms apply.
2. Open the repository's **Settings > Secrets and variables > Actions > New repository secret**. Name it exactly **BESTBUY_API_KEY** and paste the value.
3. Merge the pull request adding this folder and .github/workflows/bestbuy-tv-deals.yml. Scheduled workflows only run on the default branch.
4. Go to **Actions > Best Buy large TV deal monitor > Run workflow**, choose a dry run first, then a normal run. Confirm the run succeeds. The script prints matching offers in the logs.
5. In personal GitHub **Settings > Notifications**, enable notifications for issue assignments (web, mobile or email as desired). Issue alerts in this public repository are public. GitHub notification delivery depends on your preferences.

The workflow uses the automatically generated GITHUB_TOKEN (no second secret required), Python's standard library only, and GitHub Issues for notifications. It requests only contents:read and issues:write.

## What it actually checks

- Best Buy Buying Options API open-box offers (excellent/certified where provided)
- Best Buy Products API listed new-product sale prices
- TV category **abcat0101001**
- Model titles clearly containing 75 or 85 inches
- Asking price under $400, excluding tax (not equal to $400)
- All brands, not just LG

Product information comes from publicly advertised API feeds. **This does not prove stock or price at any Gainesville store.** Open the offer and select your pickup ZIP, **32608**, to verify availability, actual condition and final cost. In-store-only markdowns like your friend's exceptionally low price may be absent from the Buying Options API. Clearance/refurbished inventory is not exhaustively covered.

For local/manual browsing: https://www.bestbuy.com/site/electronics/outlet-refurbished-clearance/pcmcat142300050026.c

## Running tests locally

In this folder, run:

    python -m unittest discover -s tests -v

Set BESTBUY_API_KEY to your key, then run:

    DRY_RUN=true python monitor.py

GitHub scheduled actions may occasionally be delayed. Public repositories can have schedule workflows disabled after prolonged inactivity; review the Actions tab periodically.

Best Buy API docs: https://bestbuyapis.github.io/api-documentation/#buying-options-api
Best Buy developer terms: https://developer.bestbuy.com/legal
