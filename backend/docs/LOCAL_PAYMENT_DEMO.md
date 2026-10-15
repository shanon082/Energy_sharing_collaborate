# Local payment demo — NO REAL MONEY

The opt-in `backend.alwaysdata_sandbox_settings` now defaults to
`PROTOTYPE_PAYMENT_PROVIDER=LOCAL_DEMO`. The ordinary alwaysdata/Render/core
profile does not enable this simulator. A consumer cannot choose the provider,
currency, price, timing, success or accounting environment in a request.
Next.js and Capacitor use the shared consumer component and the same Django
services. No PIN, real phone prompt, provider network request or device command
occurs. MTN code, provisioned private credentials and recovery records remain
intact and dormant; do not run the provisioning helper for this deployment.

See [Automatic demo assessment](AUTOMATIC_DEMO_ASSESSMENT.md) for signup, enrollment,
synthetic provenance, the fourth additive migration and preview-first existing-user repair.
Android no longer calls the legacy questionnaire.

## Records and proposed prototype policy

| Domain | Currency | Payment provider | Allocation accounting environment |
| --- | --- | --- | --- |
| Existing EUR test | EUR TEST | MTN_SANDBOX | SANDBOX |
| New local demo | UGX DEMO | LOCAL_DEMO | UGX_DEMO |
| Existing core | UGX as recorded | Original provider as recorded | CORE |

`SandboxQuote`, `SandboxLoan` and `SandboxSettlement` now persist explicit
currency/environment pairs. Existing rows default to their already-known EUR
MTN domain; amounts, terms, decisions, obligations and allocation history are
not converted or replayed. Old EUR history remains readable. One active loan
per owner **per test environment** is allowed, so an existing EUR test borrower
can enroll/select their owned prototype meter and create a separate UGX demo
loan. No existing loan is automatically closed. UGX demo payments cannot repay
EUR loans. Core obligations still require separate review and block borrowing.
An operator may later deliberately restore MTN_SANDBOX mode and its scheduler
to service EUR debt after resolving credential/provider issues; do not delete,
refund, replay or cancel uncertain MTN records during this pause.

**DEMO-UGX-v1 defaults are synthetic prototype assumptions, not approved utility
pricing, loan terms, an exchange rate or a replacement for existing tariffs.**

| Setting | Default / effect |
| --- | --- |
| DEMO_MINIMUM / DEMO_MAXIMUM | 1,000 / 50,000 whole UGX, quote range |
| DEMO_STARTER_LIMIT | 5,000 UGX retained configuration; automatic assessment requires READY, no missing-data starter fallback |
| DEMO_RATE_PER_KWH | 1,000 UGX/kWh, test price only |
| DEMO_INTEREST_PERCENT / DEMO_FEE | Flat 5% once / 0 UGX |
| DEMO_DUE_DAYS / DEMO_QUOTE_MINUTES | 7 days / 15 minutes |
| Overdue charges | 0%; no new accrual after or before closure |
| DEMO_SCORE_THRESHOLD | 75; stored automatic simulated assessment using existing three-factor calculator |
| Stored-score limit | ≥90:50,000; ≥85:37,500; ≥80:25,000; otherwise12,500, then threshold check |
| DEMO_PURCHASE_PER_POINT / DEMO_PURCHASE_SCORE_CAP | 10,000 billed demo UGX / 10 points, only READY automatic demo assessments |
| Request maximum | 1,000,000 UGX; new repayment ≤ outstanding at initiation |

Money uses Decimal. Payments are positive **whole UGX**; interest is half-even
rounded once to a whole shilling. Allocation precision remains **0.01 kWh =
10 Wh**, floored once at the accepted quote. Received money is never reduced
to billed money: 1,003 UGX at the default test price allocates 1.00 kWh,
bills 1,000 UGX, preserves 3 UGX residual. Fractional calculated billed/residual
values at other configured integer prices are retained exactly (ledger six
decimal places). No automatic refund, extra energy, write-off or currency
conversion is performed. Config changes require a new DEMO_POLICY_VERSION;
accepted quotes and loans retain their policy/price/interest/fee/rounding snapshots.

