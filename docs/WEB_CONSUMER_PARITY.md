# Consumer web parity and focused workspace

This finishes the previously assembled consumer workspace against the existing
Android contracts. It preserves the current EnergyFlex branding and unrelated
uncommitted edits, public landing/authentication pages, admin interface, newer
AC lab integration and native Android build/signing configuration. No commit,
push, deployment, hosted migration, operational record inspection, provider call
or Android build was performed for this work.

## Root causes verified in source

These findings concern the checked-out source and synthetic regression fixtures;
the deployed Vercel/alwaysdata revision and the user's personal records were not
inspected. The 5,000 / 5,250 / 2,500 / 2,750 example occurs only in tests, never as
an application fallback.

- Legacy widgets (`dashboard/_components/loan-overview.tsx`,
  `contexts/selected-meter-context.tsx`) read CORE loan/wallet data and initialize
  values to zero. They do not represent UGX_DEMO obligations. The partially updated
  `dashboard-loans.tsx` can use sandbox history, but bounded history remains an
  insufficient source for account totals.
- `sandbox/loans/` and `sandbox/payments/` contain bounded history. Summing recent100
  rows loses older obligations and repayments. The new summary projects the full
  owner/environment ledger with the same debt calculation as loan details.
- The legacy meter context stores a meter number, while `SandboxWeb` has an
  independent ID selection that remains empty with multiple linked meters.
  Assessment requests therefore lack `meter_id`. The focused shell now owns a
  visible stable-ID selection and gives it to assessment, energy and transactions.
- The earlier incomplete summary tests were missing a unique payment external ID
  and valid historical five-second authorization timestamps. These isolated
  fixtures now obey the existing constraints; no payment policy was weakened.
- The old default Vercel CORS origin had a trailing slash. The checkout's corrected
  exact origin is retained; allow-all CORS remains false. Browser reads/mutations
  continue through the same-origin Next.js proxy and HttpOnly cookies.

## Authoritative scopes and API

`GET /api/v1/sandbox/summary/?environment=UGX_DEMO` requires the existing verified
consumer permission and enabled sandbox capability. Owner is always `request.user`;
query-supplied owner IDs do not select another account. Supported domains are
UGX_DEMO/UGX and MTN_SANDBOX/EUR. CORE is rejected as a separate ledger.

An optional owned `meter_id` narrows the summary; malformed IDs reject, foreign
meters return404. Successful responses are private/no-store. No settlement,
provider polling, assessment recalculation or balance mutation occurs on this GET.

Example response structure (identifiers/figures are synthetic):

```json
{
  "owner_id": 7, "environment": "UGX_DEMO", "currency": "UGX",
  "scope": "OWNER", "meter_id": null,
  "loan_count": 1, "active_loan_count": 1,
  "principal": "5000", "total_due": "5250",
  "applied_repayments": "2500", "outstanding": "2750",
  "energy": {"available_kwh": "8.95", "pending_kwh": "5.00", "confirmed_kwh": "0.00"}
}
```

`consumer_summary.loans_with_applied` obtains exact applied settlements through a
correlated sum. `SandboxLoan.applied_repayments` and `outstanding` share the same
calculation for overview/detail. Frozen accepted total due is not recalculated
from current pricing. Rejected decisions count as history, not debt/principal. Their proposed total is labelled quoted/not owed, and their decision reason remains visible.
No Python model field or database schema change is required for this projection.

| Card/read | Scope/source |
|---|---|
| Outstanding, applied repayments, active loans | All owned loan records in the current currency/environment; full summary, not loaded history |
| Available/reserved/recorded energy | Explicit selected meter and environment, existing `entitlement_summary`/`meter/mobile-meters/<id>/` |
| Score/limit/eligibility | Stored backend assessment for the selected meter ID; pending/unavailable is not zero |
| Recent activity and history | Bounded owner history, clearly labelled as history rather than account totals |
| Physical balance/usage | Unavailable without reviewed device evidence; no readings manufactured from allocations |

