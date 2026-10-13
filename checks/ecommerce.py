from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urljoin


def _looks_store(html: str, technology: dict[str, Any]) -> bool:
    platform = technology.get("platform", "")
    if platform in {"Shopify", "WooCommerce", "Magento", "BigCommerce"}:
        return True
    patterns = [r"add[-_ ]?to[-_ ]?cart", r"/cart", r"/checkout", r"product-price", r"buy now"]
    return sum(bool(re.search(p, html, re.I)) for p in patterns) >= 2


def run(url: str, config: dict[str, Any], technology: dict[str, Any]) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return {"status": "error", "is_store": False, "cart_status": "unknown", "checkout_status": "unknown", "error": str(exc)}

    timeout = int(config["settings"].get("browser_timeout_ms", 30000))
    ua = config["settings"].get("user_agent", "Mozilla/5.0")
    result: dict[str, Any] = {
        "status": "ok",
        "is_store": False,
        "product_status": "unknown",
        "cart_status": "unknown",
        "checkout_status": "unknown",
        "evidence": [],
    }

    try:
        with sync_playwright() as p:
            executable = os.getenv("CHROMIUM_EXECUTABLE_PATH")
            launch_kwargs = {"headless": True}
            if executable:
                launch_kwargs["executable_path"] = executable
            browser = p.chromium.launch(**launch_kwargs)
            context = browser.new_context(viewport={"width": 1366, "height": 768}, user_agent=ua)
            page = context.new_page()
            page.set_default_timeout(timeout)
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            html = page.content()
            result["is_store"] = _looks_store(html, technology)
            if not result["is_store"]:
                result["status"] = "not_applicable"
                context.close(); browser.close()
                return result

            product_link = None
            candidates = page.locator('a[href*="/products/"], a[href*="/product/"], a[href*="/p/"]')
            for i in range(min(candidates.count(), 20)):
                href = candidates.nth(i).get_attribute("href")
                if href:
                    product_link = urljoin(page.url, href)
                    break
            if product_link:
                try:
                    resp = page.goto(product_link, wait_until="domcontentloaded", timeout=timeout)
                    result["product_status"] = "pass" if (resp is None or resp.status < 400) else "fail"
                    result["evidence"].append(f"Product candidate: {product_link}")
                except Exception as exc:
                    result["product_status"] = "fail"
                    result["evidence"].append(f"Product navigation failed: {exc}")
            else:
                result["evidence"].append("No reliable product-page link found on sampled page")

            # Safe cart heuristic: click only a visible add-to-cart control. Never fill forms or submit checkout.
            add_selectors = [
                'button[name="add"]',
                'button:has-text("Add to cart")',
                'button:has-text("Add to bag")',
                '[data-add-to-cart]',
                'input[type="submit"][value*="Add" i]',
            ]
            clicked = False
            for selector in add_selectors:
                if page.locator(selector).count() > 0:
                    try:
                        page.locator(selector).first.click(timeout=5000)
                        clicked = True
                        break
                    except Exception:
                        continue
            if clicked:
                try:
                    page.wait_for_timeout(1500)
                    body = page.content()
                    cart_signal = bool(re.search(r"cart|checkout|subtotal|your bag", body, re.I))
                    result["cart_status"] = "pass" if cart_signal else "unknown"
                    result["evidence"].append("Visible add-to-cart control was clicked safely")
                except Exception:
                    result["cart_status"] = "unknown"
            else:
                result["cart_status"] = "unknown"
                result["evidence"].append("No safe add-to-cart control could be activated")

            checkout_link = page.locator('a[href*="/checkout"], button:has-text("Checkout"), a:has-text("Checkout")')
            if checkout_link.count() > 0:
                try:
                    # We do not click checkout because some stores can launch third-party flows; presence is enough for reachability heuristic.
                    href = checkout_link.first.get_attribute("href")
                    result["checkout_status"] = "pass"
                    result["evidence"].append(f"Checkout control present{': ' + href if href else ''}")
                except Exception:
                    result["checkout_status"] = "unknown"
            else:
                # A missing checkout button after an unknown cart state is not proof of failure.
                result["checkout_status"] = "unknown"
                result["evidence"].append("Checkout control not confirmed on current state")

            context.close(); browser.close()
        return result
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)
        return result
