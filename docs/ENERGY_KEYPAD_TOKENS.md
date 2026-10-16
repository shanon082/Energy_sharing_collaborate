# Eleven-digit enrollment and online keypad tokens

This is a software implementation, not commissioned ESP32 firmware or physical
meter testing. The hosted consumer deployment remains LOCAL_DEMO. New tokens
can be displayed there after the operator opts in; **all bench/physical device
routes remain blocked on alwaysdata**. The complete redemption/application
exercise uses a separate loopback bench database and independent SQLite device
journal. A token from the hosted database is deliberately not usable in that
bench database. No STS compatibility or offline token validation is claimed.

## Accounting and history

New enrollment accepts a string of exactly 11 ASCII digits, trims surrounding
whitespace only and preserves leading zeros. Internal spaces, Unicode numerals,
signs and punctuation fail with “Enter your 11-digit meter number.” Existing
nonconforming meter identifiers remain unchanged and readable. Their enrollment
retry through the new form is unavailable; do not pad or replace them. Run the
read-only `report_meter_numbers` command for IDs/lengths, not personal records.
New software-bench provisioning requires a conforming identifier.

`EnergyAllocation` is the authority for attributable energy. Its unique source
is a settled purchase, disbursed CORE loan, or disbursed sandbox/demo loan.
Repayment reduces debt and issues no energy/token. Existing accepted tariff,
money, residual and repayment snapshots are unchanged. CORE UGX, SANDBOX EUR
and UGX_DEMO remain separate. Energy allocations use 0.01 kWh = 10 Wh; delivery
uses the exact integer Wh equivalent. Local consumption can debit one Wh.

`EnergyKeypadToken` has one protected allocation, source-owner/meter/environment
snapshots, exact Wh, a frozen command UUID, unique HMAC lookup and encrypted
15-digit value. `secrets.randbelow` generates digits including leading zeros.
Issuance happens inside new allocation/financial transactions. A digest
collision retries with a database savepoint. Existing allocation retries recover
the existing token; they never backfill a missing historical token. No historical
wallet conversion, token replay or financial repair is performed.

Fernet authenticated encryption permits owner redisplay; HMAC-SHA256 permits
lookup without storing plaintext. Keys must be private and backed up separately
from data. `ENERGY_TOKEN_ENCRYPTION_KEYS` is a comma-separated list: first key
encrypts, all keys decrypt. Keep old keys while old ciphertext exists; rotation
and re-encryption need a separately reviewed maintenance procedure. **Keep
ENERGY_TOKEN_LOOKUP_KEY stable**: changing it invalidates existing lookup and
redisplay verification. There is no automatic lookup-key rotation/reindex.
Missing keys fail closed, never create a replacement token. Losing both keys
and backups requires explicit entitlement reconciliation, not reissue/replay.

## Lifecycle and HTTP contract v1

Owner-only GET `/api/v1/meter/energy-tokens/?allocation_id=123` (or `meter_id=45`)
uses consumer authentication/permissions. It returns at most 100 newest matching
rows, with private/no-store and no-referrer headers. Allocation filtering allows
retrieval of older details independently of the meter list limit. Other owners
see no rows. Tokens are never URL parameters or request-log fields. Raw tokens
are held in authorized UI memory; copy is explicit and users should clear their
clipboard. Do not add analytics/session replay to these views.

```json
{"tokens":[{"id":"11111111-1111-4111-8111-111111111111","allocation_id":123,
"token":"000000000000001","meter_number":"00000001234","energy_wh":"1000",
"energy_kwh":"1","environment":"UGX_DEMO","source":"PURCHASE",
"source_reference":"demo-example","state":"ISSUED",
"application_environment":"UNCONFIRMED","created_at":"2026-10-17T09:00:00Z"}],
"bench_only":true}
```

The numeric token above is an illustrative fixture, not a credential or a valid
hosted token. Purchase/loan details and history show meter, energy, source,
copy action and loading status. Funding alone says **Awaiting meter
confirmation**. APPLIED here always says **software bench confirmation only**.
Physical remaining credit, contact, relay feedback and readings remain unavailable
without independent device evidence. This change adds no physical telemetry.

