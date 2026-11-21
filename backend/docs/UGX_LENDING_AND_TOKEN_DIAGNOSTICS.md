# UGX lending, paused new payments, and token diagnostics

Latest capability audit and coordinated rollout: [UGX_CAPABILITY_PARITY_ROLLOUT.md](UGX_CAPABILITY_PARITY_ROLLOUT.md). Its mapping proposal is pending a decision; no UGX MTN conversion is implemented. This earlier document records the prior pause decision; preserve the host’s existing explicit payment setting during deployment.

Implemented locally; no hosted deployment, provider initiation, phone or physical
board test performed. This supersedes the **new-payment** instructions in
MTN_AC_LAB_SANDBOX.md. Do not start another purchase to investigate a rejected token.

## Approved scope and outstanding policy

Keep `PROTOTYPE_PAYMENT_PROVIDER=MTN_SANDBOX`. The current user decision is to
pause new EUR payments, not switch to LOCAL_DEMO and not relabel EUR receipts.
`SANDBOX_NEW_PAYMENTS_ENABLED=false` is the alwaysdata sandbox default; explicit
boolean parsing rejects invalid values. Purchase quotes, payment initiation and
never-submitted MTN intents fail closed before provider calls. Already-submitted
references retain their original provider and can still reconcile. The scheduled
query skips never-submitted NEW intents while paused, preventing batch starvation;
these records remain pending for operator review, never automatically cancelled.

The official MTN community confirms sandbox accepts EUR only:
https://momodevelopercommunity.mtn.com/momo-api-sand-box-q-a-6/currency-not-supported-invalid-currency-258
Uganda production uses UGX and requires separate production onboarding:
https://momodevelopercommunity.mtn.com/how-to-59/momo-api-production-configuration-101
This change does not perform that onboarding or enable real money.
New UGX purchases and repayments therefore remain unavailable. A matching UGX
provider or a separately approved simulator decision is still required. Existing
EUR payments, debts and receipts keep their actual currency and amounts.

## Authoritative UGX prototype lending

`SANDBOX_UGX_LOANS_ENABLED=true` defaults only in the alwaysdata consumer sandbox.
Core/Render paths do not acquire this capability. Financial records reuse the
existing `UGX_DEMO` ledger and `SandboxQuote` / `SandboxLoan`; no competing ledger,
currency conversion, historical rewrite or schema migration is introduced.

| Rule | Source / current default | Freeze or fresh check |
|---|---|---|
| Minimum / maximum | Existing DEMO_MINIMUM=1000 / DEMO_MAXIMUM=50000 UGX | Accepted quote policy |
| Starter configuration | Existing DEMO_STARTER_LIMIT=5000 UGX | Never bypasses 80% |
| Minimum score | Existing threshold, at least 80% | Stored assessment and fresh debt/limit check |
| Interest / fee / term | Existing DEMO_INTEREST_PERCENT=5 / DEMO_FEE=0 / DEMO_DUE_DAYS=7 | Accepted quote policy |
| Pricing | Admin active DOMESTIC ElectricityTariff and TariffBlock, owner-level UGX_DEMO purchase bands and service charge | Frozen inputs, revision, breakdown; changed pricing invalidates stale quote |
| Monetary precision | Whole UGX; existing half-even interest rounding once | Frozen calculation description |
| Energy | Floor to 0.01 kWh = 10 Wh; integer Wh command | Billed + residual conserves principal |
| Repayment | Unavailable in MTN EUR mode | Warning in terms, loan record, both clients |

These are inherited **prototype assumptions**, not approved utility tariffs or
real underwriting. The admin tariff is required; there is no UGX fallback price.
The established UGX policy checks outstanding UGX_DEMO debt and core obligations.
A historical EUR test loan remains a separate obligation; this increment does not
invent a new cross-currency borrowing limit or silently close/convert that debt.
It stays visible in earlier-currency history. An existing active UGX_DEMO loan or
unresolved core obligation still blocks new UGX borrowing under the existing rules.
New UGX loans
cannot be settled by EUR receipts, even if numeric amounts happen to match.

The existing `loan.scoring` weighted calculation and stored `DemoCreditAssessment`
are reused. `SIMULATED_ACCOUNT_V1` supplies fixed explicit synthetic scenarios;
no CRB calls, questionnaire, personal-identifier hashing or random screen-refresh
scores. Registration creates pending evidence; verified meter enrollment or the
owner-only `POST sandbox/assessment/` with **only meter_id** completes it. GETs
remain read-only. Existing ready evidence is not overwritten. Existing UGX demo
purchase contributions keep their frozen policy and stable source identities;
EUR payments add no UGX scoring points.

