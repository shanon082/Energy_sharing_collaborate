# Approved UGX / MTN sandbox authorization release

Implemented locally on21 November2026. **Not deployed; no actual MTN, phone or
physical-board test was performed.** This supersedes the previous unapproved
mapping/pause runbooks for the new UGX journey. Preserve all historical evidence.

## Policy and authoritative records

The user approved **UGX-MTN-TEST-AUTH-v1**: one fixed **EUR1.00 MTN Sandbox test
transaction authorizes one immutable UGX prototype instruction**. It is not an
exchange rate, a real UGX collection, wallet deposit or production payment.

| Record | Authority / units |
|---|---|
| Existing PaymentIntent | Actual MTN_SANDBOX/EUR1.00 reference, external ID, purpose, owner, provider transaction identity and terminal settlement. Existing reconciliation/lease service remains the only payment pipeline. |
| New SandboxUGXInstruction | Whole UGX, UGX_DEMO financial environment, owner, selected meter, purpose, loan if repayment, quote, accepted terms/hash, provider-reference binding and immutable v1 policy snapshot. Persisted before provider I/O. |
| Existing SandboxSettlement | Actual EUR1.00 receipt conserved separately. All EUR1.00 is retained in its residual as unallocated **test evidence**, not utility billing or a UGX asset/refund promise. No UGX cash received is asserted. |
| New SandboxUGXSettlement | One noncash test effect per instruction: authorized UGX = billed + residual + applied + excess. Purchase billed/residual and repayment applied/excess are never stored as EUR. |
| Existing SandboxLoan | UGX principal/debt and accepted loan terms. Debt reads sum matching legacy UGX repayments and new UGX test effects, never EUR receipts. Full repayment closes permanently. No second lending model. |
| Existing EnergyAllocation / EnergyKeypadToken | One source-linked allocation and one meter-bound15-digit token for a settled purchase or approved loan. IntegerWh transport;0.01kWh=10Wh increments. No second energy balance. |
| Existing delivery/command/ACK records | Queued/reserved credit differs from acknowledged durable device storage and physical output. Relay remains prohibited. |

Migration `transactions.0013_sandboxugxinstruction_sandboxugxsettlement_and_more`
creates two models, source/purpose/conservation constraints and PostgreSQL triggers
rejecting UPDATEs to instructions and effects. There is no data conversion,
backfill, token reset, historical bill rewrite or operational migration in this
local implementation. Models use PROTECT relationships; one-to-one intent/quote/
effect links prevent one source from issuing multiple authorizations. Existing
provider+transaction unique constraints remain authoritative across intents.

### Settlement and failure behavior

The existing MTNSandbox adapter still requests **EUR1.00**, with one durable
reference/external ID; it still requires trusted HTTPS status evidence matching
reference, external ID, amount, currency, payer and a successful provider
transaction ID. HTTP202 is submission/pending; HTTP200 only means the lookup
returned. Only JSON SUCCESSFUL (normalized SUCCESS internally) can settle.
PENDING, FAILED, unknown, timeout, mismatches or client success claims grant no
credit. A timeout does not generate a second charge/reference. Status GET remains
read-only. Reconciliation POST and the existing finite scheduled command use the
same settlement transaction and durable lease/backoff.

New purchase uses its frozen **UGX admin tariff**; the EUR challenge is not priced
through that tariff. Each billing input, owner-month purchase-band position,
service charge, VAT, rounding and breakdown is frozen/hash-validated. Only stable
verified economic purchase allocations affect bands; loans, loading and ACKs do
not. The same owner-level bands include earlier LOCAL_DEMO UGX and the new UGX
instructions; old EUR purchases are not converted into UGX band events. Frozen
simulated-assessment purchase contributions use each source exactly once.

Repayment locks the owner and selected matching UGX debt, applies the lesser of
instruction and remaining debt, and preserves excess for review. No automatic
refund, write-off, currency conversion, additional allocation or token. Normal
initiation disallows a second pending payment; settlement also handles two
pre-existing concurrent authorized records without negative debt/lost updates.

