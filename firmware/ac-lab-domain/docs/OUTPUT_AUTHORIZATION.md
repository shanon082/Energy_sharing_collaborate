# Audited GPIO14 output authorization

This protocol adds a backend-controlled, expiring authorization lease for the
commissioned AC-lab firmware. It does not report relay-contact feedback and it
does not replace the board's compile-time gates or the low-voltage hardware
commissioning procedure.

## Authorization decision

The device session and accepted telemetry responses carry:

```json
{
  "output_authorized": false,
  "output_lease_seconds": 0,
  "output_restart_policy": "MANUAL",
  "output_authorization_expires_at": null,
  "output_commissioning_mode": null,
  "output_reason": "OUTPUT_GRANT_MISSING"
}
```

An accepted telemetry response confirms that the server has the validated
observation. `output_reason` describes the independent lease decision and also
appears in the redacted server log. The firmware logs it as
`OUTPUT_LEASE ... server_reason=... local=...` with the same request ID. For an
older backend the firmware displays `UNREPORTED`. For an allowed server response
the firmware can still report a local interlock or a response that arrived too
late for the lease. The staff GET endpoint reports the current decision.

An eligible response carries a positive lease of at most 90 seconds, bounded by
the freshness remaining on the latest valid meter sample and any temporary grant
expiry. A persistent record has no expiry and uses `AUTO`. The server will not
extend an old sample's lease. A lease is granted
only when all of the following hold:

- The deployment-owned global output switch is exactly `true`.
- The isolated AC-lab capability and device binding are valid.
- The device has a committed authenticated measurement baseline.
- There is a current, acknowledged credit balance greater than zero.
- No command acknowledgement is pending and no uncertain credit remains.
- The latest PZEM sample is valid, fault-free, recent and reports positive
  remaining credit.
- The latest sample's compiled relay active level matches the audited record.
- A valid per-device temporary grant or persistent commissioning exists. A
  persistent record is scoped to the reviewed binding and can be revoked.

The firmware independently requires healthy NVS, its committed baseline, a
valid recent PZEM sample, credit, completed acknowledgement, a live session and
lease, no fault/hold, `GPAWA_COMMISSIONED_OUTPUT=1`, and the explicit
`GPAWA_RELAY_COMMISSIONING_APPROVED=1` flag. Its default build keeps output
disabled. An expired or missing lease, backend rejection, stale PZEM reading,
zero credit, or critical local fault switches GPIO14 to the configured
inactive level.

The current firmware operates automatically with `AUTO` and ignores keypad `D`.
It keeps the output off for `MANUAL` grants, which remain available to older test
firmware. A temporary test on current firmware can use `AUTO` with a short expiry.
Any failed local safety condition switches the output off. The API reports
commanded state. Contact feedback remains `UNKNOWN`.

## Staff controls

Only an authenticated Admin (or superuser) can use these endpoints:

- `GET /api/v1/admin/prototype-devices/{device_id}/output-authorization/`
  returns current eligibility and the latest 100 immutable authorization events.
- `POST /api/v1/admin/prototype-devices/{device_id}/output-authorization/`
  grants an authorization for at most 24 hours.
- `POST /api/v1/admin/prototype-devices/{device_id}/output-authorization/persistent/`
  accepts an administrative `reason`, verifies the current binding and prior
  grant evidence, and creates a persistent `AUTO` commissioning entry with an
  immutable `PROMOTED` event. The operation is idempotent for the active record.
  It can reuse an expired temporary record and refuses a revoked source.
- `POST /api/v1/admin/prototype-devices/{device_id}/output-authorization/revoke/`
  revokes the active grant. Repeated revocation is safe.

The grant JSON requires exactly:

```json
{
  "expires_at": "2026-01-01T12:00:00Z",
  "reason": "Approved controlled AC lab commissioning",
  "restart_policy": "MANUAL",
  "evidence": {
    "contact_tested_ac_disconnected": true,
    "startup_state_verified": true,
    "reset_state_verified": true,
    "controller_power_loss_verified": true,
    "relay_supply_loss_verified": true,
    "zero_credit_cutoff_verified": true,
    "meter_fault_cutoff_verified": true,
    "electrical_installation_reviewed": true,
    "relay_active_level": "LOW",
    "evidence_reference": "commissioning-record-identifier"
  }
}
```

The evidence flags and evidence reference are retained with the grant, and
grant/revoke/expiry events are append-only. A grant is rejected unless a fresh
valid reading from the matching compiled relay-polarity profile has arrived.
The deployment's `PROTOTYPE_RELAY_OUTPUT_ENABLED=false` setting is the
immediate global inhibit and does not erase any device or credit records.

## Rollout and safe use

1. Keep AC disconnected and complete the separate low-voltage relay tests,
   electrical review, and authenticated meter transition.
2. Verify the commissioned firmware profile reports its chosen relay polarity
   while output remains unauthorized. Never infer polarity from GPIO readback.
3. Use an Admin account to review the device binding, telemetry, credit,
   migration state, fault state and recorded physical evidence.
4. Use a short temporary `AUTO` grant for an explicitly reviewed current-firmware
   test window, or promote the previously reviewed binding for ongoing operation.
   The command is rejected while any accounting, meter, acknowledgement or
   freshness condition is unresolved.
5. Observe `output_authorized`, lease expiry, `lab_output_command`, and fault
   state in the owner view. Physical relay contact remains unverified unless
   separately measured using the safe hardware procedure.
6. Revoke after the test. For an immediate global inhibit, set
   `PROTOTYPE_RELAY_OUTPUT_ENABLED=false` in the sandbox deployment settings
   and restart the service. No production deployment is implied by this guide.

The backend global switch is enabled by default only in the explicitly selected
Alwaysdata sandbox settings profile; setting it to false is a fail-closed
deployment override. Device grants and the firmware default remain disabled
until individual commissioning evidence is provided.