Loan history now returns the latest100 decisions **plus any older active loans**,
so a still-outstanding obligation cannot disappear from self-repayment just because
newer records fill the history. API metadata `history.recent_limit` and
`history.includes_older_active` explains that extension. Pending payments remain
independently recovered by the existing controller.

CORE UGX and EUR test records are not converted or merged into current demo cards.
Earlier EUR loans remain visible in the shared historical section in their own
currency. Existing CORE read routes remain separate and owner-authorized; they
are not the new demo dashboard's totals.

## Screens and safety

Routes: Home `/dashboard`, Meters `/dashboard/my-meters`, Loans
`/dashboard/loans`, Apply `/dashboard/loans?tab=apply`, Buy Units
`/dashboard/buy-units`, Activity `/dashboard/transactions`, Account
`/dashboard/myaccount`. The legacy wallet navigation maps to the read-only Home.
Desktop uses a sidebar; narrow screens use Home/Meters/Loans/Buy Units/Account
navigation with Activity available from the header and recent history.

`ConsumerRouter` lives in the persistent dashboard layout. Its finance controller
stays mounted even on Home/Meters/Account; only its presentation is hidden. This
preserves pending recovery, non-secret request IDs, quote binding/expiry, explicit
consent and submission guards across navigation. No financial success is inferred
from the five-second timer. The default shared mobile/legacy component behavior
is retained through the `surface="web"` presentation option.

New meter enrollment accepts exactly11 ASCII digits as strings with leading zeros.
Existing13-digit/other stored identifiers remain selectable for history; they are
not passed through new-enrollment validation or renamed. The meter list refreshes
with the account, and late results cannot restore an old selection. Removed
assignments do not silently select another meter. Read failures show unavailable
and retry, not synthetic zero balances.

Profile editing uses the existing ordinary account-details API, not the obsolete
assessment questionnaire. Historical preference values remain visible; unchanged
values are omitted from PATCH so an unrelated address edit cannot clear them.
Logout clears private browser state and existing HttpOnly session cookies.

The web Loan list exposes principal, accepted due, actual applied repayments,
outstanding, due date and readable status. Below80% explains the disabled action;
server ownership, debt, limit and frozen tariff checks remain authoritative. Loan
rejections remain visible in history with their reason and no invented allocation.
Money formatting preserves meaningful fractions without changing accounting.
References remain available in expandable details with copy actions; historical
missing tokens are not regenerated or backfilled.

No seven-feature flag, live-provider restriction, account-email schedule,
verification/reset contract, token key or physical-device capability is enabled.
The newer AC lab source files/migration are preserved, remain opt-in/default off
and are **a separate deployment milestone**.

## File inventory

Backend implementation (including the earlier incomplete stage):
- `backend/loan/consumer_summary.py`
- `backend/loan/sandbox_api.py`, `sandbox_urls.py`, `sandbox_models.py`, `sandbox_service.py`
- `backend/loan/tests_consumer_summary.py`
- `backend/backend/settings.py` (retain the earlier exact-origin correction)
- `backend/deploy/web-consumer-parity.files`

Focused web workspace:
- `frontend/src/components/consumer/{workspace,account,legacy-boundary}.tsx` and `read.ts`.
- `frontend/src/lib/consumer-parity.ts`, `sandbox-presentation.ts`, `sandbox.ts`
- `frontend/src/styles/consumer-workspace.css`
- `frontend/src/app/(dashboard)/layout.tsx` and `dashboard/layout.tsx`
- Dashboard page markers for Home, my-meters, loans, buy-units, transactions,
  myaccount and wallet; the earlier page implementations are retained in their
  colocated `legacy-page.tsx` files for review, not executed by focused routes.
