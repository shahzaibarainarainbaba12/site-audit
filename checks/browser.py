from __future__ import annotations

import os
import base64
from pathlib import Path
from typing import Any


def run(url: str, config: dict[str, Any], screenshot_path: str | Path) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return {"status": "error", "page_loaded": False, "error": f"Playwright unavailable: {exc}"}

    timeout = int(config["settings"].get("browser_timeout_ms", 30000))
    ua = config["settings"].get("user_agent", "Mozilla/5.0")
    screenshot_path = Path(screenshot_path)
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []
    failed_requests: list[str] = []
    popup_like = False
    broken_images = 0
    horizontal_scroll = False
    final_url = url

    try:
        with sync_playwright() as p:
            executable = os.getenv("CHROMIUM_EXECUTABLE_PATH")
            launch_kwargs = {"headless": True}
            if executable:
                launch_kwargs["executable_path"] = executable
            browser = p.chromium.launch(**launch_kwargs)
            context = browser.new_context(
                viewport={"width": 390, "height": 844},
                user_agent=ua,
                is_mobile=True,
                device_scale_factor=1,
            )
            page = context.new_page()
            page.set_default_timeout(timeout)
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("requestfailed", lambda req: failed_requests.append(req.url))
            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            try:
                page.wait_for_load_state("networkidle", timeout=min(timeout, 10000))
            except Exception:
                pass
            final_url = page.url
            broken_images = page.locator("img").evaluate_all(
                "els => els.filter(i => i.complete && i.naturalWidth === 0).length"
            )
            horizontal_scroll = bool(page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 2"))
            popup_like = bool(page.locator(
                '[role="dialog"], [class*="cookie" i], [id*="cookie" i], [class*="popup" i], [class*="modal" i]'
            ).count())
            page.screenshot(path=str(screenshot_path), full_page=True)
            status_code = response.status if response else None
            context.close()
            browser.close()
        return {
            "status": "ok",
            "page_loaded": status_code is None or status_code < 500,
            "http_status": status_code,
            "final_url": final_url,
            "console_error_count": len(console_errors),
            "console_errors": console_errors[:20],
            "failed_request_count": len(failed_requests),
            "failed_requests": failed_requests[:30],
            "broken_images": broken_images,
            "horizontal_scroll_mobile": horizontal_scroll,
            "popup_or_cookie_overlay_detected": popup_like,
            "screenshot_path": str(screenshot_path),
        }
    except Exception as exc:
        return {
            "status": "error",
            "page_loaded": False,
            "final_url": final_url,
            "console_errors": console_errors[:20],
            "failed_requests": failed_requests[:30],
            "error": str(exc),
        }


def screenshot_base64(path: str | Path) -> str:
    path = Path(path)
    if not path.exists() or not path.is_file():
        return ""
    return base64.b64encode(path.read_bytes()).decode("ascii")
