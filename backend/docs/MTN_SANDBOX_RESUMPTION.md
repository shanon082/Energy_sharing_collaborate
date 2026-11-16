# New collections: MTN Sandbox, existing ledgers retained

Prepared locally on 2026-11-17. **Not deployed. No actual MTN, board or phone test
was performed for this change.** This document supersedes the LOCAL_DEMO default
and the “pause MTN reconciliation” instructions in older prototype runbooks.

## Scope and decisions

Use `backend.alwaysdata_sandbox_settings` with
`PROTOTYPE_PAYMENT_PROVIDER=MTN_SANDBOX` for **new** purchases and self-repayments.
Do not enable the legacy financial flags. Missing sandbox credentials return
`Sandbox payments unavailable`; there is no fallback to LOCAL_DEMO, core money,
another provider, or an exchange rate. Both clients consume `/features/` and the
same sandbox payment APIs. Existing authentication, account pages/CSRF, restrictive
CORS and scheduled account mail are unchanged. All seven deferred features stay off.

| Activity | Supported terms / boundary |
| --- | --- |
| New EUR TEST purchases | Existing `SANDBOX-TEST-v1` policy: default range EUR1–20, exact fixed EUR1/kWh. Explicit `SANDBOX_RATE_PER_KWH` is an isolated prototype assumption, **not** a utility tariff or conversion. Operator must review the EUR values before testing. Quote freezes rate, rounding, owner, meter, amount, residual and policy. Missing/nonpositive/non-EUR pricing blocks new energy; domestic UGX bands/service charges are not used. |
| Existing EUR TEST loans | Own DISBURSED EUR/MTN_SANDBOX obligations can receive EUR repayments up to current debt at initiation. Frozen original principal/interest/fee/due terms apply. Concurrent excess is retained, no refund or energy. Fully repaid debt remains closed. |
| NEW EUR loans | **Unavailable in the hosting profile.** `SANDBOX_EUR_LOANS_ENABLED=False` is hard-coded. The existing EUR service has historical profile/questionnaire-based scoring; the current automatic meter-bound assessment is UGX-only. Decide and implement a versioned EUR automatic assessment/limit policy before enabling new origination. No questionnaire, score copy or currency conversion is introduced. Historical EUR origination tests explicitly opt into the old fixture policy; they are not evidence of current eligibility. |
| Existing UGX_DEMO obligations/history | Never changed to EUR. Existing LOCAL_DEMO pending records can still complete under their original timed simulator through their bound status POST or the finite demo job. No NEW UGX demo payment/loan is initiated in MTN mode. Existing UGX loans cannot be repaid with an EUR receipt; a separately reviewed same-currency servicing arrangement is needed for new repayments. Do not delete or close them to bypass this boundary. |
| CORE UGX | Unchanged and blocked from these settlement routes. |
| AC_LAB device | UGX_DEMO-only contract unchanged. The current lab capability also requires LOCAL_DEMO mode, so switching new payments to MTN leaves its routes unavailable. Existing tokens/commands are retained. No EUR token/device domain was implemented or enabled. A separately tested domain or lab/servicing design is required before EUR-backed device credit. Relay remains disabled. |

Existing EUR fixed-price loans and purchases already have compatible currency
snapshots. That does not make old profile inputs suitable for new automatic loans.
No historical obligation is recalculated from current configuration. Existing UGX
automatic assessments stay stored; MTN mode reports EUR assessment unavailable,
not a zero score or a fabricated allowance. No external CRB lookup occurs.

## One durable payment pipeline

Reuse `transactions.sandbox_payments`, `mtn_momo.sandbox.MTNSandbox` and
`transactions.payment_settlement`; no second collection or ledger was added.

1. `POST /api/v1/sandbox/quotes/`: owned active sandbox meter, PURCHASE, EUR amount.
   Review exact terms/hash/expiry. New loan quote requests fail closed under the
   hosted EUR assessment restriction.
2. `POST /api/v1/sandbox/payments/`: explicit consent, quote/hash or own EUR loan,
   test MSISDN, stable `client_request_id`. Owner lock/idempotency persist one
   provider UUID and external ID **before** network I/O. An unresolved test payment
   in either provider blocks another initiation. Retry/recovery uses its identity.
