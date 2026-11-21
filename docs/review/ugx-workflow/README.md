# UGX workflow — local browser evidence

**LOCAL NEXT.JS PRODUCTION BUILD + SYNTHETIC HTTPS API ONLY.** These are actual
protected Next.js routes with isolated fixture authentication/data. They are not
live Vercel, Android-phone, MTN or physical-board tests. No real account, money,
provider credential or customer token appears. Token fields are masked.

Browser report: [results.json](results.json). Both the Next.js client and API
transport were exercised; this is not a screenshot of an isolated story/mock page.
All nonlocal browser/API requests were blocked. TLS remained verified using a
process-local test CA for the reserved fixture hostname; no global TLS bypass.

| View / state | Screenshot |
|---|---|
| UGX dashboard, with legacy EUR history excluded from Home | [Desktop](dashboard-ugx.png), [phone width](dashboard-phone-width-ugx.png) |
| Buy Units — selected owned meter, UGX amount | [Form](buy-units-form.png) |
| Buy Units — tariff quote, test number, consent | [Confirmation](buy-units-confirmation.png) |
| Request Loan — selected meter,85% score, UGX37500 limit, UGX amount | [Form](request-loan-form.png) |
| Request Loan — terms and explicit consent | [Terms](request-loan-terms.png) |
| Below80%:62% remains visible with eligibility reason | [Ineligible](loan-ineligible-62-percent.png) |
| Missing/pending assessment | [Pending](loan-assessment-pending.png) |
| Assessment HTTP503 | [Loan error](loan-api-error.png) |
| Purchase stays usable during assessment HTTP503 | [Independent purchase](purchase-with-assessment-failure.png) |
| Purchase pricing HTTP503, form and reason stay visible | [Purchase error](purchase-api-error.png) |
| Loading | [Loading](account-loading.png) |
| Partial repayment:4000 against10500 leaves6500 | [Receipt](partial-repayment-receipt.png) |
| Server-confirmed purchase and one synthetic token | [Receipt/token masked](purchase-settled-token-synthetic.png) |
| Small screen purchase | [Phone width](phone-width-buy-units.png) |

The fixed browser tariff is synthetic and is not the project's production tariff.
Actual financial arithmetic, source binding, provider validation, concurrency and
device ACKs are verified separately by isolated Django/PostgreSQL tests.

Reproduce after building Next.js, using separate terminals:

```bash
# Tools are isolated under /tmp, not added to frontend/mobile dependencies.
npm install --prefix /tmp/gpawa-browser playwright
PLAYWRIGHT_BROWSERS_PATH=/tmp/gpawa-browsers node /tmp/gpawa-browser/node_modules/playwright/cli.js install chromium --only-shell
CONSUMER_FIXTURE_UGX_AUTHORIZATION=1 node frontend/scripts/consumer-preview.mjs
PLAYWRIGHT_BROWSERS_PATH=/tmp/gpawa-browsers node frontend/scripts/ugx-workflow-browser.mjs
```

Use only loopback. Stop the owned preview afterward. The fixture is never imported
into the installed APK or deployed application. Actual live-site verification
requires the separately deployed Django configuration and Vercel build, then an
authorized sign-in; installing an APK cannot update the web deployment.
