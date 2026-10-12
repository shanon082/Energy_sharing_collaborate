# Consumer expansion build and verification — 12 October 2026

This is earlier build evidence. The updated signed sandbox APK now includes
immediate SELF_DECLARED enrollment and automatically selects the returned meter.
No staff review/inventory/simulator is required for new prototype enrollment.
Use [SANDBOX.md](SANDBOX.md) and the linked current validation/runbook for the
latest artifact and deployment steps; historical evidence below is preserved.

Backend authority, scope, policies and deployment gates:
[`../backend/docs/CONSUMER_EXPANSION.md`](../backend/docs/CONSUMER_EXPANSION.md).

Deployment preparation follow-up: staff can use a narrowly authorized Django
HTTPS review page without hosted Next.js. See
[`../backend/docs/CONSUMER_EXPANSION_DEPLOYMENT.md`](../backend/docs/CONSUMER_EXPANSION_DEPLOYMENT.md).
The request screen now distinguishes rejection and unavailable former assignment,
and displays only the safe explanation. **These label changes are not yet in the
APK described below: another APK rebuild is needed.** No phone testing or hosted
deployment was performed by this follow-up.

Follow-up verification: mobile strict type check and **31 focused tests pass**;
backend combined suite **177 tests, 2 hosted-only skips, 1 known expected failure**;
actual hosted-profile configuration/auth/review suite **36 tests pass**, including
both skipped cases. Commands and limits are in the deployment runbook. Earlier
APK/build metadata below remains the previous artifact, not a rebuilt binary.

## Available implementation

- Existing registration/login, email verification/recovery through Django HTTPS
  account pages, refresh/logout and profile/security are preserved.
- Ugandan phone validation shared with web: local 10 digits starting 0,
  12 digits starting 256 or equivalent +256; canonical +256. Invalid characters
  and lengths are rejected; no ownership claim and no historical rewrite.
- First sign-in fetches onboarding; no assigned meter offers a pending request.
  Staff verification/assignment is still required. One initially assigned meter
  can be selected automatically; multiple meters require explicit selection.
  Reassignment/replacement invalidates selection and is never silently redirected.
- Eligibility shows the authoritative lending score, contributing factors,
  timestamps and existing starter-policy floor. Incomplete new users show no score.
- Provisional purchase/loan quotes reuse Django calculations; may be unavailable
  when no approved current tariff or sufficient profile evidence exists.
- Saved payment request IDs recover owner/purpose/meter or loan-bound stored
  status, including old pending requests beyond the first history page.
  Recovery and app resume do not replay a financial POST or contact a provider.
- Receipts distinguish verified payment, source allocation and acknowledged
  application. Residual and excess amounts remain recorded for reconciliation.
- Meter contact/staleness, exact simulator credit/usage and reported relay are
  distinct from cloud entitlement. Resets/unknown counter baselines withhold
  remaining credit. Physical reported credit remains unavailable.
- Serial foreground reads poll at 15 seconds, back off to 120 seconds, pause on
  page/native background and resume. Balances/records remain memory-only and
  show fetch time/staleness; persistent request IDs contain no financial authority.

These are local implementations. New onboarding/recovery/scoring metadata
requires the reviewed backend upload and migrations. Existing authorized meter
reads fall back to the older meter-list endpoint on an onboarding-route 404;
new mutations never fall back to unsafe legacy registration/payment routes.
Do not interpret APK assembly as proof the hosted backend has these changes.

Loan submission is deliberately contained, not completed. Existing mobile
purchase/repayment initiation stays disabled by server settings and alwaysdata
middleware; quote/review/receipt screens do not enable collection. New purchase
scoring remains disabled with no numeric policy defaults. Seven deferred
features remain disabled. There is no new physical device control.

## Tests and builds

Isolated local PostgreSQL 18, port 55445, role `gpawa_alwaysdata_test`; dedicated
Django test database from the guarded runner. External HTTP forbidden; email,
providers and devices mocked. No hosted/operational database was accessed.

```bash
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py accounts.tests_consumer_expansion backend.tests_alwaysdata.PrivateEnvironmentTests backend.tests_alwaysdata.AccountMailOutboxTests accounts.tests_authentication accounts.tests_mobile_api accounts.tests_mobile_cors accounts.tests_mobile_profile_meters accounts.tests_mobile_activity backend.tests_feature_flags backend.tests_render_config.RenderEnvironmentTests transactions.tests_payment_settlement meter.tests_allocation_delivery loan.tests_financial_correctness
```

**161 tests, OK (1 expected failure)**, 115.552 seconds. Includes 19 new
consumer tests, separate-connection concurrent pending meter requests, unchanged
settlement/provider replay/concurrent repayment/allocation/simulator regressions
and `makemigrations --check --dry-run` for changed models. The known expected
failure is `test_completed_loan_stays_closed_when_overdue_clock_advances`.
Pre-existing caught `wallet_meterbalance_meter_number_key` fixture/signal errors
are still logged during synthetic test resets; not new failing assertions.

```bash
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --profile accounts.tests_account_pages backend.tests_alwaysdata.AlwaysdataProfileTests backend.tests_alwaysdata.AlwaysdataAuthenticationFlowTests
```

