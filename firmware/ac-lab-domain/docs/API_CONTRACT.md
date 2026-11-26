# GPAWA_PZEM_V2 SANDBOX API — local integration, relay disabled

## Sensor-free authenticated credit milestone (2026-11-19)

The existing session/redeem/ACK payloads do not require a PZEM baseline. Explicit
GPAWA_AUTH_CREDIT_ONLY mode uses those unmodified authenticated V2 operations and
session heartbeats, while sending **no telemetry** or fabricated zero measurements.
No backend schema/runtime change is required. See [USB_CREDIT_ONLY.md](USB_CREDIT_ONLY.md)
for the journal-v3 marker (wire protocol remains V2), preserved identity/counters,
uninitialized/suspended measurement state and blocked automatic metered activation.
The metered telemetry contract below applies only to a reconciled sensor mode.

The four existing Django routes are reused. This contract update is implemented locally; no hosted deployment or board test is claimed.
They must not be implemented by disabling the existing hosting middleware globally.
The existing `/bench-device/v1/` Python/SQLite harness remains independent and unchanged.

Scope: explicitly provisioned ESP32 **AC_LAB** devices. MTN Collections Sandbox uses EUR TEST financial records and **SANDBOX** energy allocations/tokens/device identities, with **GPAWA_PZEM_V2**. Legacy UGX_DEMO devices retain GPAWA_PZEM_V1 under their original domain. No currency conversion, real household meter or live money claim.
Online API transport is HTTPS. Requests are POST JSON; response bodies <=4095 bytes;
no redirects. All API responses and owner telemetry reads use `Cache-Control: private, no-store`.

## Authentication and provisioning

Every device call has `X-Device-Id: <UUID>` and `X-Device-Token: <unique secret>`.
Store only a password hash of the secret on Django, redact both token payloads and
credentials from logs. Consumer JWTs must not authenticate device calls.
Use server-side shared rate limiting, maximum body sizes and strict schemas.

Provision the device explicitly to one owned, active 11-digit meter and explicit SANDBOX environment,
binding epoch >=1 and a fresh random storage UUID. Self-declared enrollment alone
must not create a device credential. Staff must authorize commissioning with an audit
record. One active AC lab binding per meter; no consumer-supplied rebindings.
Credential rotation/revocation must preserve delivery reservations and receipts.

All requests except a fully nested command contain these identity fields:

```json
{"protocol":"GPAWA_PZEM_V2","device_id":"11111111-1111-4111-8111-111111111111","meter_number":"00000001234","storage_id":"22222222-2222-4222-8222-222222222222","binding_epoch":1,"environment":"SANDBOX","hardware_class":"AC_LAB"}
```

All successful responses MUST repeat those fields at the top level. Django derives
and verifies these bindings from the authenticated device, never trusts a supplied
meter as authorization. IDs use canonical lowercase UUID strings. JSON numeric fields
are integers (not strings, booleans, floats or null). Database IDs <=2^53-1.

## POST /api/v1/prototype-device/v1/session/

Additional request fields:
- `boot_id` UUID, `boot_counter` positive uint32;
- `application_counter` uint32, `initialize` boolean, `ack_pending` boolean;
- for nonzero application counter: `last_command_id`, `last_payload_digest`, `last_receipt_id`;
- `credited_uwh`, `consumed_uwh`, `uncertain_uwh`, nonnegative integers <=9e15.

Validate persistent storage identity, owner/binding, credited counters and last
accepted consumption against the retained server state. A new boot counter must
advance; duplicate session requests for the same boot ID/counter are idempotent.
Reject retired boot identities and regressed counters. A fresh `initialize:true`
is allowed only for a provisioned unused binding. Retrying the identical initialization
for that same unused binding must be safe; once used, storage reset cannot initialize it again.

A device may have applied the server's one pending command before its ACK arrived.
Permit reconciliation of exactly that pending sequence and matching frozen command,
not arbitrary device credit. It may also have not received that pending command yet.
Never overwrite device credit from a session response.