- `frontend/src/components/sandbox-mobile-view.tsx`, `energy-token-card.tsx`
- `frontend/tests/consumer-parity.test.mjs`, `sandbox-presentation.test.mjs`
- `frontend/scripts/consumer-browser.mjs`, `frontend/scripts/consumer-preview.mjs`, `frontend/tests/fixtures/consumer-api.mjs`
- `docs/review/consumer-parity/` contains synthetic browser evidence only.

Existing public/admin/auth/branding edits and AC-lab files in the current git diff
are unrelated work and were preserved. Review them separately before publishing
the whole checkout.

## Local checks and synthetic browser setup

Use the existing guarded isolated PostgreSQL launcher; it refuses the wrong
cluster/role and prohibits external provider HTTP:

```bash
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py loan.tests_consumer_summary transactions.tests_demo_payments loan.tests_meter_credit_tariffs loan.tests_sandbox meter.tests_allocation_delivery backend.tests_feature_flags
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --sandbox-profile loan.tests_consumer_summary backend.tests_alwaysdata backend.tests_feature_flags
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --check-migrations
```

Browser fixtures are only under tests/scripts and are never imported by runtime
application code. A fake authentication cookie is used solely against the local
synthetic API; no production authentication bypass was added.

The completed browser run used the built production app, not a relaxed development
configuration. Prepare a production build, then run this helper from the root:

```bash
# Optional QA tooling installation only under /tmp (not project dependencies):
npm install --prefix /tmp/gpawa-browser --no-audit --no-fund playwright@1.65.1
PLAYWRIGHT_BROWSERS_PATH=/tmp/gpawa-browser/browsers /tmp/gpawa-browser/node_modules/.bin/playwright install chromium
# Build first from frontend; CIRCLE_NODE_TOTAL=2 limits WSL static workers to one:
cd frontend
CIRCLE_NODE_TOTAL=2 API_URL=https://shanonsimon.alwaysdata.net/api/v1 npm run build -- --webpack
cd ..
node frontend/scripts/consumer-preview.mjs
# Separate terminal, repository root:
PLAYWRIGHT_BROWSERS_PATH=/tmp/gpawa-browser/browsers node frontend/scripts/consumer-browser.mjs
```

The helper starts only loopback fixtures and the existing production build. It
creates a short-lived private TLS certificate in /tmp, maps the reserved
`consumer-api.example.test` hostname inside its Node test process, and trusts only
that test certificate through NODE_EXTRA_CA_CERTS. Standard TLS verification stays
on. Its fetch allowlist prohibits hosted/non-fixture requests. No /etc/hosts,
firewall, production URL validator, CORS or authentication setting changes. Ctrl+C
stops its owned processes and removes the temporary certificate material. The
production API validator correctly rejects raw localhost/private-IP API bases;
the helper does not change or disable that validator. These fixtures/preload files
are not imported by application code or included in Android bundles.

The browser uses `http://localhost:3100`, resolved explicitly to loopback: NextURL
normalizes127.0.0.1 to localhost. Using a127.0.0.1 browser Origin with that normalized
URL correctly trips the existing exact-origin POST guard. The guard was retained;
no CORS/CSRF/auth relaxation was used to make the QA fixture work.

Run mobile/web tests without isolated child-process reporting to list individual
cases. The retained component supports the native app without a new APK:

```bash
cd mobile
npm run typecheck
node --test --test-isolation=none tests/*.test.mjs
cd ../frontend
node --test --test-isolation=none tests/*.test.mjs
npx eslint src/components/consumer src/lib/consumer-parity.ts src/components/sandbox-mobile-view.tsx src/components/energy-token-card.tsx 'src/app/(dashboard)/dashboard/layout.tsx'
# Stop only the owned preview before generating .next production artifacts.
npm run build -- --webpack
npx tsc --noEmit
```

## Deployment requirements — instructions only

Deploy the backend summary/read changes before the web workspace. This parity
package introduces **no migrations**. It depends on the already-existing sandbox,
settlement, meter-enrollment and source-allocation migrations/contracts. Do not
apply the unrelated AC lab0032 migration as a prerequisite for these loan-only
files; if separately uploading the newer device milestone, follow its own reviewed
migration plan and keep its capability disabled until explicitly commissioned.