Example loan: 1,000 UGX → one 1.00-kWh cloud allocation, 50 UGX interest,
1,050 UGX debt. Partial repayment 300 leaves 750; final 750 permanently closes
it. Repayment creates no energy. Two separately authorized 800-UGX payments
received for that debt record full 1,600, apply 1,050 and retain excess550.
Cloud energy is available entitlement, not a physical-meter receipt. Enrollment
remains SELF_DECLARED, no staff approval/inventory/simulator required; ownership
and live readings are not verified with the electricity provider. Physical
balance, actual usage, relay feedback/contact and application acknowledgement
remain unavailable without real device evidence.

## Server-authoritative sequence

1. POST `sandbox/quotes/` with PURCHASE, owned meter ID, amount `"1003"`;
   explicitly accept the returned terms/hash.
2. POST `sandbox/payments/` with quote ID/hash, PURCHASE,
   accept_test_terms:true, stable client_request_id UUID. Or use LOAN_REPAYMENT,
   owned **UGX_DEMO** loan_id and whole amount. No MSISDN/PIN is required.
3. Server records `LOCAL_DEMO`, `UGX`, immutable source binding and pending
   identity; `demo_eligible_at` is at least five seconds after `initiated_at`.
   The database enforces that minimum; no request sleeps for five seconds.
4. UI displays “Demo payment: simulating phone authorization. No PIN or real
   money is required.” Countdown uses server time, not the phone's wall-clock
   offset. It polls stored GET status, then makes explicit completion POST to
   `sandbox/payments/<reference>/`. GET never settles. A forged success flag,
   provider evidence dictionary or early POST cannot settle.
5. Timed server completion locks the intent, validates the test-domain/source
   snapshot and invokes shared settlement/allocation services with an internal
   demo capability. Deterministic `demo-<reference>` evidence and existing
   provider-transaction uniqueness prevent cross-intent replay. One settlement
   and one purchase allocation; owner/loan locking preserves distinct repayment
   arrivals and excess. A response/timer alone never proves settlement.
6. Only a SETTLED server receipt displays “Demo payment successful — no real
   money was deducted.” Restart/reconnect uses owner-bound recovery and GETs;
   retry handles are namespaced separately from EUR and cleared on logout.
   No transaction is initiated offline. Unavailable backend leaves pending
   status/error visible, never fabricated success.

Existing API paths are reused; status and history show each record's currency,
environment, provider and original terms. Application idempotency and automatic
loan decisions remain. Receipt ledger satisfies received=billed+residual+applied+
excess. Sandbox settlement never spends ambiguous wallets/UnitBalance, changes
core score history or creates hardware/delivery evidence.

## Upload, private configuration and migration review — not executed

From the repository root, review this allowlisted dry-run, then upload during a
maintenance window. No --delete; paths map backend contents to the existing
remote backend directory. Existing baseline migrations must be present.

```bash
rsync -avn --files-from=backend/deploy/consumer-sandbox.files --exclude='.env*' --exclude='venv*/' --exclude='__pycache__/' --exclude='*.pyc' --exclude='*.log' --exclude='logs/' --exclude='media*/' --exclude='staticfiles/' --exclude='*.sqlite3*' --exclude='*.db' --exclude='*.sql' --exclude='*.dump' --exclude='*.pem' --exclude='*.key' backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
rsync -av --files-from=backend/deploy/consumer-sandbox.files --exclude='.env*' --exclude='venv*/' --exclude='__pycache__/' --exclude='*.pyc' --exclude='*.log' --exclude='logs/' --exclude='media*/' --exclude='staticfiles/' --exclude='*.sqlite3*' --exclude='*.db' --exclude='*.sql' --exclude='*.dump' --exclude='*.pem' --exclude='*.key' backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
ssh shanonsimon@ssh-shanonsimon.alwaysdata.net
chmod 700 /home/shanonsimon/.config/energy-sharing
chmod 600 /home/shanonsimon/.config/energy-sharing/backend.env
nano /home/shanonsimon/.config/energy-sharing/backend.env
```