Return the identity fields plus `{"status":"READY"}` only after these checks.
A 409 reconciliation response locks the firmware output. Offline journal retention is allowed within a previously authorized identity. Physical relay output remains disabled regardless of handshake, available credit or keypad D. This branch refuses commissioned-output compilation.

## POST /api/v1/prototype-device/v1/redeem/

Additional fields: `token` exactly 15 ASCII digits, `application_counter` uint32.
Never put the token in a URL or log. Validate HMAC lookup using the existing Django
key, encrypted token integrity, allocation/source provenance, owner, meter,
environment, state, active binding and unreserved entitlement.

Under a database transaction and appropriate row locks:
- Allow at most one unresolved command for this device.
- Reserve the entire allocation once using the existing authoritative delivery service.
- Assign a frozen **command_sequence** equal to device's last acknowledged sequence +1.
- Reuse the issuance command UUID when available, never mint another on retry.
- Retries for that token while pending return the same command and sequence.
- A token applied previously returns 409 TOKEN_ALREADY_USED, never another credit.
- Another token while a command is pending returns 409 PENDING_COMMAND.
- Do not cancel/release an uncertain command on timeout.

Return the identity fields plus `command`. The command has exactly fourteen fields:

```json
{"allocation_id":123,"binding_epoch":1,"command_id":"44444444-4444-4444-8444-444444444444","command_sequence":1,"credit_wh":10,"delivery_id":456,"device_id":"11111111-1111-4111-8111-111111111111","environment":"SANDBOX","hardware_class":"AC_LAB","meter_number":"00000001234","protocol":"GPAWA_PZEM_V2","storage_id":"22222222-2222-4222-8222-222222222222","type":"AC_LAB_CREDIT","payload_digest":"<64 lowercase hex characters>"}
```

`credit_wh` is positive, <=1,000,000 and divisible by 10. The SHA256 digest is over
JSON containing the other thirteen fields in alphabetical key order, with ASCII
identifiers and compact separators `,`/`:`. Use an AC-specific vector; the older DC digest will not match.
The digest detects changed contents; TLS/authentication provide authenticity.
No raw token is returned in the command.

### Device durable application
A single NVS journal transaction records accepted command, credit and receipt before ACK. Retain the same receipt across resets. Meter cumulative Wh replaces DC power integration. See ../README.md for checkpoint and recovery assumptions. Responses must not overwrite remaining balance.

## POST /api/v1/prototype-device/v1/ack/

Additional fields:
`type: AC_LAB_APPLIED`, `command_id`, `command_sequence`, `payload_digest`,
`credit_wh`, `receipt_id` UUID, `applied_at` ISO8601 UTC,
`allocation_id`, `delivery_id`.

Verify all fields against the persisted frozen command and authenticated device.
Uniqueness: command/delivery, receipt ID, device+binding+sequence.
Commit server receipt, APPLIED state and device acknowledged high-water sequence
atomically. Identical duplicate ACK returns the same accepted receipt. Changed
identity/content is 409. No second allocation, credit or financial mutation occurs.

Response: identity fields plus
`status: APPLIED`, `command_id`, `command_sequence`, `payload_digest`, `receipt_id`.
Label this on clients as **AC lab application**, not utility meter delivery.
A device attestation alone is not independent proof of flash durability or load accuracy.

## POST /api/v1/prototype-device/v1/telemetry/

Additional fields:
- `boot_id`, `boot_counter`, strictly increasing per-boot `sequence`;
- `measured_at` ISO UTC, `clock_status: NETWORK_TIME`;
- `application_counter`, `credited_uwh`, `consumed_uwh`, `uncertain_uwh`, `remaining_credit_uwh`;
- `voltage_mv`, `current_ma`, `power_mw`, integer measurements, plus pzem_wh (raw lifetime Wh);
- `output_requested` boolean, `output_feedback: UNKNOWN`, `sensor_status: OK|FAULT`.

1 Wh = 1,000,000 microWh; 1 kWh = 1,000,000,000 microWh.
Validate body bounds, existing session/boot and nonregressing counters. Deduplicate
identical identity+boot+sequence payloads, reject same sequence with changed data,
ignore/reject delayed stale snapshots. Derive received_at on Django. Do not use
client timestamps as the sole ordering or freshness proof.

