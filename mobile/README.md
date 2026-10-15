# gPawa consumer Android prototype

The latest LOCAL_DEMO UGX flow and automatic assessment are documented in
[CONSUMER_EXPANSION.md](CONSUMER_EXPANSION.md) and
[the backend runbook](../backend/docs/LOCAL_PAYMENT_DEMO.md). No questionnaire
is required; ordinary account preferences remain.

The earlier opt-in sandbox journey and signed APK are documented in
[SANDBOX.md](SANDBOX.md). It supports immediate SELF_DECLARED meter enrollment,
automatic selection, EUR TEST loans/purchases/self-repayments and recovery.
No staff approval, pre-created inventory or simulator is required for new sandbox
enrollment. The earlier interface/preview notes below are historical; the installed
consumer welcome screen does not expose the preview link.

This is a separate React, TypeScript and Vite bundle packaged by Capacitor. The existing Next.js web app remains a server-rendered application. The methodology names a Kotlin client; this prototype uses Capacitor as requested and reuses the web app's transport-independent finance controller, contracts and feature-availability parser. Django remains responsible for authentication and all financial and meter decisions.

## Current testing APK — 15 October 2026

The redesigned real-client bundle is integrated. See [VALIDATION.md](VALIDATION.md) for commands and evidence. Debug APK: `android/app/build/outputs/apk/debug/app-debug.apk`, **4,476,294 bytes**, SHA-256 `9da05eddf3f92c34d4fe41f3f92d16fed19d36b5b5eabcc59d7b30aacdd23a60`. API: `https://shanonsimon.alwaysdata.net/api/v1`. Original application ID and debug signing certificate are preserved. This is a testing APK; phone checks and the existing Next.js production-build stall remain outstanding.

## Current scope

The integrated redesign has five destinations: **Home, Meters, Loans, Buy Units, Account**. Usage and receipts are child screens. Welcome, login and signup are unchanged; welcome has no preview link. Home shows the server-stored assessment, borrowing limit, debt and cloud energy. Loans separates My Loans from Apply for Loan, with quote review and explicit consent. Purchases and self-repayments use LOCAL_DEMO when the server permits it. Pending recovery remains mounted across navigation; a countdown never confirms a payment.

See [INTEGRATION.md](INTEGRATION.md) and [VALIDATION.md](VALIDATION.md) for the current repository integration, tests and signed APK. Demo UGX, earlier EUR test history and physical readings remain distinct. The seven deferred features remain disabled. Browser-preview fixtures are excluded from the installed bundle.

### Earlier prototype scope (historical)

The following preview/core-rollout description predates the current LOCAL_DEMO integration; it is not the installed app's navigation or current hosted-demo capability contract.

**Explore the app preview** is an independent frontend workspace that needs no backend. Its persistent banner labels every page as sample data. It includes dashboard/energy status, meter selection, consumption, credit/loan detail, purchase/application/self-repayment/own-meter-load forms and review pages, activity/receipts, notifications, profile, security and help. Scores, charges and tariffs remain unavailable rather than being invented. Transaction forms end at a review explaining that submission requires the approved backend workflow; they send no API requests, create no obligations and persist no sample records. Profile edits and notification read state stay in memory and disappear on leaving preview. Sample loans and receipts keep their original meter binding when the selected viewing meter changes. Preview controls demonstrate empty and offline/stale layouts.

The preview is separate from a real signed-in account: sample values never replace missing live balances. Existing connected account screens continue to use owner-bound Django reads and guarded actions. Do not reuse sample fixture values as financial policy or physical meter evidence. The seven deferred feature flags and the mobile transaction rollout flag are unchanged.

Consumers can register, verify email, resend verification, reset or change a password, sign in and out, edit permitted profile fields, select an assigned meter, and read source-linked entitlement, consumption, loans, payment receipts, alerts and history. The app can reserve authorized energy for an **enrolled development simulator**. This is not physical meter delivery. Unknown values appear as unavailable rather than zero.

Purchase and self-repayment forms use the verified PaymentIntent route and a unique client request ID, but Django disables mobile initiation by default (`MOBILE_PAYMENT_ACTIONS_ENABLED=false`). A real verified provider and financial-policy approval are required before enabling it. Loan eligibility and an informational current-tariff quote are available; submission remains blocked because the existing application path can auto-disburse without mobile idempotency and still has unresolved calculation policy. The seven deferred features remain disabled by default. See [PARITY.md](PARITY.md) for the exact status and release blockers.