Device POSTs require `X-Bench-Device-Id` (public UUID) and
`X-Bench-Device-Token` (private, >=32 characters, stored as a password hash).
Consumer JWTs do not authenticate devices. Bindings snapshot owner, meter,
environment, binding epoch and persistent storage UUID. The server derives the
meter; a body-supplied destination is never an authorization. Credentials must
not be shared between devices. TLS is required for any future non-loopback
transport; this harness rejects non-loopback servers and redirects.

1. POST `/api/v1/bench-device/v1/session/`:
   `{"contract_version":1,"storage_id":"22222222-2222-4222-8222-222222222222","initialize":true,"application_counter":0}`.
   Initialization is permitted only for a fresh unused binding. Later sessions
   use `initialize:false` and the persistent journal's counter. A changed storage
   identity or regressed counter requires reconciliation.
2. POST `/api/v1/bench-device/v1/redeem/`:
   `{"contract_version":1,"token":"000000000000001"}`.
   Validates source, owner, current assignment, inventory/environment and exact
   energy. Shared PostgreSQL rate buckets limit all IP attempts to120/minute
   and authenticated devices to30/minute; errors also count, across workers.
   Do not put tokens in URLs, logs or diagnostics. Generic token errors reveal
   no other consumer details. Missing/bad/revoked credentials401, malformed400,
   disabled404 (host503), binding/conflict409, rate limit429.
3. Response `{"command":{...}}` contains the following immutable command:

```json
{"contract_version":1,"type":"BENCH_CREDIT","bench_only":true,
"device_id":"33333333-3333-4333-8333-333333333333","meter_number":"00000001234",
"binding_epoch":1,"environment":"UGX_DEMO",
"storage_id":"22222222-2222-4222-8222-222222222222",
"allocation_id":123,"delivery_id":456,
"command_id":"44444444-4444-4444-8444-444444444444","credit_wh":1000,
"payload_digest":"<SHA256_OF_CANONICAL_COMMAND_WITHOUT_THIS_FIELD>"}
```

Canonical digest is SHA256 of JSON with sorted keys and separators `,` and `:`.
It detects changed command contents; it is not a replacement for authenticated
transport or a firmware signature. The raw numeric token is not sent back to
the device in the command.

4. Device atomically commits command identity, full immutable payload, energy
   credit and original receipt together with durable storage before ACK.
   Duplicate identical commands return the stored receipt, with no second
   credit; changed content for an existing UUID fails.
5. POST `/api/v1/bench-device/v1/ack/` includes command binding fields
   `contract_version,device_id,command_id,delivery_id,allocation_id,binding_epoch,
   environment,storage_id,credit_wh,payload_digest`, plus
   `type:"BENCH_APPLIED",receipt_id:<UUID>,application_counter:<positive integer>,
   applied_at:<timezone-aware ISO timestamp>`.
   The exact authenticated receipt is persisted uniquely per delivery and
   device/counter. Duplicate identical ACK returns `newly_applied:false`.
   Changed receipt identity/content fails. Delayed earlier receipts can arrive
   after a later counter; uniqueness and the retained high-water counter prevent
   duplicate application without discarding a legitimate lost ACK.

`ISSUED → DELIVERY_PENDING → APPLIED`: redeem atomically reserves the entire
allocation in one MeterDelivery and returns its frozen command on every retry.
New token allocations cannot enter automatic delivery. An existing automatic
reservation prevents issuance. The simulator worker rejects keypad deliveries.
HTTP200/redeem does not mark APPLIED. Only ACK commits it. If ACK is lost, the
reservation remains pending; retry/recover the original command/receipt.
Already APPLIED redemption returns409 `TOKEN_ALREADY_USED`.

