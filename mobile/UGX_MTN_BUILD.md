# UGX / MTN testing release —21 November2026

Implemented and tested locally. **Not deployed; no real MTN, phone or physical-board
test performed.** The approved UGX-MTN-TEST-AUTH-v1 policy is implemented, replacing
the earlier pending-decision report. Read the [coordinated Django/Vercel/phone
rollout](../backend/docs/UGX_MTN_TEST_AUTHORIZATION.md) before installation/testing.

## APK

- Absolute path: `/home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk`
- Size: **4,635,116 bytes**.
- SHA256: `aad15235b24653e22df3e463f82db26d1f33363b8549c3d4e59cbe87c576cba7`.
- Application ID: `org.gpawa.consumer.prototype`; version1.0/code1.
- Minimum Android24 (Android7); target36.
- Embedded API: `https://shanonsimon.alwaysdata.net/api/v1`; verified against the signed APK's JavaScript assets.
- Debug WebView origin: `http://localhost`. Release configuration retains HTTPS.
- Signing certificate SHA256: `e9fb53040e78b6a525b67462cc5cc72a656de66ebe6c55061714e785eae86b4c`.
  Matches the earlier local testing APK certificate read before replacement; the
  existing private debug key was reused. No replacement signing identity created.
- APK JavaScript bytes match current `mobile/dist`; no old LAN URL, duplicate
  /api/v1/api/v1, synthetic browser cookie or fixture API host in the bundle.

```bash
adb install -r "/home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk"
```

From WSL, if copying to Windows first (adjust Windows username if different):

```bash
cp mobile/android/app/build/outputs/apk/debug/app-debug.apk /mnt/c/Users/USER/Downloads/gpawa-ugx-testing.apk
```

Then Windows: `adb install -r C:\Users\USER\Downloads\gpawa-ugx-testing.apk`.
Matching identity permits an update; do not uninstall or erase app/device data.

## What changed

Django remains the sole settlement authority. Existing MTN PaymentIntent,
reconciliation/lease service and EUR provider receipt are reused. New immutable
UGX instructions and noncash effects are linked one-to-one; actual EUR1 test
receipts are not renamed or used as an exchange rate. Purchases use frozen admin
DOMESTIC tariffs and issue one source allocation/token; approved loans issue one
allocation/token without payment; repayments reduce owned matching debt only.

Dashboard, Android Home and ordinary forms now use UGX. Home excludes earlier EUR
activity and provider authorization details, while accurate EUR records/details
remain in Activity/receipts. Current headings follow business currency rather than
provider name. Financial/energy read domains remain stable while new payments are
paused; disabling authorization cannot reopen legacy EUR charging. Missing provider
configuration explains repayment unavailability without claiming UGX cannot repay
UGX. No questionnaire, invented score, currency conversion or accounting migration.

Request Loan is a canonical authenticated Next route; Buy Units and Request Loan
both render the shared controller with explicit selected meter, stored score/limit,
pricing, quote/consent and clear unavailable/error states. The approved policy
uses whole UGX inputs, stored score>=80%, fresh debt/limit checks and existing
rounding/fees/terms. No new tariff/rates or financial formula were invented.

## Validation

- Final combined **180 PostgreSQL tests passed**,127.008s. Dedicated isolated
  role/cluster on127.0.0.1:55445; all external HTTP blocked except explicit mocks.
  Includes actual adapter202→pending→successful handling, failures/mismatches,
  immutable source, repeated/concurrent settlement, cross-intent transaction replay,
  excess/partial/full debt closure, paused recovery, no EUR fallback, explicit
  lending switch, missing tariff/assessment, account isolation, purchase bands,
  token/device diagnostics, duplicate redemption/ACK and lost response/recovery.
- Earlier core run: **93 tests, OK with1 existing expected failure**:
  `test_completed_loan_stays_closed_when_overdue_clock_advances`. Not suppressed or
  declared a valid financial policy. Legacy fixture logs still include caught
  wallet duplicate/missing-tariff warnings; new prototype quotes have no fallback.
- Mobile strict TypeScript + **14 test files passed**; web strict TypeScript +
  **13 test files passed**. Same shared components/capability fixtures tested for
  both surfaces, including UGX lending while legacy EUR lending=false, current
  UGX Home with earlier EUR history, pending recovery and visible denial reasons.
- Focused ESLint: **9 changed modules,0 errors/0 warnings**.
- Next production webpack build passed, strict types and49 pages; actual protected
  routes exercised through the production server, not an isolated story/preview page.
  Existing middleware-deprecation/browser-mapping-age warnings remain unchanged.
- **9 browser acceptance scenarios passed**, including both forms, tariff/terms,
  consent,85%/62%/pending assessment, HTTP503, purchase independence from assessment,
  dashboard/Home currency, partial repayment, duplicate purchase click, recovery
  after reload, one synthetic token and phone widths. **Zero browser runtime errors**.
  [Screenshots/results](../docs/review/ugx-workflow/README.md) are explicitly local /
  synthetic, not live Vercel/MTN/device evidence. Token fields masked.
- Vite bundle, Capacitor sync and Gradle assembleDebug passed. Final Home rebuild:
  **BUILD SUCCESSFUL in1m9s**,153 tasks. APK signature and certificate continuity
  verified; current private signing key preserved.