Example: a UGX10000 purchase freezes its configured tariff and exact Wh/billed/
remainder; actual provider receipt remains EUR1.00. A UGX4000 repayment against
UGX10500 leaves UGX6500 while its separate EUR1.00 receipt remains EUR1.00. A
concurrent UGX14000 authorization total against UGX10500 debt preserves applied
10500/excess3500, and two provider receipts total EUR2.00. These are noncash test
records, not a real-money collection or exchange quotation.

## Loans, capability contract and web routing

Stored meter-specific DemoCreditAssessment remains authoritative; no questionnaire,
client score or new scoring formula. Minimum80%, current eligibility/debt/limit,
owned active meter, configured DOMESTIC ElectricityTariff/TariffBlock, fresh quote,
hash/expiry and explicit consent are all required. Approved lending needs **no
payment** and creates exactly one allocation/token. The independent lending flag
is checked in services as well as UI: payment authorization cannot enable loans
when SANDBOX_UGX_LOANS_ENABLED=false.

The profile hard-requires UGX authorization for NEW MTN activity. Disabling the
authorization flag pauses new instructions and keeps UGX read domains; it cannot
reopen EUR charging. Historical reference reconciliation still uses frozen policy.

New public `features.sandbox` when activated:

```json
{"enabled":true,"provider":"MTN_SANDBOX","currency":"UGX","environment":"UGX_DEMO","loans":false,"purchases":true,"repayments":true,"physical_delivery":false,"authorization":{"policy":"UGX-MTN-TEST-AUTH-v1","provider":"MTN_SANDBOX","currency":"EUR","amount":"1.00","no_real_money":true,"energy_environment":"SANDBOX"},"lending":{"enabled":true,"currency":"UGX","environment":"UGX_DEMO","energy_environment":"SANDBOX","policy":"DEMO-UGX-ACLAB-v1","repayment_available":true}}
```

Availability still depends on server flags, token service and dedicated MTN key
configuration; per-user tariff/assessment/debt checks occur later. Legacy
`mobile_actions` remain disabled; legacy EUR loan origination stays false. Invalid
or incompatible new capability metadata fails closed with a visible contract error.

Both clients use the shared sandbox parser, finance controller, status/receipt and
owner-selected meter. New forms, limits, debt and quotes show UGX. Provider EUR
amounts remain accurate in receipt/authorization details and earlier EUR history.
Dashboard and Android Home now show current UGX activity only; earlier EUR
transactions remain accessible in accurate history. The shared overview follows
business currency, not the provider name. Provider EUR details are outside Home.
The concise confirmation disclosure is **“Test payment—no real money.”**
No timer can complete an MTN payment. Pending handles survive navigation/restart;
server-side scheduled reconciliation does not depend on an open app.

Actual Next routes:

* `/dashboard/buy-units/`: page is intentionally a child placeholder; authenticated
  dashboard layout mounts ConsumerRouter/ConsumerWorkspace and the shared finance
  controller. Its form depends on authoritative sandbox capabilities and an owned
  selected meter, not mobile_actions or an eligible loan assessment.
* `/dashboard/request-loan/`: now a canonical ConsumerRouter application route,
  without the old query-redirect/legacy meter-context dependency. The old
  `/dashboard/loans/?tab=apply` alias remains compatible.
* Both show exact loading, API, capability, meter, pricing, score/debt, stale quote,
  consent and phone-input blockers. A62% score stays visible with the80% reason.
* `sandbox/assessment/?meter_id=...&purpose=PURCHASE` returns existing policy/tariff
  context without calling assessment. An assessment failure cannot unnecessarily
  hide or block purchase pricing. No new payment/pricing subsystem is introduced.

The reported public hosted response before rollout was the earlier MTN/EUR
contract without new UGX metadata. An APK update cannot update Django or Vercel.
Authenticated live pages were not accessed in this work; browser evidence below
uses the actual local production Next build and synthetic API, never hosted records.

## Historical preservation and production isolation

