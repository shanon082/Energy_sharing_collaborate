# Integrated repository validation — 15 October 2026

This section records checks in the actual repository. The original package-only report below is historical.

## Completed checks

- Mobile `npm run typecheck`: passed. `npm test`: all seven test files passed; `node --test --test-isolation=none --test-reporter=spec tests/*.test.mjs`: **50 individual cases passed** on final code.
- Real-App mocked Chromium: **11 redesigned finance scenarios passed**, plus **9 authentication/account scenarios passed**. APIs were intercepted, external requests blocked by the finance harness. No Django records, payment providers or devices were used.
- Finance scenarios cover 320/390/768 px navigation, a 380 px keyboard-sized viewport, no meter/pending assessment, enrollment, profile/logout, approved/rejected loans, partial/full repayment without extra energy, duplicate taps, countdown without settlement, interrupted initiation/restart recovery, stale/expired quotes, server-disabled actions, a capability-network error retaining pending state, separate EUR history and Android Back through review steps.
- Native Back uses a browser-only Capacitor test adapter. Viewport resizing approximates a keyboard; neither proves physical Android keyboard or Back behaviour. Home/Meters/Loans/Buy Units/Account screenshots were inspected locally.
- Next.js `npx tsc --noEmit`: passed; targeted ESLint on `sandbox-consumer.tsx`, `sandbox-mobile-view.tsx`, `sandbox.ts` and `finance-navigation.ts`: passed; `node --test --test-isolation=none tests/features.test.mjs`: **3 passed**.
- `npm run build` and bounded `npm run build -- --webpack` each timed out after **180 seconds** during optimized compilation (exit 124), reproducing the existing production-build stall. No source error or explicit font error was emitted. Full web production build remains unverified; no type-check bypass was added.
- Mobile debug bundle, Capacitor sync and final offline Gradle `assembleDebug`: passed. Gradle final result: **153 tasks, 27 executed, 126 up-to-date**, 1m 27s.
- `git diff --check`: passed. SHA-256 preservation checks confirmed **346 backend/authentication files unchanged** from integration start, including Access.tsx, SessionManager and secure storage. Backend regressions were not rerun in this UI-only integration; their earlier results are not counted as new evidence. The known core completed-loan/overdue expected failure remains unresolved.

## APK and packaged-code verification

- Path: `/home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk`
- Size: **4,476,294 bytes**.
- SHA-256: `9da05eddf3f92c34d4fe41f3f92d16fed19d36b5b5eabcc59d7b30aacdd23a60`.
- Application ID: `org.gpawa.consumer.prototype`; version **1.0 / code 1**; minimum **Android 7.0 / API 24**, target/compile **36**.
- Embedded API: `https://shanonsimon.alwaysdata.net/api/v1` exactly once; no old LAN base or duplicated `/api/v1`.
- `apksigner verify --verbose --print-certs`: passed, v2 signature; original certificate SHA-256 **e9fb53040e78b6a525b67462cc5cc72a656de66ebe6c55061714e785eae86b4c**. No replacement key was created.
- Every packaged web asset equals the final `dist` file. Preview screen/receipt fixtures and browser test adapters are absent. The example meter number is only an empty form input placeholder, not an enrolled meter.
- Debug Capacitor origin remains `http://localhost`; backend API uses HTTPS. Merged debug manifest permits existing debug HTTP and uses `adjustResize`. Release manifest keeps cleartext disabled and release Vite configuration requires HTTPS.

## Reproduce the build

From `mobile/`:

```bash
npm run typecheck
npm test
node --test --test-isolation=none --test-reporter=spec tests/*.test.mjs
VITE_API_BASE_URL=https://shanonsimon.alwaysdata.net/api/v1 VITE_ACCOUNT_COMPLETION=browser npm run android:sync:debug
```

From the repository root (uses the original ignored debug key):