3. MTN request-to-pay HTTP202 records `ACCEPTED`, still `PENDING`. No timer,
   authorization screen or HTTP success creates energy or pays debt. Timeout or
   uncertain HTTP response becomes `OUTCOME_UNKNOWN`; subsequent work queries the
   **same reference**, never sends the charge again. An expired SUBMITTING lease
   also resumes status lookup. An unresolved provider404 is not permission to retry.
4. `GET /sandbox/payments/<reference>/` is a read-only stored receipt;
   `POST` explicitly asks Django to reconcile with backoff/lease protection.
   Both clients poll these Django endpoints. The finite job performs the same
   operation when clients are closed.
5. MTN HTTP200 JSON `PENDING`/unknown produces no settlement. JSON `FAILED`
   with matching source evidence is terminal with no financial effect.
   `SUCCESSFUL` requires matching reference binding, external ID, exact amount,
   EUR currency, payer, owner/purpose, quote/environment and a nonempty financial
   transaction ID. The reference is bound by the exact trusted HTTPS status URL;
   MTN's JSON does not independently echo it. Redirects are forbidden. Database
   locks plus existing provider/transaction uniqueness prevent duplicate effects
   across intents as well as retries. External I/O stays outside locked transactions.
6. Purchases create one source-linked SANDBOX allocation and conserve received =
   billed + residual. Energy is floored once to **10 Wh**, residual retained.
   Repayments create a debt settlement only: **no allocation or keypad token**.
   Same-currency concurrent excess remains separately recorded for reconciliation.

All receipts retain original provider/currency, and both clients recover request
handles from both environments. A missing recovery row after a timeout does not
clear the identity or permit another initiation: it may race an in-flight POST.
If no record ever appears, operator review is required before abandoning the
uncertain handle; no automatic new UUID, cancellation or refund is performed. Payment confirmed, token issued (if enabled),
and credit durably saved by a device acknowledgement are distinct. EUR token
cards explicitly say they cannot be used on the current AC lab. No telemetry,
requested relay state, gateway receipt or queued command proves application.

The five-second countdown remains only for already-existing LOCAL_DEMO requests
(or an explicitly selected local simulator deployment). MTN pending payments have
no five-second completion rule. Both modes require a Django SETTLED receipt.

