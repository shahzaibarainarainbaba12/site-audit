# Project Status

Implemented from the supplied Website Audit Automation SOW, with reliability-focused adjustments.

## Complete

- TSV / published CSV lead ingestion
- URL cleanup and duplicate-domain filtering
- PageSpeed mobile + desktop
- HTML/SEO checks
- TLS + security header checks
- lightweight technology fingerprinting
- Playwright mobile browser checks + screenshot
- conservative e-commerce flow heuristics
- configurable scoring in YAML
- Excel, CSV, HTML, JSON, screenshot and log outputs
- per-site failure isolation
- same-day local resume state
- GitHub Actions scheduled/manual workflow
- unit tests
- privacy-focused `.gitignore`
- README deployment/troubleshooting guidance

## Intentional changes from the rough SOW

1. Replaced hard dependency on python-Wappalyzer with lightweight maintained-code fingerprinting.
2. E-commerce uncertain states remain `unknown`; the tool does not manufacture failures.
3. PageSpeed key is recommended but the code can attempt a request without it.
4. Runtime is treated as a target, not a guarantee, because remote sites and bot protection vary.
5. Real lead data is excluded from source control by default.
