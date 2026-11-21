> Current new-payment policy: [UGX lending and token diagnostics](UGX_LENDING_AND_TOKEN_DIAGNOSTICS.md) pauses new EUR purchases/repayments while preserving MTN history and recovery. The earlier initiation instructions below are historical, not authorization to start a payment.

# MTN Sandbox → SANDBOX token → AC_LAB credit-only milestone

Implemented locally, **not deployed or tested against MTN, a phone or a board**.
This supersedes the earlier UGX-only/MTN-denied sections in PROTOTYPE_AC_LAB.md,
MTN_SANDBOX_RESUMPTION.md and COMBINED_AC_MTN_ROLLOUT.md. Existing records, private
credentials, account-page CSRF handling and email schedules are retained.

## Explicit domains, no second payment pipeline

| Source | Financial records | Energy/token/device domain | Protocol |
|---|---|---|---|
| New MTN Collections Sandbox purchase | MTN_SANDBOX, EUR TEST | SANDBOX | GPAWA_PZEM_V2 |
| Existing demo obligations | LOCAL_DEMO, UGX DEMO | UGX_DEMO | GPAWA_PZEM_V1 |
| Historical core activity | Existing core UGX | CORE | Not accepted by this adapter |

Keep `PROTOTYPE_PAYMENT_PROVIDER=MTN_SANDBOX`. Seven deferred features stay off;
sharing/transfers are retired; all five configurable optional flags stay false.
New EUR lending is still hard-disabled pending its independently reviewed policy.
Existing matching EUR debt can be repaid; a repayment creates no allocation/token.
Neither UGX debt nor monetary limits are converted to EUR.

The existing `MTNSandbox` adapter, PaymentIntent, settlement authority, accepted
SandboxQuote and SandboxSettlement are reused. HTTP202 is pending; HTTP200 only
means the lookup succeeded. The adapter maps JSON SUCCESSFUL to trusted evidence;
settlement checks reference, externalId, amount, currency, payer, purpose, source
and nonempty unique financialTransactionId. Invalid/unknown evidence leaves the
intent unresolved, FAILED has no financial effect. Network calls stay outside
locking transactions. Persistent leases/backoff and one durable provider reference
remain authoritative; a timeout does not initiate another charge.

All NEW MTN energy purchases now require token issuance and valid private keys,
even when the device flag is off. Missing keys disable purchases before collection;
they do not disable EUR debt recovery or switch to demo. Frozen accepted pricing
is reproduced without consulting a current UGX tariff. The financial transaction
creates exactly one allocation and encrypted, meter-bound 15-digit token, or rolls
back both local effects. It also preserves billed+residual=received. Accepted
energy must fit the existing firmware contract: positive integer Wh, divisible by
10, at most1,000,000Wh. Unsupported quotes are rejected before provider dispatch.
A late key failure retains a pending funded outcome for same-reference recovery.
Old settled records missing tokens are not backfilled or replayed automatically.

## Device capability and lifecycle

`prototype_device.enabled()` still requires the opt-in alwaysdata consumer-testing
profile, a recognized provider domain and the hard-false relay setting. The four
existing POST routes are reused; no duplicate URL implementation or global hosting
middleware exception is added:

| Route under `/api/v1/prototype-device/v1/` | Accepted additions to identity | Effect/retry |
|---|---|---|
| `session/` | boot ID/counter, application counter, journal totals, initialization/ACK state | Validates durable binding/recovery; no new credit |
| `redeem/` | 15-digit token, application counter | One entire-allocation reservation and frozen command; lost response returns identical pending command |
| `ack/` | command/receipt IDs, digest, sequence, exact Wh, allocation/delivery IDs, applied_at | Idempotent durable-credit attestation; no new allocation/payment |
| `telemetry/` | boot/sequence, cumulative microWh, PZEM readings, measurement time, output request/UNKNOWN feedback | Ordered evidence only; cannot issue energy or mark delivery applied |

Every request includes `X-Device-Id` and a separate unique `X-Device-Token`.
Consumer JWTs do not authenticate here. Device, owner, current meter ownership,
active verified consumer, environment, storage ID, binding epoch and protocol must
match. A UGX token fails even inside an otherwise valid SANDBOX request. Revoked
devices fail closed. One unresolved command/device and receipt/sequence uniqueness
are enforced in PostgreSQL. Acknowledgements recheck source/domain bindings.

Example public identity (all IDs illustrative; no credentials/token):

```json
{"protocol":"GPAWA_PZEM_V2","device_id":"11111111-1111-4111-8111-111111111111","meter_number":"00000001234","storage_id":"22222222-2222-4222-8222-222222222222","binding_epoch":1,"environment":"SANDBOX","hardware_class":"AC_LAB"}
```

Command identity/digest/credit remain frozen across retries. Integer `credit_wh`
is derived from the allocation (0.01kWh=10Wh). Telemetry uses integer microWh
(1Wh=1,000,000microWh), with device sequence/boot ordering and server receipt time.
Restart before ACK may reconcile precisely the one pending command. No timeout
releases an uncertain reservation; no storage reset or prior command is replayed.
Full payloads/canonical digest rules: `firmware/ac-lab-domain/docs/API_CONTRACT.md`.

