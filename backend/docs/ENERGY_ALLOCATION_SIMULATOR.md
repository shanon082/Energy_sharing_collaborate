# New electricity entitlement and simulated delivery

This is a development-only meter simulator and a proposed device contract v1,
pending meter/firmware review. It does not command an ESP32, ThingsBoard, LoRa
gateway, or physical relay. `DEBUG=true` and `SIMULATED_METER_ENABLED=true` are
both required to dispatch; the flag defaults to false. No historical token,
wallet entry, or pending physical credit is replayed.

## Accounting authority and invariants

- New `PaymentIntent.amount`, matching provider evidence, loan applications,
  disbursed principal and verified repayment requests are whole UGX. The
  `LoanApplication.outstanding_balance` property now uses exact Decimal
  interest/penalty arithmetic. Two-decimal UGX charge rounding is documented
  in `BILLING_ACCOUNTING.md`; formal policy approval remains open. Provider
  settlement is the authority for a paid purchase; an
  approved and disbursed loan is a separate legitimate source of energy before
  repayment. Repayment reduces debt and creates no new entitlement.
- `EnergyAllocation.amount_kwh` is authoritative **for new source-attributable
  entitlement only**. It is `Decimal(20,2)` kWh: one quantum is 0.01 kWh = 10 Wh.
  Source calculations round once, half up, to this quantum. A row has exactly
  one protected, unique source: a settled purchase `PaymentIntent` or a
  `LoanDisbursement`. It records owner and explicitly selected intended meter.
- `MeterDelivery` reserves exact kWh from one allocation under a row lock.
  A load spanning allocations creates one delivery per source. For each
  allocation, `sum(all delivery amounts) <= allocation amount` and
  `available = allocation amount - sum(all delivery amounts)`; failed, expired,
  and uncertain deliveries still hold their reservation. `confirmed` is only
  the sum of `APPLIED` deliveries. `pending = reserved - confirmed`, including
  failed or uncertain commands that require reconciliation.
- `SimulatedCommand` is the simulator's durable, unique record of application.
  `SimulatedMeter.applied_kwh` is the simulator's local cumulative grant;
  `consumed_wh` is measured simulated consumption in integer Wh. These are
  distinct from Django entitlement and from requested relay state. Binary
  floating point is not used for authoritative new balances.
- `UnitBalance` and `Meter.units/pending_units` remain historical/compatibility
  projections. Old writers include purchase/loan flows, sharing, USSD, token
  and legacy meter paths; their past provenance and occasional UGX/kWh mixing
  are unresolved. New verified purchase and disbursement still credit
  `UnitBalance` for compatibility, but delivery never spends it. The legacy
  aggregate still appears in legacy wallet/history views and includes those
  new credits; it is **not** another spendable balance. Do not backfill
  allocations from it without reconciliation.

The new purchase writer is `transactions.payment_settlement._settle_purchase`;
the new loan writer is `loan.services.disburse_loan`. Both create the allocation
in the same transaction as their existing projection. All active web and admin
disbursement paths call the service. The old direct purchase/repayment routes
reject new effects, and deferred sharing/USSD routes remain off. `PaymentIntent`
also has a database unique constraint on nonempty `(provider,
provider_transaction_id)`, across purposes. Existing provider IDs must be
checked for duplicates before an operational migration.
Historical approved loans with no intended meter are never assigned the first
meter automatically. An authorized disbursement request must supply an explicit
currently owned `meter_no`; otherwise the loan stays approved for review.
The staff disbursement screens accept that explicit meter number when the
historical loan has none. A stored `LoanDisbursement.token` is displayed as
history only; it is not a validated STS command or proof of application.

Writer trace: `wallet.models.UnitBalance.add_units/deduct_units` is the legacy
mutation API. The active new writers above call `add_units` only. The routed
`meter.api.views.ApplyWalletToMeterView` now delegates to source-bound
reservation without deducting `UnitBalance`; STS generation and received-unit
activation reject new mutation. The older `meter.api.views.BuyUnitsView` and
`meter.buy_units_payment` are not the routed purchase implementation. The
sharing and USSD writers remain behind the seven default-off feature flags.
The large old bodies after early returns in meter/loan views remain in source
for historical review but are unreachable through their current routes.

## Delivery lifecycle

`POST /api/v1/meter/deliver/` (and the existing own-meter alias
`/api/v1/meter/apply-wallet-units/`) requires consumer authentication,
an active, owned AMI `meter_no`, an exact kWh amount, and an enabled simulator.
It returns HTTP 202 `QUEUED` with stable delivery and command IDs, never a
claim of meter application. `GET /api/v1/meter/allocation-status/?meter_no=...`
returns available, pending, confirmed, and last simulated contact. It does not
present the ambiguous legacy balance as newly deliverable entitlement.
Last contact alone is not application proof; only the durable command receipt
can move a delivery to `APPLIED`.
An unenrolled simulator is rejected before reservation. If enrollment or meter
assignment changes after reservation, the held delivery needs reconciliation.

