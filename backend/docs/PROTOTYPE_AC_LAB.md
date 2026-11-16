# ESP32-S3 / PZEM AC lab milestone — physical output disabled

This is a local implementation, not a hosted or electrical commissioning report.
No hosted migrations, provider/ThingsBoard/device calls, key rotations or firmware
writes were performed. The existing Android design is preserved.

## Source and previous absence

Inspected current checkout c1d25ad plus existing uncommitted work. There was no
prototype-device implementation or URL registration. The three existing
`bench-device/v1/{session,redeem,ack}/` routes are **software bench only**, with a
different contract and explicit alwaysdata denial. They remain unchanged.

Actual firmware read at
`C:\Users\USER\OneDrive\Documents\Arduino\gPawa-S3-Keypad-Update`:
`docs/API_CONTRACT.md`, `GpawaAC/Firmware.cpp`, `GpawaAC/Protocol.h`, and
`GpawaAC/HardwareConfig.h`. Protocol `GPAWA_PZEM_V1` uses HTTPS POST JSON, native
device headers, integer counters, a fourteen-field canonical credit command and
microWh telemetry. Source macros currently read `GPAWA_USB_EXERCISE 1` and
`GPAWA_COMMISSIONED_OUTPUT 0`. The server cannot independently prove what firmware
is flashed or whether wiring physically disconnects the relay. USB exercise mode bypasses online redemption and uses local exercise tokens.
For the network/PZEM test, an operator must compile `GPAWA_USB_EXERCISE=0` while
retaining `GPAWA_COMMISSIONED_OUTPUT=0`. This read-only combination never configures
or drives the relay GPIO. Confirm the actual image and physically disconnected
relay/load before connecting the board; no mains/load switching is authorized here.

## Capability, identity and money boundaries

`PROTOTYPE_AC_LAB_ENABLED` defaults false and uses explicit boolean parsing, only
in `backend.alwaysdata_sandbox_settings`. Services also require alwaysdata testing,
consumer sandbox, LOCAL_DEMO provider and hard-coded disabled relay output. The
middleware allowlists **only the four exact POST routes below** when enabled;
each independently authenticates and validates the binding. Unrelated physical,
bench, CORE and live-provider operations retain their restrictions. All seven
optional features remain disabled/retired. Account CSRF, authentication, email
schedule, payment completion schedule and keys are unchanged.

Provisioning creates one random credential (only its password hash and uniqueness
fingerprint are stored in Django), a storage UUID and a device UUID. A verified
staff ADMIN/OPERATOR authorizes it, recorded as `provisioned_by/created_at`.
The selected meter must be active, owned by the explicit verified consumer,
11 ASCII digits, and test inventory. No previous bench or AC binding is replaced.
No consumer enrollment endpoint provisions a device. The AC device model enforces
one active lab binding per meter and an output-disabled UGX_DEMO/AC_LAB constraint.
Revocation records staff actor/time and retains all reservations/receipts.

Device headers are `X-Device-Id` and `X-Device-Token`. User JWTs/session cookies do
not authenticate these routes. Credentials/tokens are never logged or put in URLs;
request fields are bounded to 4096 bytes, schema-checked, duplicate JSON keys
rejected and authentication attempts share PostgreSQL rate buckets. Credentials
must stay in the private device configuration, outside Git. Do not enable request
body/header capture in hosting/APM logs. No CORS change is needed for ESP32's
native HTTPS client; installed app consumer origins remain unchanged.

Only source-backed UGX_DEMO allocations may be reserved: LOCAL_DEMO settled
purchases also require the matching UGX_DEMO settlement receipt; approved demo
loans remain a valid separate entitlement source. EUR/CORE records are not
converted, tokenized retrospectively or provisioned. Repayment does not allocate
energy. The existing encrypted token and lookup keys remain authoritative.

## Routes and lifecycle

Every successful response repeats the authenticated identity below. The firmware
must fill its provisioned values; these are non-secret example placeholders:

```json
{"protocol":"GPAWA_PZEM_V1","device_id":"11111111-1111-4111-8111-111111111111","meter_number":"00000001234","storage_id":"22222222-2222-4222-8222-222222222222","binding_epoch":1,"environment":"UGX_DEMO","hardware_class":"AC_LAB"}
```

All four POST JSON routes live under `/api/v1/prototype-device/v1/`:

| Suffix | Additional fields | Effect and retry |
|---|---|---|
| `session/` | `boot_id`, `boot_counter`, `application_counter`, `initialize`, `ack_pending`, `credited_uwh`, `consumed_uwh`, `uncertain_uwh`; positive application counter adds `last_command_id`, `last_payload_digest`, `last_receipt_id` | Authorizes a durable boot. Same boot retry safe; retired boot/storage/counter rollback rejected. Returns `status: READY`. |
| `redeem/` | `token` (15 ASCII digits), `application_counter` | HMAC lookup plus encrypted integrity/source/binding checks. Reserve entire existing allocation once in `MeterDelivery`, freeze issuance command UUID and next sequence. Returns `{identity..., command: {...}}`. One unresolved command; identical pending-token retry returns same frozen payload. Applied token rejects. |
| `ack/` | `type: AC_LAB_APPLIED`, `command_id`, `command_sequence`, `payload_digest`, `credit_wh`, `receipt_id`, `applied_at` (UTC), `allocation_id`, `delivery_id` | Match every command/binding field, atomically persist unique receipt and mark delivery/token APPLIED. Exact duplicate returns identical accepted receipt; changed receipt rejects. |
| `telemetry/` | Firmware fields listed below | Append deduplicated owner-bound measured evidence. Never creates credit, ACK, allocation or financial effect. Returns `status: ACCEPTED`, `boot_id`, `sequence`. |

Frozen command fields are identity's seven fields plus `allocation_id`,
`delivery_id`, `command_id`, `command_sequence`, `credit_wh`, `type: AC_LAB_CREDIT`,
`payload_digest`. Digest is SHA256 over the other thirteen fields sorted
alphabetically, compact JSON. Amount is exact positive integer Wh, <=1,000,000,
divisible by 10. IDs are <=2^53-1. The authenticated response fits firmware's
4095-byte response buffer. TLS/authentication provide authenticity, not the digest.

`EnergyAllocation` and `MeterDelivery` remain the authoritative entitlement and
reservation ledger. `reserve_ac_lab_token` in `allocation_service.py` reserves the
entire token allocation under locks. `PrototypeCommand` binds the device and
sequence/receipt to that existing delivery; it is not another balance. Redeem
persists DISPATCHED before responding. ACK persists APPLIED only after the device
attests its durable NVS write. **Purchase settled, credit saved on device and load
switched on are separate states.** This milestone never asserts load switching or
independent flash verification. HTTP success alone does not prove application.

No timer releases reservations. A lost response is recovered by redeeming the
same token; a lost ACK response is recovered by sending the same durable receipt.
An applied-but-unacknowledged device may handshake/report only exactly the one
pending command and its amount, never arbitrary extra credit. Session/telemetry
high-water counters prevent observed applied credit from later regressing before
ACK. Different token while pending requires completion/reconciliation. Storage
replacement/firmware erasure, changed receipts or counter discontinuity require
operator review, not balance reset or new credit. There is no automatic binding
replacement or credential reactivation. After revocation, reconcile receipts and
provision a reviewed future recovery process; never manually clear reservations.

## Telemetry and consumer evidence

Telemetry includes the identity and:

```json
{"boot_id":"33333333-3333-4333-8333-333333333333","boot_counter":1,"sequence":1,"measured_at":"2026-11-16T10:00:00Z","clock_status":"NETWORK_TIME","application_counter":1,"credited_uwh":1000000000,"consumed_uwh":1000000,"uncertain_uwh":0,"remaining_credit_uwh":999000000,"voltage_mv":230000,"current_ma":100,"power_mw":23000,"pzem_wh":500,"output_requested":false,"output_feedback":"UNKNOWN","sensor_status":"OK"}
```

1 Wh = 1,000,000 microWh; 1 kWh = 1,000,000,000 microWh. Authoritative values stay
integers/Decimal. Allocation increment remains 10 Wh; telemetry is not rounded to
that increment. Credited = consumed + uncertain + remaining, and credited must
match ACKed commands or exactly the one known pending command. Consumption and
uncertainty cannot regress; PZEM raw lifetime counter regression rejects with
`PZEM_COUNTER_RESET`. Same boot/sequence/body is idempotent without refreshing the
reading timestamp; changed duplicate and reordered snapshots reject. Missing
sequences remain gaps, no invented daily/minute chart data. Sensor FAULT produces
unavailable measured usage, not zero. Output requested must be false; feedback is
UNKNOWN even when the requested output is off.

Owner-only existing APIs expose the evidence:
- `GET /api/v1/meter/mobile-meters/<meter_id>/`: `contact_source: AC_LAB`,
  `lab_consumed_uwh`, `lab_remaining_credit_uwh`, `lab_pzem_wh`, `lab_uncertain_uwh`,
  sensor status, measurement/receipt/contact times, output disabled/feedback unknown.