Owner APIs: `GET /api/v1/meter/mobile-meters/<id>/?environment=SANDBOX` and
`GET /api/v1/meter/mobile-consumption/?meter_id=<id>&environment=SANDBOX`.
The default consumer-testing domain follows the provider, while explicit UGX/CORE
history remains separate. Responses expose lab_environment/protocol, exact journal
credit, measured usage and contact/measurement times. Missing evidence is null;
after90s it is stale; revoked devices cannot be called recent. Sensor faults are
unavailable, not zero. Output feedback remains UNKNOWN and output_enabled=false.
Android and shared token UI distinguish payment confirmed, token issued, pending
application and ACKed **credit saved on AC lab device**. No utility delivery or
load switching is claimed. This is periodic telemetry, not certified live metering.

## Schema and existing binding boundary

Migration **meter0033_ac_lab_sandbox_environment** depends on existing meter0032.
It replaces the output/domain check constraint to admit SANDBOX as well as legacy
UGX_DEMO, while still enforcing AC_LAB/output-disabled. It changes no rows, default
currency, credentials, journal IDs or financial amounts. Never edit/fake0032.

Provisioning now requires explicit `--environment SANDBOX` in MTN mode. It retains
one-time private credential generation,0600 exclusive file creation and staff
authorization. It refuses a meter with ANY prior bench/AC binding, including a
revoked binding. An old UGX device cannot be relabelled/reused automatically. A
fresh eligible unbound test meter/binding or a separately reviewed recovery plan is
required. Existing UGX credentials/journals/obligations are preserved; they cannot
authenticate under the active SANDBOX capability. Do not erase them to unblock setup.

## Ordered alwaysdata rollout — operator commands, not executed here

1. From repository root, review dry-run and the read-only migration preview first:

   ```bash
   rsync -avnc --files-from=backend/deploy/mtn-ac-lab-domain.files backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
   python3 backend/deploy/preview_combined_migrations.py
   ```

   The expanded allowlist includes the earlier combined rollout, meter0032,
   new0033 and all changed backend services/tests. It excludes environment files,
   credentials, virtualenvs, generated/static/media files, database files and APKs.
   No --delete. Preview reads host metadata using local migration source, verifies
   the exact DB/TLS, and does not upload code, mutate records or contact MTN.
   Stop on unavailable SSH, mismatched DB/TLS, unexpected migrations or divergence.

2. Before uploading, follow the **private code/config/device-key/database backup**
   commands in COMBINED_AC_MTN_ROLLOUT.md step3. Verify the private pg_dump can be
   restored; never expose backups or overwrite current payments with a stale dump.
   Then upload only the reviewed allowlist:

   ```bash
   rsync -avc --files-from=backend/deploy/mtn-ac-lab-domain.files backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
   ```

3. On host, preserve the existing private file; edit privately, do not copy a local
   .env or paste secrets into a shell command/history/chat:

   ```bash
   chmod 700 /home/shanonsimon/.config/energy-sharing
   chmod 600 /home/shanonsimon/.config/energy-sharing/backend.env
   nano /home/shanonsimon/.config/energy-sharing/backend.env
   ```

   Keep `PROTOTYPE_PAYMENT_PROVIDER=MTN_SANDBOX`, dedicated existing MTN_SANDBOX_*
   credentials, EUR currency, exact HTTPS sandbox base, explicit stored EUR pricing
   policy and `DB_SSLMODE=require`. Set `ENERGY_TOKEN_ISSUANCE_ENABLED=true` with
   the EXISTING private ENERGY_TOKEN_ENCRYPTION_KEYS and ENERGY_TOKEN_LOOKUP_KEY;
   see energy-tokens.env.example for syntax. Do not rotate/replace existing keys.
   Set `PROTOTYPE_AC_LAB_ENABLED=true` only for reviewed credit-only commissioning.
   The settings default remains false. PROTOTYPE_RELAY_OUTPUT_ENABLED stays
   hard-false; general physical routes, core money writes, simulator dispatch,
   all deferred flags and EUR loan origination remain blocked. Preserve Gmail
   secrets, Django account URLs, CSRF/CORS/HTTPS settings and account-email outbox.

4. Check target/actual TLS and review the real migration plan after code upload:

   ```bash
   cd /home/shanonsimon/energy-sharing
   export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
   export DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings
   /home/shanonsimon/energy-venv/bin/python -m pip check
   /home/shanonsimon/energy-venv/bin/python manage.py check_alwaysdata_database
   /home/shanonsimon/energy-venv/bin/python manage.py check --deploy
   /home/shanonsimon/energy-venv/bin/python manage.py showmigrations meter
   /home/shanonsimon/energy-venv/bin/python manage.py migrate --plan
   ```

   Require DB shanonsimon_energy_test, user shanonsimon, host
   postgresql-shanonsimon.alwaysdata.net and encrypted=True. Review0032 if not
   already applied, then0033; stop for unexpected pending work. Only after review:

   ```bash
   /home/shanonsimon/energy-venv/bin/python manage.py migrate --noinput
   /home/shanonsimon/energy-venv/bin/python manage.py collectstatic --noinput
   mkdir -p /home/shanonsimon/.config/energy-sharing/devices
   chmod 700 /home/shanonsimon/.config/energy-sharing/devices
   ```

