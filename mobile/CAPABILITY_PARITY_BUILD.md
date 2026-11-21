# Capability parity testing build — 21 November 2026

Local debug build, not a production release. No phone, provider or physical-board
test was performed; no hosted deployment or migration was run. The complete UGX
purchase/repayment journey is **not implemented** until its test-authorization
mapping is approved. See [backend audit, proposed receipts and exact rollout](../backend/docs/UGX_CAPABILITY_PARITY_ROLLOUT.md).

## Artifact and identity

- APK: `/home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk`
- Size: **4,635,116 bytes**.
- SHA-256: `1d65cc4472799c38f5ee4d1d73ee873e2069358cc7c5c8bd424f4523bb80ad07`.
- Application ID: `org.gpawa.consumer.prototype`, versionName1.0/versionCode1.
- Android minimum24 (Android7), target36.
- API embedded and verified in signed ZIP assets: `https://shanonsimon.alwaysdata.net/api/v1`.
- Debug WebView origin: `http://localhost`; release remains HTTPS.
- Certificate SHA256: `e9fb53040e78b6a525b67462cc5cc72a656de66ebe6c55061714e785eae86b4c`.
- Previous testing APK SHA256: `f92602af12b8b9e89892f288f7bb619c768d0334b67be935bb83107e48d220dc`.
  Its certificate was read **before** replacement and matches this APK exactly.
  Existing private debug key was used; no replacement key or uninstall required.
- APK JavaScript bytes match current `mobile/dist` assets; no previous LAN API
  address or duplicated `/api/v1/api/v1`. Welcome/login/signup UI unchanged.

## Local validation

- Mobile `npm run typecheck` and `npm test`: pass, **14 test files**.
- Web `npx tsc --noEmit`, `node --test tests/*.test.mjs`: pass, **13 test files**.
- Focused ESLint on eight changed shared/component modules: **0 errors, 0 warnings**.
- Backend combined sandbox run: **161 tests passed** with isolated PostgreSQL,
  provider mocks and unmocked external HTTP prohibited. Includes UGX contract while
  legacy EUR loans=false, stored-score/debt/limit gates, MTN202/PENDING/SUCCESSFUL,
  HTTP200/FAILED, timeout/recovery, duplicate/concurrent settlement, currency mismatch,
  same-currency partial/full repayment, no repayment token, token/device diagnostics,
  lost ACK/reboot recovery, flags and hosted account CSRF security.
- Core regression run: **93 tests, OK with 1 existing expected failure**
  `test_completed_loan_stays_closed_when_overdue_clock_advances`.
  No policies were approved by encoding unresolved behavior in a test. Core fixture
  execution still logs caught legacy duplicate `wallet_meterbalance` and missing-
  tariff fallback warnings; these are not failures introduced by this change.
- UGX partial/full accounting uses isolated LOCAL_DEMO test fixtures **only**.
  It is not a working UGX MTN repayment or permission to switch the hosted provider.
- Vite Android debug bundle / Capacitor sync: pass.
- Gradle offline `assembleDebug`: **BUILD SUCCESSFUL**,153 tasks;2m42s.
  First sandbox attempt failed on its local lock socket; approved retry succeeded.
- APK `apksigner verify --verbose --print-certs`: pass; signing continuity confirmed.
- Next.js production webpack build passed, strict TypeScript and49 pages, with normal
  server features retained. See final build log/result in the release validation.
- `git diff --check`: pass. Device diagnostic source byte-identical to HEAD.

### Exact commands

From repository root:

```bash
npm --prefix mobile run typecheck
npm --prefix mobile test
(cd frontend && npx tsc --noEmit && node --test tests/*.test.mjs)
(cd frontend && npx eslint src/lib/finance-setup.ts src/lib/sandbox.ts src/lib/quote-availability.ts src/components/consumer/read.ts src/components/consumer/workspace.tsx src/components/sandbox-consumer.tsx src/components/sandbox-mobile-view.tsx src/components/sandbox-web.tsx)
(cd frontend && npm run build -- --webpack)
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --sandbox-profile --slow-test-cleanup loan.tests_ugx_lab loan.tests_mtn_transition loan.tests_sandbox loan.tests_demo_assessment transactions.tests_demo_payments meter.tests_mtn_device meter.tests_credit_only meter.tests_device_diagnostics backend.tests_combined_rollout backend.tests_feature_flags accounts.tests_account_pages
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --slow-test-cleanup transactions.tests_payment_settlement meter.tests_allocation_delivery loan.tests_financial_correctness backend.tests_feature_flags accounts.tests_authentication
(cd mobile && VITE_API_BASE_URL=https://shanonsimon.alwaysdata.net/api/v1 VITE_ACCOUNT_COMPLETION=browser npm run android:sync:debug)
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 ANDROID_HOME=/home/shanon/Android/Sdk ANDROID_USER_HOME="$PWD/mobile/.android-signing" GRADLE_USER_HOME="$PWD/mobile/.gradle-user" PATH="/usr/lib/jvm/java-21-openjdk-amd64/bin:$PATH" mobile/android/gradlew --offline --no-daemon --max-workers=2 '-Dorg.gradle.jvmargs=-Xmx768m -XX:ActiveProcessorCount=2' -p mobile/android assembleDebug -Pandroid.injected.signing.store.file="$PWD/mobile/.android-signing/debug.keystore" -Pandroid.injected.signing.store.password=android -Pandroid.injected.signing.key.alias=androiddebugkey -Pandroid.injected.signing.key.password=android
/home/shanon/Android/Sdk/build-tools/35.0.0/apksigner verify --verbose --print-certs mobile/android/app/build/outputs/apk/debug/app-debug.apk
sha256sum mobile/android/app/build/outputs/apk/debug/app-debug.apk
```

Generic Android debug passwords above are the existing local debug-key convention,
not service secrets or a production signing identity. Java21, existing Linux SDK,
Gradlewrapper8.14.3 and existing project dependencies retained. No global Gradle.

## Installation and ordered phone/web checks (outstanding)

After backend plan/configuration review and authorized rollout:

```bash
adb install -r "/home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk"
```

For Windows, in WSL (replace the destination Windows username if different):

```bash
cp mobile/android/app/build/outputs/apk/debug/app-debug.apk /mnt/c/Users/USER/Downloads/gpawa-capability-parity-debug.apk
```

Then `adb install -r C:\Users\USER\Downloads\gpawa-capability-parity-debug.apk`
or open the APK on the phone and allow installation from your chosen source.
Do not uninstall: matching signature permits an update preserving app data.

1. Sign in; compare HTTPS API and selected meter between web and Android.
2. No meter: Add your unique11-digit meter; preserve leading zeros. Choose meter.
3. UGX capability present with legacy EUR loans=false: ready stored simulated score,
   limit/reasons visible. Pending/missing/low-score/debt cases explain unavailability;
   initialize automatic assessment only through the owner flow, no questionnaire.
4. UGX loan: amount → server quote/admin tariff → terms → consent → submit once.
   Server decision/rejection reason, one allocation/token; no physical-credit claim.
5. Purchases: only currently enabled **EUR TEST** provider path works before mapping
   approval. Missing keys/pause/pricing/recovery shows the actual reason. A pending
   request stays pending after5s and app restart; do not pay again after timeout.
   Do not initiate a provider test until explicitly authorized.
6. Repayment: UGX debt clearly explains no approved EUR authorization mapping.
   Historical eligible EUR debt can accept a partial same-currency test repayment;
   receipts keep EUR and no energy/token is created. Provider testing outstanding.
7. History: old UGX/EUR receipts/balances remain separate and owner-only. Inspect
   payment confirmed, token issued and device credit saved as distinct facts.
8. Refresh/error/offline recovery, Android Back between amount/terms/confirm,
   pending navigation, logout/session expiry; another account must not inherit reads.

All seven deferred features remain disabled. Relay output remains prohibited.
No firmware/key/NVS changes are part of this release. Existing token-rejection
root cause still needs the preserved request-ID diagnostics from an authorized
attempt; mocked redemption tests are not physical validation.