- `GET /api/v1/meter/mobile-consumption/?meter_id=<id>`: up to30 raw AC lab snapshots
  in `ac_lab_telemetry`, separate from simulator/daily history.
- Existing token and delivery reads label ACKed evidence `AC_LAB`.

All device responses and these meter/consumption responses are private/no-store.
No prior owner's lab readings become visible after meter reassignment. Other-owner
meter reads return404. Stale threshold is90seconds based on both measurement and
server receipt, independent of later session requests. A recent session without
telemetry is not a fresh zero. Android polls selected-meter reads every30seconds
while foreground, supports AC_LAB separately, displays exact microWh as Wh,
remaining credit and last contact on Meters, and raw history under Usage. Older
backends without AC fields still parse. Stale readings remain labelled stored;
periodic PZEM evidence is not instantaneous or utility-verified data. Existing APKs
reject AC_LAB source; distribute a reviewed rebuilt APK before enabling this
capability for phone testing. No APK was rebuilt as part of this backend milestone.

## Local validation

See final results appended below. Tests use an isolated local PostgreSQL database
on127.0.0.1:55445 with synthetic accounts/meters, mocked external HTTP and no board.
They do not validate electrical safety, actual NVS atomicity, real PZEM accuracy,
TLS certificates/network reliability, hosting quotas or physical Android rendering.

## Exact deployment preparation (operator-run; NOT executed here)

From the repository root, preview and upload only this milestone's allowlist.
No `--delete`, `.env`, private config, venv, database, APK or generated artifacts:

```bash
rsync -avnc --files-from=backend/deploy/prototype-ac-lab.files \
  backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
rsync -avc --files-from=backend/deploy/prototype-ac-lab.files \
  backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
ssh shanonsimon@ssh-shanonsimon.alwaysdata.net
```

On host retain working sandbox WSGI/site/venv and existing secret keys/schedules.
The following path must match the existing private environment file. Inspect only
schema/connection metadata and review the migration plan before approving changes:

```bash
cd /home/shanonsimon/energy-sharing
export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
export DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings
/home/shanonsimon/energy-venv/bin/python manage.py check_alwaysdata_database
/home/shanonsimon/energy-venv/bin/python manage.py check
/home/shanonsimon/energy-venv/bin/python manage.py showmigrations meter
/home/shanonsimon/energy-venv/bin/python manage.py migrate --plan
```

Review `meter.0032_prototypedevice_prototypecommand_prototypeboot_and_more`: only
new device, boot, command-receipt and telemetry tables/constraints. 0031 is unchanged.
This patch has no historical data migration. If the plan contains other unapplied
migrations, review those independently; do not blindly migrate an unknown target.
Back up the database and existing private token keys using the established private
backup process. After operator approval, on the confirmed testing target only:

```bash
/home/shanonsimon/energy-venv/bin/python manage.py migrate meter 0032
/home/shanonsimon/energy-venv/bin/python manage.py collectstatic --noinput
```

Edit the existing private file with an editor; never copy the example over working
secrets or print the file. Keep mode0600 and parent0700. Add
`PROTOTYPE_AC_LAB_ENABLED=true` only after the reviewed board/output prerequisites;
retain LOCAL_DEMO, seven disabled features and existing ENERGY_TOKEN_* values.
There is no relay-enable setting. Provision for actual known database IDs privately:

```bash
mkdir -p /home/shanonsimon/.config/energy-sharing/devices
chmod 700 /home/shanonsimon/.config/energy-sharing/devices
/home/shanonsimon/energy-venv/bin/python manage.py provision_ac_lab_device <METER_ID> \
  --owner-id <CONSUMER_ID> --operator-id <VERIFIED_STAFF_OPERATOR_ID> \
  --private-config /home/shanonsimon/.config/energy-sharing/devices/esp32-ac.json \
  --confirm-output-disabled
```

The command writes secret configuration exclusively to a new0600file; stdout
contains only device ID/status. Transfer values to the private firmware config
using a private editor/transfer, never shell history, logs or Git. Preserve the
provisioned storage identity and firmware's durable state across retries. API_BASE
is `https://shanonsimon.alwaysdata.net/api/v1` without trailing slash. Configure its
trusted root CA per the firmware instructions. Keep `GPAWA_COMMISSIONED_OUTPUT=0`; use `GPAWA_USB_EXERCISE=0` for the network test (exercise=1 bypasses the API).
Do not dump token/credential values in diagnostic requests.

