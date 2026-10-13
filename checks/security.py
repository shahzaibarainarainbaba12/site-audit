from __future__ import annotations

import socket
import ssl
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests


def _cert_days(host: str, timeout: int) -> tuple[bool, int | None, str | None]:
    try:
        context = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
        not_after = cert.get("notAfter")
        if not not_after:
            return True, None, None
        expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        days = int((expiry - datetime.now(timezone.utc)).total_seconds() // 86400)
        return True, days, expiry.isoformat()
    except Exception as exc:
        return False, None, str(exc)


def run(url: str, config: dict[str, Any]) -> dict[str, Any]:
    timeout = int(config["settings"].get("request_timeout_seconds", 15))
    headers = {"User-Agent": config["settings"].get("user_agent", "Mozilla/5.0")}
    p = urlparse(url)
    host = p.hostname or ""
    cert_valid, cert_days, cert_info = _cert_days(host, timeout) if host else (False, None, "missing host")
    try:
        r = requests.get(url, timeout=timeout, headers=headers, allow_redirects=True)
        h = {k.lower(): v for k, v in r.headers.items()}
        final_https = urlparse(r.url).scheme == "https"
        return {
            "status": "ok",
            "https": final_https,
            "cert_valid": cert_valid,
            "cert_days_remaining": cert_days,
            "cert_detail": cert_info,
            "hsts": "strict-transport-security" in h,
            "csp": "content-security-policy" in h,
            "x_frame_options": "x-frame-options" in h,
            "x_content_type_options": "x-content-type-options" in h,
            "referrer_policy": "referrer-policy" in h,
            "permissions_policy": "permissions-policy" in h,
            "server": h.get("server", ""),
        }
    except Exception as exc:
        return {"status": "error", "https": p.scheme == "https", "cert_valid": cert_valid, "cert_days_remaining": cert_days, "error": str(exc)}