5. Select an existing owned, active, 11-digit, unbound sandbox-inventory meter and
   a verified active staff ADMIN/OPERATOR. Replace the three numeric placeholders
   with privately reviewed IDs; they are not credentials. Do not create/reassign
   meters automatically. Provision ONLY after physically disconnecting relay/load:

   ```bash
   /home/shanonsimon/energy-venv/bin/python manage.py provision_ac_lab_device METER_ID --environment SANDBOX --owner-id OWNER_ID --operator-id OPERATOR_ID --private-config /home/shanonsimon/.config/energy-sharing/devices/ac-lab-sandbox.json --confirm-output-disabled
   ```

   This changes hosting data when the operator eventually runs it; it was not run
   on the host here. The0600 file contains the new unique secret: transfer/edit it
   privately into the matching firmware configuration, never log/cat it publicly.
   Existing private files are not overwritten. Revocation (if required later) uses
   `revoke_ac_lab_device DEVICE_UUID --operator-id OPERATOR_ID`; reservations stay.
   Rotation/rebinding used storage requires a separate recovery review, not a new
   identity over old credits.

6. Web → Sites → shanonsimon.alwaysdata.net → **Restart**. Retain Python3.12.15,
   venv `/home/shanonsimon/energy-venv`, backend working directory and
   `backend/alwaysdata_sandbox_wsgi.py`, the two environment variables above,
   static mapping and HTTPS redirect. Recheck features over HTTPS. Expected:
   MTN_SANDBOX/EUR, loans=false, physical_delivery=false, seven flags=false,
   ac_lab enabled=true/environment=SANDBOX/protocol=GPAWA_PZEM_V2/output=false.
   Unauthenticated device POST must401, not successful initialization. Flag-off
   or ordinary hosting returns503. These checks do not initiate a payment.

7. Preserve the existing account-email schedule exactly. Preserve original-provider
   recovery of old pending demo payments; never cancel/replay/convert records.
   MTN reconciliation remains a finite scheduled task (every minute subject to
   plan limits; lease/backoff may delay status beyond one minute):

   ```bash
   ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings /home/shanonsimon/energy-venv/bin/python /home/shanonsimon/energy-sharing/manage.py reconcile_sandbox_payments --limit 2 --max-seconds 50
   # --run performs provider work: review pending intents/authorization before enabling.
   ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings /home/shanonsimon/energy-venv/bin/python /home/shanonsimon/energy-sharing/manage.py reconcile_sandbox_payments --run --limit 2 --max-seconds 50
   ```

   The first line is dry-run; the second may submit previously authorized NEW
   intents and query existing references. Neither was executed here. Keep the old
   `complete_demo_payments --run --limit 20 --max-seconds 50` schedule for old
   LOCAL_DEMO pending records. No Celery/Redis process or general delivery worker
   is required for device-initiated HTTPS. Free-plan quota/latency remains untested.

## Firmware and later real test gate

Correct active path, patch instructions, retained diagnostics/hd44780, private
configuration, journal separation and local C++ checks are documented in
`firmware/ac-lab-domain/README.md`. No new signing key or TLS bypass is introduced.
The corrected active Arduino sketch received the seven public-source changes;
its previous public files were backed up and private headers verified unchanged.
Diagnostic mode remains1; no target compile or flash was performed. Rebuild and
explicitly commission authenticated mode before expecting V2 requests. A fresh
signed testing APK is documented in `mobile/MTN_AC_LAB_BUILD.md`; its signature
matches the previous local testing artifact. Install that update for the current
capability labels/readers. No phone testing was performed here.

Only after deployment, private provisioning, target compilation and reviewed
credit-only configuration: separately authorize one MTN sandbox transaction and
confirm pending states issue no token, SUCCESSFUL yields exactly one accepted-Wh
allocation/token, keypad redemption on the matching board saves durable credit,
unplug/restart preserves that credit/receipt, lost ACK retries recover the same
command, and owner reads show measured/stale/unavailable evidence honestly. Do
not operate a relay, erase NVS, use real money or expose token/credential logs.

## Local evidence

See tests in meter/tests_mtn_device.py and meter/tests_prototype_device.py for
mocked-provider end-to-end, reference/currency/amount mismatch, missing transaction
ID, wrong meter/domain/consumer authentication, revoked binding, pending-command
reboot/lost ACK, duplicate ACK, concurrent redemption/ACK and ordered telemetry.
Client tests exercise shared web/Android capability and receipt presentation.
Exact final test commands/results are recorded in MTN_AC_LAB_VALIDATION.md.
Host C++ tests validate journal/contract logic, not ESP32 flash durability, actual
TLS, MTN credentials, PZEM accuracy, phone networking or physical safety.

The explicit recovery check also requires a SANDBOX token when an already-submitted
MTN purchase is reconciled while new collections are paused. It never falls back
to a UGX token or silently settles tokenless because the current mode differs.
