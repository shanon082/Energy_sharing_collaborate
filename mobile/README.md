# gPawa consumer Android prototype (Phase 1)

This is a separate React, TypeScript and Vite bundle packaged by Capacitor. The existing Next.js web app remains a server-rendered application. The methodology names a Kotlin client; this prototype uses Capacitor as requested and shares only the web app's pure feature-availability parser. Django remains responsible for authentication and all financial and meter decisions.

## Current scope

After sign-in, consumers can choose an assigned meter and read source-linked available energy, reserved or unresolved delivery, acknowledged applied energy, last meter contact, stored daily usage, simulator counter events, loans, and repayment history. The seven deferred features remain controlled by Django and have no action screens here. No purchases, loan applications, repayments, wallet spending, or meter-loading commands are available in this phase. Unknown values are displayed as unavailable, not zero. Simulator events are explicitly labelled and are not evidence of physical meter accuracy.

The app uses `POST auth/login/`, `POST auth/refresh/token/`, `POST auth/mobile-logout/`, and these GET routes under `/api/v1/`: `features/`, `auth/mobile-account/`, `meter/my-meter/`, `meter/allocation-status/?meter_no=...`, `meter/mobile-consumption/?meter_no=...`, and `loans/mobile-overview/`. The last three consumer-specific routes were added for side-effect-free, owner-bound reads. Existing web authentication routes remain available. Enabling the SimpleJWT blacklist app supports mobile refresh-token revocation and requires its **package migrations** in each deployment before use; this phase did not run operational migrations.

## Authentication and storage

Access tokens live only in memory. On Android, the refresh token and user ID use `capacitor-secure-storage-plugin` 0.13.0, whose Android implementation encrypts its private preferences using Android Keystore. This version declares Capacitor 8 compatibility. Browser preview uses memory only because the plugin's web fallback is ordinary browser storage. Android backup is disabled so encrypted preferences cannot be restored without their device key. A single in-flight refresh rotates concurrent requests; a failed refresh ends the session, and a request retries a 401 once. The client verifies the account ID after refresh before showing any account data. Staff two-factor accounts and users required to change their password are directed to the web app; unverified accounts receive the server's verification error.

Logout clears local state immediately and asks Django to blacklist the current refresh token. If the device is offline, local logout still works, but server revocation cannot occur until a connection exists; the abandoned token remains valid until its normal expiry. This limitation should be addressed before a production release with an agreed revocation policy. No provider or device credentials belong in the APK. Keep the secure-storage dependency under maintenance review and verify behavior on actual target Android versions.

## Development and build

Use Node 22 or newer and a compatible Android Studio/JDK/SDK installation. From this directory:

```bash
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export ANDROID_HOME=/home/shanon/Android/Sdk
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"
export GRADLE_USER_HOME="$PWD/.gradle-user"
npm ci
npm run typecheck
npm test
npm run android:sync:debug
cd android && ./gradlew assembleDebug
```

This WSL project pins Gradle 8.14.3 through its wrapper and Android Gradle Plugin 8.13.0. It compiles against API 36, targets API 36, and supports Android API 24 and newer. Android Gradle Plugin 8.13 uses Build Tools 35.0.0 by default. For a fresh WSL SDK, obtain Google's Linux command-line tools from the [official download page](https://developer.android.com/studio), verify its published SHA-256, place its contents under `$ANDROID_HOME/cmdline-tools/latest`, and run `sdkmanager --sdk_root="$ANDROID_HOME" --licenses` interactively. Then install `"platforms;android-36" "build-tools;35.0.0" "platform-tools"` with `sdkmanager --sdk_root="$ANDROID_HOME"`. The SDK and Gradle caches are outside tracked source or ignored locally; no global Gradle installation is needed.

The APK, if Gradle succeeds, is `android/app/build/outputs/apk/debug/app-debug.apk`. The sync command builds the Vite bundle and copies it into the native project. After changing web code or `VITE_API_BASE_URL`, sync again before assembling. `npm run build` and `npm run android:sync:release` require an explicit HTTPS `VITE_API_BASE_URL`; release signing is a later task. Never commit a signing key.

In Windows, install Android Studio 2025.2.1 or newer with Android SDK Platform 36 and its build tools, then open `mobile/android` in Android Studio or run `cd mobile\android` followed by `.\gradlew.bat assembleDebug` in PowerShell. Android Studio supplies its compatible JDK. For a WSL-only build, install a Linux JDK and Linux Android SDK Platform 36/build tools, set `JAVA_HOME` and `ANDROID_HOME` to their Linux paths, then run `cd mobile/android && ./gradlew assembleDebug`. The Windows SDK executables are not a substitute for Linux SDK tools in WSL. Install `platform-tools` to use `adb install -r app/build/outputs/apk/debug/app-debug.apk` after a successful build.

