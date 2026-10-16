# Hardware integration readiness

Follow-up: [online keypad tokens and isolated bench contract](ENERGY_KEYPAD_TOKENS.md)
adds owner-visible encrypted tokens and authenticated software-bench redeem/ACK.
It does not enable physical routes or change this audit's commissioning limits.

Audit date: 2026-10-16. **Verdict: Ready with named prerequisites** for
firmware/interface development in isolation; **not ready for physical credit,
relay control, live metering, or real-money operation**. Agree the contract,
hardware, radio/gateway and worker environment below before implementation.
The accepted Android/Next.js design and API response shapes are unchanged.

This audit inspected source, route registration, hosting guards and isolated
tests. It did not inspect the remote environment, hosted data or scheduled-job
dashboard, deploy code, contact MTN/ThingsBoard, operate hardware, rotate keys,
or use a phone. “Current hosted profile” below means the repository's
`backend.alwaysdata_sandbox_settings` with `PROTOTYPE_PAYMENT_PROVIDER=LOCAL_DEMO`;
actual deployed revision/settings still need operator verification.

## Authority and trust boundaries

`meter.models.EnergyAllocation` is the authority for new source-attributable
cloud entitlement: one protected, unique purchase intent, loan disbursement,
or sandbox loan. `transactions.payment_settlement._settle_locked` and
`loan.services.disburse_loan` / `loan.sandbox_service` create it in their
accounting transaction. Repayment never creates energy. Approved/disbursed
loans legitimately allocate energy before repayment; telemetry does not.

`EnergyAllocation.amount_kwh` and `MeterDelivery.amount_kwh` are Decimal(20,2)
kWh; allocation quantum **0.01 kWh = 10 Wh**. Telemetry cumulative and accepted
consumption deltas are integer Wh, never rounded to 10 Wh per reading.
`MeterDelivery` is the database outbox and reservation. Its unique `command_id`
is the application identity; optional `request_id` groups source splits, with
database uniqueness on (allocation, request_id). Allocation row locks serialize
reservation. The request-ID reuse check binds owner, meter and total amount.
It is not a global cross-meter database uniqueness constraint.

For each allocation, available = authorized minus **all** reservations;
pending/unresolved = reserved minus applied; confirmed = APPLIED only. Failed,
expired and unknown rows retain reservations. No timeout refunds or replay of
historical tokens. `UnitBalance`, `Meter.units/pending_units`, old STS tokens,
and shared ThingsBoard attributes do not authorize new delivery. Old ambiguous
balances require reconciliation, not conversion or automatic backfill.

Domains stay separate: CORE UGX, historical EUR/MTN_SANDBOX, UGX/LOCAL_DEMO
(`accounting_environment=UGX_DEMO`). Self-declared `sandbox_inventory` is
logical test inventory; enrollment is neither verified physical ownership nor
a connection. LOCAL_DEMO payments create cloud test allocations only. No demo
allocation is a permission to credit a real meter.

## Route/capability inventory

Routes come from `backend/urls.py`, `backend/api1.py`, `meter/api/urls.py`,
`webhooks/api/urls.py`, `loan/api/urls.py`, `loan/sandbox_urls.py` and
`transactions/api/urls.py` (paths below are complete and trailing slashes matter).
Owner APIs use `accounts.authentication.AccountJWTAuthentication` or Django
session authentication; session writes retain CSRF protection. Mobile read
views also use `ConsumerAccountPermission`. Device simulator routes explicitly
disable consumer authentication and verify their own hashed credential.