New clients request `GET sandbox/assessment/?meter_id=<id>&lending=ugx`. Additive
`features.sandbox.lending` metadata exposes the new contract; the legacy EUR
`sandbox.loans` flag remains false. Loan quote POSTs require
`loan_contract=UGX-PROTOTYPE-SANDBOX-v1`, then the existing quote hash, expiry,
explicit consent and idempotent application ID. Both clients retain pending recovery.

### Financial domain is not the device energy domain

New accepted terms explicitly freeze policy `DEMO-UGX-ACLAB-v1`, lending contract
`UGX-PROTOTYPE-SANDBOX-v1`, financial UGX/UGX_DEMO and energy SANDBOX. The source
validator checks this marker, quote hash, owner, meter, principal and frozen admin
pricing before admitting that loan's energy to SANDBOX/GPAWA_PZEM_V2. Legacy
UGX_DEMO loans/tokens without this marker remain UGX_DEMO; EUR sources remain EUR
money/SANDBOX energy; CORE stays CORE. Merely removing a domain check is forbidden.

One approved disbursement produces one source-linked allocation and one encrypted
15-digit meter-bound token. Retries cannot create a second credit. Approved loan
energy is authorized before repayment by design. Repayments create no energy or
tokens. Device ACK means durable device credit, not load switching or measured
delivery. Physical output remains prohibited in firmware and backend.

## Token rejection: what is and is not known

Confirmed: the previous firmware mapped several HTTP400/404/409 cases to one
"Token not accepted" message. That obscured route, lookup, source and reservation
failures. It does **not** establish which failure affected the hosted purchase.
The attempted read-only SSH audit was refused by SSH authentication; no hosted
record or provider evidence was inspected or changed.

Firmware and Django now emit only operation, HTTP status and a fixed allowlisted
code, e.g. `DEVICE operation=redeem http=404 code=TOKEN_LOOKUP_MISS`. Arbitrary
response values/bodies, token digits, credentials and Authorization headers are
never diagnostics. Failures log at WARNING so default hosted logging captures them without DEBUG or a global log-level change; successful calls remain INFO. LCD distinguishes missing token, key/source review, pending
command and already-used token. Wrong-owner/meter/domain remain generic. Firmware uses a conservative code subset and HTTP fallbacks; when it falls back, correlate that one operation/status with the Django WARNING line, which preserves the full fixed backend protocol vocabulary. No response body is needed.

The exact missing evidence is **one normal redeem operation's HTTP status and
fixed error code**, or this sanitized read-only operator report after upload:

```bash
python manage.py audit_ac_lab_credit --operator-id 1 --owner-id 3 --meter-id 3 --limit 5
# Optional: --purchase-reference <existing-receipt-reference>
```

The command requires active verified staff, uses a PostgreSQL read-only
transaction, and reports stored settlement/source/domain/key-lookup integrity,
device binding and pending command/ACK status. It never contacts MTN, decrypts
token digits into output, issues a token or retries a command. A stored consistent
chain is not a fresh independent provider verification. Preserve all existing
keys, identity, tokens and allocations while diagnosing; no automatic backfill.

## Ordered alwaysdata rollout (operator only; not executed)

From the repository root, review this allowlist and dry-run **before** upload:

```bash
rsync -avni --files-from=backend/deploy/ugx-lending-diagnostics.files backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
python3 backend/deploy/preview_combined_migrations.py
# Read-only hosted migration plan from local sources; stop on unavailable SSH.
```

The existing unchanged `backend/settings.py` is intentionally not uploaded: its legacy local-development DB-password fallback must not be exported. The already-working hosted base file is retained; the private alwaysdata profile obtains DB credentials from its existing private environment. No credential or local configuration is changed here.

The allowlist excludes all `.env` files (including examples), private keys,
firmware, virtualenvs, DB files, generated/static/media artifacts and APKs. No
`--delete`. Review the actual output and migration preview before changing host files. In a
separate hosted terminal take private backups with these exact commands (not
executed here):