The app calls Django under `/api/v1/` for authentication, profile, meter/consumption/allocation, eligibility/quote, receipts, alerts and history. Mobile payment initiation has separate guarded `meter/mobile-buy-units/` and `loans/mobile-repay/momo/<loan_id>/` routes; their provider status routes are the canonical web/Django routes. The mobile-only `meter/mobile-purchase-quote/` is an estimate, not a binding settlement price. Existing web routes remain available. Before using the new database-backed endpoints on a **confirmed development database**, apply the reviewed project migrations, including `token_blacklist`, `meter.0025` and `transactions.0010`. This work did not run operational migrations.

## Authentication and storage

The first backend integration stage is documented in [MOBILE_BACKEND_STAGES.md](../backend/docs/MOBILE_BACKEND_STAGES.md). Login/refresh URLs remain shared with the web app; the backend now validates account state and password revocation and serializes refresh rotation. Existing JWTs from before the revocation setting require one fresh sign-in after the backend restarts. This backend-only stage requires no APK rebuild and introduces no database migration.

Historical Stage 2 (the questionnaire has since been removed) connected profile and assigned-meter screens through `auth/mobile-profile/`, `auth/mobile-account-details/`, and `meter/mobile-meters/` with an ID-bound dashboard at `meter/mobile-meters/<id>/`. Profile choices come from Django; privileged fields are not editable. Missing account details are reported without creating records. Explicit meter selection is cleared on reassignment/replacement, and stale profile values show their last fetch time with editing disabled until a successful refresh. Existing web endpoints remain unchanged. This stage introduces no migration; its mobile endpoint changes require rebuilding/syncing the APK. Reload the development backend before installing the updated build.

Access tokens live only in memory. On Android, the refresh token and user ID use `capacitor-secure-storage-plugin` 0.13.0, whose Android implementation encrypts its private preferences using Android Keystore. This version declares Capacitor 8 compatibility. Browser preview uses memory only because the plugin's web fallback is ordinary browser storage. Android backup is disabled so encrypted preferences cannot be restored without their device key. A single in-flight refresh rotates concurrent GET requests; a mutation is never replayed after a 401. The client verifies the account ID after refresh before showing private data. Staff two-factor accounts use the web app; consumers required to change their password can do so in the app. Unverified accounts receive the server's verification error. Verification/reset email links can be copied into the app for local development; Android App Links require a verified production domain and are not claimed here.

Logout clears local state immediately and asks Django to blacklist the current refresh token. If the device is offline, local logout still works, but server revocation cannot occur until a connection exists; the abandoned token remains valid until its normal expiry. This limitation should be addressed before a production release with an agreed revocation policy. No provider or device credentials belong in the APK. Keep the secure-storage dependency under maintenance review and verify behavior on actual target Android versions.

## Development and build

Use Node 22 or newer and a compatible Android Studio/JDK/SDK installation. For
an update, first confirm `.android-signing/debug.keystore` exists and matches the
previous APK certificate (details below). If missing, restore its private backup
before building; do not generate a replacement. From this directory:

```bash
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export ANDROID_HOME=/home/shanon/Android/Sdk
export ANDROID_USER_HOME="$PWD/.android-signing"
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

The current phone-test build uses the ignored `.env.android-debug.local`:

```dotenv
VITE_API_BASE_URL=https://shanonsimon.alwaysdata.net/api/v1
VITE_ACCOUNT_COMPLETION=browser
```

This public configuration contains no backend secrets. The API base includes
`/api/v1` once; clients append relative paths such as `auth/login/`. The phone
needs internet access to alwaysdata, not laptop hotspot routing, local Django,
port forwarding or a hosted Next.js website. Existing LAN/emulator development
remains possible by changing this ignored file and choosing
`VITE_ACCOUNT_COMPLETION=api` for the legacy in-app token flow.

In browser mode, verification and reset screens tell users to open the emailed
link in their phone browser, complete the Django CSRF-protected form, then return
to Android manually. They do not paste tokens into the app, call verification
GET, submit a reset PATCH, or claim completion. Actual sign-in still checks
Django's verified-account requirement. Resend/recovery requests remain available;
queued mail is not a delivery claim. The alwaysdata outbox constructs links at
`https://shanonsimon.alwaysdata.net/account/verify-email/` and
`https://shanonsimon.alwaysdata.net/account/reset-password/`. No deep links or
hosted Next.js page are required.