Privately add `PROTOTYPE_PAYMENT_PROVIDER=LOCAL_DEMO` and the DEMO_* values
in `alwaysdata-sandbox.env.example`. Keep working SECRET_KEY, DB and Gmail
SMTP credentials unchanged. Do not paste example secret placeholders into the
private file. Existing valid dedicated MTN_* credentials may stay dormant;
for a new demo-only installation leave credential variables absent. Dormant
credential UUID validation is deferred in LOCAL_DEMO; actual key/UUID validation
remains required when deliberately resuming MTN_SANDBOX. Never use
legacy/production credentials. Keep DB_SSLMODE=require, trusted hostname
shanonsimon.alwaysdata.net and Django-hosted verification/reset links. Preserve
all seven deferred feature flags false, MOBILE_PAYMENT_ACTIONS_ENABLED=false,
MTN_USE_SIMULATED_PAYMENTS=false, SIMULATED_METER_ENABLED=false,
PURCHASE_HISTORY_SCORING_ENABLED=false, CELERY_TASK_ALWAYS_EAGER=false.

On the host (commands for operator review; none executed here):

```bash
cd /home/shanonsimon/energy-sharing
export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
export DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings
/home/shanonsimon/energy-venv/bin/python manage.py check_alwaysdata_database
/home/shanonsimon/energy-venv/bin/python manage.py showmigrations loan meter transactions accounts token_blacklist
/home/shanonsimon/energy-venv/bin/python manage.py migrate --plan
/home/shanonsimon/energy-venv/bin/python manage.py sqlmigrate loan 0024
/home/shanonsimon/energy-venv/bin/python manage.py sqlmigrate loan 0025
/home/shanonsimon/energy-venv/bin/python manage.py sqlmigrate meter 0030
/home/shanonsimon/energy-venv/bin/python manage.py sqlmigrate transactions 0012
```

Stop if the target differs, the full plan contains unexpected migrations or
required baseline files are missing. Back up the testing DB privately using the
existing hosted backup process. New schema changes:
`loan.0024_demo_currency_domains`, `meter.0030_demo_allocation_domain`,
`transactions.0012_demo_payment_deadline_and_domains`, and
`loan.0025_democreditassessment` (a separate empty assessment table; no historical
score rewrite or automatic backfill). They add explicit known
EUR domain metadata and the nullable/indexed demo deadline, expand source and
domain constraints, scope active-loan uniqueness by environment, and change
new initiated_at default to an explicit trusted timestamp. Existing timestamp
values are unchanged. No balance/amount/loan-decision rewrite or credit replay.
Schema constraints/index changes can lock tables; use a maintenance window.
After target/plan/backup review:

```bash
/home/shanonsimon/energy-venv/bin/python manage.py migrate --noinput
/home/shanonsimon/energy-venv/bin/python manage.py collectstatic --noinput
/home/shanonsimon/energy-venv/bin/python manage.py check --deploy
/home/shanonsimon/energy-venv/bin/python manage.py complete_demo_payments --limit 20 --max-seconds 50
```

Keep Web → Sites using Python3.12.15, virtualenv
`/home/shanonsimon/energy-venv`, WSGI
`/home/shanonsimon/energy-sharing/backend/alwaysdata_sandbox_wsgi.py`, private
ALWAYSDATA_ENV_FILE above; static alias /static/ points to
`/home/shanonsimon/energy-sharing/staticfiles/`. Click **Restart** for the existing
site. The ordinary alwaysdata WSGI deliberately keeps transactions unavailable;
use only the explicit prototype WSGI for this demo. No Next.js hosting required.

## Finite scheduled simulator and verification

In Advanced → Scheduled tasks, **pause the old reconcile_sandbox_payments task**
without deleting its records/credentials. Add this finite command every minute:

```bash
ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings /home/shanonsimon/energy-venv/bin/python /home/shanonsimon/energy-sharing/manage.py complete_demo_payments --run --limit 20 --max-seconds 50
```

