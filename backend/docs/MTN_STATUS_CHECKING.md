# MTN Collections status diagnosis and correction

This is a patch to the existing adapter, PaymentIntent reconciliation and shared
web/Android UI. It introduces no payment policy, currency conversion, new charge
pipeline, firmware change or migration. Keep `PROTOTYPE_PAYMENT_PROVIDER=MTN_SANDBOX`
and the approved `UGX-MTN-TEST-AUTH-v1` instruction/actual EUR1 receipt separation.
Seven deferred features, hosting restrictions and relay prohibition are unchanged.

## Verified code findings versus hosted unknowns

* RequestToPay persists its UUID and external ID before I/O. HTTP202 stores
  `ACCEPTED`/PENDING, not success. Subsequent lookups use precisely that UUID in
  the authenticated HTTPS status URL; MTN does not echo a reference field in its
  JSON. An uncertain submission is **never** resubmitted. GETs to Django remain
  read-only. Status POSTs/the finite scheduler reuse the authoritative settlement
  service; network I/O is outside database-locking transactions.
* The official Collections status operation explicitly documents HTTP200 for
  both success and failure; the JSON status decides the outcome. It publishes a
  string schema **and an integer-valued success example** for the financial
  transaction ID/payer. The adapter formerly passed integers to string-only
  matching and rejected that supported representation. Exact integer IDs now
  normalize losslessly to strings. Floats, booleans, missing/oversized transaction
  IDs remain invalid. Numeric payer identity must still match the original digit
  string exactly: lost leading zeros are not reconstructed. Amounts use Decimal.
* Successful evidence still requires the trusted reference URL, matching external
  ID, exact amount, EUR currency, payer and frozen owner/purpose/source terms, plus
  a nonempty financial transaction identity and provider/transaction uniqueness.
  Missing/mismatched fields do not settle. FAILED requires matching source details
  but not a successful transaction ID. No fields are invented from client success
  flags or copied from an intent to disguise absent provider evidence.
* Old reconciliation collapsed authentication/transport/parser/matching errors
  into one generic string. It also backed ordinary PENDING checks off to an hour.
  Adapter logs now show local intent ID/reference, stage, HTTP status, allowlisted
  provider status/error code only. Persisted safe error codes distinguish auth,
  transport/schema, amount, currency, payer, external ID, reference and source
  validation. Never log exception strings, headers, payer, tokens or bodies.
* Next status check is due five seconds after accepted submission and fifteen
  seconds after a normal PENDING response. These are polling intervals, not
  settlement timers. Errors back off 30–300 seconds; the existing lease prevents
  overlapping checks. As soon as a lookup returns validated SUCCESSFUL, that same
  reconciliation call settles; it never waits for the 300-second checkout expiry.
* Web/Android share receipt-based messaging: “Checking sandbox payment status…”,
  “Payment completed”, “Payment failed”, or “Confirmation delayed”. Checkout
  expiry is local UI/retry metadata, never provider failure/cancellation. Late
  successful attempts still fulfill the frozen operation at most once. The
  existing replacement/deduplication and retained-extra-authorization rules remain.

**Not confirmed on hosted data:** outcome/submission state/test scenario for
`fcc6c1af-e0cb-4bee-b848-94137a8df770`; actual response shape; whether the scheduled
job is installed/running. Noninteractive SSH was denied. No provider call, payment
submission, hosted mutation, migration, restart or deployment was performed here.
The parser incompatibility is established from code/official examples, not proof
that this reference encountered it. The command below resolves that distinction.

## Official response/test-scenario references