| Route / handler | Authentication and accepted input | Effects/retry and LOCAL_DEMO hosting result |
|---|---|---|
| POST `/webhooks/thingsboard/low-units` → `ThingsBoardLowUnitsWebhookView.post` | Constant-time `X-ThingsBoard-Webhook-Secret` against nonempty `THINGSBOARD_WEBHOOK_SECRET`; JWT grants nothing. Legacy body: `device_token, units_kwh, occurred_at`. | **Hosted 503 before view**. Else missing/bad secret 401; valid secret now **410 DEVICE_PROTOCOL_UNAVAILABLE** before lookup/write/task. Old body had arrival-time snapshots and alerts, no event ID/order, ambiguous `.first()` token mapping. No automatic retries enabled. |
| POST `/webhooks/thingsboard/daily-usage` → `ThingsBoardDailyUsageWebhookView.post` | Same shared secret; legacy body `device_token, usage_date, kwh_used`. | Hosted 503; otherwise 401/410 as above. Old overwrite-by-date behavior is contained; no ingestion or source correction is enabled. Historical daily rows remain readable. |
| POST `/api/v1/webhooks/token/` → `TokenDecryptionView.post`; POST `/api/v1/loans/verify-token/` → `LoanTokenVerificationView.post` | Historical AllowAny declarations remain, **no accepted mutation body**. GETs describe legacy formats (`token,meterNo` or `token,meter_number`), not an operational protocol. | Hosted POST 503; elsewhere POST 410 before token use or balances. No authenticated physical STS/device implementation exists. Do not replay old tokens. |
| POST `/api/v1/meter/simulator/telemetry/` → `SimulatorTelemetryView.post` | Development only: DEBUG and SIMULATED_METER_ENABLED. `X-Sim-Device-Id` UUID + `X-Sim-Device-Token`, checked against `SimulatedMeter.credential_hash`. Body v1 example below. No consumer JWT substitute. | Hosted 503; elsewhere disabled 404, credential failure 401, malformed 400. Stores device-bound `SimulatedTelemetry`; accepted cumulative deltas update simulator consumption/feedback/contact only. Event ID dedup + boot/sequence classification. No allocation, payment or delivery application. |
| POST `/api/v1/meter/simulator/ack/` → `SimulatorAcknowledgementView.post` | Same simulator credentials; `contract_version=1, delivery_id` positive integer, `command_id` UUID, exact `amount_kwh`. | Hosted 503; otherwise 404 disabled / 401 unauthorized / 409 binding error. Requires matching device/meter/current allocation owner **and durable SimulatedCommand**, not a claimed success flag. Duplicate APPLIED receipt returns newly_applied=false. |
| POST `/api/v1/meter/deliver/` and `/api/v1/meter/apply-wallet-units/` → `reserve_delivery_response` | Authenticated owner; active assigned AMI `meter_no`, exact `amount`, optional UUID `request_id`; simulator enrollment and switches required. | Hosted 503. Local development reserves attributable source rows, returns 202 QUEUED/stable command IDs. No wallet debit, network call or physical application. Retry same request identity; insufficient or foreign entitlement 409. |
| GET `/api/v1/meter/allocation-status/?meter_no=...` → `AllocationStatusView.get` | Authenticated owner; explicit number filters to own meter (without number: own aggregate). | Hosted allowed read; available/pending/confirmed and last simulator contact; no dispatch. delivery_environment UNAVAILABLE on host. Values may span historical owned domains: do not treat aggregate as a new physical spending authorization. |
| GET `/api/v1/meter/mobile-meters/`, `mobile-meters/<int:meter_id>/`, `mobile-consumption/?meter_id=...`, `mobile-deliveries/?meter_id=...` | ConsumerAccountPermission, selected owned meter. Number-based read alias remains. | Hosted allowed stored reads. Physical remaining Wh is null. Contact/relay and simulator telemetry retain source labels; delivery history includes application_confirmed only with matching durable simulator command. Consumption scope is current assigned meter, not proof of previous owner attribution. No gateway calls. |
| GET `/api/v1/meter/ami-status/`, `thingsboard-health/`, `check-units/`, `power-usage/` | Authenticated user/owned meter where applicable; legacy report may select first own AMI meter without explicit number. | **Hosted 503**. power-usage newly contained: it used to synchronize ThingsBoard and seed dev-* usage on a GET. check-units also used old retry/shared-balance bootstrap; legacy credit helpers now reject globally. Read-only mobile routes above remain usable. |
| POST `/api/v1/meter/test-meter-push/`, `admin-test-meter-push/` | First consumer auth / second IsAdminUser; DEBUG, mock AMI_GATEWAY and dev-* meter token. `amount,reference_id`; admin adds meter_no. | Hosted 503. Only local dev-* logging stub permitted by transport guard; no physical request, ledger or real receipt. Prefer durable simulator tests, not these old diagnostic success messages. |
| POST `/api/v1/meter/load-token/`, `activate-received-units/`, `generate-token/` | Authenticated consumer; unsupported legacy token operations. | Hosted 503; elsewhere explicit disabled response (load-token 410, provisioning 503). GET `/api/v1/meter/token/` remains owner-meter-bound historical token lookup, not proof of valid firmware/keypad credit. |
| PUT/PATCH `/api/v1/meter/update/` → `update_meter` | Authenticated current owner; only `label` plus current_meter_no/original_meter_no selectors. | Hosted 503 as before. Other profiles permit label update only; device token, meter number, architecture, IP, owner or balance changes return403 DEVICE_PROVISIONING_FORBIDDEN. Old web update Server Action exists but has no current component caller; its provisioning-shaped payload is explicitly rejected. Mobile flow unchanged. |
| POST `/api/v1/admin/meters/`; PATCH `/api/v1/admin/meters/<int:meter_id>/`; POST suffixes `deactivate/`, `delete/`, `transfer/` | MeterManagementView/MeterDetailView require Operator/Admin for creation/patch; lifecycle/ownership functions enforce their existing staff RBAC and audit. | Hosted writes503; GET staff registry/diagnostics retained. Legacy token assignment is not yet a unique, revocable physical device binding. No consumer access to these provisioning actions is introduced. |
| POST `/api/v1/admin/transactions/<uuid:transaction_id>/redeliver/` → `TokenRedeliveryView.post` | Existing Customer Service/Operator/Admin RBAC retained. | Hosted503. Else authorized request now503 TOKEN_REDELIVERY_UNAVAILABLE before audit/token lookup. Old code only wrote an audit containing the token then claimed SMS sent, with no delivery call. No pending obligation is cancelled. |
| POST `/api/v1/meter/send-units/`, `receive-units/`; `/api/v1/share/share-units/`, `transfer-units/`; USSD/wallet deposit/withdraw/third-party repayment aliases | Auth + corresponding seven default-off server feature guards, including confirmations/shared services. | Hosted writes 503; other profiles FEATURE_DISABLED 403. No new sharing, transfer, withdrawal or credit. Existing history/models retained. |

There is **no registered physical command-poll, physical telemetry-v2 or physical
application-ack endpoint**, no MQTT subscriber, radio receiver, LoRaWAN network
server or implemented physical credential registry. Django is not listening
to the meter radio. `utils.ami_gateway.MockAMIGateway` status is synthetic;
its `last_seen=now` is not physical contact. The old ThingsBoard gateway's
`queried_at` is a server read time, not device measurement time.

### Internal command/outbox paths (not HTTP routes)

- `meter.simulation.dispatch_delivery`: locks reservation, persists DISPATCHED
  / attempt count/time, commits, then calls the database simulator outside that
  transaction. `apply_simulated_command` durably stores unique command + local
  applied total under device lock; `acknowledge_application` alone moves the
  reservation to APPLIED after inspecting that receipt. Duplicate/concurrent
  dispatch has one credit effect. A lost ack is OUTCOME_UNKNOWN; retries reuse
  command ID. Assignment change after possible dispatch stays unknown; a never
  dispatched queued binding failure is FAILED. No automatic reservation release.