```bash
set -eu
umask 077
cd /home/shanonsimon/energy-sharing
export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
export DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings
/home/shanonsimon/energy-venv/bin/python manage.py check_alwaysdata_database
export GPAWA_ROLLOUT_BACKUP="/home/shanonsimon/.local/backups/energy-sharing/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$GPAWA_ROLLOUT_BACKUP"
chmod 700 "$GPAWA_ROLLOUT_BACKUP"
cp -p "$ALWAYSDATA_ENV_FILE" "$GPAWA_ROLLOUT_BACKUP/backend.env"
chmod 600 "$GPAWA_ROLLOUT_BACKUP/backend.env"
if test -d /home/shanonsimon/.config/energy-sharing/devices; then cp -a /home/shanonsimon/.config/energy-sharing/devices "$GPAWA_ROLLOUT_BACKUP/devices"; fi
tar -czf "$GPAWA_ROLLOUT_BACKUP/backend-source-before.tgz" --exclude='.env*' --exclude='*.env' --exclude='*.pem' --exclude='*.key' --exclude='*.keystore' --exclude='venv*' --exclude='__pycache__' --exclude='*.pyc' --exclude='*.log' --exclude='media*' --exclude='staticfiles' -C /home/shanonsimon/energy-sharing .
/home/shanonsimon/energy-venv/bin/python manage.py shell -c 'import os, subprocess; from pathlib import Path; from django.conf import settings; d=settings.DATABASES["default"]; assert (d["HOST"],d["NAME"],d["USER"])==("postgresql-shanonsimon.alwaysdata.net","shanonsimon_energy_test","shanonsimon"); p=Path(os.environ["GPAWA_ROLLOUT_BACKUP"])/"database-before.dump"; env={**os.environ,"PGHOST":d["HOST"],"PGPORT":str(d["PORT"]),"PGDATABASE":d["NAME"],"PGUSER":d["USER"],"PGPASSWORD":d["PASSWORD"],"PGSSLMODE":"require"}; subprocess.run(["pg_dump","--format=custom","--file",str(p)],env=env,check=True); p.chmod(0o600); assert p.stat().st_size>0; print("Private database backup created; no records displayed")'
```

Stop if pg_dump fails or is unavailable. Verify the private backup/restore procedure;
never overwrite newer payments with an old dump. Return to the local repository
root and run the same rsync command without `-n`:

```bash
rsync -avi --files-from=backend/deploy/ugx-lending-diagnostics.files backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
ssh shanonsimon@ssh-shanonsimon.alwaysdata.net
cd /home/shanonsimon/energy-sharing
export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
export DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings
export PATH=/home/shanonsimon/energy-venv/bin:$PATH
```

Edit the existing private file on the host (0600, parent0700), never upload a
local .env. Keep existing secrets/MTN/token keys/device binding unchanged. Set
`PROTOTYPE_PAYMENT_PROVIDER=MTN_SANDBOX`, `SANDBOX_NEW_PAYMENTS_ENABLED=false`,
`SANDBOX_UGX_LOANS_ENABLED=true`. Preserve existing seven deferred-feature values,
financial restrictions and account-email schedule. Do not turn on real payment or
relay flags. AC_LAB stays separately opt-in for an already commissioned binding.

```bash
python manage.py check_alwaysdata_database
# Must confirm shanonsimon_energy_test, shanonsimon,
# postgresql-shanonsimon.alwaysdata.net and encrypted TLS (sslmode=require).
python manage.py showmigrations meter loan transactions token_blacklist
python manage.py migrate --plan
```

Review the plan before any migration. This increment adds **no new migrations**.
Existing prerequisite `meter.0032` and additive `meter.0033_ac_lab_sandbox_environment`
must be present/applied. Stop on an unexpected plan; do not fake/edit old migrations.
Only after backup/target/plan review, operator may run:

```bash
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check --deploy
python manage.py initialize_demo_assessments --user-id 3 --meter-id 3
# Review preview. Only if missing/pending and intended, run the same with --apply.
python manage.py audit_ac_lab_credit --operator-id 1 --owner-id 3 --meter-id 3 --limit 5
```

Restart the existing site using alwaysdata Web → Sites → Restart; preserve its
WSGI file, Python3.12, virtualenv and environment path. Check HTTPS features,
credential-free auth validation and account CSRF pages. Verify new payment flags
false, lending UGX, old receipts accurate and relay false. No test payment needed.

Keep Advanced → Scheduled tasks for `drain_account_emails` unchanged. Retain:

```bash
ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings /home/shanonsimon/energy-venv/bin/python /home/shanonsimon/energy-sharing/manage.py reconcile_sandbox_payments --limit 2 --max-seconds 50
# Review dry run; existing bounded scheduled job retains --run:
ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings /home/shanonsimon/energy-venv/bin/python /home/shanonsimon/energy-sharing/manage.py reconcile_sandbox_payments --run --limit 2 --max-seconds 50
```

Preserve `complete_demo_payments` for old LOCAL_DEMO pending records under their
original provider. Never-submitted MTN NEW rows remain for explicit review; no
automatic cancellation, refunds, replay or new collection during the pause.

## Firmware and phone handoff

Public diagnostic changes are in `firmware/ac-lab-domain/GpawaAC/Firmware.cpp` and
`SafeDiagnostics.h` and the active Arduino sketch. Private headers, journal/NVS,
binding and counters are preserved. No flash was performed. Use the existing
ESP32S3 Dev Module options recorded in CREDIT_ONLY_BUILD.md, Verify first, then
only with operator authorization upload the sketch using the existing IDE port.
Keep erase-all disabled and partition layout unchanged; do not flash a merged
erase image, regenerate keys, clear NVS or enable output. Read the fixed-code
redeem diagnostic before changing server records. USB credit-only mode is
independent of PZEM, consumption remains unavailable without sensor evidence.

The rebuilt APK and final local validation evidence are recorded in
`mobile/UGX_LENDING_BUILD.md`. Update with `adb install -r` using the same debug
identity. Phone checklist: login → select meter → ready simulated assessment →
UGX quote/terms/consent → one loan/token → pending device acknowledgement →
durable saved-credit ACK. Check history, denied new purchases/repayments and
logout. Existing funded purchases need no second payment to diagnose redemption.

## One demonstration acceptance sequence (five-day scope freeze)

1. Back up and deploy this reviewed backend package; verify the testing DB/TLS,
   email schedule, feature restrictions and existing device identity. Do not
   provision again, clear NVS or initiate another purchase.
2. Verify/flash the diagnostic sketch only with separate operator authorization;
   USB power only, relay/load physically disconnected. Firmware output stays
   compile-prohibited. Read one failed redeem's fixed operation/status/code or run
   the read-only audit for the existing purchase. Resolve the identified lookup,
   binding, key, source or pending-command issue, preserving its original records.
3. Redeem the existing funded token. Confirm one pending command, then durable
   saved credit and an idempotent ACK. Interrupt network/USB before ACK and retry
   after reboot: same command, unchanged credited total. Repeat after ACK: no
   second credit. Consumption remains unavailable without PZEM evidence.
4. Install the matching APK with `adb install -r`; login, select the owned meter,
   initialize missing automatic demo assessment only if needed. Review UGX admin
   tariff quote, percentage score/reasons, terms and repayment limitation. Accept
   once: one decision, one allocation, one SANDBOX token. Repeated submission
   preserves the same application/allocation/token.
5. Redeem the approved loan token on the same authorized SANDBOX device; repeat
   the durable-credit and lost-ACK checks. Do not confuse saved credit with a
   switched load or certified metering.
6. Repayment is the sole financial-policy blocker: the current chosen profile
   pauses new EUR payments. The smallest no-conversion option is the existing
   explicitly labelled UGX simulator for UGX prototype repayment only, retaining
   MTN keys/history and the purchase pause. That exception requires an explicit
   provider decision; it is not enabled by this package. No EUR receipt may be
   renamed UGX or reduce UGX debt. A new MTN-to-UGX sandbox mapping would need
   separate explicit, frozen terms and a receipt that retains both currencies.
7. Check unchanged owner-only history, unavailable sensor values, denied new
   purchases and logout. Record actual phone/board/provider observations separately
   from automated local evidence. No extra dashboards, redesign or radio work.

### Concrete MTN-only policy decision, if the UGX simulator is declined

Proposed **TEST_AUTHORIZATION_UGX_v1**, not enabled or approved: a frozen request
for UGX10,000 of prototype repayment would request **EUR1.00 TEST** from MTN;
validated JSON SUCCESSFUL would authorize a separately recorded UGX10,000
**non-cash prototype debt adjustment**. The actual provider receipt stays EUR1.00;
both values must remain visible in audit/receipt details. This is an explicit
per-instruction sandbox authorization, **not** 1EUR=10,000UGX or any exchange rate;
a different UGX instruction could still use the same EUR1.00 test authorization.
One reference could authorize only its frozen instruction once. It would require
an additive typed adjustment record to avoid mixing currencies in the current
SandboxSettlement amount/applied/excess invariant. None of that mapping/schema is
introduced here. Approving this exact test policy (including truthful dual-value
receipts), using the existing UGX simulator, or obtaining actual UGX provider
support is the smallest decision needed to complete repayment. Merely changing
currency strings or treating HTTP200 as payment success cannot implement it.

