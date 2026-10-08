import sys
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import monitor

class MonitorTests(unittest.TestCase):
    def test_title_sizes(self):
        self.assertEqual(monitor.screen_size('LG 75" QNED 4K TV'), 75)
        self.assertEqual(monitor.screen_size("Sony 85-inch TV"), 85)
        self.assertEqual(monitor.screen_size("Samsung 85 in. QLED TV"), 85)
        self.assertIsNone(monitor.screen_size("65 inch TV"))
        self.assertIsNone(monitor.screen_size("75cm soundbar"))
    def test_exclusive_price_cap(self):
        self.assertEqual(monitor.price("399.99"), Decimal("399.99"))
        for x in ("400", "400.00", "-1", "0", "NaN", None):
            self.assertIsNone(monitor.price(x))
    def test_open_box_offer_and_condition(self):
        p = {"sku": "6673133", "names": {"title": 'LG 75" QNED'},
             "links": {"web": "https://www.bestbuy.com/site/tv/6673133.p"},
             "offers": [{"condition": "excellent", "prices": {"current": 399.99}},
                        {"condition": "certified", "prices": {"current": 449}}]}
        found = monitor.normalize(p, "open")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["condition"], "Open Box Excellent")
        self.assertEqual(found[0]["price"], Decimal("399.99"))
    def test_new_offer(self):
        found = monitor.normalize({"sku": "123", "name": 'Sony 85" 4K', "salePrice": 300}, "new")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["price"], Decimal(300))
    def test_no_api_key_leak(self):
        url = monitor.clean_url("https://www.bestbuy.com/site/tv?apiKey=SECRET&color=black", "123")
        self.assertNotIn("SECRET", url)
        self.assertNotIn("apiKey", url)
        self.assertEqual(monitor.clean_url("https://bad.example/items", "123"),
                         "https://www.bestbuy.com/site/searchpage.jsp?st=123")
    def test_locality_explicit(self):
        item = monitor.normalize({"sku": "123", "name": 'TCL 75" 4K', "salePrice": 390}, "new")[0]
        self.assertIn("Store availability NOT verified", monitor.issue_body(item))
    def test_dedup_cheapest(self):
        def pages(key, endpoint, kind):
            if kind == "open":
                return monitor.normalize({"sku": "123", "names": {"title": 'LG 75" QNED'},
                                          "offers": [{"condition": "excellent", "prices": {"current": 375}},
                                                     {"condition": "excellent", "prices": {"current": 360}}]}, kind)
            return monitor.normalize({"sku": "456", "name": 'Sony 85" 4K', "salePrice": 399}, kind)
        with patch.object(monitor, "fetch_offers", side_effect=pages):
            offers = monitor.find_deals("test-key")
        self.assertEqual(len(offers), 2)
        self.assertEqual(offers[0]["price"], Decimal(360))

if __name__ == "__main__":
    unittest.main()