- `meter.tasks.dispatch_simulated_outbox`: finite batch of at most 100 QUEUED /
  OUTCOME_UNKNOWN or DISPATCHED older than 30s. Local default beat every minute;
  requires worker/broker or explicit local invocation. It returns 0 when the
  simulator switches are off. It is not a physical transport worker.
- Simulator state/receipts live in PostgreSQL across Python/module restarts,
  **not a separate embedded device**. `enroll_simulated_meter` uses private env
  `SIMULATOR_DEVICE_TOKEN` (>=32 characters), stores password hash, prints only
  device ID. It refuses re-enrollment; no rotation/revocation workflow yet.
  `simulate_meter_consumption` models local exhaustion with whole Wh and refuses
  excess consumption. Both commands fail outside development simulator mode.
- `meter.ami_delivery.attempt_ami_delivery`, `credit_ami_meter`,
  `retry_pending_for_meter`, `retry_all_pending_ami_deliveries`, and
  `utils.ami_gateway.apply_units_to_meter` now **reject before any effect** with
  DeviceOperationUnavailable/503. These amount-only helpers cannot be repaired
  merely by a feature switch: they lack source IDs/dedup/application receipts.
  Existing pending balances are retained. Dormant old bodies are reference code.
- `meter.services.push_units_to_thingsboard`, `set_shared_remaining_units`,
  `increment_shared_remaining_units`: no real writes accepted. Only DEBUG +
  mock gateway + dev-* stub on non-test/core inventory is allowed (logging only).
  `query_latest_units_from_thingsboard` / `query_usage_timeseries_from_thingsboard`
  reject hosted/sandbox/test inventory even when called directly. CORE read code
  remains, but has no physical freshness guarantee. Shared attribute increments
  cannot be used as an accounting or delivery acknowledgement protocol.

### Payment callbacks and reconciliation

**No active MTN callback route exists.** `loan/api/urls.py` comments out
`momo-callback/`; the old classes in `loan/api/momo_views.py` are not registered.
There is no callable webhook accepting a client/provider “success” as settlement.
The routed handlers import `transactions/api/payment_views.py` instead.

| Registered route/service | Input, effect, retry, and profile result |
|---|---|
| POST `/api/v1/meter/buy-units/`, `mobile-buy-units/`, `/api/v1/transactions/buy-units/` | Current verified purchase routes authenticate owner, explicit owned meter, whole amount, payer and request identity; only trusted provider settlement creates purchased allocation. Hosted mutations 503. Old transaction buy route is contained. Core mobile action additionally defaults off. |
| POST `/api/v1/loans/repay/momo/<int:loan_id>/`, `repay/momo/active/`, `mobile-repay/momo/<int:loan_id>/` | Verified self-repayment, owner-bound loan, whole UGX, idempotency key; provider success reduces debt only. Hosted 503 and core mobile action off. Legacy wallet/direct repayment paths do not authorize spending ambiguous balances. |
| POST `/api/v1/meter/check-payment-status/` and GET `/api/v1/loans/payment-status/<str:external_id>/` | Authenticated owner; purchase status body contains `transaction_id` (purchase integer ID); loan path uses UUID provider reference. Calls reconciliation, so **hosted 503**, not an innocent stored read. Provider request occurs outside locking transaction. Neither class adds an opposite-method alias. |
| `/api/v1/sandbox/payments/` GET/POST; `/api/v1/sandbox/payments/<uuid:reference>/` GET/POST; `/api/v1/sandbox/payment-recovery/<uuid:request_id>/` GET | Verified consumer/owner. Initiate with `purpose,amount,meter_id` or own loan ID, quote/hash as required, `client_request_id`, explicit test-term consent. Durable pending LOCAL_DEMO intent, eligible >=5 s later. GETs never settle. Owner POST completion or finite job invokes `complete_demo_payment`; early completion 409. Server-only demo authority/evidence reaches shared locked settlement; no provider I/O. These sandbox writes are explicit hosting allowlist exceptions. |
| `transactions.payment_settlement._settle_locked` | Locks intent, validates trusted evidence (provider/reference/external ID/currency/amount/purpose/status); unique nonempty (provider,provider_transaction_id) across intents + unique allocation source. Pending/failed no credit. Demo evidence cannot be submitted through normal provider evidence API. Debt locks preserve concurrent partial payments/excess; no energy on repayment. |
| `transactions.tasks.reconcile_pending_payments` | Default core beat every 5min, max100 pending MTN_PRODUCTION older than1min; no running host beat/worker. `require_real_ugx_provider` rejects sandbox profile. No automatic replay of old ambiguous operations. |
| `reconcile_sandbox_payments` / `reconcile_sandbox_payment` | Bounded EUR MTN_SANDBOX batch with persistent90s lease, timed retry/backoff30s to1h, unknown initiation not replayed as NEW. **Paused/rejected in LOCAL_DEMO** via require_mtn_sandbox. MTN implementation/credentials retained dormant, not certified operational. |
| `complete_demo_payments --run --limit 20 --max-seconds 50` | Finite host job for eligible pending LOCAL_DEMO UGX only. Default without --run is dry-run. Durable completion after browser closes, locked exactly-once effect, no physical delivery. Server countdown is eligibility, not proof of settlement. |

Payment provider purpose is validated against stored source/context; it is not
always a provider-supplied field. `_validate_evidence`/`validate_sandbox_evidence`
also bind the provider's available identifiers. Prototype and CORE payment
tests are software tests against mocked evidence, not bank/MTN certification.

## Confirmed defects and fixes in this change

