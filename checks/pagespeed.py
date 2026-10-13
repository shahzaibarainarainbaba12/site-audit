from __future__ import annotations

import os
import time
from typing import Any

import requests

API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def _metric(audits: dict[str, Any], key: str, field: str = "numericValue") -> Any:
    value = audits.get(key, {}).get(field)
    return value if value is not None else None


def _one(url: str, strategy: str, api_key: str | None, retries: int, timeout: int) -> dict[str, Any]:
    params: list[tuple[str, str]] = [
        ("url", url),
        ("strategy", strategy),
        ("category", "performance"),
        ("category", "seo"),
        ("category", "accessibility"),
        ("category", "best-practices"),
    ]
    if api_key:
        params.append(("key", api_key))
    last_error = ""
    for attempt in range(retries):
        try:
            r = requests.get(API_URL, params=params, timeout=timeout)
            if r.status_code in {429, 500, 502, 503, 504}:
                last_error = f"HTTP {r.status_code}"
                time.sleep(min(2 ** attempt, 8))
                continue
            r.raise_for_status()
            data = r.json()
            lr = data.get("lighthouseResult", {})
            cats = lr.get("categories", {})
            audits = lr.get("audits", {})
            loading = data.get("loadingExperience", {})
            origin = data.get("originLoadingExperience", {})
            return {
                "status": "ok",
                "strategy": strategy,
                "performance": round((cats.get("performance", {}).get("score") or 0) * 100),
                "seo": round((cats.get("seo", {}).get("score") or 0) * 100),
                "accessibility": round((cats.get("accessibility", {}).get("score") or 0) * 100),
                "best_practices": round((cats.get("best-practices", {}).get("score") or 0) * 100),
                "lcp_ms": _metric(audits, "largest-contentful-paint"),
                "cls": _metric(audits, "cumulative-layout-shift"),
                "tbt_ms": _metric(audits, "total-blocking-time"),
                "fcp_ms": _metric(audits, "first-contentful-paint"),
                "speed_index_ms": _metric(audits, "speed-index"),
                "field_page": loading.get("overall_category"),
                "field_origin": origin.get("overall_category"),
            }
        except Exception as exc:
            last_error = str(exc)
            time.sleep(min(2 ** attempt, 8))
    return {"status": "error", "strategy": strategy, "error": last_error}


def run(url: str, config: dict[str, Any]) -> dict[str, Any]:
    settings = config["settings"]
    api_key = os.getenv("PSI_API_KEY") or None
    retries = int(settings.get("pagespeed_retries", 3))
    timeout = max(20, int(settings.get("request_timeout_seconds", 15)) * 2)
    mobile = _one(url, "mobile", api_key, retries, timeout)
    desktop = _one(url, "desktop", api_key, retries, timeout)
    primary = mobile if mobile.get("status") == "ok" else desktop
    return {
        "status": "ok" if primary.get("status") == "ok" else "error",
        "api_key_configured": bool(api_key),
        "mobile": mobile,
        "desktop": desktop,
        "performance": primary.get("performance"),
        "seo": primary.get("seo"),
        "accessibility": primary.get("accessibility"),
        "best_practices": primary.get("best_practices"),
        "lcp_ms": primary.get("lcp_ms"),
        "cls": primary.get("cls"),
        "tbt_ms": primary.get("tbt_ms"),
        "fcp_ms": primary.get("fcp_ms"),
        "speed_index_ms": primary.get("speed_index_ms"),
    }