There is currently **no automatic token expiry, token cancellation, timeout
release or replacement credit**. Device credential revocation preserves tokens,
commands and uncertain reservations. Future expiry/revocation needs a separately
approved entitlement-preserving reconciliation policy. An authenticated device's
ACK is an attestation: Django cannot prove remote flash durability. The harness
tests durable behavior independently; real firmware must pass power-cut tests.

## Isolated software bench (never alwaysdata)

Use a dedicated local PostgreSQL database/role and a private environment file
outside the checkout (directory0700,file0600). Copy `backend/bench.env.example`
as a naming template; fill private values. Never import hosted data, secrets,
tokens or credentials. `backend.bench_settings` refuses a non-loopback database
or a database without prefix `gpawa_bench_`, and requires explicit enablement.
It fixes LOCAL_DEMO, disables all seven optional flags, physical transports,
Celery eager mode and real-provider configuration. Self-declared enrollment is
not device commissioning; explicit bench provisioning is a separate action.

```bash
cd /home/shanon/projects/next_projects/Energy-sharing-project/backend
export DJANGO_SETTINGS_MODULE=backend.bench_settings
export BENCH_ENV_FILE=/absolute/private/path/bench.env
venv/bin/python manage.py check
venv/bin/python manage.py migrate --plan
# Only after confirming this is the isolated gpawa_bench_* database:
venv/bin/python manage.py migrate
venv/bin/python manage.py runserver 127.0.0.1:8001 --noreload
```

Use normal local consumer API registration/verification and enrollment with
isolated users. Configure a bench tariff through existing administration; do not
invent a new tariff or reuse a live ledger. New funded purchases/loans create
bench tokens. LOCAL_DEMO completion remains server-authoritative; the existing
finite `complete_demo_payments --run --limit 20 --max-seconds 50` command may run
locally (use spaced CLI arguments as in the hosting example below).

In another shell with the same private profile and bench virtualenv:

```bash
read -r -s -p 'New private bench device credential: ' BENCH_DEVICE_TOKEN
export BENCH_DEVICE_TOKEN
venv/bin/python manage.py provision_bench_device <METER_ID> --environment UGX_DEMO --confirm-software-bench
# Copy the public UUID printed above; journal parent directory must be private.
venv/bin/python device_bench/client.py --device-id <DEVICE_UUID> --state /private/path/device.sqlite --initialize
# Later attempts/reboots: omit --initialize. Token prompt is hidden, not an arg.
venv/bin/python device_bench/client.py --device-id <DEVICE_UUID> --state /private/path/device.sqlite --drop-ack
venv/bin/python device_bench/client.py --device-id <DEVICE_UUID> --state /private/path/device.sqlite --recover
venv/bin/python device_bench/client.py --device-id <DEVICE_UUID> --state /private/path/device.sqlite --consume-wh 1
venv/bin/python manage.py revoke_bench_device <DEVICE_UUID> # preview only
# --confirm revokes only after explicit operator review; no automatic rotation.
unset BENCH_DEVICE_TOKEN
```

The client defaults to `http://127.0.0.1:8001/api/v1`, uses bounded HTTP timeouts,
and never contacts ThingsBoard/MTN or controls a relay. SQLite WAL + FULL sync
commit credit and receipt atomically. Loaded credit can be consumed locally
without network; a new token always requires online server validation.

On journal loss/reset, stop redemption and retain server reservations. Automatic
replacement provisioning is refused even after revocation. Reconcile receipts,
remaining credit, consumption and paid entitlement before any manually reviewed
replacement. On database restore, **quarantine dispatch and redemption first**;
compare restored tokens/commands/receipts and device journals before enabling.
Frozen issuance command UUIDs mitigate a lost-delivery-row retry, but full
database/journal rollback cannot be made safe by UUID dedup alone. Never restore
an old device journal then continue spending without reconciliation. Retain
encrypted backups with keys separately; no automated reissue/replay is provided.

## Hosted consumer upload and manual rollout

Run locally from the repository root. This allowlist preserves the prior consumer
baseline plus the new runtime files; no deployment is performed by this task.
Review the dry-run and take an operator-managed database/private-config backup.
Use a maintenance window: pause site traffic while uploading and applying the
reviewed additive schema so new delivery/token queries cannot precede migration.

