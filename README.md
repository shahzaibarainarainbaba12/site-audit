# Website Audit Automation

A zero-cost, cloud-first website auditing pipeline designed for roughly 80 public websites per day. It reads leads from a TSV file or published Google Sheet CSV, runs independent audit checks, scores each site with editable rules, and produces an Excel workbook, CSV summary, per-site HTML report, raw JSON, screenshots, and a run log.

## What it audits

- **PageSpeed** — Google PageSpeed Insights mobile + desktop: Performance, SEO, Accessibility, Best Practices, LCP, CLS, TBT, FCP, Speed Index, and field-data category when available.
- **HTML / SEO** — title, meta description, canonical, H1/headings, image alt attributes, Open Graph, Twitter tags, JSON-LD, viewport, robots.txt, sitemap.xml, up to 30 internal links, HTTP→HTTPS redirects, redirect count, and page size.
- **Security** — HTTPS, TLS certificate validity/expiry, HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy.
- **Technology** — lightweight HTML/header fingerprinting for Shopify, WooCommerce, WordPress, Wix, Squarespace, Magento, BigCommerce, Webflow and common marketing/review tools.
- **Browser / mobile** — Playwright Chromium, console errors, failed requests, broken images, mobile screenshot, overlay/cookie detection, horizontal overflow.
- **E-commerce flow** — conservative store detection, product-page heuristic, safe add-to-cart attempt, and checkout-control presence. It never fills checkout forms, enters personal data, or submits orders. Uncertain results are reported as `unknown`, not forced failures.

## Outputs

Each run writes to `output/`:

```text
output/
  summary.xlsx
  summary.csv
  run.log
  reports/<lead_id>_<company>.html
  raw/<lead_id>.json
  screenshots/<lead_id>.png
  state/<lead_id>.json
```

`summary.xlsx` contains:

1. **Summary** — one row per site, scores, platform, issue counts and top issues.
2. **All Issues** — one row per scoring issue with evidence and a fix.
3. **Raw Metrics** — flattened underlying metrics.

## Input format

`leads.tsv` is tab-separated and has no header. Empty cells are allowed.

| Col | Field |
|---:|---|
| 1 | lead_id |
| 2 | first_name |
| 3 | last_name |
| 4 | job_title |
| 5 | company |
| 6 | website_url |
| 7 | unused |
| 8 | phone |
| 9 | email |
| 10 | linkedin_url |
| 11 | location |
| 12 | industry |

The parser adds `https://` when missing, skips duplicate domains, tolerates missing columns, and can recover a website URL from another cell if column 6 is invalid. LinkedIn URLs are never treated as the website.

Copy `leads.example.tsv` to `leads.tsv` for local testing. **Do not commit real leads** because names, emails and phone numbers are personal data; `leads.tsv` is already in `.gitignore`.

## Cloud-first deployment (recommended)

You do **not** need Python installed on your laptop for daily operation. Use a private GitHub repository and GitHub Actions.

### 1. Create the repository

Create a private GitHub repository and upload this project. Do not upload the real `leads.tsv`.

### 2. Use a Google Sheet as the lead source

Keep the same 12 columns in a Google Sheet. Publish/export the sheet as CSV and save that CSV URL as the repository secret `LEADS_CSV_URL`.

If you prefer not to publish a Sheet URL, you may instead manually provide `leads.tsv` to a controlled runner; the included scheduled workflow is optimized for the CSV URL approach.

### 3. PageSpeed API key

Create a Google Cloud project, enable the **PageSpeed Insights API**, create an API key, then add it to GitHub repository secrets as `PSI_API_KEY`.

The code can call PageSpeed without a key when Google permits it, but a configured key is recommended for predictable quota handling.

### 4. Enable Actions

The workflow at `.github/workflows/daily_audit.yml`:

- runs daily and on manual dispatch;
- restores/saves same-day resume state through the GitHub Actions cache, so a rerun can skip sites already completed that day;
- installs Python dependencies and Playwright Chromium;
- reads `PSI_API_KEY` and `LEADS_CSV_URL` from secrets;
- audits the sites;
- uploads the full `output/` folder as an artifact for 14 days.

Go to **Actions → Daily Website Audit → Run workflow** for a manual test.

## Local commands (optional)

If you ever want a local run:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python main.py --input leads.tsv --limit 3
```

Full run:

```bash
python main.py --input leads.tsv
```

Useful flags:

```text
--limit N                 Audit only first N leads
--workers N               Concurrent site workers (default from config.yaml: 4)
--force                   Re-audit sites already marked complete today
--only-check pagespeed    Run only one check group
--only-check html_seo
--only-check security
--only-check technology
--only-check browser
--only-check ecommerce
--config path.yaml        Use another scoring/settings config
```

## Scoring

All point deductions and severity levels live in `config.yaml`. You can change rules without editing Python. The five category weights total 100 by default:

- Performance 25
- SEO 25
- Security 20
- UX/Mobile 15
- E-commerce 15

A triggered rule creates an issue with severity, point deduction, evidence and a plain-English fix. Category deductions are capped at that category's weight before conversion into a 0–100 category score.

## Reliability design

- Every check is isolated; a failed check becomes an error on that site and does not stop the batch.
- PageSpeed retries temporary 429/5xx responses with exponential backoff.
- Network checks have timeouts.
- Browser resources are closed after each site.
- Internal link checks are sampled and capped.
- E-commerce automation never places an order or submits personal information.
- `unknown` is preferred to a false `fail` when a storefront cannot be safely interpreted.

## Testing

Core unit tests do not require external websites:

```bash
python -m unittest discover -s tests -v
```

For a real integration test, use three sites:

```bash
python main.py --input leads.tsv --limit 3 --force
```

Verify:

- `summary.xlsx` opens and has three sheets;
- `summary.csv` has one row per audited site;
- each site has raw JSON and an HTML report;
- browser-capable sites have a PNG screenshot;
- a blocked/broken site is recorded without terminating the batch.

## Known limitations

- Storefronts vary heavily. Add-to-cart and checkout checks are heuristic and may return `unknown`.
- Bot protection can block PageSpeed, requests, or Playwright and produce partial results.
- Technology detection is intentionally lightweight; it is not a commercial fingerprint database.
- A published Google Sheet CSV URL can be accessed by anyone who has that URL. If that is not acceptable for lead PII, use a private authenticated source in a future version.
- GitHub Actions free minutes for private repositories are plan/quota dependent. The project itself uses no paid API, but unusually long daily browser runs can consume the account's included Actions allowance.

## Future improvements

- Authenticated private Google Sheets ingestion instead of a published CSV.
- Better platform-specific product/cart selectors.
- Optional long-term audit history storage/dashboard.
- Optional LLM-written summaries only when API budget exists.
- Trend/history dashboard across multiple days.

## Privacy and safety

This auditor is read-only against public websites except for a conservative add-to-cart click on sites identified as stores. It does not submit checkout, contact, login, newsletter, or payment forms. Keep repositories private and do not commit lead PII.