- Migration model-state check: no pending generated changes. New additive
  transactions0013 only; its PostgreSQL constraints/triggers ran in isolated tests.
- `git diff --check` passed. No source commit/push performed.

Temporary test tooling was cleared during a session restart. A restoration run
failed because pinned cryptography was missing (85 environment import errors).
The existing pins were restored only under /tmp, then the full180-test suite
passed. No virtualenv upgrade, skipped financial checks or assertion suppression.
Earlier intermediate fixtures were corrected to expect provider initiation to
remain pending and the stricter explicit403 when authorization is disabled.

## Reproducible commands

From repository root (the isolated cluster must already be running):

```bash
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --sandbox-profile --slow-test-cleanup transactions.tests_ugx_authorization loan.tests_ugx_lab loan.tests_mtn_transition loan.tests_sandbox loan.tests_demo_assessment transactions.tests_demo_payments meter.tests_mtn_device meter.tests_credit_only meter.tests_device_diagnostics backend.tests_combined_rollout backend.tests_feature_flags accounts.tests_account_pages loan.tests_consumer_summary
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --slow-test-cleanup transactions.tests_payment_settlement meter.tests_allocation_delivery loan.tests_financial_correctness backend.tests_feature_flags accounts.tests_authentication
npm --prefix mobile run typecheck
npm --prefix mobile test
(cd frontend && npx tsc --noEmit && node --test tests/*.test.mjs)
(cd frontend && npx eslint src/lib/sandbox.ts src/lib/finance-setup.ts src/lib/sandbox-presentation.ts src/lib/consumer-parity.ts src/components/sandbox-consumer.tsx src/components/sandbox-mobile-view.tsx src/components/consumer/workspace.tsx src/components/energy-token-card.tsx 'src/app/(dashboard)/dashboard/request-loan/page.tsx')
(cd frontend && npm run build -- --webpack)
(cd mobile && VITE_API_BASE_URL=https://shanonsimon.alwaysdata.net/api/v1 VITE_ACCOUNT_COMPLETION=browser npm run android:sync:debug)
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 ANDROID_HOME=/home/shanon/Android/Sdk ANDROID_USER_HOME="$PWD/mobile/.android-signing" GRADLE_USER_HOME="$PWD/mobile/.gradle-user" PATH="/usr/lib/jvm/java-21-openjdk-amd64/bin:$PATH" mobile/android/gradlew --offline --no-daemon --max-workers=2 '-Dorg.gradle.jvmargs=-Xmx768m -XX:ActiveProcessorCount=2' -p mobile/android assembleDebug -Pandroid.injected.signing.store.file="$PWD/mobile/.android-signing/debug.keystore" -Pandroid.injected.signing.store.password=android -Pandroid.injected.signing.key.alias=androiddebugkey -Pandroid.injected.signing.key.password=android
/home/shanon/Android/Sdk/build-tools/35.0.0/apksigner verify --verbose --print-certs mobile/android/app/build/outputs/apk/debug/app-debug.apk
```

The debug-key passwords above are the existing generic Android debug convention,
not backend/provider credentials. Java21, existing SDK/Gradlewrapper8.14.3 retained.
Browser setup and local-only commands are in the screenshot README. The restored
hosted-test libraries use the existing requirements pins (WhiteNoise6.12.0 and
cryptography50.0.2); no frontend/application dependency upgrade was made.

## Deployment and remaining acceptance

1. Review the262-file backend allowlist and dry-run; private backup; verify exact
   shanonsimon_energy_test target and encrypted DB; review/apply transactions0013
   and any reviewed dependencies; collectstatic. No hosted migration was run here.
2. Privately enable SANDBOX_UGX_AUTHORIZATION_ENABLED=true,
   SANDBOX_UGX_AUTHORIZATION_POLICY=UGX-MTN-TEST-AUTH-v1,
   SANDBOX_NEW_PAYMENTS_ENABLED=true, SANDBOX_UGX_LOANS_ENABLED=true. Keep
   PROTOTYPE_PAYMENT_PROVIDER=MTN_SANDBOX and actual provider currency EUR.
   Preserve credentials/token keys/device binding; verify configured admin tariff.
3. Restart alwaysdata; verify capabilities and existing finite reconciliation job.
   Preserve account-email schedule. No Redis/Celery eager shortcut.
4. Separately deploy this frontend commit through the **existing Vercel project**
   (Root Directory frontend, webpack build, server API_URL HTTPS). An APK rebuild
   cannot update Vercel. Exact operator steps are in the coordinated runbook.
5. Install this APK. Sign in → selected meter → UGX Home/assessment → purchase
   quote/consent → pending/restart recovery → verified provider settlement → one
   token → matching keypad → durable saved credit. No relay or mains load.
6. Loan quote/consent → automatic decision/token without payment → partial4000
   repayment against10500 →6500 remaining → full repayment/closure; no repayment
   electricity/token. Compare web and Android and verify original EUR history.

Actual MTN sandbox, phone, live authenticated Vercel and physical board validation
remain outstanding. Firmware/provisioning/NVS and the relay prohibition are
unchanged; the existing SANDBOX/GPAWA_PZEM_V2 integerWh interface is reused. The
older token-rejection root cause is not claimed confirmed by mock tests; preserve
request-ID diagnostics for one authorized attempt if rejection persists.
