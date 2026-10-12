# Consumer loan and MTN sandbox build

The alwaysdata **ordinary profile remains read-only**. The new backend
`backend.alwaysdata_sandbox_settings` / `alwaysdata_sandbox_wsgi.py` is an explicit
operator opt-in. Follow [deployment and policy instructions](../backend/docs/CONSUMER_SANDBOX.md)
before expecting the installed APK to offer sandbox actions. This build queries
`features/` and fails closed; it cannot enable the profile or the seven optional
features through request flags.

Dashboard, Loans and Activity expose the shared consumer form when Django returns
`sandbox.enabled=true`, currencyEUR, providerMTN_SANDBOX and physical_deliveryfalse.
After login, use **Add your meter**: the registered/verified user's entered number
is assumed to belong to them for prototype testing. It links immediately and is
automatically selected; no staff approval, inventory command or simulator is needed.
Numbers stay trimmed strings (including leading zeros); foreign/core/pre-created
inventory collisions are unavailable. Existing pending requests offer an explicit
retry; declined requests still need support review. SELF_DECLARED ownership and
hardware connection pending are shown honestly. Then review a server quote, explicitly
accept terms, submit the actual loan application, and view its automatic decision
and identifiable allocation. Payments use MTN's real sandbox HTTP adapter on Django;
the app never contains provider keys or claims a mocked payment is real.

All test money is labelled **EUR TEST / SANDBOX / NO REAL MONEY**, separate from
the old read-only UGX loan position/history. A starter allowance is not a real
credit score. Test energy allocation, simulator acknowledgement and physical
readings remain distinct; hosted sandbox allocation does not deliver to hardware.
Self-repayments never create energy. Purchase remainder/repayment excess stay
visible on the receipt and are retained for reconciliation.

After interruption, account-scoped UUID handles recover stored loan/payment
records by GET, including records older than the first history page. Financial
POSTs are never replayed automatically. Persistent authentication continues to
use the existing Android Keystore storage. Pending receipts block new payment
initiation; explicit status checks use server leases/backoff. The scheduled
backend reconciler continues without the app. Offline values show stale timestamps;
no offline financial request queue exists. Logout clears local retry handles,
but does not cancel the server's obligations. Recovery also fetches all server
pending receipts when local handles are absent.

Reusable code: `frontend/src/lib/sandbox.ts` (capabilities, exact string contracts,
validation, recovery handles) and `frontend/src/components/sandbox-consumer.tsx`
(shared presentational/workflow component). Transport is injected: Android uses
SessionManager; web uses the existing cookie-authenticated Next proxy. No Next
Server Action, cookie utility or route-handler enters the APK. Vite deduplicates
React/ReactDOM when consuming the shared component. Web has `/dashboard/sandbox`
and sandbox panels on Loans/Buy Units, using the same services. No web static export
or dependency upgrade. Capacitor differs from the methodology's Kotlin approach.

Build from the repository's mobile directory:

```bash
npm run typecheck
node --test --test-isolation=none --test-reporter=spec tests/*.test.mjs
VITE_API_BASE_URL=https://shanonsimon.alwaysdata.net/api/v1 VITE_ACCOUNT_COMPLETION=browser npm run android:sync:debug
cd android
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 ANDROID_HOME=/home/shanon/Android/Sdk ANDROID_USER_HOME=/home/shanon/projects/next_projects/Energy-sharing-project/mobile/.android-signing GRADLE_USER_HOME=/home/shanon/projects/next_projects/Energy-sharing-project/mobile/.gradle-user PATH=/usr/lib/jvm/java-21-openjdk-amd64/bin:$PATH ./gradlew --offline --no-daemon --max-workers=2 '-Dorg.gradle.jvmargs=-Xmx768m -XX:ActiveProcessorCount=2' assembleDebug -Pandroid.injected.signing.store.file=/home/shanon/projects/next_projects/Energy-sharing-project/mobile/.android-signing/debug.keystore -Pandroid.injected.signing.store.password=android -Pandroid.injected.signing.key.alias=androiddebugkey -Pandroid.injected.signing.key.password=android
```

Use the **existing ignored key**, never `~/.android/debug.keystore` or a newly
generated identity. APK update: `adb install -r app-debug.apk`. The standard debug
key password above is not a production signing secret. API URL construction joins
`/api/v1` once. Debug originhttp://localhost; releasehttps://localhost. Release
requires HTTPS. No need to host Next.js for verification/password recovery.

See [local validation and artifact evidence](../backend/docs/SANDBOX_VALIDATION.md).
Actual MTN, deployment and physical-phone acceptance remain separate. The full
phone checklist is in the backend runbook; production financial policy and
physical firmware integration have not been approved or implemented here.