Old EUR/LOCAL_DEMO intents retain their original amount, provider and frozen policy
and continue through their original reconciliation path. New mapping applies only
to records carrying the immutable v1 instruction; no retroactive mapping. Historical
EUR loans remain readable and are not repayable by a UGX instruction. Earlier UGX
prototype debt can receive an owned matching UGX test repayment without converting
it. Old tokens/allocations retain original energy environments.

Explicit opt-in is restricted to ALWAYSDATA_TESTING + CONSUMER_SANDBOX_ENABLED +
MTN_SANDBOX, dedicated official sandbox URL/currency/environment and exact policy
version. App startup refuses an incompatible enabled configuration. Production /
CORE settlement rejects this test evidence. Pausing new activity does not discard
already authorized instructions: frozen settlement/recovery remains permitted in
the testing profile. Ordinary core/Render paths are not activated.

Future real UGX payments require separate Uganda production onboarding and an
approved production accounting/lending policy. Their provider amount/currency must
match the actual UGX instruction, never the fixed EUR1 challenge. Test lending,
synthetic assessments and test energy must not be migrated into production debt.
This release does not implement or activate real-money payments.

## Ordered alwaysdata rollout — operator only, not executed

Existing hosting: shanonsimon@ssh-shanonsimon.alwaysdata.net,
code `/home/shanonsimon/energy-sharing`, venv `/home/shanonsimon/energy-venv`,
Python3.12.15. No new application dependency: keep the existing requirements and
cryptography/requests/Django versions; do not upgrade packages unnecessarily.

1. **Review source scope and dry-run BEFORE changing host files.** From repo root:

   ```bash
   rsync -avnic --files-from=backend/deploy/ugx-mtn-authorization.files backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
   python3 backend/deploy/preview_combined_migrations.py
   ```

   Preview transmits migration source only to a read-only hosted metadata process,
   checks exact DB/TLS, refuses divergent histories and never runs DDL/provider HTTP.
   This session did not execute remote preview or upload. The allowlist excludes
   all .env files/examples, keys, firmware private headers, virtualenv/DB/media/
   static/build artifacts. No --delete. Keep the unchanged hosted base settings
   file; its legacy local-development secret fallback must not be exported.

2. **Private backups and maintenance window.** On host:

   ```bash
   set -eu
   umask 077
   cd /home/shanonsimon/energy-sharing
   export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
   export DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings
   export PATH=/home/shanonsimon/energy-venv/bin:$PATH
   python manage.py check_alwaysdata_database
   export GPAWA_UGX_BACKUP="/home/shanonsimon/.local/backups/energy-sharing/ugx-$(date -u +%Y%m%dT%H%M%SZ)"
   mkdir -p "$GPAWA_UGX_BACKUP"
   chmod 700 "$GPAWA_UGX_BACKUP"
   cp -p "$ALWAYSDATA_ENV_FILE" "$GPAWA_UGX_BACKUP/backend.env"
   chmod 600 "$GPAWA_UGX_BACKUP/backend.env"
   if test -d /home/shanonsimon/.config/energy-sharing/devices; then cp -a /home/shanonsimon/.config/energy-sharing/devices "$GPAWA_UGX_BACKUP/devices"; fi
   python manage.py shell -c 'import os,subprocess; from pathlib import Path; from django.conf import settings; d=settings.DATABASES["default"]; assert (d["HOST"],d["NAME"],d["USER"])==("postgresql-shanonsimon.alwaysdata.net","shanonsimon_energy_test","shanonsimon"); p=Path(os.environ["GPAWA_UGX_BACKUP"])/"database-before.dump"; env={**os.environ,"PGHOST":d["HOST"],"PGPORT":str(d["PORT"]),"PGDATABASE":d["NAME"],"PGUSER":d["USER"],"PGPASSWORD":d["PASSWORD"],"PGSSLMODE":"require"}; subprocess.run(["pg_dump","--format=custom","--file",str(p)],env=env,check=True); p.chmod(0o600); assert p.stat().st_size>0; print("Private backup created; no records displayed")'
   tar -czf "$GPAWA_UGX_BACKUP/backend-source-before.tgz" --exclude='.env*' --exclude='*.env' --exclude='*.pem' --exclude='*.key' --exclude='*.keystore' --exclude='venv*' --exclude='__pycache__' --exclude='*.pyc' --exclude='*.log' --exclude='media*' --exclude='staticfiles' -C /home/shanonsimon/energy-sharing .
   python -m pip check
   python -c 'import django,psycopg,requests,cryptography,whitenoise; from cryptography.fernet import Fernet; print("Required runtime imports available")'
   ```

   Stop on wrong DB/TLS, missing pg_dump, failed backup or dependency errors. If
   required imports are missing, install only the existing pinned
   `python -m pip install -r requirements-alwaysdata.txt` and recheck; no upgrades
   or new service credentials are required. Keep
   backups/private device files off Git/public storage. Avoid new user financial
   activity during code/schema activation. Temporarily pause only payment
   reconciliation/completion schedules during that window, retaining every queue
   row; keep account-email delivery enabled. Resume the preserved payment schedules
   after schema/configuration health checks. Never restore an old dump over newer
   payments automatically.

