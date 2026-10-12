# Sandbox validation and debug artifact — 13 October 2026

Implemented locally. No upload, hosted migration, actual MTN collection,
physical meter operation or phone installation was performed.

## Changed implementation

- Opt-in `backend/alwaysdata_sandbox_settings.py`, dedicated WSGI, exact-path
  hosting middleware exceptions and server capabilities; ordinary profiles and
  seven deferred flags unchanged.
- `loan/sandbox_*`: versioned quote, self-reported/starter assessment, actual
  automatic decision, debt closure, API and authorized Django staff page.
- `transactions/sandbox_*`, `payment_settlement.py`, `mtn_momo/sandbox.py`:
  real sandbox adapter, durable intent/lease/backoff, trusted single settlement,
  currency-isolated receipts and conservation ledger.
- `meter/models.py`, `sandbox_enrollment.py`, allocation service and mobile reads:
  immediate SELF_DECLARED prototype ownership, protected provenance and unique
  source allocations; stricter staff review retained for physical/legacy inventory;
  old meter response shape remains unchanged unless it is a test meter.
- Four sandbox schema migrations: loan0023, meter0028, transactions0011 and new
  meter0029 (provenance only); no data rewrite.
- Shared `frontend/src/lib/sandbox.ts`, `components/sandbox-consumer.tsx`, web
  wrapper/page and Loan/Buy Units panels; mobile App/contracts and React dedupe.
- Sandbox tests, isolated test-runner profile support, placeholder environment,
  operator provisioning helper and deployment documentation. Prior dirty work
  was preserved. The incremental backend upload list is `deploy/consumer-sandbox.files`.

Enrollment revision files: new `meter/sandbox_enrollment.py`,
`meter/migrations/0029_sandboxmeterenrollment.py`, `meter/tests_sandbox_enrollment.py`,
shared `frontend/src/lib/meter-enrollment.ts` and `mobile/tests/meter-enrollment.test.mjs`.
Updated backend meter models/onboarding/mobile views/URLs/legacy alias,
review service/page, loan sandbox eligibility, features and hosting middleware.
Updated mobile App/Onboarding/contracts/enrollment labels and browser scenario;
web register component/action and shared sandbox consumer/web forms. Environment
example, runbooks, upload allowlist and earlier-scope documentation pointers
were updated. No unrelated working-tree changes were reset or committed.

## Local test commands and evidence

All backend runs use the guarded local `/tmp` PostgreSQL18 cluster, port55445,
synthetic test credentials, disposable test database, mock SMTP and prohibited
external HTTP by default. Provider tests explicitly inject mocks; no operational
database is read or migrated. Hosting tests use private temporary environment
files and local TLS-disabled PostgreSQL, not the hosted database.

```bash
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py meter.tests_sandbox_enrollment loan.tests_sandbox meter.tests_enrollment_review accounts.tests_consumer_expansion backend.tests_alwaysdata.PrivateEnvironmentTests backend.tests_alwaysdata.AccountMailOutboxTests accounts.tests_authentication accounts.tests_mobile_api accounts.tests_mobile_cors accounts.tests_mobile_profile_meters accounts.tests_mobile_activity backend.tests_feature_flags backend.tests_render_config.RenderEnvironmentTests transactions.tests_payment_settlement meter.tests_allocation_delivery loan.tests_financial_correctness
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --sandbox-profile meter.tests_sandbox_enrollment loan.tests_sandbox meter.tests_enrollment_review accounts.tests_account_pages backend.tests_alwaysdata.AlwaysdataProfileTests backend.tests_alwaysdata.AlwaysdataAuthenticationFlowTests
```

Sandbox-hosting final enrollment run: **82 tests, OK**, 39.605 seconds.
Includes auth/account-page CSRF,
scheduled email policy, staff ownership review, actual test-loan API, simulator
containment, HTTP transaction separation and source/settlement concurrency.
Combined final enrollment run: **223 tests, OK (skipped=4, expected failures=1)**,
148.319 seconds. The four hosting-profile-only skips are exercised in the separate
sandbox-profile run. The expected failure is the existing completed-core-loan
overdue calculation, not a newly approved sandbox loan.

Concurrency evidence uses separate PostgreSQL connections/threads and barriers:
same request creates one loan/allocation; distinct applications permit one active
approval; duplicate settlement applies once; distinct already-funded repayments
preserve received/applied/excess; overlapping workers collect once. Mock initiate
asserts database connection is outside an atomic HTTP transaction.

Fifteen new enrollment tests cover leading zeros, string-only validation, same-owner
retries/legacy aliases, simultaneous same/distinct owners, generic foreign denial,
physical/core/unowned/deleted/legacy-number collisions, preserved pending transition,
prior rejection, suspended/unverified/staff denial, ownership change/inactive
authorization, no fabricated device evidence and completed loan/purchase/repayment
without staff approval/inventory/simulator. No wallet signal, ownership approval
audit, legacy balance conversion or device command is produced by enrollment.

Further cases cover explicit terms/expiry, low-score actual rejection, unverified
and wrong-owner/meter access, pending/failed purchases, wrong evidence,
same/cross-purpose transaction replay, unknown collection acknowledgement,
expired worker lease/restart/status recovery, EUR conservation and exact purchase
residual, frozen quote after configuration changes, purchase bonus cap/dedupe,
unchanged legacy UnitBalance, old receipt currency isolation, repayment after
meter reassignment and completed sandbox debt staying zero after time advances.

Frontend commands:

```bash
cd mobile
npm run typecheck
node --test --test-isolation=none --test-reporter=spec tests/*.test.mjs
VITE_API_BASE_URL=https://shanonsimon.alwaysdata.net/api/v1 VITE_ACCOUNT_COMPLETION=browser npm run android:sync:debug
cd ../frontend
npx tsc --noEmit
npx eslint src/lib/meter-enrollment.ts src/components/sandbox-web.tsx src/components/sandbox-consumer.tsx 'src/app/(dashboard)/dashboard/request-loan/register-meter.tsx' 'src/app/(dashboard)/dashboard/request-loan/register-meter/action.ts'
timeout 180 npm run build
```

Mobile strict typecheck, **38 focused tests**, Vite debug build and Capacitor sync
passed. Existing authentication/refresh/logout/owner isolation, feature and
recovery checks retained; new tests cover sandbox currency/capability rejection,
explicit inventory, amount/phone validation, stable deduplicated receipts and
account-bound handles cleared by logout. Web strict typecheck and targeted ESLint
passed without errors/warnings or suppression.

The preceding Next.js production build **timed out (exit124)** after180s while optimizing,
without a completed build or a reported compile error. Earlier font-download
limitations remain documented in the project; this timeout did not provide a
specific font error and must not be presented as proof of its cause. The mobile
APK build is independent. Baseline warnings include outdated browser-mapping
data, middleware naming, Node module-type reparsing, Gradle flatDir/SDK XML version.
Dependencies were not upgraded to silence warnings. Browser UI script was syntax
checked; the updated immediate enrollment/auto-selection browser scenario was
also syntax checked, not executed. Chromium/Playwright UI and physical-phone
runtime checks remain outstanding. This enrollment revision reran strict web
typecheck/targeted lint; it does not claim a new completed Next.js production build.

Intermediate verification defects were fixed: the hosted test asserted exact old
database options without the new bounded timeout suffix; the ordinary meter
response initially included an extra false inventory key, breaking its existing
shape assertion. A strengthened wrong-owner test also exposed DRF marking the TestCase outer transaction for rollback after an expected API404. The response now has its own savepoint, the service assertion expects specifically NotFound, and no unauthorized intent is created. This was a test-isolation defect, not a production financial error. The refresh guard also prevents an old response from clearing the protection for a newer read. These fixes were not suppressed.
Caught legacy MeterBalance duplicate-key signal logs are pre-existing and remain
visible. The existing core completed-loan overdue expected failure remains;
new sandbox loans use frozen debt/closure and do not have that defect.

## APK verification

Absolute artifact:
`/home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk`

Size **4,465,028 bytes**. SHA-256:

```text
940122723b823537be588932043a07ebd3cfde710ebd9753f827b8a743a403cb
```

ID `org.gpawa.consumer.prototype`, versionName1.0 / versionCode1,
minimumSDK24 (Android7), target/compileSDK36. Embedded API verified by inspecting
APK JavaScript: `https://shanonsimon.alwaysdata.net/api/v1`, no old LAN addresses
or duplicate `/api/v1/api/v1`. Debug originhttp://localhost confirmed from packaged
Capacitor configuration; release origin/HTTPS policy preserved. Actual application
button, sandbox banner, new enrollment endpoint and SELF_DECLARED ownership notice
found in packaged assets.

Final offline wrapper Gradle8.14.3 / Java21 / installed Linux SDK build succeeded
in **1 minute 22 seconds**,
153 tasks (27 executed), using the original ignored `.android-signing/debug.keystore`.
The earlier resource-heavy build was stopped and rerun with max-workers2,
`-Dorg.gradle.jvmargs=-Xmx768m -XX:ActiveProcessorCount=2`, without changing project
Gradle settings. `apksigner verify --verbose --print-certs` passed APK v2 signing.
Signer SHA-256 matches the previous testing identity:

```text
e9fb53040e78b6a525b67462cc5cc72a656de66ebe6c55061714e785eae86b4c
```

Build command, including worker/heap options, is in `mobile/SANDBOX.md`.
This revision initially hit the execution sandbox's local network restriction
(Gradle could not determine a wildcard IP); rerunning the same offline command
with approved unrestricted local networking succeeded. No signing key was created,
printed or committed.

From WSL:

```bash
/home/shanon/Android/Sdk/platform-tools/adb install -r /home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk
# Or copy for manual Android installation; replace <WindowsUser>:
cp mobile/android/app/build/outputs/apk/debug/app-debug.apk '/mnt/c/Users/<WindowsUser>/Downloads/gPawa-sandbox-debug.apk'
```

These installation commands were **not executed**. Update assumes the installed
certificate matches; do not uninstall as the default workaround. APK is testing
debug output, not a production signed release.

## Operator actions and external evidence

Follow `CONSUMER_SANDBOX.md`: private sandbox keys, reviewed target/backup/migration
plan, opt-in WSGI switch, immediate consumer self-enrollment and finite payment
schedule alongside unchanged email job. No staff approval or pre-created inventory
is a new sandbox prerequisite. The updated allowlist contains 78 files.
Actual MTN evidence/schema, alwaysdata network/quota/job behavior, phone
interaction/connectivity/recovery and web production build remain unverified.
Core pending payments/old token obligations are preserved; the sandbox job cannot
settle UGX/real-provider records. They need separate approved core reconciliation,
not cancellation, currency conversion or replay here.

A process diagnostic inadvertently included a local VS Code connection token in
tool output. Do not share that output. The operator should restart the WSL VS Code
server to replace that local session token. No credential rotation was performed;
hosted SMTP/provider secrets were not displayed.
