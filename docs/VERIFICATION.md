# Executed verification — 2026-10-01

Environment: Windows, Python 3.12.14, PostgreSQL 18.6, local Edge via Playwright. Exact installed Python versions are in `backend/requirements.lock.txt`.

| Check | Result |
|---|---|
| Full pytest suite against isolated PostgreSQL | **63 passed, 0 failed, 0 skipped**, 23.92 seconds |
| Warning | One Starlette TestClient HTTPX deprecation warning |
| Database migrations | Nine applied; checksums, idempotence and freeze constraints tested |
| Dependency consistency | `pip check`: no broken requirements |
| Ruff checks / Python compilation | Passed |
| Browser JavaScript parsing | `node --check` passed for app, forms and views |
| Headless browser | All ten product pages loaded without JavaScript exceptions or application error banners |
| Browser interaction | Run inspection, case inspection, paired comparison and Malayalam filter passed |
| Comparison safety | Fixture comparison displayed HOLD |
| Responsive layout | Loaded 390px viewport checked for document horizontal overflow; screenshot inspected |
| Visual QA | Desktop/mobile overview inspected; screenshots saved for all modules |
| Provider adapter | Local HTTP protocol stub: success, rejected redirect, malformed schema and HTTP 429 tested |
| Real AI inference / genuine human labels | None |
| Backend wheel | Built offline; confirmed bundled frontend and migration 009 are present |
| Source package | ZIP integrity checked; runtime/secret paths excluded; known key/private-key pattern scan found zero matches |
| Docker / Linux / public deployment / load tests | Not executed |

The browser script originally captured a mobile loading frame due to an event-order race. It now waits for the heading and completed load before measuring layout. The new HTTP tests initially used an incorrect request-contract field; the test was corrected and all four transport cases passed. Errors were not ignored.

Evidence: `docs/evidence/test-results.xml`, `docs/evidence/browser-results.json`, and `docs/screenshots/`. These are engineering artifacts, not benchmark experiment results. No line/branch coverage percentage was measured.

```powershell
$env:ADRIVA_LIBPQ_DIR='D:\Postgre\bin'
$env:ADRIVA_TEST_DATABASE_URL='postgresql://adriva@127.0.0.1:55439/adriva_test'
.\.venv\Scripts\python.exe tools\run_local.py pytest backend\tests -q -p no:cacheprovider --basetemp .local\tests-quorum --junitxml=.local\test-results.xml
.\.venv\Scripts\ruff.exe check --config backend\pyproject.toml backend tools
.\.venv\Scripts\ruff.exe format --check --config backend\pyproject.toml backend tools
.\.venv\Scripts\python.exe -m pip check
```

Browser runner: `node tools/browser_smoke.cjs`, with `PLAYWRIGHT_MODULE` pointing to the installed package if necessary.

## Method references checked

ADRIVA uses a paired percentile cluster bootstrap, not SciPy's default BCa. Tests use hand-checkable mathematical fixtures rather than a runtime SciPy dependency. Reference inspection is not independent certification or empirical validation.

- https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html
- https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html
- https://www.asc.upenn.edu/sites/default/files/2021-03/Computing%20Krippendorff%27s%20Alpha-Reliability.pdf
- https://fastapi.tiangolo.com/advanced/middleware/