The database-backed outbox is the set of `MeterDelivery` rows. A Celery beat
poll runs `meter.tasks.dispatch_simulated_outbox`; a worker is also required.
It commits `DISPATCHED` before simulator I/O, then processes the command using
its original ID. The simulator commits `SimulatedCommand` and its local credit
before returning a receipt. Django sets `APPLIED` only after finding that
durable receipt and validating device, meter, owner, amount, and command ID.
Duplicate dispatches and acknowledgements have one application. A lost
acknowledgement becomes `OUTCOME_UNKNOWN`; retry uses the same ID and finds the
durable application. Missing enrollment or changed assignment marks `FAILED`
but keeps the reservation. There is no automatic release, replacement meter,
refund, or generated second command for an uncertain outcome. Reconciliation
must decide what actually happened first.

Example reservation:

```json
{"meter_no":"SIM-OWN-1","amount":"0.50"}
```

Example response (IDs illustrative):

```json
{"status":"QUEUED","meter_no":"SIM-OWN-1","deliveries":[{"id":42,"command_id":"f75759ad-8775-4a6d-9f49-60d8baf5cd99","amount_kwh":"0.50","status":"QUEUED"}]}
```

Example status before acknowledgement:

```json
{"unit":"kWh","quantum_kwh":"0.01","meter_no":"SIM-OWN-1","available_kwh":"0.50","pending_kwh":"0.50","confirmed_kwh":"0.00","last_meter_contact":null,"delivery_environment":"SIMULATOR"}
```

## Proposed firmware/device contract v1

The device identity is a UUID separate from consumer login. Simulator
enrollment uses `enroll_simulated_meter <meter_no>` with a simulator-only
`SIMULATOR_DEVICE_TOKEN` environment value of at least 32 characters; only its
password hash is stored. The token is never printed. Simulator message routes
require `X-Sim-Device-Id` and `X-Sim-Device-Token`; they are development-only.
`simulate_meter_consumption <meter_no> <whole_wh>` exercises local enforcement
and creates telemetry without a physical device. Both commands require the
development simulator switches to be enabled.
Production credentials, transport security, key rotation, enrollment and
revocation remain hardware-review decisions.

Command payload proposal:

```json
{"contract_version":1,"device_id":"<uuid>","command_id":"<uuid>","delivery_id":42,"amount_kwh":"0.50"}
```

After **durable** local application, acknowledgement proposal:

```json
{"contract_version":1,"device_id":"<uuid>","command_id":"<uuid>","delivery_id":42,"amount_kwh":"0.50","applied_at":"2026-09-30T10:00:00Z","reported_relay_state":"CLOSED"}
```

Telemetry proposal to `POST /api/v1/meter/simulator/telemetry/`:

```json
{"contract_version":1,"event_id":"<uuid>","boot_id":"<uuid>","sequence":12,"cumulative_wh":1250,"measured_at":"2026-09-30T10:02:00Z","reported_relay_state":"CLOSED"}
```

The server stores `received_at` independently. Event ID deduplicates; boot
ID and sequence expose resets and gaps. Reordered or delayed events are
retained but cannot roll the consumption cursor backward, including messages
from a previous boot that arrive late. A new boot starts a fresh counter
baseline; consumption before its first observed counter remains unknown and
needs reconciliation. Counter
decrease within a boot is `DISCONTINUITY` and requires reconciliation. A
sequence gap flags missing telemetry; it is not interpolated. Requested relay
state and reported feedback are separate. The simulator locally refuses
consumption beyond applied energy and reports relay open at exhaustion.
Firmware must persist command IDs and applied energy across power loss before
it can satisfy this contract.

## Historical reconciliation and remaining decisions

Before exposing physical delivery, compare provider statements, existing
`PaymentIntent`, purchase and loan records, `UnitBalance` entries, historical
tokens, `Meter.units/pending_units`, and any gateway/meter receipts. Resolve
duplicates or ambiguous provenance manually; do not auto-convert, refund,
cancel, or replay uncertain items. New allocations are not a backfill of these
records. Existing pending physical obligations remain available to trusted
reconciliation, but the old automatic AMI retry beat is disabled.

The existing billing history helper adds `UnitTransaction` and meter purchase
rows, which can double-count the same purchase and affect later tariff bands;
it also includes float-valued legacy unit entries. This must be reconciled
before production billing accuracy can be claimed. Existing loan debt is also
float-derived, as described above. Neither historical calculation is silently
converted in this simulator phase.

Decide the physical meter's unit quantum, persistence and dedup capacity,
application receipt semantics, secure transport, actual relay feedback,
counter-reset behavior, offline policy, and whether STS keypad loading is
supported at all. LoRa and LoRaWAN need different gateway/server designs; no
radio stack is selected or validated here. Simulator tests prove software
idempotency and accounting only, not physical accuracy or radio reliability.
