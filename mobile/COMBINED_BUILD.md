# Combined AC_LAB + MTN Android testing APK

Built locally from checkout **5950316** plus the current documented integration fixes.
Backend rollout: [ordered checklist](../backend/docs/COMBINED_AC_MTN_ROLLOUT.md).
No hosted deployment or phone runtime test is claimed.

- APK: `/home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk`
- File size: **4,635,116 bytes**.
- SHA-256: `cd8bfafdeb60331e5f05d008531081ba738b9695e963e0ee9f3dff6761024476`.
- Application ID: `org.gpawa.consumer.prototype`; versionName **1.0**, versionCode **1**.
- Android minimum: **API24 / Android7.0**; target/compile API36.
- Embedded API: `https://shanonsimon.alwaysdata.net/api/v1`; Capacitor debug origin `http://localhost`.
- APK signature verification passed (v2). Certificate SHA-256:
  `e9fb53040e78b6a525b67462cc5cc72a656de66ebe6c55061714e785eae86b4c`.
- Certificate matches the previous local testing APK (SHA-256
  `f3ff45da24cbcb37703d0a132bdd2a494f9b0cf4822695ff9c7ba6ef0cb6515d`) and the original documented fingerprint.
  Existing ignored `mobile/.android-signing/debug.keystore` was used explicitly;
  no replacement key or signing credentials were created/committed.
- Packaged assets match the current Vite debug bundle byte-for-byte. No previous
  LAN API, `/__fixture__` endpoint or browser-preview fixture marker is present.
- Debug-only HTTP WebView origin/manifest remains; API itself is HTTPS. Release
  cleartext prohibition and release HTTPS build validation remain unchanged.
- No ADB-authorized device/emulator was available. Installed-phone certificate,
  install/update/launch/Back/keyboard and runtime networking remain untested.

## Checks executed

- Mobile strict type check passed; **70 tests passed**, including shared web/mobile
  receipt rendering, pending/error outcomes, original-provider recovery, retained
  consent progression under enabled LOCAL_DEMO loans, blocked EUR loan reason,
  older UGX debt/receipt visibility, exact ledger reads and secure auth regressions.
- Mobile debug bundle and Capacitor sync passed (82 modules).
- Native Gradle wrapper `assembleDebug` passed: **153 tasks;27 executed,126 up to date**,
  **56s**, offline cache, Java21.0.13.0.3, Gradle8.14.3, AGP8.13.0, Build Tools35.0.0.
- Combined isolated PostgreSQL/alwaysdata-profile regressions: **112 passed**;
  includes software-only AC token/redeem/ACK/telemetry, wrong-device/owner and
  concurrency cases, MTN transitions, mode/currency isolation, seven flags and CSRF.
- Settlement/allocation/financial/TLS regressions: **81 tests**, with the existing
  CORE overdue-after-completion **expected failure retained**; no new failures.
- Web strict type check/scoped lint and **29 tests passed**; production webpack
  build passed with dynamic Next.js pages and strict type checks retained.
- Migration drift: no changes to loan/meter/transactions. Existing additive meter
  migration0032 is included in the combined source upload; it was not applied hosted.
- Hosted SSH/dry-run/plan were attempted but blocked by authentication. Only local
  dry-run and simulated0031→0032 plan evidence is available. No live MTN or board test.

## Scope fixes in this build

Android meter reads now request the active allocation ledger explicitly, matching
web behavior. Both clients expose separate read-only historical ledgers and earlier
currency receipts; no money or wallet units are converted. Existing UGX debt now
explains why an EUR receipt cannot repay it. Meter screens explain why AC lab
redemption is unavailable in MTN mode. Missing/stale physical evidence stays unavailable.

The public hosted endpoint still reports LOCAL_DEMO with loans enabled. Therefore
its current Amount-step report is **not confirmed to be the MTN policy gate**.
This build explains assessment, pricing, amount, pending-payment and unresolved
request blockers explicitly; eligible LOCAL_DEMO Amount/Terms/consent progression
is tested. The displayed owner-specific reason is still needed to finish that
phone-account diagnosis; no hosted private account was inspected.

After the planned MTN switch, **new EUR loan acquisition is deliberately unavailable**,
pending review/implementation of a versioned EUR automatic assessment/limit policy.
The app explains that before an unusable form. No hidden flag, questionnaire,
invented score or conversion enables it. Existing loans and balances are retained.

## Reproduce and install

From `mobile/` (no dependency upgrade or Next.js build dependency):

```bash
npm run typecheck
node --test --test-isolation=none tests/*.test.mjs
VITE_API_BASE_URL=https://shanonsimon.alwaysdata.net/api/v1 VITE_ACCOUNT_COMPLETION=browser npm run android:sync:debug
```

From the repository root, using the existing private debug identity:

```bash
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 ANDROID_HOME=/home/shanon/Android/Sdk ANDROID_USER_HOME="$PWD/mobile/.android-signing" GRADLE_USER_HOME="$PWD/mobile/.gradle-user" PATH="/usr/lib/jvm/java-21-openjdk-amd64/bin:$PATH" mobile/android/gradlew --offline --no-daemon --max-workers=2 '-Dorg.gradle.jvmargs=-Xmx768m -XX:ActiveProcessorCount=2' -p mobile/android assembleDebug -Pandroid.injected.signing.store.file="$PWD/mobile/.android-signing/debug.keystore" -Pandroid.injected.signing.store.password=android -Pandroid.injected.signing.key.alias=androiddebugkey -Pandroid.injected.signing.key.password=android
```

Standard debug-key passwords above are not production signing credentials.
Do not generate a replacement if the existing file is missing.

Install using an authorized ADB connection:

```bash
adb install -r "/home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk"
```

`-r` preserves data when the installed certificate matches; do not uninstall to
bypass a signature mismatch. To access from Windows, run `explorer.exe mobile/android/app/build/outputs/apk/debug`
from the repository root, copy the APK to Downloads, then use Windows `adb.exe install -r`
with the copied path. WSL may need USB forwarding or Windows ADB; no USB/network
configuration was changed here.

Phone checklist after the reviewed backend rollout: login → meter selection →
current EUR TEST allocation → separate historical ledger balances → existing
loan/history and explicit unavailable-EUR-application reason → purchase quote/review
and no-real-money disclosure **without submitting a payment in this no-payment
check** → repayment currency explanation → device redemption unavailable → logout.
Actual MTN settlement scenarios and AC hardware tests need separate authorization.