* [MTN Collections API](https://momodeveloper.mtn.com/api-details#api=collection&operation=RequesttoPayTransactionStatus)
* [Public operation definition used by MTN's portal](https://ericssonbasicapi2.management.azure-api.net/subscriptions/000/resourceGroups/000/providers/Microsoft.ApiManagement/service/EricssonBasicAPI2/apis/collection/operations/RequesttoPayTransactionStatus?api-version=2022-04-01-preview)
* [Official sandbox use cases](https://momodeveloper.mtn.com/content/html_widgets/z0smm.html)

The generic API example's UGX currency does **not** change the sandbox EUR rule.
The RequestToPay test table distinguishes failure, rejection, expiry, ongoing and
delayed scenarios; other valid numbers use the ordinary success scenario. This
classification predicts a test scenario, never authorizes settlement. The
operator command prints the scenario label without printing the stored number.
No phone popup, real account number or PIN is needed for sandbox completion.

## Exact operator lookup: existing reference only, no charge or writes

After reviewing/uploading the patch below, open your existing alwaysdata terminal:

```bash
cd /home/shanonsimon/energy-sharing
export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
export DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings
export PATH=/home/shanonsimon/energy-venv/bin:$PATH
python manage.py check_alwaysdata_database
python manage.py inspect_mtn_sandbox_payment --reference fcc6c1af-e0cb-4bee-b848-94137a8df770
python manage.py inspect_mtn_sandbox_payment --reference fcc6c1af-e0cb-4bee-b848-94137a8df770 --lookup
```

First command previews stored metadata without network calls. `--lookup` requests
an access token, then **GET status for that same reference only**. It cannot call
RequestToPay, settle, change checkout/debt/energy, or bypass a source check. It
prints JSON with safe stage/HTTP/provider status, validation code, stored status,
submission classification, attempts, next check, operation linkage and scenario.
It deliberately omits provider bodies, transaction IDs, amounts, account details,
phone numbers, credentials and tokens. Share only that sanitized output.

`MATCHED; NOT SETTLED...` means evidence validated but this diagnostic command did
not write anything. The existing reconciliation job applies valid due evidence.
`EVIDENCE_*` identifies the rejected field/stage; missing fields stay unconfirmed.
HTTP401/403 indicates auth/subscription/environment access needs operator review;
HTTP404 is unknown, **not** permission to resubmit. HTTP500 or transport failure
is not provider FAILED. Never run another purchase to diagnose this reference.

After inspecting the lookup, an operator may run the following **separate,
explicit settlement operation**, using the existing authoritative service:

```bash
python manage.py reconcile_sandbox_payments --reference fcc6c1af-e0cb-4bee-b848-94137a8df770 --status-only
# Review the targeted dry-run first; this next command can settle validated evidence.
python manage.py reconcile_sandbox_payments --reference fcc6c1af-e0cb-4bee-b848-94137a8df770 --status-only --run
```

This only queries the specified reference, bypasses an old future backoff, respects
the active reconciliation lease and never invokes RequestToPay, even for a NEW
record. It does not process other checkouts. Both flags are mandatory together;
without `--run` it remains a local read-only preview. It cannot make absent or
invalid provider evidence successful. No such hosted operation was run here.

## Local-to-host rollout, operator-run only

This patch assumes the preceding UGX authorization/checkout release is deployed.
If not, review `CHECKOUT_RECOVERY.md` and its current full allowlist first. Those
earlier additive migrations include transactions0013/0014 and meter0032/0033.
Do not overwrite current token diagnostics/firmware with an older release.

From the repository root:

```bash
rsync -navic --files-from=backend/deploy/mtn-status-check.files backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
# Review the dry-run, privately back up changed server files and testing DB.
rsync -avic --files-from=backend/deploy/mtn-status-check.files backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
```

No `--delete`, private env, keys, databases, dependencies or generated artifacts
are included. On the host, after the environment/target checks above:

```bash
python manage.py migrate --plan
python manage.py check --deploy
python manage.py collectstatic --noinput
python manage.py inspect_mtn_sandbox_payment --reference fcc6c1af-e0cb-4bee-b848-94137a8df770 --lookup
python manage.py reconcile_sandbox_payments --limit 2 --max-seconds 50
```

**No migration belongs to this patch.** Stop on unexpected migrations; review
earlier release plans independently. Require database `shanonsimon_energy_test`,
host `postgresql-shanonsimon.alwaysdata.net`, user `shanonsimon`, sslmode=require
and an actual encrypted connection. Never apply a plan to an operational DB.

Restart existing site in **alwaysdata → Web → Sites → Restart**. Preserve private
credentials/keys, HTTPS, restrictive CORS, email account pages/CSRF settings.
Check `/api/v1/features/` read-only; do not initiate a payment as a health check.

Keep **Advanced → Scheduled tasks**, every minute, with logging enabled:

```bash
ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings /home/shanonsimon/energy-venv/bin/python /home/shanonsimon/energy-sharing/manage.py reconcile_sandbox_payments --run --limit 2 --max-seconds 50
```

Review actual last-run times, exits and sanitized `intent_id/status/submission/
effect/error` results. This finite job is what recovers MTN payments after apps
close. Do not assume its presence from source code. It can submit only a provably
new, unexpired instruction; uncertain/submitted references get status lookup only.
It also retains local checkout expiry work. No persistent Celery/Redis required.
Retain `drain_account_emails --send --limit 5` and legacy-provider
`complete_demo_payments --run --limit 20 --max-seconds 50` on their existing
schedules. Do not switch providers or clear old handles to unstick a reference.

Vercel is a separate update: root `frontend`, `npm ci`,
`npm run build -- --webpack`, existing server API_URL HTTPS `/api/v1` once; preserve
auth/environment/CORS. Review and redeploy the current branch through the existing
Vercel project (no commit/push/deploy done here). Installing an updated APK does
not update the website. Android uses the same shared status component and HTTPS
Django API; keep the existing application ID/signing identity.

## Verification

Local tests mock provider/device transport and use only isolated PostgreSQL on
port55445. They do not demonstrate actual MTN, hosted scheduler, phone or board
operation. The coordinated local evidence/build results are recorded below when
completed.

### Executed locally, 23 November 2026

| Check | Result |
| --- | --- |
| Final combined isolated PostgreSQL suite | 113 tests, OK; provider/device transport mocked |
| Existing CORE settlement/allocation/financial/auth suite | 93 tests, OK with 1 retained expected failure |
| Model/migration check | No changes in loan, meter or transactions |
| Web contract tests | 15 files passed |
| Mobile contract/render/auth tests | 15 files passed; actual shared TSX rendered for both surfaces |
| Mobile strict TypeScript + Vite debug bundle + Capacitor sync | Passed |
| Next.js production build including strict TypeScript | Passed, 49 pages; existing middleware/browser-data warnings only |
| Android wrapper `assembleDebug` | BUILD SUCCESSFUL, offline; existing signing key |
| APK v2 signature and previous certificate comparison | Verified; same certificate |
| APK assets vs current mobile/dist | Byte-for-byte match; HTTPS API present, previous LAN URL absent |
| Actual MTN transaction/provider status or phone/ESP32 testing | Not performed |

The retained CORE expected failure is overdue calculation after completion; no
financial policy change is made by this patch. An intermediate test process
straddled a service/command edit and was discarded; the final clean 113-test run
above verifies the complete frozen code. Initial test-environment prerequisites
were installed only into `/tmp`; project dependency versions were not changed.

Commands, from repository root (isolated local PostgreSQL port55445 only):

```bash
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --sandbox-profile --slow-test-cleanup transactions.tests_mtn_status loan.tests_mtn_transition transactions.tests_checkouts transactions.tests_ugx_authorization loan.tests_ugx_lab meter.tests_mtn_device meter.tests_device_diagnostics backend.tests_feature_flags
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --slow-test-cleanup transactions.tests_payment_settlement meter.tests_allocation_delivery loan.tests_financial_correctness backend.tests_feature_flags accounts.tests_authentication
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --check-migrations
npm --prefix mobile run typecheck
(cd mobile && node --test --test-concurrency=1 tests/*.test.mjs)
(cd frontend && node --test --test-concurrency=1 tests/*.test.mjs)
(cd frontend && NODE_OPTIONS=--max-old-space-size=1536 npm run build -- --webpack)
(cd mobile && VITE_API_BASE_URL=https://shanonsimon.alwaysdata.net/api/v1 VITE_ACCOUNT_COMPLETION=browser npm run android:sync:debug)
```

The public hosted features endpoint was read without credentials: it reports
MTN_SANDBOX, customer currency UGX, purchases/repayments enabled, and the approved
UGX-MTN-TEST-AUTH-v1 authorization with separate EUR1 receipt and SANDBOX energy.
This verifies advertised capabilities only, not credential validity, the supplied
reference's outcome or a running reconciliation schedule.

### Updated debug APK

* Absolute path: `/home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk`
* Bytes: `4635116`
* SHA-256: `a713095b83427fe682280db8789b34a05030f5491f281571d8da357cea99a17d`
* ID: `org.gpawa.consumer.prototype`; version `1.0` / code `1`; minimum API24,
  target/compile API36.
* Embedded API: `https://shanonsimon.alwaysdata.net/api/v1` exactly once.
* Certificate SHA-256, same as preceding testing APK:
  `e9fb53040e78b6a525b67462cc5cc72a656de66ebe6c55061714e785eae86b4c`.

Build used Java21, the existing Gradle8.14.3 wrapper/caches, Android SDK36 /
Build Tools35.0.0, `--offline --no-daemon --max-workers=2`, existing
`mobile/.android-signing/debug.keystore`, and the documented debug signing
identity. The key was not generated, replaced, copied into this package or printed.
Gradle needed sandbox socket permission; its offline build succeeded. Signature
was verified using `build-tools/35.0.0/apksigner`; embedded bundle was compared to
current `mobile/dist`. No connected-device install/launch was performed.

From WSL with a device already available to adb:

```bash
/home/shanon/Android/Sdk/platform-tools/adb install -r /home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk
```

Or copy via `\\wsl.localhost\<your-WSL-distribution>\home\shanon\projects\next_projects\Energy-sharing-project\mobile\android\app\build\outputs\apk\debug\app-debug.apk`
and use Windows adb or install from Files. Keep the existing app installed;
matching signing identity permits an update without clearing pending handles.
This is a debug testing app, not a production release.