```bash
rsync -avzn --files-from=backend/deploy/consumer-sandbox.files \
  --exclude='.env*' --exclude='*.pem' --exclude='*.key' --exclude='*.keystore' \
  --exclude='venv/' --exclude='__pycache__/' --exclude='*.sqlite*' \
  --exclude='node_modules/' --exclude='staticfiles/' --exclude='media/' \
  backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
rsync -avz --files-from=backend/deploy/consumer-sandbox.files \
  --exclude='.env*' --exclude='*.pem' --exclude='*.key' --exclude='*.keystore' \
  --exclude='venv/' --exclude='__pycache__/' --exclude='*.sqlite*' \
  --exclude='node_modules/' --exclude='staticfiles/' --exclude='media/' \
  backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
# Never add --delete, upload local .env, or upload bench settings/credentials.
```

Keep the working alwaysdata WSGI/profile, Django-hosted account pages, CSRF
configuration, `http://localhost` debug CORS origin and HTTPS release policy.
Edit `/home/shanonsimon/.config/energy-sharing/backend.env` privately with an
editor; parent0700,file0600. Add the names from `energy-tokens.env.example`.
Generate independent random keys privately (Fernet.generate_key for encryption,
at least32 random characters for HMAC). Do not display or commit values. Back up
the keys before opting into `ENERGY_TOKEN_ISSUANCE_ENABLED=true`. Leave
`BENCH_DEVICE_ENABLED=false`, all seven FEATURE_* flags false and existing
financial/device restrictions unchanged. This switch affects **new** sources
only. Hosted tokens wait for a future commissioned transport; they cannot load
household electricity or cross into the local bench database.

On the host, commands for operator execution only:

```bash
cd /home/shanonsimon/energy-sharing
. /home/shanonsimon/energy-venv/bin/activate
export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
export DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings
python -m pip install -r requirements-alwaysdata.txt
python -m pip check
python manage.py check_alwaysdata_database
python manage.py showmigrations meter
python manage.py migrate --plan
python manage.py sqlmigrate meter 0031
python manage.py report_meter_numbers
# STOP if host/database/user are not the confirmed testing target, or plan
# contains unexpected/unreviewed migrations. Only after operator review:
python manage.py migrate meter 0031
python manage.py collectstatic --noinput
python manage.py check --deploy
```

Expected database: `shanonsimon_energy_test`, role `shanonsimon`, PostgreSQL
host `postgresql-shanonsimon.alwaysdata.net`, TLS required. Migration0031 is
additive: token/device/rate/receipt tables and delivery transport/binding/payload
fields; no historical rows are tokenized, renamed, converted or replayed.
Prerequisite migrations remain part of the reviewed plan. Restart via alwaysdata
Web → Sites → existing Django site → Restart; do not change its WSGI entrypoint
`backend/alwaysdata_sandbox_wsgi.py` or Python3.12 virtualenv.

Keep the existing one-minute finite jobs, same private environment/settings:
`python manage.py drain_account_emails --send --limit 5` and
`python manage.py complete_demo_payments --run --limit 20 --max-seconds 50`.
There is no physical delivery worker, Redis/Celery daemon or device job to enable.
The new keypad path needs none: redeem/ACK persist its database outbox command.
GET status is read-only. No hosted bench provisioning or client command belongs
in the scheduler. Check HTTPS `/api/v1/features/`, credential-free login400,
account pages/CSRF, owner token reads after login and bench POST503. Do not
send provider requests as a deployment health check.

## Acceptance and remaining firmware prerequisites

- New11-digit enrollment preserves leading zeros; historical meters stay
  readable; concurrent claims retain unique ownership.
- New settled purchase or disbursed approved loan yields one owner-visible
  15-digit token. Pending/failed/repayment/rejected sources yield none.
- Purchase/loan status and token-loading status remain separate. Copy/details
  survive app restart via server retrieval; no token is cached persistently.
