from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import requests
import yaml

from audit_types import Lead

LOGGER = logging.getLogger("site_audit")
URL_RE = re.compile(r"^(?:https?://)?(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}(?:[/:?#].*)?$", re.I)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_config(path: str | Path = "config.yaml") -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def ensure_scheme(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not re.match(r"^[a-z][a-z0-9+.-]*://", url, flags=re.I):
        url = "https://" + url
    return url


def is_valid_website_url(value: str) -> bool:
    value = (value or "").strip()
    if not value or "linkedin.com" in value.lower():
        return False
    candidate = ensure_scheme(value)
    try:
        p = urlparse(candidate)
        return p.scheme in {"http", "https"} and bool(p.netloc) and "." in p.netloc
    except Exception:
        return False


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-")
    return value or "site"


def domain_key(url: str) -> str:
    p = urlparse(ensure_scheme(url))
    host = p.netloc.lower().split("@")[-1].split(":")[0]
    return host.removeprefix("www.")


def read_text_url(url: str, timeout: int = 20) -> str:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.text


def load_leads(input_path: str | Path, leads_csv_url: str | None = None) -> tuple[list[Lead], list[str]]:
    errors: list[str] = []
    if leads_csv_url:
        LOGGER.info("Loading leads from published CSV URL")
        text = read_text_url(leads_csv_url)
        rows = list(csv.reader(text.splitlines()))
    else:
        with open(input_path, "r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f, delimiter="\t"))

    leads: list[Lead] = []
    seen: set[str] = set()
    for idx, raw in enumerate(rows, start=1):
        row = [c.strip() for c in raw]
        if not any(row):
            continue
        padded = row + [""] * max(0, 12 - len(row))
        website = padded[5] if len(padded) > 5 and is_valid_website_url(padded[5]) else ""
        if not website:
            website = next((c for c in row if is_valid_website_url(c)), "")
        if not website:
            errors.append(f"Row {idx}: skipped; no valid website URL")
            continue
        website = ensure_scheme(website)
        key = domain_key(website)
        if not key or key in seen:
            errors.append(f"Row {idx}: skipped duplicate or invalid URL: {website}")
            continue
        seen.add(key)
        lead_id = padded[0] or f"ROW-{idx:04d}"
        leads.append(Lead(
            lead_id=lead_id,
            first_name=padded[1],
            last_name=padded[2],
            job_title=padded[3],
            company=padded[4],
            website_url=website,
            phone=padded[7],
            email=padded[8],
            linkedin_url=padded[9],
            location=padded[10],
            industry=padded[11],
        ))
    return leads, errors


def write_json(path: str | Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def sleep_polite(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def nested_get(data: dict[str, Any], path: str, default: Any = None) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current