3. **Upload reviewed current source** from local repository:

   ```bash
   rsync -avic --files-from=backend/deploy/ugx-mtn-authorization.files backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
   ```

   This includes latest diagnostics, middleware, all required services, and meter
   migrations0032/0033 plus the new transactions0013. Do not apply older diagnostic
   patches over current files. Do not copy local .env or keys to the host.

4. **Database target and migration review** in the hosted terminal:

   ```bash
   cd /home/shanonsimon/energy-sharing
   export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
   export DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings
   export PATH=/home/shanonsimon/energy-venv/bin:$PATH
   python manage.py check_alwaysdata_database
   python manage.py showmigrations meter loan transactions token_blacklist
   python manage.py migrate --plan
   python manage.py sqlmigrate transactions 0013
   ```

   Expected target: postgresql-shanonsimon.alwaysdata.net / shanonsimon_energy_test /
   shanonsimon, actual encrypted TLS and sslmode=require. Review all unapplied
   dependencies, including meter0032/0033. New0013 creates two new tables and
   immutable-record triggers only; no historical transformation. The database
   role needs normal schema creation and PL/pgSQL-function/trigger privileges.
   Stop on unexpected plans or privilege errors; do not fake migrations.

   Only after backup/target/plan review:

   ```bash
   python manage.py migrate --noinput
   python manage.py collectstatic --noinput
   python manage.py check --deploy
   ```