| Finding | Containment/correction and regression |
|---|---|
| Hosted `power-usage/` GET escaped legacy polling denylist; could call provider and write generated dev data. | Add exact prefix to FreeTestingMiddleware unavailable reads; stored mobile consumption unchanged. Test full HTTPS hosting middleware and direct gate. |
| Internal legacy AMI amount-only credit/retry could bypass endpoint restrictions, double-send pending energy and declare HTTP acceptance “delivered”. | Reject all legacy amount-only delivery before calls/writes; no balance cancellations or replays. Transport writes only permit isolated local dev stubs; host/test-domain direct helpers reject. Tests preserve pending balance and assert zero external calls. |
| Legacy low-units arrival snapshots ignore event time; daily webhook overwrites date totals; both lack stable event/order and unique device binding. Shared-secret authentication alone cannot solve replay. | Fail closed on missing/bad secret as before; valid-secret unversioned callbacks now410. No unsafe new ingestion; implement versioned adapter later. Hosted remains503. Tests no snapshot/daily row/alert/task dispatch. |
| A previously seen old boot carrying a later measured_at could become RESET/current, replacing newer simulator cursor/relay. | Persisted boot-history check classifies retired-boot messages DELAYED regardless of their clock. Duplicate event payload mismatch already rejected. Regression verifies boot/counter/relay/reset_count unchanged. |
| API int() silently truncated1.5Wh/sequence and accepted booleans; oversized counters could hit PostgreSQL bounds. | Strict JSON integers within signed64-bit range; positive integer delivery IDs. Service validates exact types; tests reject before insert. |
| Simulator telemetry accepted for suspended/deleted/unassigned meters. | Recheck active assigned AMI binding under device lock; no telemetry/effect on invalid binding. |
| Missing/changed binding after lost ack reclassified a potentially applied delivery FAILED. | Once dispatched, keep OUTCOME_UNKNOWN and reservation; retry cannot redirect allocation to new owner. Regression preserves one durable command and 0.40 kWh reservation. |
| ThingsBoard read exceptions could include the device-token URL in logs/API errors; rejected response bodies were logged verbatim. | Log only status or exception class; never exception text/traceback or response body. Mocked credential-marker regression verifies redaction. dev-* readings also reject outside development. |
| Consumer meter-update used MeterSerializer permitting credential/architecture/number/IP replacement. | Narrow to owner-bound label metadata and reject provisioning fields403. Staff provisioning remains distinct; host restriction unchanged. Regression covers each prohibited field and retained label editing. |
| Staff token-redelivery claimed a sent SMS without any sender call, and logged the raw token in its audit. | Preserve staff RBAC, reject that specific unsupported action503 before audit/write. No general administrative disabling. Regression proves no audit or false success. |

No migrations or financial policy changes. Seven deferred flags unchanged and
disabled; all existing records, credentials, obligations and historical scores
are preserved. No enabled route is added. No frontend/mobile change or APK rebuild.

Any existing physical credential previously exposed through old URLs/tracebacks
needs an operator-led exposure review and rotation **before a physical pilot**.
The registry still stores legacy ThingsBoard access tokens in plaintext; new
provisioning/secret storage and revocation must be designed. No credential values
were displayed or rotated here, and historical credentials were not deleted.

## Proposed physical contract v2 — NOT implemented/enabled

Build the physical adapter around the existing allocations/outbox. Do not send
the simulator's v1 endpoints or database-backed receipt rules to a physical
meter. Current v1 uses exact decimal `amount_kwh`; v2 wire format should use
integer Wh (a multiple of10 for these allocations). JSON examples are HTTP
gateway envelopes, **not an agreed compact radio encoding**.

### Provisioning and credentials

1. Privileged operator creates immutable device UUID, validated physical-meter
   association and **binding epoch**, environment and active credential version.
   Self-declared prototype enrollment cannot provision hardware. Enforce unique
   active device binding per physical meter and unique device identity. A
   consumer may select an owned allocation, never pick a device/IP/key or rebind
   its destination. Deactivation/replacement requires audited review.
2. Agree device/gateway trust boundary: proposed individual device signing key
   (public key registry) and separately authenticated gateway HTTPS connection.
   Alternatively review a per-device symmetric MAC scheme. No shared consumer
   JWT or global ThingsBoard secret as device identity. Provision keys privately
   on the bench; no credentials in URLs, APK, logs or example payloads.
3. Authenticate exact canonical message bytes including version, type, IDs,
   environment, binding epoch, key version, sequence and payload. Verify device
   evidence at Django or an explicitly trusted adapter; a relay gateway receipt
   cannot impersonate meter application. Keep TLS certificate verification.
4. Add audited rotation/revocation with short reviewed overlap, server/device
   acknowledgement, and emergency disable. Rotate credentials without resetting
   command dedup ledger. Simulator tokens have no implemented rotation protocol;
   do not silently use them as production keys or rotate existing keys here.

### Command and application receipt

Proposed authenticated gateway command:

```json
{
  "contract_version": 2, "type": "CREDIT_COMMAND", "environment": "BENCH",
  "device_id": "d9148ef6-7d99-4bb4-887a-946f05500b65",
  "meter_id": 42, "binding_epoch": 1, "credential_version": 1,
  "allocation_id": 71, "delivery_id": 93,
  "command_id": "05706bc3-e5dd-437e-b2f6-b33731fb31c6",
  "credit_wh": 500, "created_at": "2026-10-16T10:00:00Z"
}
```

BENCH is a proposed isolated test scope, **not a new accepted ledger enum**.
Mapping it to a separate non-operational database is a prerequisite. Do not
make test-domain allocations consumable by a real-money/core adapter.