Capacitor's Android WebView uses `http://localhost` as the origin of this debug build. Set Django's `MOBILE_APP_ORIGIN=http://localhost` for its CORS preflight; the API host is a separate address. The mobile login requests `POST https://shanonsimon.alwaysdata.net/api/v1/auth/login/` with JSON, so the browser checks `OPTIONS` first. Django permits only configured origins and the `GET`, `POST`, `PATCH`, `OPTIONS` methods with `authorization` and `content-type` request headers. This also keeps the web app's configured origins. A phone-browser GET to `features/` proves the host is reachable, but does not test the WebView origin or login preflight.

The client now attempts requests even if Android reports `navigator.onLine=false`, which can be misleading for a local hotspot. A failed fetch is shown as an API transport error; HTTP authentication errors and invalid JSON responses have separate messages. Refresh remains available after a transport failure. To diagnose a persistent login issue, compare one attempt's `OPTIONS` and `POST /api/v1/auth/login/` entries in the Django console and inspect filtered Android Logcat/WebView network errors. Do not collect request bodies, passwords, or tokens.

Sign-in errors now identify whether a response failed during saved-session refresh, the login POST, or the authenticated mobile-account check. A successful login POST is not proof that the subsequent account check completed. The debug connection test can exercise the account route's Authorization preflight with a fixed invalid test token; a readable HTTP 401 is expected.

The session client invokes WebView `fetch` with the browser global as its receiver. Calling the stored function as a method of the session object can make WebView reject it before any OPTIONS or POST reaches Django. The direct debug probe did not use that session method, which is why it could succeed while sign-in failed.

The debug login and signup screens have **Development connection tools**. They display the actual WebView origin and API URL, plus the last account request's method, path without query parameters, start time, HTTP status/outcome and a bounded exception category. No request bodies, headers, tokens, email addresses or raw exception text are retained in this diagnostic. The **Test API connection** button makes public GETs, empty JSON login/signup POSTs, an account GET with a fixed invalid test token, and a no-CORS GET. The empty POSTs should yield HTTP 400 with readable JSON; the invalid-token GET should yield HTTP 401. The probe now actually parses JSON rather than reporting only a readable status. An opaque response is not proof of a readable API response. The tools are absent from release builds. Do not infer CORS failure from a transport error alone.

The server controls feature flags; the mobile app defaults them to disabled if availability cannot be fetched. It stores no balance cache. During connectivity loss, already displayed values are marked stale with their fetch time; after an app restart offline, account data is unavailable until reconnection. No financial mutations can be queued offline. An uncertain payment initiation remains a pending PaymentIntent for Django reconciliation; the app shows its receipt and does not automatically repeat the POST. Nonsecret, account-scoped payment and delivery request UUIDs survive a WebView restart for a manual retry; logout removes them. Phone numbers, passwords and tokens are not stored with those handles. Provider approval prompts and queued simulator commands are not settlement or meter application proof.

## Device validation still required

On an emulator or phone, install the debug APK and check welcome, registration/recovery, consumer login, unverified-account rejection, meter selection, all six tabs, Android Back (account tab to dashboard, then minimize), access expiry/refresh, connectivity loss and reconnection, and logout followed by failed refresh reuse. Check both zero-meter and multiple-meter accounts, a simulator meter, and a staff account. The welcome page no longer exposes the sample preview. These are runtime checks, not established by TypeScript and mocked tests.

## Frontend browser checks

`npm run typecheck` and `npm test` check types and session/contracts. `tests-ui/consumer-ui.mjs` exercises the actual interface with Chromium at 320, 390 and 768 pixels. It intercepts **all** `/api/v1/` requests, uses synthetic credentials, and verifies authentication errors, registration validation, browser account-completion instructions, logout, the absent preview entry, meter binding, profile failures, navigation and horizontal overflow. It never calls Django or any provider/device.

Start `npm run dev -- --mode android-debug --host 127.0.0.1` in one terminal. To keep browser tooling separate from both mobile and web dependencies, install Playwright into a temporary directory and run in another terminal:

```bash
npm install --prefix /tmp/gpawa-mobile-ui-check playwright --no-audit --no-fund
PLAYWRIGHT_BROWSERS_PATH=/tmp/gpawa-mobile-ui-check/browsers /tmp/gpawa-mobile-ui-check/node_modules/.bin/playwright install chromium
PLAYWRIGHT_BROWSERS_PATH=/tmp/gpawa-mobile-ui-check/browsers \
PLAYWRIGHT_MODULE=/tmp/gpawa-mobile-ui-check/node_modules/playwright/index.mjs \
MOBILE_UI_SCREENSHOTS=/tmp/gpawa-mobile-ui-check/screenshots \
node tests-ui/consumer-ui.mjs
```