5. **Activate privately** by editing the existing environment file (not uploading
   the template). Parent0700/file0600; preserve every existing secret/token key:

   ```bash
   chmod 700 /home/shanonsimon/.config/energy-sharing
   chmod 600 /home/shanonsimon/.config/energy-sharing/backend.env
   nano /home/shanonsimon/.config/energy-sharing/backend.env
   ```

   Exact non-secret settings for this journey:

   ```dotenv
   PROTOTYPE_PAYMENT_PROVIDER=MTN_SANDBOX
   SANDBOX_UGX_AUTHORIZATION_ENABLED=true
   SANDBOX_UGX_AUTHORIZATION_POLICY=UGX-MTN-TEST-AUTH-v1
   SANDBOX_NEW_PAYMENTS_ENABLED=true
   SANDBOX_UGX_LOANS_ENABLED=true
   MTN_SANDBOX_BASE_URL=https://sandbox.momodeveloper.mtn.com
   MTN_SANDBOX_CURRENCY=EUR
   DB_SSLMODE=require
   MOBILE_PAYMENT_ACTIONS_ENABLED=false
   MTN_USE_SIMULATED_PAYMENTS=false
   SIMULATED_METER_ENABLED=false
   PURCHASE_HISTORY_SCORING_ENABLED=false
   CELERY_TASK_ALWAYS_EAGER=false
   FEATURE_THIRD_PARTY_REPAYMENT_ENABLED=false
   FEATURE_USSD_ENABLED=false
   FEATURE_WALLET_DEPOSITS_ENABLED=false
   FEATURE_WALLET_WITHDRAWALS_ENABLED=false
   FEATURE_EXTERNAL_CRB_ENABLED=false
   ```

   Keep existing private MTN_SANDBOX_SUBSCRIPTION_KEY/API_USER_ID/API_KEY,
   SECRET_KEY, DB password, Gmail app password and ENERGY_TOKEN encryption/lookup
   keys **unchanged**. Sharing/transfers are hard-retired; all seven deferred
   features stay disabled. Preserve the already commissioned AC_LAB opt-in and
   existing SANDBOX/GPAWA_PZEM_V2 binding; do not run provisioning, rotate device
   credentials, erase NVS or enable output. Relay output is hard-false.
   Django defaults keep authorization/new payments off until this explicit opt-in.

   Preserve existing DEMO_* loan terms (default1000–50000UGX,5% interest,fee0,7days,
   threshold80) as prototype assumptions, not new utility policies. Configure/review
   one effective active DOMESTIC ElectricityTariff and ordered TariffBlocks through
   existing administration. Tariff HTTP writes remain restricted on this host; if
   configuration is missing, an operator must review/supply the intended test
   schedule through the existing authorized management workflow. Do not unblock
   general financial/admin writes or automatically seed unspecified rates.
   No tariff fallback, exchange rate or new rate is
   installed by this release. Existing EUR SANDBOX_* policy remains for old records.
   Keep Django-hosted HTTPS verification/reset pages, CSRF fix, trusted origins,
   http://localhost debug APK CORS origin and working scheduled Gmail delivery.

   Verify configuration before site restart:

   ```bash
   python manage.py check --deploy
   python manage.py check_alwaysdata_database
   python manage.py initialize_demo_assessments --user-id 3 --meter-id 3
   ```

   The last command previews only. Review before --apply to initialize missing/
   pending synthetic evidence; never overwrite ready/real assessments.

6. **Restart existing site**, alwaysdata Web → Sites → Restart. Keep current
   sandbox WSGI, Python3.12 and virtualenv/private-env path. Then read-only HTTPS:

   ```bash
   curl --fail --silent --show-error https://shanonsimon.alwaysdata.net/api/v1/features/ | python3 -m json.tool
   ```

   Require UGX/MTN_SANDBOX plus v1 authorization metadata, lending.enabled=true,
   legacy loans=false, expected purchases/repayments, mobile_actions=false,
   physical_output=false and all seven flags false. Missing credentials/token
   configuration/tariffs must be resolved explicitly, never LOCAL_DEMO fallback.

7. **Preserve/verify scheduled jobs**, Advanced → Scheduled tasks. Dry-run first:

   ```bash
   ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings /home/shanonsimon/energy-venv/bin/python /home/shanonsimon/energy-sharing/manage.py reconcile_sandbox_payments --limit 2 --max-seconds 50
   ```

   Existing bounded mutating schedule (e.g. each minute) remains:

   ```bash
   ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings /home/shanonsimon/energy-venv/bin/python /home/shanonsimon/energy-sharing/manage.py reconcile_sandbox_payments --run --limit 2 --max-seconds 50
   ```

   It completes old/new MTN references under original policies, including app closure.
   No Redis/Celery worker or global eager mode is needed. Preserve
   `drain_account_emails --send --limit 5` unchanged. Keep the existing finite
   `complete_demo_payments --run --limit 20 --max-seconds 50` schedule only for old
   LOCAL_DEMO obligations; it cannot settle MTN records. Network/provider outages
   remain pending/unknown with backoff, not fake success or silent task loss.

## Vercel deployment — separate required step, not executed

Deploying Django or installing an APK does **not** update the website. Review this
same checkout in the existing Vercel project serving
`energy-sharing-collaborate.vercel.app`:

1. Settings → Build and Deployment: **Root Directory frontend**, Framework Next.js,
   install `npm ci`, build **`npm run build -- --webpack`**, default Next.js output.
   Preserve server components, proxy, secure cookies and authentication. No static
   export and no ignored TypeScript/build failures.
