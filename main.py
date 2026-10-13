from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Callable

from audit_types import AuditRecord, Lead
from checks import browser, ecommerce, html_seo, pagespeed, security, technology
from report.excel_report import write_summary_csv, write_workbook
from report.html_report import write_report
from scoring import score
from utils import load_config, load_leads, slugify, utc_now_iso, write_json

CHECK_NAMES = ["pagespeed", "html_seo", "security", "technology", "browser", "ecommerce"]


def setup_logging(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    handlers = [logging.StreamHandler(sys.stdout), logging.FileHandler(output_dir / "run.log", encoding="utf-8")]
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", handlers=handlers, force=True)


def audited_today(output_dir: Path, lead: Lead) -> bool:
    state = output_dir / "state" / f"{slugify(lead.lead_id)}.json"
    if not state.exists(): return False
    try:
        data = json.loads(state.read_text(encoding="utf-8"))
        return data.get("date") == datetime.now().date().isoformat() and data.get("website") == lead.website_url
    except Exception:
        return False


def mark_audited(output_dir: Path, lead: Lead) -> None:
    write_json(output_dir / "state" / f"{slugify(lead.lead_id)}.json", {"date": datetime.now().date().isoformat(), "website": lead.website_url})


def audit_one(lead: Lead, config: dict, output_dir: Path, only_check: str | None = None) -> AuditRecord:
    start = time.time(); rec = AuditRecord(lead=lead, started_at=utc_now_iso())
    shot = output_dir / "screenshots" / f"{slugify(lead.lead_id)}.png"
    def call(name: str, fn: Callable, *args):
        if only_check and name != only_check: return
        try:
            rec.checks[name] = fn(*args)
            if isinstance(rec.checks[name], dict) and rec.checks[name].get("status") == "error":
                rec.errors.append(f"{name}: {rec.checks[name].get('error','unknown error')}")
        except Exception as exc:
            rec.checks[name] = {"status":"error","error":str(exc)}; rec.errors.append(f"{name}: {exc}")

    call("pagespeed", pagespeed.run, lead.website_url, config)
    call("html_seo", html_seo.run, lead.website_url, config)
    call("security", security.run, lead.website_url, config)
    call("technology", technology.run, lead.website_url, config)
    call("browser", browser.run, lead.website_url, config, shot)
    tech = rec.checks.get("technology", {"platform":"Unknown"})
    call("ecommerce", ecommerce.run, lead.website_url, config, tech)
    # Ensure all namespaces exist so config expressions stay safe.
    defaults = {
        "pagespeed": {"performance":None,"lcp_ms":None,"cls":None},
        "html_seo": {"title_missing":False,"meta_description_missing":False,"h1_count":None,"images_missing_alt":0,"canonical_missing":False},
        "security": {"https":None,"cert_days_remaining":None,"hsts":None,"csp":None},
        "browser": {"horizontal_scroll_mobile":None,"broken_images":0,"page_loaded":None},
        "ecommerce": {"is_store":False,"cart_status":"unknown","checkout_status":"unknown"},
    }
    for k,v in defaults.items(): rec.checks.setdefault(k,v)
    rec.scores, rec.issues = score(rec.checks, config)
    covered = sum(1 for name in CHECK_NAMES if isinstance(rec.checks.get(name), dict) and rec.checks[name].get("status") in {"ok", "not_applicable"})
    rec.scores["coverage_percent"] = round(covered * 100 / len(CHECK_NAMES))
    rec.finished_at = utc_now_iso(); rec.duration_seconds = time.time() - start
    return rec


def parse_args():
    p = argparse.ArgumentParser(description="Zero-cost website audit automation")
    p.add_argument("--input", default="leads.tsv")
    p.add_argument("--limit", type=int)
    p.add_argument("--workers", type=int)
    p.add_argument("--force", action="store_true")
    p.add_argument("--only-check", choices=CHECK_NAMES)
    p.add_argument("--config", default="config.yaml")
    return p.parse_args()


def main() -> int:
    args = parse_args(); config = load_config(args.config)
    output_dir = Path(config["settings"].get("output_dir","output")); setup_logging(output_dir); log = logging.getLogger("site_audit")
    leads, parse_errors = load_leads(args.input, os.getenv("LEADS_CSV_URL") or None)
    for e in parse_errors: log.warning(e)
    if args.limit: leads = leads[:args.limit]
    if not args.force and not args.only_check:
        original = len(leads); leads = [x for x in leads if not audited_today(output_dir,x)]
        if original != len(leads): log.info("Skipped %s site(s) already audited today", original-len(leads))
    if not leads:
        log.info("No sites to audit."); return 0
    workers = args.workers or int(config["settings"].get("workers",4)); log.info("Auditing %s site(s) with %s worker(s)",len(leads),workers)
    records: list[AuditRecord] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futures = {ex.submit(audit_one, lead, config, output_dir, args.only_check): lead for lead in leads}
        for f in as_completed(futures):
            lead = futures[f]
            try:
                rec = f.result(); records.append(rec)
                raw_path = output_dir / "raw" / f"{slugify(lead.lead_id)}.json"; write_json(raw_path, rec.to_dict())
                report_name = f"{slugify(lead.lead_id)}_{slugify(lead.company or lead.website_url)}.html"; write_report(rec, output_dir / "reports" / report_name)
                if not args.only_check: mark_audited(output_dir, lead)
                log.info("Done %s | score=%s | %.1fs", lead.website_url, rec.scores.get("overall"), rec.duration_seconds)
            except Exception as exc:
                log.exception("Unexpected site failure %s: %s", lead.website_url, exc)
    records.sort(key=lambda r: r.lead.lead_id)
    write_summary_csv(records, output_dir / "summary.csv"); write_workbook(records, output_dir / "summary.xlsx")
    log.info("Finished. Reports: %s", output_dir.resolve())
    return 0


if __name__ == "__main__": raise SystemExit(main())
