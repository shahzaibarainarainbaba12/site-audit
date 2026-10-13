from __future__ import annotations

import re
from typing import Any

import requests

FINGERPRINTS = [
    ("Shopify", [r"cdn\.shopify\.com", r"Shopify\.theme", r"shopify-section", r"x-shopid"]),
    ("WooCommerce", [r"woocommerce", r"wp-content/plugins/woocommerce", r"wc-ajax"]),
    ("WordPress", [r"wp-content", r"wp-includes", r"generator[^>]+WordPress"]),
    ("Wix", [r"wixstatic\.com", r"wix-image", r"X-Wix"]),
    ("Squarespace", [r"static\.squarespace\.com", r"squarespace-cdn"]),
    ("Magento", [r"Magento", r"mage/cookies", r"static/version\d+/frontend"]),
    ("BigCommerce", [r"cdn\d*\.bigcommerce\.com", r"stencil-utils", r"bigcommerce"]),
    ("Webflow", [r"webflow\.com", r"webflow\.js"]),
]
NOTABLE = [
    ("Google Tag Manager", r"googletagmanager\.com"),
    ("Google Analytics", r"google-analytics\.com|gtag\("),
    ("Klaviyo", r"klaviyo"),
    ("Hotjar", r"hotjar"),
    ("Meta Pixel", r"connect\.facebook\.net|fbq\("),
    ("Yotpo", r"yotpo"),
    ("Judge.me", r"judge\.me"),
]


def run(url: str, config: dict[str, Any]) -> dict[str, Any]:
    timeout = int(config["settings"].get("request_timeout_seconds", 15))
    headers = {"User-Agent": config["settings"].get("user_agent", "Mozilla/5.0")}
    try:
        r = requests.get(url, timeout=timeout, headers=headers, allow_redirects=True)
        text = r.text[:2_000_000]
        header_blob = "\n".join(f"{k}:{v}" for k, v in r.headers.items())
        blob = text + "\n" + header_blob
        detected = [name for name, pats in FINGERPRINTS if any(re.search(p, blob, re.I) for p in pats)]
        platform = next((x for x in detected if x in {"Shopify", "WooCommerce", "Wix", "Squarespace", "Magento", "BigCommerce", "Webflow"}), "Custom/Unknown")
        if platform == "Custom/Unknown" and "WordPress" in detected:
            platform = "WordPress"
        apps = [name for name, pat in NOTABLE if re.search(pat, blob, re.I)]
        return {"status": "ok", "platform": platform, "technologies": detected, "notable_apps": apps}
    except Exception as exc:
        return {"status": "error", "platform": "Unknown", "technologies": [], "notable_apps": [], "error": str(exc)}
