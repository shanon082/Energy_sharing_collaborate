# Authenticated physical-meter transition

The transition converts a valid SANDBOX journal marked version 3 / paused into
version 2 / baselined without modifying any credit, receipt, application
counter, binding, storage identity or prior meter reading. It never interprets
the new PZEM lifetime value as historical consumption.

## Device protocol

Both POST requests use the established `X-Device-Id`, `X-Device-Token`, TLS,
request-correlation, exact identity and bounded JSON rules:

- `/prototype-device/v1/measurement/prepare/` (`GPAWA_BASELINE_V1`)
- `/prototype-device/v1/measurement/commit/`

Prepare binds a random transition UUID to protocol/source journal version,
identity, previous baseline presence/value, newly validated PZEM baseline,
credit totals, application counter, pending-ACK state and last credit receipt.
The backend holds the device row and inserts a unique transition receipt. The
exact request may be retried; a changed payload or transition UUID is rejected.
New redemptions are blocked after prepare until commit.

Commit is bound to the returned immutable receipt. The server persists
`COMMITTED` idempotently and returns the baseline and receipt. Transition
responses explicitly deny output; committing the baseline is never an output
authorization.

## Firmware persistence / recovery

Firmware requires three consecutive valid PZEM frames, no pending ACK, no hold,
and valid authenticated session before writing its migration record to the
existing NVS namespace. The journal's migration key contains its own CRC and a
snapshot of accounting and credit receipt fields. Firmware never clears NVS.

1. Persist `INTENT` and verify NVS readback.
2. Retry byte-identical prepare requests until the durable server receipt is
   received. Persist `PREPARED` and verify readback.
3. Retry commit with the same transition/receipt IDs.
4. Persist the original credit journal with only its measurement version,
   pause marker, `hasMeter`, and baseline changed. Verify readback.
5. Remove the migration key and verify its removal.

## Existing-credit migration procedure

1. Record the device's provisioned device/meter/storage identity, current
   credit, application counter, latest receipt and acknowledgement state from
   trusted records. Keep the existing private credentials, verified CA,
   accounting environment, NVS namespace and journal; do not initialize a new
   identity or use the unused-device first-boot option.
2. Build the authenticated metered mode with the explicit flags in the
   repository README and `GPAWA_COMMISSIONED_OUTPUT=0`. Review the active
   provisioning privately. Do not copy secrets into public source or logs.
3. Keep the AC/load disconnected and preserve power during the first boot.
   The device authenticates using its existing binding, waits for healthy PZEM
   readings, and then performs prepare/commit. The PZEM's current lifetime Wh
   becomes the new baseline; it is not charged to the prior credit balance.
4. If power or network is interrupted, restore the same device identity and
   service, then boot the same compatible firmware. It retries the persisted
   transition ID and exact request/receipt; do not create a new transition or
   clear Preferences.
5. Confirm the committed baseline and preserved credit/counter/receipt from
   authenticated server and device records before treating post-baseline Wh
   deltas as debitable consumption. Keep output disabled; transition success
   does not commission the relay.

This repository change does not upload firmware or modify the physical NVS.
Perform a device upgrade only under a separately controlled maintenance
procedure with the device owner present.

Power-loss outcomes:

- Before intent write: remain paused; retry after new valid measurement.
- After intent / before prepare: resend the identical prepare.
- After backend prepare / before local receipt write: prepare retry returns the
  same receipt.
- After local prepared write / before backend commit: retry the same commit.
- After backend commit / before local journal write: commit retry returns the
  same commit receipt; finish the local journal write.
- After journal write / before migration-key removal: boot verifies that the
  committed baseline matches, then removes only the migration record.
- Any CRC, identity, accounting-snapshot, receipt, or baseline mismatch latches
  an error and keeps output off. Do not clear the migration key or paused marker
  manually. Preserve NVS and give the device ID and safe request ID to the
  operator for reconciliation.

  Do not roll back by erasing NVS, restoring an old journal, changing device
  identity, or flashing credit-only firmware over a prepared/committed transition.
  Before an intent exists, a compatible maintenance rollback leaves the paused
  journal and its credit untouched. Once intent is persisted, recover forward
  with the same protocol and transition ID; after commit, use a forward-compatible
  firmware fix that retains the v2 journal fields and the server's committed
  receipt. A server-side additive schema rollback must not delete transition
  receipts; reconcile any database rollback with device state before resuming.

The one transition record is retained server-side for audit. Transition is
one-time per device and cannot change credit or authorize relay output.

## Metering and output

After transition the firmware accounts only whole-Wh increases over the
authenticated baseline, checkpoints the same journal, and reports voltage,
current, active power, energy, frequency, power factor and fault status.
Missing measurements are JSON `null`, not zero. Backend telemetry confirms the
reported energy delta against available credit and acknowledged applications.
Counter regression or credit-conservation mismatch is rejected and the firmware
holds output off.

Firmware relay output defaults to disabled. A build that enables it additionally
requires an explicit `GPAWA_RELAY_ACTIVE_LEVEL` and
`GPAWA_RELAY_COMMISSIONING_APPROVED=1`, authenticated metered mode, and no
diagnostic/exercise mode. Runtime operation requires a valid baseline, recent
PZEM data, healthy storage/session, a bounded backend lease, positive
acknowledged credit, no pending ACK or accounting uncertainty, no fault/hold,
and explicit local arming for `MANUAL` policy. Per-device audited authorization
and expiry are implemented in [OUTPUT_AUTHORIZATION.md](./OUTPUT_AUTHORIZATION.md).
Relay activation still requires separate safe physical polarity, reset/power
loss, driver and electrical installation verification; no physical commissioning
or AC energization is implied.

## Test and target build

Host-side deterministic journal, frame, migration retry, conservation,
fail-safe and buzzer tests run via:

```bash
python3 firmware/ac-lab-domain/tests/check.py
```

The Django protocol tests are in
`backend/meter/tests_measurement_transition.py`; run them through the isolated
hosting harness documented in the root project setup. The migration schema
change is `meter.0034_prototypemeasurementtransition`.

Physical AC, NVS erasure, deployment and device upload are not part of this
protocol. Start with AC/load disconnected and preserve the original firmware
binary/config and NVS image.

## Serial Monitor expectations

Use 115200 baud. During an interrupted transition, firmware reports the
persisted retry stage without enabling output:

```text
MEASUREMENT_TRANSITION status=RECOVERING stage=INTENT baseline_wh=<validated Wh> output_authorized=NO
```

After the backend commit and verified local journal write, the success line is:

```text
MEASUREMENT_TRANSITION status=COMMITTED baseline_wh=<validated Wh> prior_credit_preserved=YES output_authorized=NO
```

The normal output-status line remains `block=OUTPUT_NOT_COMMISSIONED` while
commissioning is disabled; it reports `gpio14=NOT_DRIVEN`. Requests that fail
are logged as `DEVICE request_id=... operation=... http=... category=...
cause=... stage=... code=... correlation=...`. Exact request IDs and status
values vary. A successful transition does not mean the relay was authorized or
that physical contacts moved.

The separate PZEM read-only diagnostic build reports a `PZEM_CONFIG` line with
9600 baud, 8N1, RX GPIO16, TX GPIO17 and address `0x01`, followed by
`PZEM_STATUS status=VALID ...` for validated samples or
`PZEM_STATUS status=INVALID reason=...` when validation fails. That diagnostic
does not authenticate to the backend or touch credit/storage; it is not the
authenticated metered operating mode.
