# Verification Report

## Passed in build workspace

- Python syntax compilation across the project.
- Core unit tests: 3/3 passed.
- Lead parsing, URL normalization, duplicate-domain handling.
- YAML scoring engine and issue generation.
- Sample run failure isolation: a network failure is recorded without crashing the batch.
- Report generation: `summary.csv`, `summary.xlsx`, raw JSON and per-site HTML produced.
- Excel workbook integrity: Summary, All Issues and Raw Metrics sheets open successfully.
- Audit coverage percentage is exported so partial/blocked audits are visible rather than silently looking complete.

## Browser integration note

The build workspace has Chromium installed, but browser network navigation is blocked by an administrator policy (`ERR_BLOCKED_BY_ADMINISTRATOR`). Therefore an actual Playwright navigation test against a public or local HTTP URL cannot be completed inside this workspace. The GitHub Actions workflow installs official Playwright Chromium and is configured to perform the browser checks in the deployment environment.

## Recommended first cloud acceptance run

Trigger the GitHub workflow manually with `limit=3`. Verify three HTML reports, raw JSON files, screenshots where browser access succeeds, `summary.csv`, `summary.xlsx`, and `run.log`. Then run the full lead batch.
