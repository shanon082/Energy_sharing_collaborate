# MTN SANDBOX / AC_LAB domain testing APK — 2026-11-18

Built from current local sources. Not installed/tested on a phone here. The prior
COMBINED_BUILD.md hash describes the previous artifact and is retained as history.

- APK: `/home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk`
- Size: **4,635,116 bytes**.
- SHA256: `4a46b4ef01375e39227cd229b1f1567d62f012dbb1ab21a929116dec32459f45`.
- Package: `org.gpawa.consumer.prototype`; version1.0/code1.
- Minimum API24 (Android7.0); target/compile API36.
- Embedded API: `https://shanonsimon.alwaysdata.net/api/v1`.
- Debug WebView origin: `http://localhost`; no CORS/HTTPS weakening.
- `apksigner verify --verbose --print-certs` passed.
- Signing certificate SHA256:
  `e9fb53040e78b6a525b67462cc5cc72a656de66ebe6c55061714e785eae86b4c`.
  Matches the previous local testing APK verified before replacement. No new key
  was generated; the certificate on a physical phone was not queried.

The existing private ignored `.android-signing/debug.keystore` was used explicitly.
No credentials/device keys are embedded. Backend capabilities remain authoritative;
installing this APK does not enable the lab or EUR lending. The current backend
must be deployed/migrated/provisioned separately using MTN_AC_LAB_SANDBOX.md.

## Build and checks

Mobile strict TypeScript,73 individual tests, bundle and Capacitor sync passed.
Java21, existing Linux SDK, Gradle wrapper8.14.3/AGP8.13.0, offline cached artifacts.
Wrapper assembleDebug: **BUILD SUCCESSFUL in55s**,153 tasks,27 executed/126 cached.
Initial sandbox build could not create Gradle's local file-lock socket; the
approved offline build outside that sandbox succeeded. No dependency install,
provider call, migration or hardware command was involved.

```bash
# From mobile/:
VITE_API_BASE_URL=https://shanonsimon.alwaysdata.net/api/v1 VITE_ACCOUNT_COMPLETION=browser npm run android:sync:debug
# From repository root (existing debug key must exist):
test -s mobile/.android-signing/debug.keystore
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 ANDROID_HOME=/home/shanon/Android/Sdk ANDROID_USER_HOME="$PWD/mobile/.android-signing" GRADLE_USER_HOME="$PWD/mobile/.gradle-user" PATH="/usr/lib/jvm/java-21-openjdk-amd64/bin:$PATH" mobile/android/gradlew --offline --no-daemon --max-workers=2 '-Dorg.gradle.jvmargs=-Xmx768m -XX:ActiveProcessorCount=2' -p mobile/android assembleDebug -Pandroid.injected.signing.store.file="$PWD/mobile/.android-signing/debug.keystore" -Pandroid.injected.signing.store.password=android -Pandroid.injected.signing.key.alias=androiddebugkey -Pandroid.injected.signing.key.password=android
```

Install (USB debugging/authorized adb connection required):

```bash
adb install -r /home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk
# Optional copy from WSL to Windows; then use Windows adb or open the APK:
cp /home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk /mnt/c/Users/USER/Downloads/gpawa-mtn-ac-lab-debug.apk
```

Do not uninstall merely to resolve an unrelated login/backend error. The -r update
preserves app data; a different installed signing identity requires investigation.

## Later phone/board checklist (not performed)

1. Login, select the explicitly owned meter, check unchanged account/history.
2. Verify EUR TEST purchase terms, all deferred features disabled and new loans
   unavailable with their actual policy reason. Old UGX debt must not accept EUR.
3. Only after separate authorization, initiate one MTN sandbox purchase.202 and
   PENDING show processing, not success; close/reopen and recover the same reference.
4. After Django confirms validated SUCCESSFUL: see one receipt, one SANDBOX token,
   and cloud entitlement. Neither means credit already saved on the board.
5. On the separately provisioned credit-only V2 board, redeem that meter's token,
   verify durable credit, lost-response/ACK retry and reboot survival; relay stays off.
6. Meter screen: correct SANDBOX protocol, periodic measured usage/remaining journal
   credit/last contact; stale or absent samples must stay stale/unavailable.
7. Repayment of an existing matching EUR loan reduces debt without energy/token;
   check history and logout. Actual provider/phone/board work needs separate review.