- Isolated provisioned software device redeems once; repeated concurrent
  redemption returns the same command, never a second reservation.
- Apply durably, drop ACK, restart, recover original receipt; verify one credit
  and pending→software-bench APPLIED only after authenticated ACK.
- Repeat command/ACK; changed content, wrong meter/environment, reset journals,
  invalid/revoked credentials and consumer JWT impersonation fail closed.
- Automatic delivery cannot also consume a token's allocation; no timeout
  releases an uncertain reservation. Repayment does not generate energy.
- Phone: login, select meter, assessment, loan/purchase→receipt/token, history,
  copy, disconnect/reconnect, Back, logout/account switch. No physical success
  is shown for hosted pending tokens. Actual phone testing is outstanding.

Before ESP32 work: agree secure provisioning/rotation and storage protection,
TLS/time handling, flash wear/power-loss guarantees, counter/journal recovery,
meter replacement and restore reconciliation; choose radio and gateway. The
methodology names LoRa: point-to-point LoRa needs a custom gateway protocol;
LoRaWAN instead needs a gateway, network/application server and payload security.
Django does not receive LoRa radio frames. This online contract is a proposed
firmware interface pending hardware review, not physical commissioning. Start
with transport tests, then low-voltage bench tests and repeated power cuts before
any mains/relay validation under an approved safety procedure.

See HARDWARE_INTEGRATION_READINESS.md for retained legacy containment, telemetry
contract and hosting limitations. Production physical delivery remains blocked.

## Local verification (17 October 2026)

Commands run against an account-owned disposable PostgreSQL cluster on loopback
port55445, role `gpawa_alwaysdata_test`. `deploy/test-hosting.py` refuses other
targets, disables local .env loading and prohibits external requests. Dependencies
needed only by this checkout's tests were installed under `/tmp`, not upgraded
in the existing virtualenv. No operational or hosted migration was executed.

```bash
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py \
  transactions.tests_demo_payments loan.tests_meter_credit_tariffs \
  loan.tests_demo_assessment meter.tests_sandbox_enrollment \
  meter.tests_enrollment_review meter.tests_allocation_delivery \
  meter.tests_hardware_readiness transactions.tests_payment_settlement \
  loan.tests_financial_correctness backend.tests_feature_flags accounts.tests_authentication
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py \
  --sandbox-profile backend.tests_alwaysdata accounts.tests_account_pages \
  transactions.tests_demo_payments backend.tests_feature_flags
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py \
  --sandbox-profile \
  meter.tests_enrollment_review.EnrollmentReviewTests.test_profile_page_csrf_and_exact_write_exception \
  meter.tests_enrollment_review.EnrollmentReviewTests.test_profile_onboarding_score_monitoring_allowed_financial_actions_blocked
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py \
  --bench-profile meter.tests_energy_tokens
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py \
  --bench-profile --check-migrations
npm --prefix mobile run typecheck
npm --prefix mobile test
cd mobile
node --test --test-isolation=none tests/*.test.mjs
cd ..
cd frontend
npx tsc --noEmit
node --test tests/*.test.mjs
npx eslint src/components/energy-token-card.tsx src/components/dashboard/meter-energy-tokens.tsx \
  src/lib/energy-token.ts src/lib/meter-validation.ts src/lib/meter-enrollment.ts
```

- Combined backend: **188 tests OK**, two hosted-only checks skipped in base
  profile; one existing CORE overdue-after-completion expected failure retained.
  Initial failures from invalid enrollment/phone test fixtures were corrected;
  the full final combined run passed. Existing caught legacy wallet-mirror unique
  constraint warnings still occur; they are not new token accounting writes.
- Hosted authentication, CSRF, outbox and restrictions: **66 tests OK**.
  The two staff/onboarding cases skipped in the base run were separately
  executed under `--sandbox-profile`: **2 tests OK**.
