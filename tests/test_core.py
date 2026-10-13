import tempfile
import unittest
from pathlib import Path

from scoring import score
from utils import ensure_scheme, load_config, load_leads


class CoreTests(unittest.TestCase):
    def test_scheme(self):
        self.assertEqual(ensure_scheme("example.com"), "https://example.com")

    def test_lead_parsing_and_dedupe(self):
        content = (
            "SL-01\tA\tB\tOwner\tOne\texample.com\t\t123\ta@b.com\t\tX\tRetail\n"
            "SL-02\tC\tD\tOwner\tTwo\thttps://www.example.com/\t\t456\tc@d.com\t\tY\tRetail\n"
            "SL-03\tE\tF\tOwner\tBad\tnot a url\n"
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "leads.tsv"
            path.write_text(content, encoding="utf-8")
            leads, errors = load_leads(path)
        self.assertEqual(len(leads), 1)
        self.assertGreaterEqual(len(errors), 2)
        self.assertEqual(leads[0].website_url, "https://example.com")

    def test_scoring(self):
        cfg = load_config("config.yaml")
        checks = {
            "pagespeed": {"performance": 40, "lcp_ms": 5000, "cls": 0.3},
            "html_seo": {"title_missing": False, "meta_description_missing": True, "h1_count": 0, "images_missing_alt": 2, "canonical_missing": True},
            "security": {"https": True, "cert_days_remaining": 100, "hsts": False, "csp": False},
            "browser": {"horizontal_scroll_mobile": True, "broken_images": 1, "page_loaded": True},
            "ecommerce": {"is_store": True, "cart_status": "unknown", "checkout_status": "unknown"},
        }
        scores, issues = score(checks, cfg)
        self.assertLess(scores["overall"], 100)
        self.assertTrue(any(i.title == "Missing meta description" for i in issues))


if __name__ == "__main__":
    unittest.main()
