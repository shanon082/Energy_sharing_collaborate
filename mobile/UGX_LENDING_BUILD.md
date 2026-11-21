# UGX lending and token diagnostics testing APK — 2026-11-20

Built locally from the current working tree. No hosted deployment, phone install,
MTN initiation or board test was performed. The current design/authentication and
secure token storage remain unchanged. New EUR payments are paused by the server;
UGX repayment still needs an explicit provider/policy decision. This build does
not pretend that the complete financial demonstration has passed on hardware.

- APK: `/home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk`
- Size: **4,635,116 bytes**
- SHA256: `f92602af12b8b9e89892f288f7bb619c768d0334b67be935bb83107e48d220dc`
- Signature verified; certificate SHA256: `e9fb53040e78b6a525b67462cc5cc72a656de66ebe6c55061714e785eae86b4c`
- Certificate matches the previous local testing APK verified before replacement.
  No new key created; the installed phone's certificate was not queried.
- Application ID: `org.gpawa.consumer.prototype`; version1.0/code1.
- Minimum API24 (Android7.0), target API36.
- Embedded API: `https://shanonsimon.alwaysdata.net/api/v1` (no duplicated /api/v1 or previous LAN URL).
- WebView origin remains `http://localhost`; release HTTPS rules unchanged.
- APK includes the UGX loan contract and paused-purchase UI; browser preview
  fixtures are not APK entry points.

## Commands and observed checks

```bash
cd mobile
npm run typecheck
npm test
VITE_API_BASE_URL=https://shanonsimon.alwaysdata.net/api/v1 VITE_ACCOUNT_COMPLETION=browser npm run android:sync:debug
cd ..
test -s mobile/.android-signing/debug.keystore
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 ANDROID_HOME=/home/shanon/Android/Sdk ANDROID_USER_HOME="$PWD/mobile/.android-signing" GRADLE_USER_HOME="$PWD/mobile/.gradle-user" PATH="/usr/lib/jvm/java-21-openjdk-amd64/bin:$PATH" mobile/android/gradlew --offline --no-daemon --max-workers=2 '-Dorg.gradle.jvmargs=-Xmx768m -XX:ActiveProcessorCount=2' -p mobile/android assembleDebug -Pandroid.injected.signing.store.file="$PWD/mobile/.android-signing/debug.keystore" -Pandroid.injected.signing.store.password=android -Pandroid.injected.signing.key.alias=androiddebugkey -Pandroid.injected.signing.key.password=android
```

Mobile strict TypeScript passed; final test invocation passed all13 test files,
including shared web/mobile UGX/EUR isolation, pause UI, session/refresh/logout,
account isolation, duplicate/pending recovery and disabled features. The new
payment/loan tests use mocks, not an MTN service or a physical meter. Vite bundle
and Capacitor sync passed. Gradle **BUILD SUCCESSFUL in12m3s**,153 tasks,
27 executed/126 up-to-date; Java21, existing SDK, Gradle8.14.3/AGP8.13, offline.
The first sandboxed Gradle attempt failed because the local lock socket was
unavailable; the approved offline build outside that sandbox succeeded.

Web strict TypeScript and12 test files passed. The bounded production webpack
build timed out after420s at optimization without a compiler error; production
web completion is not claimed. No type suppression or ignoreBuildErrors used.
Backend/firmware final evidence and rollout are recorded in
[the coordinated backend handoff](../backend/docs/UGX_LENDING_AND_TOKEN_DIAGNOSTICS.md).

## Install later (not performed)

```bash
adb install -r /home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk
# Optional copy from WSL for Windows installation:
cp /home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk /mnt/c/Users/USER/Downloads/gpawa-ugx-lending-debug.apk
```

Keep the same installed-app identity; do not uninstall to solve a server error.
After the coordinated backend rollout: login → select owned meter → initialize
missing automatic simulated assessment → review UGX amount/admin tariff/terms →
explicit consent → one approval/allocation/token → authenticated credit-only
redemption/ACK. Check lost-response/reboot recovery, receipts and logout. A new
purchase or UGX repayment is unavailable under the current paused-payment policy;
no EUR receipt is relabelled UGX. No relay/load is enabled or implied by saved credit.