From the repository root, review then upload only the allowlisted backend files:

```bash
rsync -avnc --files-from=backend/deploy/web-consumer-parity.files \
  backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
rsync -avc --files-from=backend/deploy/web-consumer-parity.files \
  backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
ssh shanonsimon@ssh-shanonsimon.alwaysdata.net
```

The allowlist contains explicit source/tests only, never.env, private keys,
credentials, virtualenv, database, generated static files or client artifacts.
It does not overwrite the newer device/profile files. On the host:

```bash
cd /home/shanonsimon/energy-sharing
export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
export DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings
/home/shanonsimon/energy-venv/bin/python manage.py check_alwaysdata_database
/home/shanonsimon/energy-venv/bin/python manage.py check
/home/shanonsimon/energy-venv/bin/python manage.py migrate --plan
/home/shanonsimon/energy-venv/bin/python manage.py collectstatic --noinput
```

Review the plan; this package requires no `migrate` execution. If unrelated pending
migrations appear, review them in their own milestone. Retain the existing private
environment, UGX_DEMO/LOCAL_DEMO mode, disabled optional flags, email/payment jobs,
HTTPS origins, token keys and device capability settings. Confirm the deployed
baseline supports `entitlement_summary(owner, meter=None, environment=None)` and
`meter/mobile-meters/<id>/?environment=UGX_DEMO|SANDBOX`; these are existing checkout
contracts, not new accounting. Restart the same alwaysdata WSGI site through
**Web → Sites → shanonsimon.alwaysdata.net → Restart**, without changing its Python,
virtualenv, account pages or WSGI target.

