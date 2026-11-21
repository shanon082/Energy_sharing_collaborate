# Checkout recovery review — local synthetic tests

These screenshots exercise actual authenticated Next.js production routes at
`http://localhost:3100` against the loopback synthetic HTTPS API. No live Vercel,
alwaysdata payment, MTN transaction, phone or physical board was tested. Fixture
accounts/references are synthetic and keypad token fields are masked.

- [Buy Units stays visible during an open payment](buy-units-pending-form.png)
- [Loan form remains available during a pending purchase](loan-available-during-pending-purchase.png)
- [Expired checkout with explicit retry consent](expired-checkout-explicit-retry.png)
- [Late successes: one token and additional evidence under review](late-success-review-one-token.png)
- [Loan errors end loading](loan-errors-end-loading.png)
- [Loan independent of payment-history error](loan-independent-of-payment-read-error.png)
- [Stalled summary ends in a timeout](stalled-summary-timeout.png)
- [Phone-width form and retry](phone-expired-checkout-form.png)

`results.json` records the five checkout scenarios and browser runtime errors.
The existing nine UGX workflow scenarios are rerun separately and documented in
`../ugx-workflow/`. Tests exercise both web/mobile shared TSX presentation; these
phone-width browser images are not physical Android runtime evidence.

Reproduce after a production build (temporary Playwright tooling already needed):

```bash
(cd frontend && npm run build -- --webpack)
CONSUMER_FIXTURE_UGX_AUTHORIZATION=1 node frontend/scripts/consumer-preview.mjs
# Separate terminal; only synthetic loopback traffic:
PLAYWRIGHT_BROWSERS_PATH=/tmp/gpawa-browsers node frontend/scripts/checkout-browser.mjs
PLAYWRIGHT_BROWSERS_PATH=/tmp/gpawa-browsers node frontend/scripts/ugx-workflow-browser.mjs
```

The checkout script deliberately delays status responses to exercise interaction
with background polling, and stalls a summary to test the real 20-second deadline.
It tests explicit retry consent, duplicate-click/reload identity preservation,
provider confirmation of both attempts and one operation effect. Financial effects
are independently verified by PostgreSQL tests, not established by the fixture.

No preview code, synthetic cookies, fixtures or test API host belongs in the APK.
See `backend/docs/CHECKOUT_RECOVERY.md` for rollout and report commands.