Restart the existing site in alwaysdata **Web → Sites → shanonsimon.alwaysdata.net
→ Restart** (reload the WSGI application), retaining Python3.12.15,
`/home/shanonsimon/energy-venv` and `backend/alwaysdata_sandbox_wsgi.py`. No Redis,
Celery, MQTT or persistent device worker is required for bounded HTTP uploads and
keypad pull/ACK; existing finite email/payment schedules remain exactly as before.
At30s uploads, one board sends~2,880 telemetry requests/day plus Android reads;
measure Free-plan storage/CPU/latency quotas before increasing device count. No
LoRa gateway is introduced: this specific contract uses ESP32 Wi-Fi HTTPS.

Credential-free checks after restart (expect features200, device401 if enabled;
503 if disabled). A401 proves route/auth boundary only, not hardware operation:

```bash
curl --fail --silent --show-error https://shanonsimon.alwaysdata.net/api/v1/features/
curl --silent --show-error -o /dev/null -w '%{http_code}\n' \
  -H 'Content-Type: application/json' -d '{}' \
  https://shanonsimon.alwaysdata.net/api/v1/prototype-device/v1/session/
```

Do not run a real purchase or token redemption as an automatic deployment check.
Board tests follow only after explicit local operator setup and below prerequisites.
To stop this capability, set the flag false and restart; records/reservations remain.
Revoke a single device without deleting data:

```bash
/home/shanonsimon/energy-venv/bin/python manage.py revoke_ac_lab_device <DEVICE_UUID> \
  --operator-id <VERIFIED_STAFF_OPERATOR_ID>
```

## Physical board acceptance still required

1. Relay/load physically disconnected; independently confirm the disabled macros in
   the actual compiled image. Verify boot leaves GPIO/output disabled. Use network mode (USB_EXERCISE=0, COMMISSIONED_OUTPUT=0), not offline exercise mode. Start with the provisioned fresh unused journal; do not erase any journal that may contain applied/pending credit.
2. Provision private identities, CA/time/Wi-Fi; fresh NVS session then normal reboot.
3. Use a new UGX_DEMO purchase/token on that same meter; test lost redeem response,
   power interruption after NVS save, same-command retry and lost ACK recovery.
4. Observe PZEM isolated UART/approved sensor setup without enabling a switched load.
   Confirm units, counter baseline, fault/reset behavior and device journal accuracy.
5. Confirm selected meter readings and90s stale indication in a rebuilt Android app;
   another consumer must not see the readings. No claims of utility/physical credit.
6. Measure HTTPS latency/retries/hosting quota and retain receipts for reconciliation.
   Mains switching, independent flash durability and calibration remain separate
   reviewed milestones; this implementation does not enable them.

Changed backend files are explicitly listed in `deploy/prototype-ac-lab.files`.
Android source changes: `mobile/src/App.tsx`, `mobile/src/LabReadings.tsx`,
`mobile/src/Delivery.tsx`, `mobile/src/api/contracts.ts`, and focused tests. Shared
web/mobile token presentation changes: `frontend/src/lib/energy-token.ts` and
`frontend/src/components/energy-token-card.tsx` plus its web test. No public/auth
screen redesign, new transaction policy or Android native plugin is introduced.

For a later phone build, retain the current application ID/signing identity and
existing debug scripts, with `VITE_API_BASE_URL=https://shanonsimon.alwaysdata.net/api/v1`.
Review/build/install that updated app separately; the backend deploy does not update
installed APK JavaScript. No provider request or hosted financial test is required
for a bundle build.

Measurement detail: `MeterCore.h::observe` caps its `consumedUWh` at available
credit, so that counter is **credit debited**, not necessarily all physical usage.
The app therefore shows raw `lab_pzem_wh` as PZEM cumulative energy, and
`lab_interval_usage_wh` as the exact counter difference between the last two
accepted OK snapshots (`lab_interval_start` identifies the start). The first
sample/fault produces unavailable interval usage, not zero. Gaps are cumulative
intervals and never fabricated minute readings. Device-journal credit debits are
labelled separately. This distinction remains important with relay output disabled.

### Inspected firmware source fingerprints

| File | SHA-256 |
|---|---|
| `docs/API_CONTRACT.md` | `439a9c0cf4e68efcf30c2550f58c9f3f89d7effa11a7627bd4c496a14a9c8bad` |
| `GpawaAC/Firmware.cpp` | `ad7d925e1fb3d760826f5962103beb945845a83aed8190e1050bc4285c49d8a2` |
| `GpawaAC/Protocol.h` | `7c93595302e4c3ed67f9d844e8b3b3389c22a0ddcc742a1bed73ea864b3a2791` |