### New loan API example (illustrative values, not a request executed here)

```json
{"purpose":"LOAN","meter_id":3,"amount":"10000","loan_contract":"UGX-PROTOTYPE-SANDBOX-v1"}
```

Send to `POST /api/v1/sandbox/quotes/` with the consumer's existing authentication.
The quote freezes currency UGX, environment UGX_DEMO, energy_environment SANDBOX,
admin pricing inputs, stored assessment, exact Wh entitlement, total due, policy,
expiry and terms_hash. After displaying all terms, submit:

```json
{"quote_id":"<returned UUID>","terms_hash":"<returned SHA256>","client_request_id":"<one durable request UUID>","accept_test_terms":true}
```

Send to `POST /api/v1/sandbox/loans/`. A client cannot supply a score, approval or
energy amount. The server checks current eligibility again and returns its stored
decision. Retrieve its existing meter-bound keypad token using the allocation
owner endpoint; never include token digits in diagnostics/support messages. A
retry retains the same client_request_id/quote and the same allocation/token.

## Local validation procedure and known baseline

```bash
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --sandbox-profile --slow-test-cleanup loan.tests_ugx_lab loan.tests_sandbox loan.tests_mtn_transition loan.tests_demo_assessment meter.tests_mtn_device meter.tests_prototype_device meter.tests_credit_only transactions.tests_demo_payments backend.tests_feature_flags backend.tests_combined_rollout loan.tests_consumer_summary accounts.tests_account_pages meter.tests_device_diagnostics
```

The opt-in harness flag extends **only isolated test DB creation/deletion and
flush transactions** to120s. Financial/request SQL keeps the profile's10s timeout
and5s lock timeout; production settings are not changed. It refuses any target
other than local127.0.0.1:55445/gpawa_alwaysdata_test, and flush only test_gpawa_*
databases. This addresses the observed local10s teardown timeout, which left
fixtures and cascaded into duplicate-fixture errors in the first160-case run.
It does not suppress assertions, swallow cleanup failures or skip tests. A second
attempt exposed the same local timeout during test DB creation, also now scoped
within this allowance. Neither attempt touched a hosted database.

Base-profile authentication/settlement/allocation/financial/feature tests ran
93 cases successfully with the existing one expected failure:
`test_completed_loan_stays_closed_when_overdue_clock_advances`. It remains visible;
this change does not declare live financial deployment ready. The dedicated
sanitized-diagnostic suite separately passed its database-free tests (now3 cases in the combined suite). See the release
validation record for the final combined run result, APK and target firmware build.

### Final local evidence for this package

- Final source: **163 combined PostgreSQL tests passed**,116.787s, using the exact
  combined command above. Includes unchanged EUR history beside new UGX borrowing,
  currency denial, same-currency partial/full closure with no energy, concurrency,
  token lookup/leading zeros, same-command recovery, device access and all7 flags.
- Separate base run:93 cases,1 known financial expected failure retained. No new
  financial policy was approved merely by a test matching its implementation.
- Mobile strict TypeScript,13 test files, Vite bundle and Capacitor sync passed.
  Signed APK assembleDebug and embedded HTTPS URL/signature verification passed.
- Web strict TypeScript exit0 and12 test files passed. Production webpack build
  timed out at420s during optimization, without a reported compiler error; full
  production web build completion is not claimed.
- Repository and active-sketch C++ suites:5 groups passed. Exact ESP32-S3 target
  compile passed; private headers unchanged. No physical power-cut, MTN service,
  phone install or board test was performed.
- No new migrations. No hosted code/schema/data change, key rotation or flash.

The local first-run timeout failures and the retained core overdue expected
failure are distinct from passing sandbox-loan closure tests. The existing token
rejection still needs its actual hosted error/audit evidence; automated fixtures
cannot identify that purchased token's live failure. Repayment still requires the
explicit sandbox provider/mapping decision above; no EUR amount is shown as UGX.
