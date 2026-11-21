# Checkout recovery testing build — 22 November 2026

Local implementation only. No hosted migration, deployment, payment initiation,
phone/board test, firmware flash, credential rotation, commit or push performed.
Read [the ordered backend/Vercel rollout](../backend/docs/CHECKOUT_RECOVERY.md).

## Installable artifact

- APK: `/home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk`
- Size: **4,635,116 bytes**.
- SHA-256: `e42f943cbcdccc8c75fc032f44e1745f92cda7d600a2267fc133b5e3f155664f`.
- Certificate SHA-256: `e9fb53040e78b6a525b67462cc5cc72a656de66ebe6c55061714e785eae86b4c`.
- Existing certificate continuity verified against the previous testing APK
  (`aad15235b24653e22df3e463f82db26d1f33363b8549c3d4e59cbe87c576cba7`). No new key created.
- Application ID `org.gpawa.consumer.prototype`, version1.0/code1, minimum SDK24
  (Android7), target SDK36.
- Embedded API `https://shanonsimon.alwaysdata.net/api/v1`. Verified APK JavaScript matches current `mobile/dist`;
  no old LAN URL, duplicate /api/v1 or browser fixture host/cookie in the APK.
- Debug origin `http://localhost`; release HTTPS configuration is preserved.

```bash
adb install -r "/home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk"
# From repository root, optional Windows copy (adjust Windows username):
cp mobile/android/app/build/outputs/apk/debug/app-debug.apk /mnt/c/Users/USER/Downloads/gpawa-checkout-testing.apk
```

Windows: `adb install -r C:\Users\USER\Downloads\gpawa-checkout-testing.apk`.
Do not uninstall or erase app data to hide a pending request. Existing non-secret
retry handles recover through authenticated Django records. Physical-board NVS,
credentials and tokens were not modified.

## Behavior

Both clients retain visible Buy Units/Request Loan forms beside operation-specific
status panels. Expiry uses original persisted server time +300s, not a client timer.
Submitted/uncertain provider requests remain under reconciliation after checkout
expiry. Only provably unsubmitted initiation closes locally. Explicit sandbox-only
retry requires consent and keeps frozen UGX-MTN-TEST-AUTH-v1 terms, new EUR1 provider
reference and a root operation link. The first verified success fulfills once;
additional authorizations remain review evidence without energy, tokens or debt
reduction. Repayment never creates energy. Unrelated pending purchases and payment
read failures do not gate loan quotes; server score/debt/limit checks still apply.

Independent reads/20-second deadlines end error loading states. Background status
polling has a separate in-flight guard so a visible form click is not silently
consumed by a poll. Current/history receipts show additional authorization review
explicitly. No EUR relabelling, conversion, new tariff or lending policy.

One additive migration: transactions0014 creates SandboxCheckout metadata and
constraints only; no historical update/backfill. The curated268-file backend list
preserves latest token diagnostics and earlier required migrations. Seven deferred
features, account verification/email schedule, authentication, device binding and
relay prohibition remain intact. Exact hosted blocking reference is unconfirmed:
read-only SSH inspection was denied. Use the preview report before local expiry.

## Reproducible checks/builds

```bash
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --sandbox-profile --slow-test-cleanup transactions.tests_checkouts transactions.tests_ugx_authorization loan.tests_ugx_lab loan.tests_mtn_transition loan.tests_sandbox loan.tests_demo_assessment transactions.tests_demo_payments meter.tests_mtn_device meter.tests_credit_only meter.tests_device_diagnostics backend.tests_combined_rollout backend.tests_feature_flags accounts.tests_account_pages loan.tests_consumer_summary
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --slow-test-cleanup transactions.tests_payment_settlement meter.tests_allocation_delivery loan.tests_financial_correctness backend.tests_feature_flags accounts.tests_authentication
npm --prefix mobile run typecheck
npm --prefix mobile test
(cd frontend && npx tsc --noEmit && node --test tests/*.test.mjs)
(cd frontend && npm run build -- --webpack)
(cd mobile && VITE_API_BASE_URL=https://shanonsimon.alwaysdata.net/api/v1 VITE_ACCOUNT_COMPLETION=browser npm run android:sync:debug)
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 ANDROID_HOME=/home/shanon/Android/Sdk ANDROID_USER_HOME="$PWD/mobile/.android-signing" GRADLE_USER_HOME="$PWD/mobile/.gradle-user" PATH="/usr/lib/jvm/java-21-openjdk-amd64/bin:$PATH" mobile/android/gradlew --offline --no-daemon --max-workers=2 '-Dorg.gradle.jvmargs=-Xmx768m -XX:ActiveProcessorCount=2' -p mobile/android assembleDebug -Pandroid.injected.signing.store.file="$PWD/mobile/.android-signing/debug.keystore" -Pandroid.injected.signing.store.password=android -Pandroid.injected.signing.key.alias=androiddebugkey -Pandroid.injected.signing.key.password=android
/home/shanon/Android/Sdk/build-tools/35.0.0/apksigner verify --verbose --print-certs mobile/android/app/build/outputs/apk/debug/app-debug.apk
```