The new summary endpoint should return401 to a credential-free GET when enabled
(safe route/auth check; do not print a real user's response or token):

```bash
curl --silent --show-error -o /dev/null -w '%{http_code}\n' \
  'https://shanonsimon.alwaysdata.net/api/v1/sandbox/summary/?environment=UGX_DEMO'
```

For Next.js, retain project root `frontend` and the server runtime: route handlers,
server actions, cookies and middleware are required. Production/Preview environment
`API_URL=https://shanonsimon.alwaysdata.net/api/v1`; no `NEXT_PUBLIC` backend secret,
static export or hosted-account-site change is needed. Build command is
`npm run build -- --webpack`; normal dependency installation follows the unchanged
lockfile. Publish only the reviewed frontend revision through the existing Vercel
pipeline after approval. No commit/push/redeploy was performed locally. Account
email links remain Django-hosted; Android is not rebuilt for this web-only rollout.

Deployment smoke checks: verified consumer sign-in → select meter → overview and
loan-detail agreement → quote/consent → pending recovery → server receipt →
profile change → logout. Use separate authorized testing records; payment completion
must still come from LOCAL_DEMO settlement. General live providers and physical
control stay blocked. Hosted runtime/phone verification remains outstanding.

## Verified results — 2026-11-17

| Check | Actual result |
|---|---|
| Combined isolated PostgreSQL summary/payment/tariff/loan/allocation/feature regressions | **108 run, OK, 2 profile-specific skips** |
| Isolated alwaysdata-profile summary/authentication/account-page/feature checks | **36 passed** |
| Frontend unit/contract/security tests | **24 passed** |
| Mobile strict TypeScript and shared-component regressions | Type check passed; **62 tests passed** |
| Scoped frontend ESLint | Passed; no broad lint rewrite |
| Final full Next.js production build | Passed with webpack, strict TypeScript, 49 generated pages and preserved dynamic server routes |
| Standalone full frontend TypeScript after the build | Passed |
| Production-preview Chromium journey | All17 checks passed; **no page runtime errors** |
| Responsive widths | **1440, 834, 390, 360**; no horizontal overflow in captured key pages |
| Migration drift | No changes detected; no parity migration required |
| Package/lockfile, Next production security settings | Unchanged |

The two base-profile skips are existing tests requiring the alwaysdata hosting
profile (`loan/tests_sandbox.py`); the separate alwaysdata-profile run exercises
that profile's summary and authentication restrictions. They are not failing
financial cases. Existing wallet/meter mirror signal diagnostics appear in the
legacy fixture suite; those code paths were not rewritten and the suite passed.

A network-sandbox build attempt ended with generic webpack errors; an approved
network-enabled build passed with one WSL static-generation worker. Cold
Next development navigation exceeded test timeouts while the machine had about
350MB available RAM. The final screenshots/flows were therefore checked on the
successful **production build**, not a partial development page. No check was
suppressed, no security validator was disabled, and no font/dependency upgrade
was applied to the project. Existing warnings about the middleware naming
convention, browser-baseline package age and direct Node TS module-type detection
remain non-fatal; this phase does not rewrite unrelated configuration.

The production browser journey covers exact overview/detail partial-debt parity;
selected-meter score and below80% explanation; slow A→B response suppression;
quote invalidation; duplicate purchase/application/repayment clicks; pending
navigation/reload recovery; a timer held at zero without settlement; server-confirmed
purchase; approved loan and partial repayment; server rejection and decision
history; unavailable summary; historical13-digit selection; saved profile choice
preservation; pending assessment; empty-meter enrollment with leading zeros;
no legacy wallet/core bootstrap; and cookie/private-state cleanup on logout.

### Screenshots (synthetic records only)

- [Desktop Home](review/consumer-parity/desktop-home.png)
- [Tablet Home](review/consumer-parity/tablet-home.png)
- [Phone Home](review/consumer-parity/phone-home.png), [small phone](review/consumer-parity/phone-small-home.png)
- [Loans](review/consumer-parity/desktop-loans.png), [partial repayment](review/consumer-parity/desktop-partial-repayment.png)
- [Apply terms](review/consumer-parity/desktop-apply-terms.png), [below-threshold explanation](review/consumer-parity/desktop-apply-ineligible.png)
- [Buy Units quote](review/consumer-parity/desktop-buy-units.png), [Activity receipt](review/consumer-parity/desktop-activity.png)
- [Rejected decision](review/consumer-parity/desktop-loan-rejected.png)
- [Phone meters](review/consumer-parity/phone-meters.png), [empty meters](review/consumer-parity/phone-empty-meters.png)
- [Phone account](review/consumer-parity/phone-account.png), [pending assessment](review/consumer-parity/phone-pending-assessment.png)
- [Machine-readable browser result](review/consumer-parity/browser-results.json)

Phone main PNGs are actual viewport captures; `-full.png` variants retain the
scrollable content. Fixed bottom navigation sits at the viewport edge, so the
full-page variants should not be mistaken for one unscrollable phone screen.

## Remaining limits and rollout checks

- The deployed revisions and real borrower records were not inspected; the
  reported arithmetic is proven with isolated PostgreSQL and browser fixtures.
  Verify the corresponding authorized testing account after deployment.
- The visible history remains bounded to recent100, with older active loans and
  pending payments retained. Account totals cover the entire ledger. A future
  server cursor/history export is needed for browsing all older completed records;
  no historical records were deleted or rewritten.
- The existing CORE overdue-after-completion expected failure remains a separate
  financial-policy issue. It was not changed or represented as approved here.
- Actual Android phone testing, live provider integration, AC-board telemetry and
  production financial readiness are outside this web phase. No APK was rebuilt.
- The AC lab deployment/migration is separate; keep it disabled until its own
  prerequisites are reviewed. If its files have independently been uploaded,
  review its schema plan separately instead of assuming this loan-only patch
  resolves those dependencies.
- Publish only reviewed source. No commit, push, deployment, hosted migration,
  operational transaction or credential rotation was performed.