### Reproducible local checks

The existing guarded test launcher refuses an unexpected cluster/role and blocks
external HTTP. Run only against the documented disposable `/tmp` PostgreSQL cluster:

```bash
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --check-migrations
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --sandbox-profile meter.tests_prototype_device transactions.tests_demo_payments backend.tests_feature_flags backend.tests_alwaysdata
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py meter.tests_prototype_device meter.tests_allocation_delivery loan.tests_financial_correctness
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --bench-profile meter.tests_energy_tokens
```

Run the base and sandbox-profile commands sequentially: they use the same disposable
test database. The bench profile uses its separate bench database. Development
simulator/core-disbursement tests deliberately use the base profile; running them
under alwaysdata correctly blocks their HTTP/financial paths and is not a valid
expectation that the hosting restriction should be loosened.

```bash
cd mobile
npm run typecheck
node --test --test-isolation=none tests/*.test.mjs
VITE_API_BASE_URL=https://shanonsimon.alwaysdata.net/api/v1 npm run build
cd ../frontend
npx next typegen
npx tsc --noEmit
npx eslint src/lib/energy-token.ts src/components/energy-token-card.tsx
node --test --test-isolation=none tests/energy-token.test.mjs
```

The initial web type check found an existing malformed generated
`.next/dev/types/validator.ts` containing a stray `sx`. That generated file was
preserved in `/tmp/ac-lab-stale-dev-validator.ts`, then route types regenerated
with Next's generator. Strict checks were retained and passed. No source type
suppression or Next build bypass was added. The first default mobile production
build refused a missing HTTPS API variable as intended; the explicit HTTPS build
above passed. Node emits a harmless existing module-type warning for direct TS
imports from the shared frontend package; its package/module settings were not
changed.

One pre-existing hosting test still expected only the web CSRF origin despite the
working Django-hosted account-page fix. Its assertion now requires the exact
backend HTTPS origin as well. Runtime CSRF/CORS settings were not broadened.

### Verified results, 2026-11-16

| Check | Result |
|---|---|
| Final alwaysdata sandbox-profile device + demo payment + feature-flag + account/hosting suite | **63 passed** |
| Base-profile device + development allocation/simulator + financial suite | **49 run; OK, 1 hosting-only skip, 1 expected failure** |
| Independent software-bench token suite | **17 passed** |
| Migration drift | No changes detected for meter/transactions/loan; new0032 matches models |
| Mobile strict type check | Passed |
| Mobile tests (no test-process isolation, explicit individual cases) | **62 passed** |
| Mobile bundle, explicit alwaysdata HTTPS API URL | Passed, Vite79modules; no APK sync/build |
| Web regenerated route types + full strict TypeScript | Passed |
| Shared web token tests | **2 passed** |
| Scoped shared token component/parser ESLint | Passed |
| Firmware host C++ recovery/PZEM frame tests | Passed; compiled recovery.cpp into /tmp, no flash or device |

The base-profile expected failure remains
`loan.tests_financial_correctness.FinancialCorrectnessTests.test_completed_loan_stays_closed_when_overdue_clock_advances`.
This is the existing CORE closure-policy issue; no financial rule was changed.
Legacy wallet-meter mirror signal diagnostics also appear in the existing
simulation/financial fixture runs; those code paths were not changed. The AC
adapter does not use that mirror as credit authority or write legacy balances.

The twelve lab tests cover the complete purchase/source token/session/redeem/retry/
ACK/owner-reading path, two-thread PostgreSQL redemption and ACK serialization,
wrong owner/meter/binding, revoked credentials, consumer credentials denial,
approved demo-loan entitlement, wrong-domain allocation denial, pending-command
conservation, telemetry without ACK, boot/storage/counter regression, changed
ACK/telemetry replay, disabled output, stale/fault readings, private provisioning
and revocation audit. The latest end-to-end case also verifies a one-Wh PZEM
interval from two snapshots without treating credit debits as total measured usage.

**Verdict: ready with named prerequisites for an output-disabled AC lab board test.**
Prerequisites: reviewed testing database migration, explicit capability opt-in,
verified operator provisioning, private firmware configuration, network mode with
commissioned output disabled, isolated sensor/wiring review and rebuilt client.
No hosted deployment, actual MTN/ThingsBoard/device exchange, phone run, independent
measurement accuracy or physical load switching has been verified here.