Debug passwords are the existing Android debug convention, not backend credentials.
Local test cluster is isolated `/tmp/gpawa-alwaysdata/pg`, port55445, test role only;
external HTTP is blocked except explicit mocks. Temporary pinned hosting-test
libraries/Playwright are under /tmp; no application dependency upgrade was made.
See [browser evidence](../docs/review/payment-checkout/README.md) for production
Next route commands/screenshots and local/mock scope. Final results are recorded
below after verification completes.

## Phone acceptance — outstanding

Login → select owned meter → check stored assessment → purchase quote/consent →
observe pending and five-minute server expiry → explicitly retry with notice →
restart/recover → confirmed single allocation/token → independent loan quote/
application → partial/full repayment and closed debt → receipts/history → logout.
Compare web/Android for the same owner and selected meter. No countdown is success.
Do not send physical commands or energize a relay during these checks.

## Final validation

- Combined isolated PostgreSQL suite: **198 tests passed in356.971s**, including18 checkout cases. Final current-code legacy/pause/checkout guard suite: **30 tests passed in225.513s**. The latter explicitly verifies missing pre-I/O proof before/after expiry and while new payments are paused.
- Core regression: **93 cases passed in198.103s with1 existing expected failure**, `test_completed_loan_stays_closed_when_overdue_clock_advances`. No financial policy was changed to hide it. Legacy fixture logs include caught wallet-duplicate/missing-tariff warnings; no new prototype tariff fallback.
- Final mobile **90 tests across15 files**, web **41 tests across14 files**; strict mobile/web type checks and focused lint of7 modules passed. No blanket any casts, type suppression or dependency upgrade.
- Final production Next build passed49 pages; existing middleware-deprecation/browser-mapping warnings remain. Vite/Capacitor and Gradle assembleDebug passed (**2m47s**,153 tasks). Existing flatDir/SDK XML warnings remain tooling notices. Signature, existing certificate, package/version/API and exact bundled JS verified.
- Final **five checkout + nine UGX browser scenarios passed**, zero runtime errors, actual protected Next routes with synthetic HTTPS APIs. Includes delayed polling, visible pending/expired forms, independent lending, explicit consent/double-click/reload recovery, late successes/one synthetic token, HTTP503 and a stalled-summary timeout. Phone-width screenshots are browser evidence, not an installed-phone test.
- Model/migration-state check: no changes detected. `git diff --check` passed. One additive migration0014; no operational migration.

An intermediate run was invalidated by my mistakenly overlapping two runners on
the same disposable test DB (missing-table errors). Both suites were rerun strictly
sequentially and passed; those errors are not claimed to be pre-existing code
failures. Memory/swap pressure also slowed local builds; checks stayed enabled.
A first browser run exposed a click consumed by background polling; its separate
guard is now covered with deliberately delayed status responses.

Historical NEW records without PRE_IO_CHECKOUT-v1 stay uncertain; no automatic
new charge or local cancellation is inferred. They retain original-provider
reconciliation, even while new payments are paused. If an original succeeds just
before retry arrives, a durable never-submitted closed attempt keeps the retry
request ID recoverable. Only authoritative local closure/terminal evidence clears
that primary handle; a missing row stays unknown. History is not erased.

Hosted reference diagnosis remains unconfirmed because SSH authentication was
denied. Use the operator's preview report. No actual MTN, phone or board test,
credential rotation, firmware flash, hosted migration, deployment or commit/push.