Browser verification is separate from Android WebView and physical-device testing. Debug APK assembly uses the independent Vite build and does not require the Next.js build or font downloads.

Stage 2 validation passed 113 backend regressions (one known financial expected failure), 18 mobile unit tests, mobile/web type checks, and 14 intercepted Chromium scenarios. The updated debug APK is `android/app/build/outputs/apk/debug/app-debug.apk`, 4,543,216 bytes, SHA-256 `20e826bb979192ca5d1e8c23e2194e5231882e544fe78b60d7f8c6f31ac20e7f`. Its embedded API is `http://192.168.193.107:8000/api/v1`. Reload Django before installing it. No Stage 2 migration or live provider/device call was performed; actual phone testing is still required. The previous Next.js production-build timeout remains unresolved.

## alwaysdata debug rebuild (11 October 2026)

The rebuilt APK uses `https://shanonsimon.alwaysdata.net/api/v1`, with
`http://localhost` as the unchanged Capacitor debug origin. The bundle was
inspected inside the signed APK: one API base, no doubled `/api/v1` and no old
LAN address. Django verification/reset pages returned generic token-free 400
HTML with no-store/no-referrer/CSP headers. Features GET returned 200, login
preflight 200 and empty login POST 400, with the exact debug-origin CORS headers.
All seven features and all mobile financial actions were false. These checks
used verified HTTPS, no credentials, no provider/device calls and no migrations.
Actual emails and physical-phone operation were not tested.

Validation: mobile type check passed; `npm test` passed all three test files.
`node --test --test-isolation=none --test-reporter=spec tests/*.test.mjs`
confirmed **23 cases passed**. Debug Vite build/Capacitor sync and offline Gradle
assembly passed. The optional Chromium UI script now covers browser completion
without token/password submissions, but was not executed: its external
Playwright/Chromium tooling is unavailable locally. Phone testing is outstanding.
Next.js was neither modified nor rebuilt.

APK: `android/app/build/outputs/apk/debug/app-debug.apk`, **4,344,725 bytes**.
SHA-256: `2fb9ee862d1da6cd25e5f7d13251db436fbbc22ead8fd728974e91aba44e9bc9`.
Application ID: `org.gpawa.consumer.prototype`; version `1.0` / code `1`;
minimum Android 7.0 (API 24), target API 36.

`apksigner verify --verbose --print-certs` passed. Certificate SHA-256:
`e9fb53040e78b6a525b67462cc5cc72a656de66ebe6c55061714e785eae86b4c`,
matching the previous Stage 3 APK. The machine's default `~/.android` key has a
different certificate and must not be used to update that APK. Its original
Stage 3 key was recovered from `/tmp/gpawa-stage3/android-user/debug.keystore`
and preserved in **`.android-signing/debug.keystore`**, a Git-ignored private
file (0600, directory 0700). Never commit/upload this key; back it up privately
and do not generate a replacement. No release signing key was created.

Future builds select this existing key with `ANDROID_USER_HOME` set to the
absolute `.android-signing` directory; `:app:signingReport` was checked and
confirmed the expected path/certificate. The final build also explicitly passed
the Gradle `android.injected.signing.store.file` override with Android's standard
debug alias/passwords. No production signing credentials are used.

Update from WSL with a connected, authorized ADB device:

```bash
/home/shanon/Android/Sdk/platform-tools/adb install -r /home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk
```

Or copy the APK from this Windows Explorer path into Downloads:

```text
\\wsl.localhost\Ubuntu\home\shanon\projects\next_projects\Energy-sharing-project\mobile\android\app\build\outputs\apk\debug\app-debug.apk
```

Then, in Windows PowerShell with Android platform-tools available:

```powershell
adb install -r "$env:USERPROFILE\Downloads\app-debug.apk"
```

This preserves app data when the installed application's certificate matches.
No phone installation was performed. If Android reports a signature mismatch,
identify the installed build's certificate first; do not uninstall it as a
shortcut and discard its account/session data.

## Remaining release work