- Reserve under allocation lock; outbox command immutable. Worker claims a
  bounded lease/attempt under lock, commits, performs network I/O, then records
  transport outcome in another transaction. Add a physical lease/backoff/attempt
  journal before multiple workers. HTTP200, gateway/RPC receipt, or LoRaWAN ACK
  means transport receipt only, never APPLIED. No physical worker exists yet.
- Device validates environment/binding/amount/auth and atomically journals
  `(command_id, payload digest, credit_wh, application counter)` with durable
  local energy **before** emitting APPLIED. Repeated identical command returns
  same receipt; changed payload under same ID rejects. Persist through power
  failure, reboot, update and storage compaction; capacity/retention must be
  agreed so an old retry can never mint a second credit. No local credit decisions.
- Illustrative application receipt:

```json
{
  "contract_version": 2, "type": "CREDIT_APPLIED", "environment": "BENCH",
  "device_id": "d9148ef6-7d99-4bb4-887a-946f05500b65",
  "meter_id": 42, "binding_epoch": 1, "credential_version": 1,
  "allocation_id": 71, "delivery_id": 93,
  "command_id": "05706bc3-e5dd-437e-b2f6-b33731fb31c6",
  "credit_wh": 500, "application_counter": 8,
  "applied_at": "2026-10-16T10:00:02Z"
}
```

The future signature/MAC is supplied by the agreed transport, omitted here.
Server must verify it plus durable pending command, exact amount, bound device,
meter, epoch, owner-at-authorization and environment. Only then APPLIED once.
Receipt time is separately recorded; device clock is not authorization.

Lost acknowledgement: retain reservation, mark OUTCOME_UNKNOWN, query receipt or
retry **same ID**. Never create another allocation, release on timeout, change
meter destination, or infer success from telemetry balance. A command proved
never sent may fail/expire; after possible dispatch its outcome needs a durable
receipt/reconciliation. Reconciliation compares immutable source, dispatch
attempts and device receipt ledger, with audited human action on uncertainty.
Database restore/device factory reset must quarantine delivery until those
ledgers reconcile. Do not replay automatically after reset or backup restore.

### Telemetry, consumption and relay feedback

```json
{
  "contract_version": 2, "type": "TELEMETRY", "environment": "BENCH",
  "device_id": "d9148ef6-7d99-4bb4-887a-946f05500b65",
  "meter_id": 42, "binding_epoch": 1, "credential_version": 1,
  "event_id": "ae477e29-fc2e-46a3-98f0-230f8c4aa91f",
  "boot_id": "61e2a6d9-f6da-4f36-b236-24956a4e2872",
  "boot_counter": 4, "sequence": 12, "cumulative_wh": 1251,
  "remaining_credit_wh": 249,
  "measured_at": "2026-10-16T10:02:00Z", "clock_status": "SYNCED",
  "relay_requested_state": "CLOSED", "relay_feedback_state": "UNKNOWN"
}
```

`received_at` comes from Django, not this body. Remaining credit is a device
report, never an allocation/wallet mutation. Cumulative Wh should be lifetime
persistent if firmware supports it; otherwise document per-boot epoch/baseline
and unmeasured interval. `boot_counter` must survive reboot; boot UUID alone
does not order previously unseen boots. The current simulator has per-boot
baselines and classifies INITIAL/RESET/GAP/ACCEPTED/REORDERED/DELAYED/
DISCONTINUITY, not this stronger production epoch scheme.

- Dedup event ID; same ID/different content rejects. Enforce sequence identity
  per device+boot, exact bounds, authorized meter/epoch and finite schema.
- Older sequence/retired boot never replaces current state. Retain delayed data
  as historical evidence. Reject/quarantine clocks in the future or unsynchronized
  time for freshness/order; agree skew/retention limits before coding. Current
  simulator does not validate future clock skew or monotonic unseen boot order.
- Within epoch use accepted cumulative **delta**, not repeated cumulative debit;
  missing sequence with monotonic counter preserves exact observed delta but
  indicates missing samples. Do not interpolate. Counter decrease/wrap, factory
  reset, initial nonzero baseline or lost epochs need reconciliation; never
  silently add credit or claim unknown consumption zero. Preserve raw events.
- Meter enforces consumption locally against durably applied credit while
  offline; no reliance on Django reachability to run protection. Agree safe
  relay failure/offline behavior and emergency reconnect policy with hardware
  engineers. No relay command endpoint is introduced here.
- Requested state is intent, actual feedback requires a measured feedback
  circuit. With no feedback input report UNKNOWN even when the MCU drove a pin.
  Current simulator `reported_relay_state` models software only, not a contactor.

### Current v1 simulator examples (local development only)

```json
{"contract_version":1,"event_id":"ae477e29-fc2e-46a3-98f0-230f8c4aa91f","boot_id":"61e2a6d9-f6da-4f36-b236-24956a4e2872","sequence":12,"cumulative_wh":1251,"measured_at":"2026-10-16T10:02:00Z","reported_relay_state":"UNKNOWN"}
```

POST to the simulator telemetry route with its two simulator credential headers
supplied privately. Meter identity derives from authenticated simulator row,
not a body-selected meter. v1 has no remaining-credit field. Its acknowledgement
body is `{"contract_version":1,"delivery_id":93,"command_id":"05706bc3-e5dd-437e-b2f6-b33731fb31c6","amount_kwh":"0.50"}`;
it succeeds only after the simulator has persisted its matching command.

### Mobile data language

- **Available cloud test allocation** is not physical balance; **queued /
  dispatched / unresolved** is not applied. Keep current labels and no fake
  device timestamps/usage. Receipt of a payment proves payment settlement only.
- Current host can display stored/simulated telemetry with its explicit source,
  measurement/receipt timestamps and contact age. It cannot call anything live
  physical data. The current dashboard uses contact_status RECENT/STALE/
  UNAVAILABLE and MOBILE_METER_STALE_SECONDS default 120; RECENT is a contact
  label, not a quality guarantee. Even replay contact cannot make old measurement
  live. Counter/reset uncertainty hides the simulator's estimated remaining.