```bash
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 \
ANDROID_HOME=/home/shanon/Android/Sdk \
ANDROID_USER_HOME="$PWD/mobile/.android-signing" \
GRADLE_USER_HOME="$PWD/mobile/.gradle-user" \
PATH="/usr/lib/jvm/java-21-openjdk-amd64/bin:$PATH" \
mobile/android/gradlew --offline --no-daemon --max-workers=2 \
  '-Dorg.gradle.jvmargs=-Xmx768m -XX:ActiveProcessorCount=2' \
  -p mobile/android assembleDebug \
  -Pandroid.injected.signing.store.file="$PWD/mobile/.android-signing/debug.keystore" \
  -Pandroid.injected.signing.store.password=android \
  -Pandroid.injected.signing.key.alias=androiddebugkey \
  -Pandroid.injected.signing.key.password=android
```

Toolchain: Java **21.0.12.1**, Gradle wrapper **8.14.3**, SDK `/home/shanon/Android/Sdk`, Build Tools **35.0.0**, platform **36**. Gradle reported existing flatDir/SDK-XML warnings; assembly succeeded. Standard Android debug passwords above are not release credentials. Keep the key private and do not generate another.

Optional browser checks need a local Vite server with the same debug configuration, plus externally installed Playwright/Chromium. Tooling was placed under `/tmp/gpawa-mobile-ui-check`, without changing project dependencies. Run from `mobile/`:

```bash
PLAYWRIGHT_BROWSERS_PATH=/tmp/gpawa-mobile-ui-check/browsers \
PLAYWRIGHT_MODULE=/tmp/gpawa-mobile-ui-check/node_modules/playwright/index.mjs \
node tests-ui/redesign-finance.mjs
# Repeat the environment prefix for tests-ui/consumer-ui.mjs.
```

## Install and phone checklist

With an authorized device reachable from WSL:

```bash
/home/shanon/Android/Sdk/platform-tools/adb install -r '/home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk'
```

Alternatively copy the APK through Windows Explorer's `\\wsl.localhost\<distribution>\home\shanon\projects\next_projects\Energy-sharing-project\mobile\android\app\build\outputs\apk\debug` folder, then transfer and open it on the phone. Try updating over the installed app; do not uninstall by default.

Phone checks outstanding: login/verification/recovery; enroll or explicitly select a meter; stored assessment/pending state; quote/consent/loan decision; demo purchase/countdown/server-confirmed receipt; partial/full self-repayment; reconnect/restart pending recovery; Back and keyboard; logout and another-account isolation. Physical readings must remain unavailable without evidence. No physical-phone installation or testing was performed during this integration. No hosted deployment, migration, real provider call, device command, commit or push was performed.

---

# Validation — 14 October 2026

## Completed

- Syntax/transpilation checks for 16 mobile TypeScript/TSX files.
- Strict TypeScript checks for the shared finance controller, new mobile finance renderer and supplied sandbox contract.
- Strict TypeScript checks for the visual preview, shared UI, formatting, navigation and native-back hook using browser adapters.
- Self-contained preview bundles built.
- Mocked Chromium workflow checks: five tabs at 360, 390 and 768 pixels, no horizontal overflow or financial POST on navigation.
- Loan quote, explicit consent, quote hash and retry identity retained; mocked approval and rejection displayed.
- Expired quotes cannot submit; late quote response discarded after meter change.
- Repayment stays pending until mock-server settlement; debt refresh creates no energy.
- Zero countdown stays pending until the server response confirms settlement.
- Purchase retains one request identity, requests no PIN, and displays energy from the settled receipt.
- Separate purchase/repayment receipt filters work.
- Pending assessments show no fallback score or limit; missing meter directs to enrollment.
- Default shared web view remains available. Its original returned JSX was preserved.
- No browser page errors in these workflow checks.
- Internal visual inspection of Home, loan terms and pending-payment screens.
- Access.tsx remains unchanged; authenticated UI styling is scoped to `.consumer-redesign`.

## Limits

These browser checks use an in-memory mock client. They are not authenticated end-to-end tests against Django, and do not prove provider payments or physical delivery.

The full repository, authentication modules, complete dependency/build configuration and Android project were not supplied. Full App.tsx type checking, full mobile/web builds, backend regression tests, hosted deployment, APK assembly/signing and phone testing were not performed here. The source overlay must be integrated and checked in the existing repository before an APK is built.

No real API, payment-provider or hardware requests were made. No preview fixture data is imported by App.tsx. See INTEGRATION.md for repository integration steps.