**20 tests pass**, 11.595 seconds: account CSRF, auth and hosted configuration.
Local Python is 3.14/Django 5.2; hosted Python 3.12.15 runtime not exercised here.

From mobile: `npm run typecheck` and
`node --test --test-isolation=none --test-reporter=spec tests/*.test.mjs`:
**30 tests pass** (auth, account isolation, request recovery guards, exact
telemetry, flags, phone parsing, serial polling/backoff/background pause).
Node warns about importing the web package's pure TS ESM helper; no package
module-type changes or type-check suppressions were introduced.

From frontend: `npx tsc --noEmit`, focused ESLint for the phone helper and
consumer meter request component/action, and `node --test tests/features.test.mjs`
pass. Next.js production builds timed out at 120 seconds, then 180 seconds with
network access, during optimized build; this run did not produce a diagnostic
proving fonts were the cause. The earlier font-download baseline remains an
independent unresolved build limitation. No new TypeScript error or build bypass.

Playwright/Chromium is not available; the intercepted browser fixture was
updated and syntax-checked, but not runtime-executed. Physical phone testing of
this artifact is outstanding. APK assembly is not browser/device test evidence.

## APK and exact build

```bash
cd /home/shanon/projects/next_projects/Energy-sharing-project/mobile
VITE_API_BASE_URL=https://shanonsimon.alwaysdata.net/api/v1 VITE_ACCOUNT_COMPLETION=browser npm run android:sync:debug
cd android
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export ANDROID_HOME=/home/shanon/Android/Sdk
export ANDROID_USER_HOME=/home/shanon/projects/next_projects/Energy-sharing-project/mobile/.android-signing
export GRADLE_USER_HOME=/home/shanon/projects/next_projects/Energy-sharing-project/mobile/.gradle-user
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"
./gradlew --offline --no-daemon assembleDebug -Pandroid.injected.signing.store.file=/home/shanon/projects/next_projects/Energy-sharing-project/mobile/.android-signing/debug.keystore -Pandroid.injected.signing.store.password=android -Pandroid.injected.signing.key.alias=androiddebugkey -Pandroid.injected.signing.key.password=android
```

Strict TS/debug Vite bundle/Capacitor sync pass. Gradle wrapper builds successfully
in 1m 53s, 153 tasks (27 executed). Private ignored existing debug key is reused;
these are Android's standard debug signing parameters, not production signing.

- Absolute APK: `/home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk`
- Size: **4,344,725 bytes**.
- SHA-256: `43dd9e8f5d078f96afafdc4c84c3de433f251453f88ad3c77f3d75fc603c3b1e`.
- ID `org.gpawa.consumer.prototype`, version 1.0/code 1, minimum SDK 24
  (Android 7), target/compile 36.
- Embedded API `https://shanonsimon.alwaysdata.net/api/v1`; no duplicated prefix
  or former LAN addresses. Packaged main JS matches the final Vite artifact.
- Debug WebView origin `http://localhost`; release config retains
  `https://localhost` and requires an HTTPS API. Debug HTTP allowance unchanged.
- `apksigner verify --verbose --print-certs` passes v2; signing certificate
  SHA-256 `e9fb53040e78b6a525b67462cc5cc72a656de66ebe6c55061714e785eae86b4c`
  matches the prior update identity. It can update that installed build without
  uninstalling; an unrelated key/package cannot be overwritten.

Install with USB debugging, from WSL if adb sees the phone:

```bash
/home/shanon/Android/Sdk/platform-tools/adb install -r /home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk
```

For Windows adb, obtain the Windows-visible path with:
`wslpath -w /home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk`.
Open that folder in Windows Explorer or copy to your Downloads, then use
`adb.exe install -r "<Windows-path-to-app-debug.apk>"`.

## Phone checklist after reviewed backend deployment

1. Update existing APK; open debug connection tools and verify actual origin
   and HTTPS API. Never share passwords/tokens/link query strings in diagnostics.
2. Register using each supported format and invalid inputs. Verify only explicit
   browser POST consumes the emailed token; return to Android and sign in.
3. New account: no fabricated score/usage. Submit a meter request twice and
   retry after interrupted connection; see pending staff verification, no access.
4. Authorized staff verifies evidence on the new Django-hosted review page and assigns clean, pre-provisioned synthetic inventory (general provisioning remains blocked). Refresh assignment; verify initial
   single-meter display and explicit multi-meter selection. Another consumer
   must not see its history; changing an assignment clears stale selection.
5. Refresh eligibility repeatedly: same evidence score; timestamps and starter
   floor are clear. Quote is nonbinding; no submit/auto-disbursement promise.
6. Foreground/background, Android Back, network loss and recovery: stale fetch
   times, no overlap/spin and no queued financial POST. Offline logout clears
   local session; reconnect revocation behavior remains documented.
7. Check exact simulator Wh/contact/relay labels; reset/unknown baseline gives
   unavailable remaining credit, not a manufactured zero or physical-live claim.
8. Confirm seven optional features and financial/device mutations remain
   inaccessible. Test transaction recovery/receipts with isolated mocks only,
   never real provider collection on the testing host.