[alwaysdata scheduled-task documentation](https://help.alwaysdata.com/en/docs/web-hosting/tasks/)
notes that jobs may start anywhere within their scheduled minute and an
overlapping run is skipped. Monitor the task log in the administration panel
or `/home/shanonsimon/admin/logs/jobs/`; reduce frequency if resource use grows.

This job selects only eligible PENDING LOCAL_DEMO UGX intents. It has a hard
55-second maximum configurable budget, bounded batch1–100, dry-run by default;
blocked records are retained and command exits with an error, never silently
cancelled. Concurrent jobs and mobile completion serialize one effect. With the
app open, completion is normally requested just after the five-second deadline.
With the app closed, expect that deadline **plus the scheduled interval, up to
59 seconds of host start jitter, and backlog/skipped runs**; scheduling is not
a guarantee of completion at exactly five
seconds. No Redis/Celery/global eager mode or persistent daemon is required.
Keep the existing `drain_account_emails --send --limit 5` schedule unchanged.

```bash
curl --fail --silent --show-error https://shanonsimon.alwaysdata.net/api/v1/features/
curl --silent --show-error -i -X OPTIONS https://shanonsimon.alwaysdata.net/api/v1/sandbox/payments/ -H 'Origin: http://localhost' -H 'Access-Control-Request-Method: POST' -H 'Access-Control-Request-Headers: authorization,content-type'
```

Verify sandbox.provider LOCAL_DEMO, currency UGX, environment UGX_DEMO, loans/
purchases/repayments true, physical_delivery false; all seven feature values
and core mobile actions false. Preflight must allow the APK's exact debug
origin http://localhost, not wildcard. Release HTTPS/CORS/auth/CSRF are unchanged.
Do not publish tokens or full private responses in diagnostics.

Install the freshly built debug APK with `adb install -r <absolute-apk-path>`.
Use the existing signing identity; do not uninstall a working same-signature app.
Phone checklist: verified login → self-declared meter/selection → demo loan →
demo purchase → visible countdown → SETTLED receipt and cloud energy → partial
repay → full repay/closed debt → restart during another pending purchase and
check scheduler recovery → disconnect/reconnect → logout/account isolation.
Old EUR histories must retain EUR labels and their obligations; actual usage/
physical balance remain unavailable. No live MTN or physical test is claimed.

## Local validation and artifact (13 October 2026)

Implemented files include `backend/demo_config.py`, the prototype settings and
capability response, test-domain model/service changes, shared payment
settlement, `transactions/demo_payments.py`, finite completion command, MTN
pause guards, staff read-only labels, shared React contracts/component, Android
banner/tests and the three migrations above. Existing provisioning-helper user
changes and prior runbook additions were preserved. No hosted deployment,
operational migration, provider/device call or phone test was performed.

The guarded local runner clears inherited/local .env values, verifies the
isolated /tmp PostgreSQL cluster on port55445 and uses a disposable test DB;
HTTP providers and email are mocked. Commands run from repository root:

```bash
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py loan.tests_demo_assessment transactions.tests_demo_payments meter.tests_sandbox_enrollment loan.tests_sandbox meter.tests_enrollment_review accounts.tests_consumer_expansion backend.tests_alwaysdata.PrivateEnvironmentTests backend.tests_alwaysdata.AccountMailOutboxTests accounts.tests_authentication accounts.tests_mobile_api accounts.tests_mobile_cors accounts.tests_mobile_profile_meters accounts.tests_mobile_activity backend.tests_feature_flags backend.tests_render_config.RenderEnvironmentTests transactions.tests_payment_settlement meter.tests_allocation_delivery loan.tests_financial_correctness
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --sandbox-profile loan.tests_demo_assessment transactions.tests_demo_payments meter.tests_sandbox_enrollment loan.tests_sandbox meter.tests_enrollment_review accounts.tests_account_pages backend.tests_alwaysdata.AlwaysdataProfileTests backend.tests_alwaysdata.AlwaysdataAuthenticationFlowTests
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --sandbox-profile transactions.tests_demo_payments
```

Final combined suite: **259 tests run, OK**, four profile-specific skips and
one known completed-core-loan overdue expected failure. Final alwaysdata sandbox
profile suite: **118 tests passed**. These runs include automatic signup/enrollment
assessment, missing/malformed provider evidence, immutable simulated fixtures,
owner isolation, concurrent initialization, questionnaire retirement, fresh
submission limits/policy changes and once-only source-linked purchase scoring.
Existing wallet-signal conflict/retry warnings occur in legacy test fixtures;
these are not new failing cases and were not suppressed.
Actual PostgreSQL concurrent threads proved duplicate completion effects
`[False, True]`, one allocation/receipt, and distinct repayment received1600=
applied1050+excess550. Early completion, read-only GET, owner/meter binding,
policy domain mismatches, no provider requests, partial/final repayment,
permanent closure, idempotent initiation/loan decisions and restart/scheduled
recovery are covered. Core expected failure was not removed or claimed fixed.

```bash
cd mobile
npm run typecheck
node --test --test-isolation=none tests/*.test.mjs
VITE_API_BASE_URL=https://shanonsimon.alwaysdata.net/api/v1 VITE_ACCOUNT_COMPLETION=browser npm run android:sync:debug
cd ../frontend
npx tsc --noEmit
node --test --test-isolation=none tests/features.test.mjs
npx eslint src/components/sandbox-consumer.tsx src/components/sandbox-web.tsx src/lib/sandbox.ts
```

Mobile: strict types, **42 tests**, Vite debug bundle and Capacitor sync passed.
Web: strict types, three required/deferred-navigation regression tests and
focused lint passed. Production Next build timed out after180s during optimized
compilation, without a specific code error in this run; no strict/build-error
bypass was enabled. The independent Android build does not depend on that build.

Offline Android assembly from repository root:

```bash
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 ANDROID_HOME=/home/shanon/Android/Sdk ANDROID_USER_HOME=/home/shanon/projects/next_projects/Energy-sharing-project/mobile/.android-signing GRADLE_USER_HOME=/home/shanon/projects/next_projects/Energy-sharing-project/mobile/.gradle-user PATH=/usr/lib/jvm/java-21-openjdk-amd64/bin:$PATH mobile/android/gradlew --offline --no-daemon --max-workers=2 '-Dorg.gradle.jvmargs=-Xmx768m -XX:ActiveProcessorCount=2' -p mobile/android assembleDebug -Pandroid.injected.signing.store.file=/home/shanon/projects/next_projects/Energy-sharing-project/mobile/.android-signing/debug.keystore -Pandroid.injected.signing.store.password=android -Pandroid.injected.signing.key.alias=androiddebugkey -Pandroid.injected.signing.key.password=android
```

The standard public Android debug-keystore passwords above are not production
signing credentials. The initial sandboxed Gradle attempt failed on its local
file-lock networking; the approved unrestricted **offline** build succeeded.
Nonfatal existing flatDir/SDK XML-version warnings remain. No dependency upgrades.

Artifact: `/home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk`
— **4,466,333 bytes**.
SHA-256: `a4ebc1c6283692906d6207bbe70cc7e612acac76cc7bdf96d86cad527483ebfe`.
Signature verified v2; existing certificate SHA-256:
`e9fb53040e78b6a525b67462cc5cc72a656de66ebe6c55061714e785eae86b4c`.
Application ID org.gpawa.consumer.prototype, version1.0/code1,
minimum Android7/API24, target36. APK assets match current mobile/dist and
contain the HTTPS alwaysdata `/api/v1` URL and demo labels, with no old LAN URL.
Debug origin is http://localhost; release configuration remains https://localhost.
No key is committed. Install after deploying the reviewed backend changes:

```bash
adb install -r /home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk
explorer.exe "$(wslpath -w /home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug)"
```

The second command opens the APK directory in Windows for copying to the phone.
Phone installation, WebView interaction and actual hosted scheduler execution
remain operator checks. Missing scheduler means closed-app payments stay pending
until explicit completion/reconciliation; no server success is fabricated.