Validate `credited = consumed + uncertain + remaining` for this snapshot and against
issued commands/receipts. Because ACK and telemetry arrive separately, allow only
specified pending-command reconciliation, never fabricate an APPLIED record from
telemetry. No telemetry creates financial credit, alters loan debt or issues a token.

Response: identity fields plus `status: ACCEPTED`, `boot_id`, `sequence`.
The firmware sends the next cumulative snapshot after a transient failure. It does
not store every missed sample. Gaps remain gaps; historical charts must not invent
minute-by-minute readings from a single cumulative interval.

Expose owner-only read APIs for latest AC lab reading and measured history, and
adapt existing mobile/web monitoring to that evidence. Distinguish:
- server-funded entitlement;
- pending token application;
- AC-lab acknowledged credit;
- AC-lab measured consumption and remaining credit;
- energy withheld for uncertainty;
- last measurement/contact, stale/offline/unknown output feedback.

Device uploads are every 30 seconds; recommend client polling no faster than that
for the active screen and mark readings stale after a documented interval, e.g.90 s.
This is periodic monitoring, not instantaneous real-time or verified utility data.

## POST /api/v1/prototype-device/v1/measurement/prepare/ and /commit/

The one-time `GPAWA_BASELINE_V1` transition applies to a paused
`AUTH_CREDIT_ONLY_V3` journal. Prepare carries the full exact device identity,
`transition_id`, prior baseline presence/value, a newly validated PZEM lifetime
Wh baseline, credit totals, application counter, ACK-pending flag and last
credit receipt binding. Pending ACKs, telemetry that predates transition,
changed transition IDs or inconsistent credit state are rejected.

Prepare durably saves an idempotency-bound transition receipt without changing
credit, consumption, command counters, receipts, or output policy. The exact
body may be retried after a lost response. Commit accepts only that transition
ID and receipt ID and durably moves the transition to COMMITTED. It is also
idempotent. New token redemption is blocked between prepare and commit. Both
responses include the transition ID, receipt and baseline; both explicitly
return `output_authorized: false`. Transition completion never grants output.

The device persists a CRC-protected INTENT before prepare and PREPARED receipt
before commit. It writes the ordinary journal's baseline/version only after
the server commit. Boot retries the same immutable proposal/receipt and checks
the final baseline before removing the migration record. Any mismatch remains
held and off; the operator must preserve NVS and reconcile, never reset it.
The new baseline is not consumption: telemetry deductions start with later
validated whole-Wh differences only.

On `sensor_status: FAULT`, all unavailable measurement values must be `null`.
Successful sensor snapshots include `frequency_cHz` and `power_factor_pct`.
`fault_status` is one of `OK`, `SENSOR_UNAVAILABLE`, `ACCOUNTING_HOLD`, or
`SAFETY_FAULT`. The backend checks each valid post-transition PZEM delta against
the change to consumed credit and conservation totals. Fault snapshots cannot
move counters or account consumption.

## Output authorization

Session and accepted telemetry responses also carry `output_authorized`,
`output_lease_seconds` (bounded to 90 seconds and to sample freshness),
`output_restart_policy` (`AUTO` or `MANUAL`) and
`output_authorization_expires_at`. Device requests report the compiled
`relay_active_level` as `HIGH`, `LOW`, or `null`. Authorization is granted only
when the active audited per-device grant matches this reported polarity and
all migration, credit, acknowledgement, meter freshness, fault and global
enablement checks pass. The firmware turns output off on lease expiry or any
local fault, regardless of a previous grant. Staff commissioning, evidence,
revocation and immutable audit events are documented in
[OUTPUT_AUTHORIZATION.md](./OUTPUT_AUTHORIZATION.md). Relay contact feedback
remains `UNKNOWN`.

## Failure semantics

400 malformed/token rejected, 401/403 credential/revoked/unauthorized,
409 conflict/reconciliation, 429 shared rate limit, 503 capability unavailable.
Malformed successful responses are rejected by firmware. Network errors cannot
produce success. Only trusted server evidence yields credits; ACK only after local
persistence. 503 from the old hosted profile is not a reason to weaken protections.