- Future **live** requires authenticated physical-source evidence, valid current
  binding, measured_at and receipt both within the agreed freshness threshold,
  valid clock/sequence/counter epoch, and source-labeled relay feedback.
  **Stale**: last valid measurement with age shown. **Unavailable**: no physical
  evidence, disconnected identity, unknown baseline/reset or unsupported field;
  never substitute zero, a shared attribute, demo allocation or mock last_seen.

## Radio and gateway decision

The methodology names **LoRa**; this is not evidence of a selected/available
radio module, board, frequency plan or tested RF link. No physical BOM or
firmware was verified in this audit. No PDF page claims are invented here.

| Option | Components between meter and Django | Required decisions |
|---|---|---|
| Point-to-point LoRa | Meter MCU/radio ↔ paired LoRa radio + local gateway MCU/Linux bridge → authenticated HTTPS adapter → Django/outbox. Bridge needs durable receipt/message buffer and internet backhaul. | Define framing, addressing, encryption/MAC, replay counters, retries/airtime, device pairing, offline buffer and downlink schedule; raw LoRa does not supply the LoRaWAN network stack. |
| LoRaWAN | Meter LoRaWAN end device → concentrator/packet-forwarder gateway → network server + application server/integration (join/key management as selected) → authenticated HTTPS adapter → Django. Downlink returns through network server/gateway receive windows. | Select regional parameters/legal frequency, classes/windows, activation/key custody, network operator, downlink budget and application receipt. A LoRaWAN MAC ACK still is not durable credit application. |