For the Android emulator, the debug default is `http://10.0.2.2:8000/api/v1`, which reaches a Django server on the host. For a physical phone on the same LAN, set `VITE_API_BASE_URL=http://<private-LAN-IP>:8000/api/v1` in `.env.android-debug.local`; make Django listen on an address reachable from that phone and set `EXTRA_ALLOWED_HOSTS` appropriately. WSL users may need Windows-to-WSL port forwarding and firewall access. A debug build alone allows local HTTP; the release build requires HTTPS and its manifest disables cleartext traffic. Configure Django `MOBILE_APP_ORIGIN=https://localhost` for a production Capacitor origin (or `http://localhost` only for a debug origin); keep the existing web origin configuration. No backend secret belongs in the mobile env file because Vite embeds `VITE_` values in the APK.

For this phone-test build, the ignored `.env.android-debug.local` selects `http://192.168.97.107:8000/api/v1`. The phone must reach that Windows Wi-Fi address and port. A Django process bound only to WSL `127.0.0.1:8000` is insufficient: run the development server on `0.0.0.0:8000`, allow the Windows LAN host in Django, and configure Windows forwarding/firewall for the current WSL IP. WSL's private IP can change after restart. Confirm the URL from the phone's browser before treating login as tested. Rebuild and sync if the LAN address changes.

Capacitor's Android WebView uses `http://localhost` as the origin of this debug build. Set Django's `MOBILE_APP_ORIGIN=http://localhost` for its CORS preflight; the API host is a separate address. The mobile login requests `POST http://192.168.97.107:8000/api/v1/auth/login/` with JSON, so the browser checks `OPTIONS` first. Django permits only configured origins and the `GET`, `POST`, `OPTIONS` methods with `authorization` and `content-type` request headers. This also keeps the web app's configured origins. A phone-browser GET to `features/` proves the host is reachable, but does not test the WebView origin or login preflight.

The client now attempts requests even if Android reports `navigator.onLine=false`, which can be misleading for a local hotspot. A failed fetch is shown as an API transport error; HTTP authentication errors and invalid JSON responses have separate messages. Refresh remains available after a transport failure. To diagnose a persistent login issue, compare one attempt's `OPTIONS` and `POST /api/v1/auth/login/` entries in the Django console and inspect filtered Android Logcat/WebView network errors. Do not collect request bodies, passwords, or tokens.

Sign-in errors now identify whether a response failed during saved-session refresh, the login POST, or the authenticated mobile-account check. A successful login POST is not proof that the subsequent account check completed. The debug connection test can exercise the account route's Authorization preflight with a fixed invalid test token; a readable HTTP 401 is expected.

The session client invokes WebView `fetch` with the browser global as its receiver. Calling the stored function as a method of the session object can make WebView reject it before any OPTIONS or POST reaches Django. The direct debug probe did not use that session method, which is why it could succeed while sign-in failed.

The debug login screen has a **Test API connection** button. It displays the actual WebView origin and the configured API URL, then makes a simple public GET, a GET with the app's JSON header, a credential-free empty JSON POST to the login route, a GET to the account route with a fixed invalid test token, and a no-CORS public GET. The empty POST should yield HTTP 400 after a successful preflight; the invalid-token account GET should yield HTTP 401. A successful simple GET followed by failed JSON GET points to a preflight/header problem. A no-CORS opaque response means the WebView reached a host but cannot read the response; it is not proof of a successful API response. If all probes fail, inspect Android network policy and device logs. This button is absent from release builds and never sends or displays real credentials or tokens.

The server controls feature flags; the mobile app defaults them to disabled if availability cannot be fetched. It stores no balance cache. During connectivity loss, already displayed values are marked stale with their fetch time; after an app restart offline, account data is unavailable until reconnection. No financial mutations can be queued offline.

## Device validation still required

On an emulator or phone, install the debug APK and check launch, consumer login, unverified-account rejection, meter selection, all five tabs, Android Back (tab to dashboard, then minimize), access expiry/refresh, connectivity loss and reconnection, and logout followed by failed refresh reuse. Check both zero-meter and multiple-meter accounts, a simulator meter, and a staff account. These are runtime checks, not established by TypeScript and mocked tests.

## Next phase

Transaction screens need separately designed APIs for meter-bound purchase intent and status, loan application/approval status, verified self-repayment, and allocation load/status with idempotency and pending outcomes. The existing financial-policy questions and overdue-after-completion expected failure remain unresolved. This prototype is not ready for live payment or physical-meter operation.