## Required deployment boundary

Create an opt-in commissioned lab-device capability default OFF with strict allowlisted
POST routes, provisioning and scoped restrictions. Keep the existing software bench
profile isolated. Verify that alwaysdata supports the bounded request workload before
rollout; this HTTPS push design needs no persistent MQTT/LoRa process, but plan quotas
and actual latency still need measurement. Preserve existing email/payment schedules.

Additive schema must preserve historical tokens, obligations and accounting domains.
Migration 0031 exists already; do not modify that applied migration. New migrations
must be reviewed separately:0032 adds AC_LAB tables,0033 extends only the allowed
device-domain constraint. Back up private keys and database independently.
No real payments, CORE provisioning, physical household delivery or LoRa transport
is enabled by this firmware specification. Do not backfill historical tokens.

## Domain binding and journal compatibility

| Financial provider / currency | Energy/device environment | Wire protocol | Authenticated journal |
|---|---|---|---|
| MTN_SANDBOX / EUR TEST | SANDBOX | GPAWA_PZEM_V2 | gpawa_sbx2 |
| Historical LOCAL_DEMO / UGX | UGX_DEMO | GPAWA_PZEM_V1 | gpawa_ac1 |
| Explicit USB exercise | USB_EXERCISE, never accepted by Django | no authenticated protocol | gpawa_ex2 |

Django provisioning requires --environment SANDBOX in MTN mode. Device identity,
owner, meter and domain are immutable for this workflow. An existing binding is
not overwritten or relabelled; use a fresh commissioned binding/meter if an old
binding exists, or obtain a separately reviewed recovery plan. Credentials and
old allocations/journals remain preserved. No clearing NVS, token replay, balance
conversion or automatic cancellation is part of configuration.

State layout and CRC are retained; version2 metered records remain readable.
Credit-only records use version3 as described above. Previously unused reserved byte1 now
binds domain: zero is legacy UGX only;1 is explicit UGX;2 is SANDBOX;3 is isolated
USB exercise. Unknown codes fail validation. Existing gpawa_ac1/gpawa_ex1 bytes
are not erased; new SANDBOX and exercise journals have separate namespaces.
Boot checks domain as well as device/meter/storage/epoch; mismatches latch safely.
A new SANDBOX journal is allowed only for a fresh server-provisioned identity with
ALLOW_FIRST_BOOT explicitly enabled for commissioning. Used bindings cannot
initialize again merely because local flash was erased. No migration rewrites
old firmware balances or changes their currency meaning.

GpawaAC/DeviceDomain.h explicitly selects commissioning::ENVIRONMENT="SANDBOX".
DeviceConfig.h must privately contain the matching
provisioned device/meter/storage/binding values, unique device secret, Wi-Fi and
a verified ROOT_CA. API_BASE is https://shanonsimon.alwaysdata.net/api/v1. Never
use setInsecure. Preserve old private configs rather than overwriting their keys.
The active sketch's hd44780 display and Wi-Fi diagnostics are preserved.
GPAWA_WIFI_TEST=1 remains the diagnostic default and never calls the device API.
Select GPAWA_WIFI_TEST=0 explicitly only after provisioning and configuration.
GPAWA_USB_EXERCISE=0 and GPAWA_COMMISSIONED_OUTPUT=0 are the authenticated
credit-only settings. Unconfigured builds run PZEM diagnostics only: no
authenticated token acceptance, no network identity and no financial credit.
Explicit exercise=1 uses synthetic local credit in its own journal and no API.

A successful MTN HTTP status lookup is not a successful payment. Only validated
provider SUCCESSFUL evidence can settle an intent. The existing settlement
service creates one accepted-quote allocation and one encrypted 15-digit token
atomically for every new MTN purchase, even while device capability is off. Required token keys/issuance
and firmware amount bounds are checked before a new collection. A later key
failure retains a funded outcome pending reconciliation; it does not duplicate,
convert or discard energy. Repayment never allocates energy or issues tokens.
New EUR lending remains disabled pending its separate policy review.