Official MTN reference: [Collections sandbox request example](https://momodeveloper.mtn.com/content/html_widgets/v98wn.html)
uses the sandbox Collections host, a UUID reference, external ID and EUR currency.
The repository's existing adapter and mocked status tests cover the implemented
contract; real credential acceptance and actual response shapes still need a
separately authorized MTN sandbox test. No provider secret belongs in either app.

## Local verification

Use `deploy/test-hosting.py` only with the documented isolated PostgreSQL cluster
on 127.0.0.1:55445; its global network mock rejects accidental external requests.
`loan.tests_mtn_transition` exercises actual adapter code with mocked HTTP:
202→PENDING→SUCCESSFUL, HTTP200+FAILED, timeout/scheduled recovery, immutable
reference, duplicate effect, currency mismatch, repayment/no token, pricing and
credentials unavailable, GET purity and legacy LOCAL_DEMO completion after switch.
Existing suites cover concurrent settlement, cross-intent replay, owner isolation,
overpayments, allocation/device restrictions and seven feature gates.

Shared client contract/presentation regressions run from both frontend and mobile;
pending remains pending after elapsed time and both surfaces read the same receipt.
Build/test results are reported with the implementation handoff, independently of
live MTN, hosted scheduler, phone or ESP32 testing.

### Executed local validation

The broad PostgreSQL run passed **200 tests**, with **3 profile-specific skips**
and **1 retained expected failure** (CORE overdue debt after completion; no policy
change was made). After the final recovery-command refinements, the hosted-profile
run below passed **96 tests**, including the added paused-mode recovery and HTTPS
CORS cases. The six existing HTTP CORS tests passed separately in their intended
development profile. Running those HTTP-only tests under enforced HTTPS returns
301 by design; it is not evidence to weaken redirect, CSRF or CORS settings.

Broad run (additional transition tests were added afterward and covered by the
final hosted-profile run):

```bash
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py loan.tests_mtn_transition loan.tests_sandbox transactions.tests_demo_payments transactions.tests_payment_settlement backend.tests_feature_flags meter.tests_prototype_device meter.tests_allocation_delivery meter.tests_hardware_readiness loan.tests_demo_assessment loan.tests_meter_credit_tariffs loan.tests_consumer_summary loan.tests_financial_correctness
```

Final hosted-profile run, plus separate HTTP-only and migration-drift checks:

```bash
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --sandbox-profile loan.tests_mtn_transition loan.tests_sandbox transactions.tests_demo_payments backend.tests_feature_flags backend.tests_alwaysdata.AlwaysdataProfileTests backend.tests_alwaysdata.AlwaysdataAuthenticationFlowTests accounts.tests_account_pages
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py accounts.tests_mobile_cors
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --check-migrations
```

No migration drift was detected in loan/meter/transactions. The sandbox suites
include PostgreSQL concurrent worker/collection claims, duplicate settlement and
distinct repayments with preserved excess; actual HTTP adapter responses are
mocked. No real MTN test occurred.

Mobile: strict `npm run typecheck`, `node --test --test-isolation=none tests/*.test.mjs`
(**65 passed**) and `npm run build:debug` passed. The built bundle contains exactly
`https://shanonsimon.alwaysdata.net/api/v1`. This is a web bundle, **not a rebuilt APK**.
The parity test renders the actual shared TSX component for both web/mobile surfaces
against identical synthetic pending/settled/failed and repayment receipts.

Frontend: production `CIRCLE_NODE_TOTAL=2 API_URL=https://shanonsimon.alwaysdata.net/api/v1 timeout --signal=TERM --kill-after=15s 600s npm run build -- --webpack`
passed, preserving dynamic server pages and strict type checking (49 generated
pages). Standalone `npx tsc --noEmit` passed **after** the build; do not run it concurrently
while Next regenerates `.next/types`. Scoped ESLint and
`node --test --test-isolation=none tests/*.test.mjs` passed (**27 tests**, zero scoped
lint errors/warnings). Existing Node
module-type, middleware-convention and browser-baseline notices are not suppressed.

## Deployment preparation — commands for the operator, NOT executed

From the repository root, inspect the narrow allowlist, then dry-run/upload:

```bash
rsync -avni --files-from=backend/deploy/mtn-resumption.files backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
rsync -avi --files-from=backend/deploy/mtn-resumption.files backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
```

No `--delete`. Only the named source/docs/test/example files are transferred;
no `.env`, credentials, virtualenv, DB, static output or APK. This is an incremental
overlay on the existing consumer sandbox/parity/device source baseline. If the
host lacks that baseline, review its earlier allowlists separately; do not pretend
this overlay deploys every uncommitted repository change.

SSH manually. Edit the existing private file; do not paste or print its contents:

```bash
chmod 700 /home/shanonsimon/.config/energy-sharing
chmod 600 /home/shanonsimon/.config/energy-sharing/backend.env
nano /home/shanonsimon/.config/energy-sharing/backend.env
```

Set/retain the following privately, using **existing dedicated sandbox keys**:

```dotenv
PROTOTYPE_PAYMENT_PROVIDER=MTN_SANDBOX
MTN_SANDBOX_BASE_URL=https://sandbox.momodeveloper.mtn.com
MTN_SANDBOX_CURRENCY=EUR
MTN_SANDBOX_SUBSCRIPTION_KEY=<PRIVATE_COLLECTIONS_SANDBOX_KEY>
MTN_SANDBOX_API_USER_ID=<EXISTING_SANDBOX_API_USER_UUID>
MTN_SANDBOX_API_KEY=<EXISTING_PRIVATE_SANDBOX_API_KEY>
SANDBOX_POLICY_VERSION=SANDBOX-TEST-v1
SANDBOX_RATE_PER_KWH=1.00
MOBILE_PAYMENT_ACTIONS_ENABLED=false
MTN_USE_SIMULATED_PAYMENTS=false
SIMULATED_METER_ENABLED=false
PROTOTYPE_AC_LAB_ENABLED=false
FEATURE_THIRD_PARTY_REPAYMENT_ENABLED=false
FEATURE_USSD_ENABLED=false
FEATURE_WALLET_DEPOSITS_ENABLED=false
FEATURE_WALLET_WITHDRAWALS_ENABLED=false
FEATURE_EXTERNAL_CRB_ENABLED=false
```

Peer sharing and meter transfers remain unconditionally retired. Keep all other
SECRET_KEY, DB_*, mail, token encryption/lookup keys, allowed hosts and Android
origins unchanged. Do not substitute production keys or run provisioning again.
Review the complete versioned EUR policy in `alwaysdata-sandbox.env.example`.
Changing provider is a deployment setting, never a client request parameter.

Verify the target and plan without reading records or printing passwords:

```bash
cd /home/shanonsimon/energy-sharing
export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
export DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings
/home/shanonsimon/energy-venv/bin/python manage.py shell -c 'from django.conf import settings; d=settings.DATABASES["default"]; assert d["NAME"]=="shanonsimon_energy_test" and d["HOST"]=="postgresql-shanonsimon.alwaysdata.net" and d["USER"]=="shanonsimon"; from django.db import connection; c=connection.cursor(); c.execute("SELECT current_database(), current_user"); assert c.fetchone()==("shanonsimon_energy_test","shanonsimon"); print("Expected testing database confirmed; no records read")'
/home/shanonsimon/energy-venv/bin/python manage.py check --deploy
/home/shanonsimon/energy-venv/bin/python manage.py migrate --plan
/home/shanonsimon/energy-venv/bin/python manage.py reconcile_sandbox_payments --limit 2 --max-seconds 50
/home/shanonsimon/energy-venv/bin/python manage.py complete_demo_payments --limit 20 --max-seconds 50
```

Both commands above are dry-runs: identifiers only, no provider I/O/settlement.
**No new migration is introduced by this change.** Review outstanding earlier
migrations separately; do not apply an unfamiliar plan. Only after operator
review of the target and pending plan, use `manage.py migrate --noinput` if
needed. This implementation has not run any hosted migration.

Then `manage.py collectstatic --noinput` with the same interpreter/environment.
Web → Sites: retain WSGI application
`/home/shanonsimon/energy-sharing/backend/alwaysdata_sandbox_wsgi.py`, Python3.12.15,
venv `/home/shanonsimon/energy-venv`, working directory
`/home/shanonsimon/energy-sharing`, same environment above, hostname and HTTPS;
click **Restart**. No Next.js dependency for email links is introduced.

Advanced → Scheduled tasks: every minute, finite command (subject to plan quotas):

```bash
ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings /home/shanonsimon/energy-venv/bin/python /home/shanonsimon/energy-sharing/manage.py reconcile_sandbox_payments --run --limit 2 --max-seconds 50
```

Retain a separate original-provider recovery job for older LOCAL_DEMO requests:

```bash
ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings /home/shanonsimon/energy-venv/bin/python /home/shanonsimon/energy-sharing/manage.py complete_demo_payments --run --limit 20 --max-seconds 50
```

Do not replace `drain_account_emails --send --limit 5`. No Redis/Celery worker or
global eager mode. MTN leases last90s; backoff30s→3600s, HTTP connect/read(3s,7s),
job wall-clock50s. Job limits can cause backlog; inspect non-sensitive job status
and oldest pending age. Interrupted submission never authorizes another charge.
Do not schedule physical dispatch or enable the relay to clear pending records.

Credential-free HTTPS check after operator deployment:

```bash
curl --fail --silent --show-error https://shanonsimon.alwaysdata.net/api/v1/features/
```

Expect provider MTN_SANDBOX, currency EUR, physical_delivery false, loans false,
all seven features false; purchases/repayments only true when configured. Presence
of keys is not proof they work. Next, with isolated test accounts and separately
authorized MTN testing: review EUR quote → submit once → confirm pending → close
app → inspect scheduled reconciliation → reopen exact reference/receipt; check
failed scenarios and own EUR repayments. Verify no repayment token and no AC lab
application. Android requires an updated build to include the shared poller and
labels; no APK was rebuilt or phone test claimed in this phase.