Stage 3 connects consumption and delivery history to the selected meter ID,
adds stored receipt details and paginated event logs, and uses the dedicated
`meter/mobile-notifications/` API for explicit alert read targets. Activity refresh
never invokes provider confirmation; pending requests are not settled payments.
Legacy event amounts/units are shown as recorded without guessing their units.
Telemetry keeps large Wh counters exact; simulator and application evidence are
labelled. Historical meter usage is not consumer-attributed because the existing
database has no tenancy history. See [Stage 3 details](../backend/docs/MOBILE_BACKEND_STAGES.md).

Stage 3 validation: 129 isolated PostgreSQL tests (one known financial expected
failure), 22 mobile unit cases, mobile/web type checks, debug Vite build and
offline APK assembly passed. Chromium and physical-phone runtime testing are
outstanding. No migration or financial-policy change is required; reload Django
before installing the new APK. On the phone, check stored pending/failed/settled
receipts and simulation labels, foreign/reassigned meter rejection, notification
read state after restarting, pagination, disconnect/reconnect, stale timestamps
and logout/account switching. Do not use real payments or physical hardware for
these prototype checks.

The earlier Stage 3 APK was `android/app/build/outputs/apk/debug/app-debug.apk`,
4,463,539 bytes; SHA-256
`30c8ca7e166b027a24b5646edd7dac308ea718bc3ac7853e2921516f553021b6`.
That historical build targeted `http://192.168.193.107:8000/api/v1`;
the alwaysdata build documented below supersedes it. Java/SDK and offline wrapper build instructions above
remain applicable. The older Stage 2 checksum documents that earlier build.

Approve the financial policy for whole-UGX versus fractional debt, purchase energy-rounding residuals, no-tariff loans and overdue-after-completion; retain the existing expected-failure test until fixed. Add a mobile-safe, idempotent loan application service with stored quote/terms and no duplicate auto-disbursement. Verify a real provider, callback/reconciliation operations and notification delivery in a controlled environment before enabling `MOBILE_PAYMENT_ACTIONS_ENABLED`. Complete a physical firmware/device contract and gateway integration separately. Add domain-verified Android App Links and release signing. No signing key or provider/device credential belongs in this repository or APK.

## Welcome and account connection update (11 October 2026)

The welcome preview link and sample-data footnote are removed; the production
app no longer mounts the preview. Its source remains preserved. Debug account
requests now expose only safe request metadata, and both login/signup probes
verify readable JSON. The phone initially reported the old
`192.168.193.107:8000` API with an HTTPS localhost origin: that installed build
was not using the hosted API. The operator subsequently confirmed sign-in works
after replacing the old app with the hosted build. That is operator-reported
phone evidence; this rebuild itself has not been installed/tested by the agent.

Current artifact: `android/app/build/outputs/apk/debug/app-debug.apk`,
**4,344,725 bytes**; SHA-256
`5bea8178415b711ab40fe85f347ef2ce196e9458d0ee3b730ead085672e1b632`.
APK inspection confirms `https://shanonsimon.alwaysdata.net/api/v1`, debug origin
`http://localhost`, no old LAN address and no welcome preview link. Signature
verification passed with the same certificate documented above. Use `adb install
-r` to update; uninstalling is unnecessary when the installed certificate matches
and removes the app's local session. Copy the freshly built file rather than an
older Downloads copy.

`npm run typecheck`, `npm test` and the explicit no-isolation Node run passed
(**26 cases**). Debug Vite build, Capacitor sync and offline Gradle assembly
passed. The Chromium script was syntax-checked but not run: its browser tooling
is unavailable locally. Hosted empty login/signup POSTs returned readable JSON
400, both preflights returned 200, and a synthetic nonexistent-account login
returned JSON 401, with exact `http://localhost` CORS. These desktop probes do
not verify valid-account token issuance or phone WebView behavior. All deployed
optional and mobile financial flags remained false. No Next.js/backend runtime
code, hosted database, provider/device configuration or SMTP delivery was changed.

A signup response saying verification mail is queued is truthful: the hosted
account-mail drain must run separately. See the read-only diagnosis and scheduled
sender instructions in [the alwaysdata runbook](../backend/docs/ALWAYSDATA_TESTING.md#verification-remains-queued-after-registration).

## Consumer expansion (October 2026)

See [CONSUMER_EXPANSION.md](CONSUMER_EXPANSION.md) for current phone validation,
pending meter onboarding, honest score factors, receipt recovery, foreground
monitoring, final test evidence and the latest APK checksum. This supersedes
older LAN build metadata. Backend upload/schema review is required for the new
endpoints; there is no completed loan submission or live financial/hardware
readiness claim. Existing Next.js, account-page CSRF and email outbox are retained.