This separation follows [Semtech's LoRa/LoRaWAN explanation](https://blog.semtech.com/understanding-the-basics-of-migrating-an-iot-sensor-design-to-lorawan)
and [The Things Network architecture](https://www.thethingsnetwork.org/docs/lorawan/architecture/).
ThingsBoard is optional application aggregation/rule processing, not a radio
gateway or substitute for the LoRaWAN network server. Its HTTP telemetry
endpoint stores telemetry, not proof of physical actuator application:
[ThingsBoard HTTP API](https://thingsboard.io/docs/reference/http-api/getting-connected/).
Radio packet authentication and application evidence must survive any gateway
mapping; do not put cloud tenant passwords/device keys in the phone.

## alwaysdata suitability and scheduled work

`alwaysdata_settings` enforces DEBUG=false, HTTPS proxy/header+redirect, secure
cookies, explicit host/CSRF origins, private environment loader, PostgreSQL,
WhiteNoise and no worker/broker. `render_config.validate_testing_environment`
rejects device/simulation/financial flags, ThingsBoard webhook/tenant secrets,
legacy MTN credentials, non-mock AMI_GATEWAY and external CRB. `alwaysdata_sandbox_settings`
adds only isolated prototype operations and LOCAL_DEMO. Debug APK CORS origin
stays `http://localhost`; configured release scheme origin is `https://localhost`.
No CORS/CSRF weakening is needed for a server-to-server gateway.

Relevant device settings (names only, no credential values):
`SIMULATED_METER_ENABLED`, `DEBUG`, `SIMULATOR_DEVICE_TOKEN`, `AMI_GATEWAY`,
`THINGSBOARD_BASE_URL`, `THINGSBOARD_INTERNAL_BASE_URL`,
`THINGSBOARD_TIMEOUT_SECONDS` (default 15), `THINGSBOARD_VERIFY_SSL` (default true),
`THINGSBOARD_WEBHOOK_SECRET`, `THINGSBOARD_TENANT_USERNAME`,
`THINGSBOARD_TENANT_PASSWORD`, `THINGSBOARD_USAGE_TELEMETRY_KEY` (default daily_kwh),
`AMI_LOW_UNITS_THRESHOLD_KWH`, `AMI_LOW_UNITS_ALERT_COOLDOWN_HOURS`,
`AMI_LOW_UNITS_POLL_SECONDS`, `MOBILE_METER_STALE_SECONDS` (default 120).
None of these settings authorizes the contained legacy physical writer.

Keep each of `FEATURE_PEER_SHARING_ENABLED`, `FEATURE_METER_TRANSFERS_ENABLED`,
`FEATURE_THIRD_PARTY_REPAYMENT_ENABLED`, `FEATURE_USSD_ENABLED`,
`FEATURE_WALLET_DEPOSITS_ENABLED`, `FEATURE_WALLET_WITHDRAWALS_ENABLED`,
`FEATURE_EXTERNAL_CRB_ENABLED` false, along with existing core mobile-payment,
purchase-history scoring, legacy simulated-provider and simulated-device switches.

- Current WSGI profile supports HTTPS requests, stored consumer monitoring,
  authentication, Django-hosted verification/reset forms and scheduled durable
  account-email draining. Physical telemetry POST, dispatch, gateway polling
  and application acknowledgements are intentionally unavailable. There is no
  operational physical reconciliation service on this host.
- BACKGROUND_TASKS_AVAILABLE=false; CELERY_TASK_ALWAYS_EAGER=false; beat schedule
  empty; broker/result backend None; REDIS_URL empty; cache is per-process LocMem
  (not an idempotency/receipt store). `HostingTask.apply_async` /
  `HostingCelery.send_task` reject unavailable queue operations. Do not turn on
  global eager tasks or claim queued work delivered. Account mail dispatch uses
  a scoped database outbox; unsupported email/task types do not silently succeed.
- Disabled default tasks: AMI snapshots (6-hourly), daily aggregation (01:15),
  low-unit polling (configured AMI_LOW_UNITS_POLL_SECONDS), simulator outbox
  (minute), core provider reconciliation (5min). Older retry_pending_ami_deliveries
  is not scheduled and now rejects direct calls too. No Redis/Celery needed for
  the two finite jobs below; Redis/Celery+beat/worker or an independently hosted
  finite dispatch mechanism would be needed for the existing task design.
- Keep the documented two every-minute jobs; their actual dashboard state was
  not inspected:

```sh
ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings /home/shanonsimon/energy-venv/bin/python /home/shanonsimon/energy-sharing/manage.py drain_account_emails --send --limit 5
ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings /home/shanonsimon/energy-venv/bin/python /home/shanonsimon/energy-sharing/manage.py complete_demo_payments --run --limit 20 --max-seconds 50
```

Pause the MTN sandbox reconciliation job in LOCAL_DEMO. These schedules do not
deliver energy or synchronize hardware. [alwaysdata's task documentation](https://help.alwaysdata.com/en/docs/web-hosting/tasks/)
says start time varies within the minute and overlapping unfinished runs are
skipped: not a real-time five-second or radio-control service.

For bench work, use a separate development database/server with the simulator,
then a separately hosted gateway/transport process. The confirmed Free-plan
deployment cannot run persistent background services; do not place an MQTT
subscriber, radio daemon or real-time worker in WSGI. A future finite HTTPS
ingest/dispatch design could use durable PostgreSQL on a suitable approved
profile, but needs new auth/routes, process/resource capacity checks and explicit
permission to enable physical capabilities. No such bypass is added here.

## Staged bench plan and decisions

1. **Software transport only:** agree schema/auth/binding/domain/clock limits;
   implement a separate loopback fake gateway and firmware state machine in an
   isolated DB. Test malformed/missing credentials, wrong meter/epoch, duplicate
   payload mismatch, telemetry cannot settle, network timeout, delayed receipts,
   concurrent workers, browser closure and server restart. Assert exact Wh
   conservation and one command/application effect. Keep current host blocked.
2. **Persistent-device storage:** software fault injection then unconnected MCU
   on low-voltage bench supply. Power interruption before/during/after journal
   commit, repeated boot, factory reset and firmware update; confirm durable
   credit/command IDs, counter epochs and replay resistance. No mains/relay load.
3. **Low-voltage wiring and measurement:** sensor simulator/calibrated reference
   and isolated safe load, indicator or low-voltage relay. Verify counter
   precision/calibration, exhaustion, requested vs measured contact feedback,
   offline enforcement and uncertain outcome quarantine. Obtain qualified
   electrical review before any mains work; do not infer accuracy from mocks.
4. **Selected radio bench:** chosen hardware/gateway/network server; test packet
   duplication/loss/reorder, receive-window/downlink limits, gateway offline
   buffers, RF interference/range and key rotation. Measure latency/loss/range;
   this evidence is separate from accounting correctness and sensor accuracy.
5. **Controlled end-to-end bench:** only explicitly authorized BENCH allocations,
   verified receipts, rollback/recovery/reconciliation drill, source-labeled
   consumer monitoring. Review results before a separate physical pilot profile.
   No reinterpretation of existing UGX_DEMO/EUR history as real physical credit.

Decisions required before firmware coding: actual meter/MCU/sensor/relay and
feedback hardware; LoRa point-to-point or LoRaWAN and regional parameters;
gateway/backhaul/operator location; physical ownership/binding lifecycle;
credential/signature/MAC/key storage and recovery; counter and command journal
power-loss guarantees/limits; clock synchronization/skew and freshness limits;
Wh resolution and independent accuracy validation; offline/relay safety policy;
worker deployment and reconciliation operator procedure. Decide whether STS
keypad tokens are required at all; existing numeric tokens are not evidence of
certified STS encoding, key management or anti-replay support.

## Validation evidence

The repository was clean at audit start; no applicable AGENTS.md was found in
the project or ancestor directories. All changes below are local/uncommitted.
Test fixture sources use example.invalid identities and mocked providers.
No actual MTN, ThingsBoard HTTP transport, radio, sensor, physical receipt,
relay feedback, credential rotation or phone runtime is certified by these tests.

Existing `meter.tests_allocation_delivery` exercises PostgreSQL concurrent
reservation/dispatch/disbursement/consumption, lost ack, process-module restart,
wrong device/owner, durable outbox and exact counter deltas. New
`meter.tests_hardware_readiness` adds retired boot, numeric/binding/auth and
legacy service containment tests; hosting HTTPS tests include all device aliases.

Isolated PostgreSQL 18 at `/tmp/gpawa-alwaysdata/pg`, port 55445, guarded role
`gpawa_alwaysdata_test`; Django creates/destroys its disposable test database.
`deploy/test-hosting.py` clears inherited environment, prevents local .env
loading, mocks mail and prohibits external requests. WhiteNoise 6.12.0 (already
pinned by the project) was installed only into `/tmp/gpawa-alwaysdata-deps` for
hosting tests; project dependencies unchanged. Local Python 3.14/Django 5.2;
host Python 3.12.15 was not executed.

```sh
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py meter.tests_hardware_readiness meter.tests_allocation_delivery transactions.tests_payment_settlement transactions.tests_demo_payments loan.tests_financial_correctness backend.tests_feature_flags
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py meter.tests_hardware_readiness meter.tests_allocation_delivery
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --sandbox-profile backend.tests_alwaysdata.AlwaysdataProfileTests backend.tests_alwaysdata.AlwaysdataAuthenticationFlowTests backend.tests_alwaysdata.AccountMailOutboxTests accounts.tests_account_pages transactions.tests_demo_payments backend.tests_feature_flags
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --check-migrations
npm --prefix mobile run typecheck
npm --prefix mobile test
node --test frontend/tests/features.test.mjs
git diff --check
```

- Combined regression run: **109 tests, OK with 1 known expected failure**
  (CORE overdue-after-completion). Log `/tmp/gpawa-hardware-final.log`.
- Final targeted run after consumer metadata/staff redelivery containment:
  **38 tests, OK**, including the new 14 hardware tests and PostgreSQL
  concurrency/restart/delivery suite. Log `/tmp/gpawa-hardware-containment-final.log`.
- Final actual alwaysdata LOCAL_DEMO profile run: **63 tests, OK**, including
  HTTPS device-route blocking, auth/refresh/logout, CSRF account forms, durable
  scheduled-email behavior, demo payment concurrency and the disabled flags.
  Log `/tmp/gpawa-hardware-hosting-complete.log`.
- Migration drift check: **no changes detected** in loan/meter/transactions;
  no migration added or applied outside the disposable test database. Python
  syntax and deployment-allowlist existence checks passed; git diff --check clean.
  Log `/tmp/gpawa-hardware-migration-check.log`.
- Mobile strict TypeScript passed; all **8 test files** passed. Web feature/
  navigation test file passed. Logs `/tmp/gpawa-hardware-mobile.log` and
  `/tmp/gpawa-hardware-web.log`. No browser/native phone session was run.

Exploratory failures were resolved rather than bypassed: the old allocation
test expected FAILED after DISPATCHED (now correctly unknown); older email
outbox fixtures used plain HTTP and a legacy verification GET that hosted
security intentionally rejects. Tests now use the real HTTPS proxy contract
and CSRF-protected explicit confirmation form, including its required confirm
checkbox. No redirect/auth/CSRF restriction was relaxed. Existing caught
wallet mirror-signal duplicate meter-number diagnostics still appear during
synthetic fixture setup; those signal modules are unchanged and test assertions
pass. They are not evidence of hosted records being inspected or repaired.

Frontend/mobile files and response contracts are unchanged; no APK rebuild or
frontend production build is necessary for this backend-only containment patch.
The known CORE overdue-after-completion expected failure remains outside this
hardware work; do not mark live financial deployment ready.

## Exact deployment handoff — instructions only, NOT executed

No schema/model change or new migration. Runtime patch allowlist:
`backend/deploy/hardware-readiness.files`. It intentionally excludes tests,
secrets, environments, keys, generated files and migrations; it requires the
existing consumer-sandbox baseline already installed. The broader
`consumer-sandbox.files` is also updated so later uploads retain these guards.

From the repository root, first review dry-run, then upload if authorized:

```sh
rsync -avnc --files-from=backend/deploy/hardware-readiness.files --exclude='.env*' --exclude='*.env' --exclude='venv*/' --exclude='.venv/' --exclude='__pycache__/' --exclude='*.pyc' --exclude='*.log' --exclude='*.sqlite3*' --exclude='*.db' --exclude='*.sql' --exclude='*.dump' --exclude='*.pem' --exclude='*.key' backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
rsync -avc --files-from=backend/deploy/hardware-readiness.files --exclude='.env*' --exclude='*.env' --exclude='venv*/' --exclude='.venv/' --exclude='__pycache__/' --exclude='*.pyc' --exclude='*.log' --exclude='*.sqlite3*' --exclude='*.db' --exclude='*.sql' --exclude='*.dump' --exclude='*.pem' --exclude='*.key' backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
ssh shanonsimon@ssh-shanonsimon.alwaysdata.net
cd /home/shanonsimon/energy-sharing
export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
export DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings
/home/shanonsimon/energy-venv/bin/python manage.py check_alwaysdata_database
/home/shanonsimon/energy-venv/bin/python manage.py migrate --plan
/home/shanonsimon/energy-venv/bin/python manage.py check --deploy
```

Verify target `shanonsimon_energy_test` / `shanonsimon` at
`postgresql-shanonsimon.alwaysdata.net` and encrypted=True. Stop if different or
the baseline has unexpected pending migrations; **this patch requires no migrate
execution**. Static assets unchanged; collectstatic unnecessary. Do not add
hardware credentials or change the private environment. Keep directory 0700,
environment 0600; never upload/source/print local .env.

Keep WSGI path `/home/shanonsimon/energy-sharing/backend/alwaysdata_sandbox_wsgi.py`,
working directory `/home/shanonsimon/energy-sharing`, virtualenv
`/home/shanonsimon/energy-venv`, Python 3.12.15, and existing static mapping.
In **Web → Sites → shanonsimon.alwaysdata.net**, use Restart (circular arrow).
See official [Python WSGI configuration](https://help.alwaysdata.com/en/docs/web-hosting/languages/python/configuration/)
and [site restart](https://help.alwaysdata.com/en/docs/web-hosting/sites/restart-a-site/).

Credential-free HTTPS checks after restart (no provider/device commands):

```sh
curl --fail --silent --show-error https://shanonsimon.alwaysdata.net/api/v1/features/
curl --silent --show-error -o /tmp/energy-device-block.json -w '%{http_code}\n' https://shanonsimon.alwaysdata.net/api/v1/meter/power-usage/
curl --silent --show-error -o /tmp/energy-ack-block.json -w '%{http_code}\n' -H 'Content-Type: application/json' --data '{}' https://shanonsimon.alwaysdata.net/api/v1/meter/simulator/ack/
```

Expect features physical_delivery=false, physical_meter=false, simulator=false,
seven optional features=false, LOCAL_DEMO. The last two checks must be 503 with
TESTING_OPERATION_UNAVAILABLE; they cannot reach a device. Confirm existing
account-page forms/CSRF, email schedule and authenticated stored meter screens
still work using isolated tester accounts. No deployment/check above was run
against the host during this audit.
