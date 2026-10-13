from __future__ import annotations

import html
from pathlib import Path

from audit_types import AuditRecord
from checks.browser import screenshot_base64


def _badge(level: str) -> str:
    return f'<span class="badge {html.escape(level)}">{html.escape(level.upper())}</span>'


def write_report(record: AuditRecord, path: str | Path) -> None:
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    lead = record.lead; s = record.scores
    browser = record.checks.get("browser", {})
    shot = screenshot_base64(browser.get("screenshot_path", ""))
    issues_html = "".join(
        f"<article class='issue'><div>{_badge(i.level)} <b>{html.escape(i.title)}</b></div><div class='muted'>{html.escape(i.category)} · -{i.points} pts</div><p><b>Evidence:</b> {html.escape(i.evidence or 'Rule triggered from audit data')}</p><p><b>How to fix:</b> {html.escape(i.fix)}</p></article>"
        for i in record.issues
    ) or "<p>No configured scoring issues were triggered.</p>"
    score_cards = "".join(f"<div class='score'><span>{html.escape(k.replace('_',' ').title())}</span><strong>{v}</strong></div>" for k,v in s.items())
    errors = "".join(f"<li>{html.escape(e)}</li>" for e in record.errors)
    screenshot_html = f"<img class='shot' src='data:image/png;base64,{shot}' alt='Mobile screenshot'>" if shot else "<p class='muted'>Mobile screenshot unavailable.</p>"
    page = f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Audit - {html.escape(lead.company or lead.website_url)}</title><style>
body{{font-family:Inter,Arial,sans-serif;margin:0;background:#f6f8fb;color:#172033}}.wrap{{max-width:1100px;margin:auto;padding:32px 20px}}.hero{{background:#0f2747;color:white;padding:28px;border-radius:18px}}.hero a{{color:#9bd3ff}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:18px 0}}.score{{background:white;border:1px solid #e6eaf0;border-radius:14px;padding:18px;box-shadow:0 4px 14px #10233a10}}.score span{{display:block;color:#677386;font-size:13px}}.score strong{{font-size:30px}}h2{{margin-top:34px}}.issue{{background:white;border:1px solid #e6eaf0;border-radius:14px;padding:18px;margin:12px 0}}.badge{{font-size:11px;font-weight:700;padding:5px 8px;border-radius:999px}}.critical{{background:#ffe4e4;color:#a91515}}.warning{{background:#fff2cf;color:#8b5b00}}.info{{background:#e9f2ff;color:#155e9a}}.muted{{color:#6a7586;font-size:13px}}.shot{{max-width:390px;width:100%;border:1px solid #ccd5df;border-radius:16px;box-shadow:0 8px 30px #10233a20}}table{{width:100%;border-collapse:collapse;background:white;border-radius:12px;overflow:hidden}}td,th{{padding:10px;border-bottom:1px solid #e8edf3;text-align:left;font-size:14px}}code{{word-break:break-word}}</style></head><body><div class='wrap'>
<section class='hero'><h1>Website Audit Report</h1><h3>{html.escape(lead.company or lead.website_url)}</h3><p><a href='{html.escape(lead.website_url)}'>{html.escape(lead.website_url)}</a></p><p>Lead: {html.escape(lead.lead_id)} · Platform: {html.escape(record.checks.get('technology',{}).get('platform','Unknown'))} · Runtime: {record.duration_seconds:.1f}s</p></section>
<div class='grid'>{score_cards}</div><h2>Prioritized Issues</h2>{issues_html}<h2>Mobile Browser Capture</h2>{screenshot_html}
<h2>Audit Summary</h2><table><tr><th>Check</th><th>Status</th></tr>{''.join(f"<tr><td>{html.escape(k)}</td><td>{html.escape(str(v.get('status','n/a') if isinstance(v,dict) else 'n/a'))}</td></tr>" for k,v in record.checks.items())}</table>
{f"<h2>Recorded Errors</h2><ul>{errors}</ul>" if errors else ''}
<p class='muted'>This is a read-only automated audit. E-commerce results marked unknown are intentionally not treated as failures when the automation cannot safely confirm a step.</p></div></body></html>"""
    path.write_text(page, encoding="utf-8")