- Isolated token bench: **17 tests OK**, including the authenticated JSON
  session/redeem/ACK/owner-status journey, concurrent issuance,
  issuance/reservation race, redeem/ACK races, independent journal restart,
  lost/delayed ACKs, shared HTTP rate limit, owner isolation and rejected sources.
- Migration dry-run: no missing changes in loan/meter/transactions.
- Mobile typecheck, nine test-file suites (**58 cases** in the explicit
  no-isolation run) and Vite debug bundle/Capacitor sync
  pass. Shared web typecheck, feature-test file and focused new-component lint
  pass. `npm run build -- --webpack` **passes the full Next.js production build**,
  including TypeScript, page-data collection and prerendering, with no strict-check
  bypasses. The default sandboxed Turbopack attempt stalled; the sandboxed webpack
  attempt failed, and a four-minute network-enabled attempt timed out during
  TypeScript after compilation. Google Fonts DNS fails inside the sandbox and
  succeeds outside it. The final network-enabled wrapper with a ten-minute bound
  completed successfully. Existing middleware deprecation and baseline-browser
  mapping warnings remain; no dependency upgrade or font/design change was made.
  A standalone typecheck accidentally overlapped generated-file replacement and
  reported temporary missing `.next/types` files; the sequential rerun after
  the successful build **passes**. No source or generated-type checks were suppressed.

Successful production command (network access required for existing Google Fonts):
`cd frontend && timeout --signal=TERM --kill-after=15s 600s npm run build -- --webpack`.
The checked-in build configuration is unchanged; the CLI selects webpack for this
verification. `git diff --check` passes.

### Debug APK

Built with Java21, existing Linux SDK (compile/target36, minimum24), wrapper
Gradle8.14.3, existing debug keystore and application ID
`org.gpawa.consumer.prototype`, version1.0/code1. The initial sandbox Gradle
lock-service failure was resolved by running the same offline wrapper outside
the networking sandbox; no dependency or signing-key replacement was needed.

```bash
cd /home/shanon/projects/next_projects/Energy-sharing-project/mobile
VITE_API_BASE_URL=https://shanonsimon.alwaysdata.net/api/v1 npm run android:sync:debug
cd android
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 \
ANDROID_HOME=/home/shanon/Android/Sdk \
ANDROID_USER_HOME=/home/shanon/projects/next_projects/Energy-sharing-project/mobile/.android-signing \
GRADLE_USER_HOME=/home/shanon/projects/next_projects/Energy-sharing-project/mobile/.gradle-user \
PATH=/usr/lib/jvm/java-21-openjdk-amd64/bin:/usr/bin:/bin \
./gradlew --offline --no-daemon assembleDebug \
  -Pandroid.injected.signing.store.file=/home/shanon/projects/next_projects/Energy-sharing-project/mobile/.android-signing/debug.keystore \
  -Pandroid.injected.signing.store.password=android \
  -Pandroid.injected.signing.key.alias=androiddebugkey \
  -Pandroid.injected.signing.key.password=android
```

Artifact: `/home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk`.
Size: **4,478,901 bytes**. SHA256:
`f3ff45da24cbcb37703d0a132bdd2a494f9b0cf4822695ff9c7ba6ef0cb6515d`.
apksigner verifies its v2 signature and existing certificate SHA256
`e9fb53040e78b6a525b67462cc5cc72a656de66ebe6c55061714e785eae86b4c`.
ZIP inspection confirms the exact HTTPS API URL, no doubled `/api/v1`, no old
LAN address, token UI and debug app origin `http://localhost`. No credentials
were embedded. This is not a release or a claim of physical-phone testing.

```bash
adb install -r /home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk
# Optional WSL → Windows copy; substitute your actual Windows username:
cp /home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk /mnt/c/Users/<WINDOWS_USER>/Downloads/gPawa-debug.apk
```

Do not uninstall to update a matching certificate; if Android reports a signature
mismatch, inspect the installed artifact rather than generating another key.
Backend schema/private opt-in rollout must precede expecting new tokens on the
hosted phone journey. Software-bench acceptance uses isolated records and the
local client, not the hosted APK as a physical device.