2. Settings → Environment Variables: server-only
   `API_URL=https://shanonsimon.alwaysdata.net/api/v1` in Production and any intended
   testing Preview environment. No provider/device secrets or LAN URLs in frontend
   public variables. Keep backend's existing exact production origin; do not use
   wildcard CORS/CSRF settings. Server/browser requests continue through the Next
   same-origin proxy.
3. In the existing project's Settings → Git, verify its connected repository and
   Production Branch. Review the source changes, commit and push **when you choose
   to publish**, then select the deployment for that new commit. This session did
   not commit or push. Deployments → Redeploy may rebuild the selected commit
   after environment changes; redeploying an old commit does not include this code.
   Do not upload a local repository/environment archive through an unrelated CLI
   project. The existing Git integration uses tracked source and Root Directory
   frontend. No replacement Vercel project is needed.
4. Verify Vercel deployment commit/build logs, login and actual routes
   `/dashboard/buy-units/` and `/dashboard/request-loan/`. Compare the same owner,
   selected meter, capabilities, quote and receipt with Android. Use an incognito
   session/hard refresh for stale old chunks. Only operator-authorized MTN testing
   should initiate a sandbox transaction.

## Device and phone acceptance checklist

Install the signed debug APK with adb install -r (identity/checksum and exact path
in `mobile/UGX_MTN_BUILD.md`). Existing firmware needs no protocol change for this
release: the provisioned SANDBOX/GPAWA_PZEM_V2 AC_LAB already consumes integerWh
commands. Preserve its unique secret, owner/meter binding and USB credit-only
journal/recovery mode. No firmware flash, NVS erase, replacement token or relay test
was performed/required by this local implementation.

* Register/verify/login; select the owned11-digit meter; stored simulated score and
  limit visible. Wrong owner/low score/missing assessment/tariff must explain denial.
* Purchase UGX amount → admin quote → consent/test number → one EUR1 authorization
  → authoritative verified settlement → one allocation/token → enter all15digits
  on the matching commissioned keypad → durable ACK/saved credit. Before ACK,
  do not call queued credit saved. Do not connect or energize a load.
* Loan amount → stored assessment/fresh limits → frozen quote/consent → automatic
  approval or reasoned rejection → one token without payment. Repay4000 of10500 →
  EUR1 test authorization → remaining6500; full repayment closes debt. No repayment
  token/energy. Compare web/Android receipts and current debt.
* Close/reopen during pending payment; reuse existing reference, never pay again
  because of a timeout. Verify finite scheduled reconciliation independently.
* Device retry/lost response/reboot uses the same command identity; duplicate ACK
  cannot add Wh. USB without PZEM reports consumption unavailable. No invented
  measurement, contact, relay feedback or physical output.
* Logout/account switch does not expose another owner's readings, receipt or token.

Actual MTN sandbox, authenticated live Vercel/Android and physical-board tests are
outstanding. Current stored/mock tests do not prove provider availability, radio,
measurement accuracy or physical reliability. The pre-existing CORE overdue-after-
completion expected failure remains visible; it is not a production-ready policy.

See [local web screenshots and browser results](../../docs/review/ugx-workflow/README.md)
and `mobile/UGX_MTN_BUILD.md` for final command/results/artifact evidence.

Deployment references: [Vercel build settings](https://vercel.com/docs/builds/configure-a-build),
[environment variables](https://vercel.com/docs/environment-variables),
[Git deployment](https://vercel.com/docs/git). Environment changes require a new
deployment; installing an Android APK cannot publish web code.

## Final local evidence

The complete combined command in `mobile/UGX_MTN_BUILD.md` passed180 tests in
127.008s after restoring the cleared temporary test dependencies. The earlier
base-profile run passed93 cases with the known CORE overdue expected failure.
Mobile14 test files, web13 test files, strict type checks and focused lint passed.
Nine actual Next.js local-browser scenarios passed, with zero runtime errors and
masked screenshots. The production web build and signed Android debug build passed.
This is local/mock evidence, not a hosted deployment, provider or board test.
