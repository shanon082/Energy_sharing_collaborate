# Subsequent SANDBOX device-domain changes

This earlier build report is preserved for its APK/signing and rollout evidence.
Its MTN-device denial describes the earlier build. Follow
[MTN_AC_LAB_SANDBOX.md](MTN_AC_LAB_SANDBOX.md) for current sources, migration0033,
V2 firmware, token prerequisites and the expanded upload allowlist. The APK hash
recorded below predates those source changes.

---

# Combined AC_LAB + MTN testing rollout

This build starts from checkout **5950316**, which contains both implementations,
plus the explicitly listed local integration fixes. No files were reset. See
`mobile/COMBINED_BUILD.md` for the final signed APK identity/checksum/test results.

## Effective capabilities and loan boundary

| Profile/mode | New purchases / repayments | New loans | AC_LAB routes |
|---|---|---|---|
| Ordinary alwaysdata | Blocked | Blocked | Blocked |
| Consumer sandbox, MTN_SANDBOX, dedicated sandbox credentials present | Eligible EUR TEST purchase; own matching EUR debt | Blocked pending reviewed automatic EUR assessment policy | Blocked, even if AC flag is true |
| Consumer sandbox, MTN_SANDBOX, missing credentials | “Sandbox payments unavailable”; no fallback | Blocked | Blocked |
| Consumer sandbox, LOCAL_DEMO | Original UGX DEMO service | Existing stored meter assessment/terms, score and debt gates | Off by default; separately commissioned lab requires explicit opt-in |

All seven deferred features remain off/retired. No production/core payment,
physical simulator dispatch or relay is enabled. The relay setting remains false.
MTN configured=true establishes key presence/shape, not successful authentication
to MTN. Only mocked provider responses were used locally.

In the NEW MTN profile, Apply for Loan is deliberately blocked by the EUR policy
gate, and this build explains it before showing an unusable form/stepper. A public
HTTPS check of the currently deployed backend instead returned LOCAL_DEMO/UGX,
with loans enabled and all seven deferred features false. Therefore the reported
current phone Amount-step problem cannot be attributed to the MTN gate alone.
Its owner-specific assessment, pricing, amount or unresolved-request reason needs
the displayed account information; no private account was inspected. The new
build shows each actual Review-terms blocker, and eligible LOCAL_DEMO progression
remains tested. This build does **not** make loan acquisition available in MTN mode. A
versioned EUR automatic assessment and lending policy still requires a separate
decision/implementation; UGX assessments and numeric limits are not copied or
converted. Tests retain the enabled LOCAL_DEMO Amount/Terms/consent progression.

Both clients show the reason existing UGX debt cannot receive an EUR repayment,
and why MTN mode cannot redeem into the UGX_DEMO-only AC lab. Existing loan and
payment history remains readable. Web history now includes earlier-currency
receipts. Meters → **Balances by allocation ledger** shows exact CORE, UGX_DEMO
and SANDBOX energy separately, through existing owner-only read endpoints.
Android's main meter read now explicitly selects its active ledger; it no longer
combines domains or implicitly switches to UGX when an old lab binding exists.

HTTP202, HTTP200 alone and five seconds never establish MTN success. The shared
web/Android controller consumes Django's durable receipt. Failed, pending,
unknown and mismatched evidence have no settlement effect; original-provider
pending recovery, idempotency and excess/remainder conservation remain intact.
Payment confirmed, token issued, durable device acknowledgement and load output
are distinct. No EUR device token domain or actual physical-board test is claimed.

## Upload scope and prerequisite review

`deploy/combined-ac-mtn.files` combines both feature lists, consumer/parity
dependencies and every backend change since c1d25ad. It includes meter **0032**,
URL registration, middleware, models/services/readers, the account/CSRF/email
changes and scheduled payment commands. Environment templates are intentionally
excluded too. No `.env`, key, credential, database, virtualenv, APK, generated
static file or cache is in the list. No upload command uses `--delete`.

Migration0032 adds four device/boot/command/telemetry models and constraints;
it does not convert balances, tokens or existing financial records. Other pending
migrations must be reviewed separately. Never assume a local plan proves the
host's migration state. The earlier individual lists remain available for history.

**Observed remote blocker:** noninteractive SSH to the confirmed account returned
`Permission denied (publickey,password,keyboard-interactive)`. Therefore no hosted
dry-run listing, hosted migration plan, backup, upload, migration, restart or job
configuration was completed. Local dry-run/package checks and a simulated
0031→0032 migration-plan test are separate evidence. No payment was initiated.

## Ordered operator checklist — do not skip the review gate

1. **Restore existing SSH authentication in your terminal.** Do not send passwords
   or private keys to chat, generate a replacement key, disable host-key checking,
   or copy local `.env` files. Verify `ssh shanonsimon@ssh-shanonsimon.alwaysdata.net`.

2. **Read-only upload dry-run and exact migration plan BEFORE changing the host.**
   From the repository root:

   ```bash
   rsync -avnc --files-from=backend/deploy/combined-ac-mtn.files -e 'ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=10' backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
   python3 backend/deploy/preview_combined_migrations.py
   ```

   The preview sends only local migration **source** over stdin. It does not
   upload files: the remote Python process reads the existing private environment,
   verifies the exact testing DB identity and actual TLS, enables PostgreSQL
   session read-only mode, builds a migration graph in memory from this checkout
   and reads only migration/schema metadata. Provider HTTP is blocked. It refuses
   a host migration absent from the checkout. Review its full plan and the rsync
   list. **Stop here** on SSH failure, unencrypted/wrong DB, divergence or unexpected
   migrations. No hosted plan has been obtained in this session.

3. **Backup, only after reviewing the dry-run/plan.** On the host:

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

   Use a host-compatible pg_dump; stop if it fails or is unavailable. These private
   server backups contain sensitive data/keys and must never enter Git, public
   storage, the APK, the code upload or chat. Verify backup completion/restore
   procedure privately. Do not automatically restore a database over newer payments.

4. **Code upload**, from local repository root, after the review/backup gate:

   ```bash
   rsync -avc --files-from=backend/deploy/combined-ac-mtn.files -e 'ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=10' backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
   ```

5. **Private MTN configuration**, on host with an editor, preserving every working
   secret and email/token setting. Do not overwrite the file with a template:

   ```bash
   chmod 700 /home/shanonsimon/.config/energy-sharing
   chmod 600 /home/shanonsimon/.config/energy-sharing/backend.env
   nano /home/shanonsimon/.config/energy-sharing/backend.env
   ```

   Set `PROTOTYPE_PAYMENT_PROVIDER=MTN_SANDBOX`, exact
   `MTN_SANDBOX_BASE_URL=https://sandbox.momodeveloper.mtn.com`,
   `MTN_SANDBOX_CURRENCY=EUR` and retain existing dedicated sandbox values for
   `MTN_SANDBOX_SUBSCRIPTION_KEY`, `MTN_SANDBOX_API_USER_ID`, `MTN_SANDBOX_API_KEY`.
   Keep versioned EUR test pricing/terms (`SANDBOX_POLICY_VERSION`,
   `SANDBOX_RATE_PER_KWH`, etc.) explicit: existing v1 EUR1/kWh is a prototype
   assumption, not an approved tariff. No UGX rate or currency conversion.
   Keep `DB_SSLMODE=require`, `DEBUG=false`, the existing fresh SECRET_KEY and
   trusted HTTPS origin. Keep `PROTOTYPE_AC_LAB_ENABLED=false`,
   `MOBILE_PAYMENT_ACTIONS_ENABLED=false`, `MTN_USE_SIMULATED_PAYMENTS=false`,
   `SIMULATED_METER_ENABLED=false` and all five configurable optional flags false;
   sharing/transfers remain retired. Do not add a relay-enable setting.
   The profile hard-codes new EUR lending unavailable. Do not enable it to unblock
   the loan button. Keep account pages on Django and existing Android CORS origins.

6. **Recheck target, TLS, requirements and complete plan**, on host:

   ```bash
   set -eu
   cd /home/shanonsimon/energy-sharing
   export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
   export DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings
   /home/shanonsimon/energy-venv/bin/python -m pip check
   /home/shanonsimon/energy-venv/bin/python manage.py check_alwaysdata_database
   /home/shanonsimon/energy-venv/bin/python manage.py check --deploy
   /home/shanonsimon/energy-venv/bin/python manage.py showmigrations meter
   /home/shanonsimon/energy-venv/bin/python manage.py migrate --plan
   ```

   Require database `shanonsimon_energy_test`, user `shanonsimon`, hostname
   `postgresql-shanonsimon.alwaysdata.net` and **encrypted=True** with actual TLS
   metadata. The updated check fails closed on missing/false TLS. Check installed
   cryptography and WhiteNoise against existing requirements; no dependency upgrade
   was performed on the host here. Confirm that the plan matches step2.

7. **Migrate and collectstatic**, only after reviewing the actual plan:

   ```bash
   /home/shanonsimon/energy-venv/bin/python manage.py migrate --noinput
   /home/shanonsimon/energy-venv/bin/python manage.py collectstatic --noinput
   ```

   If step2/6 shows anything beyond the reviewed baseline + meter0032, stop and
   review it first. Never use --fake, rollback populated migrations, replay credits
   or alter historical balances to make the rollout pass.

8. **WSGI restart**: Web → Sites → shanonsimon.alwaysdata.net → Restart. Retain
   Python3.12.15, venv `/home/shanonsimon/energy-venv`, working directory
   `/home/shanonsimon/energy-sharing`, WSGI application
   `/home/shanonsimon/energy-sharing/backend/alwaysdata_sandbox_wsgi.py`, both
   environment variables above, HTTPS redirect and existing static-file mapping.

9. **Scheduled tasks**: first inspect dry-runs (no provider calls):

   ```bash
   /home/shanonsimon/energy-venv/bin/python manage.py reconcile_sandbox_payments --limit 2 --max-seconds 50
   /home/shanonsimon/energy-venv/bin/python manage.py complete_demo_payments --limit 20 --max-seconds 50
   ```

   Preserve `drain_account_emails --send --limit 5` with its current environment.
   Prepare the following finite jobs in Advanced → Scheduled tasks, every minute
   subject to Free-plan limits. **Do not execute or enable provider work during
   this no-payment rollout review**; activation can submit already-authorized NEW
   intents as well as query previously submitted references. Inspect that queue
   and obtain authorization for provider activity before activation.

   ```bash
   ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings /home/shanonsimon/energy-venv/bin/python /home/shanonsimon/energy-sharing/manage.py reconcile_sandbox_payments --run --limit 2 --max-seconds 50
   ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings /home/shanonsimon/energy-venv/bin/python /home/shanonsimon/energy-sharing/manage.py complete_demo_payments --run --limit 20 --max-seconds 50
   ```

   Keep existing original-provider recovery schedules available; do not cancel,
   reset or convert pending records. No Celery eager mode/Redis/physical dispatch.
   MTN uses persistent90s leases and30s→3600s backoff; timeouts do not re-charge.

10. **Credential-free HTTPS checks**, no payment initiation or relay:

    ```bash
    curl --fail --silent --show-error https://shanonsimon.alwaysdata.net/api/v1/features/
    curl --silent --show-error -o /dev/null -w '%{http_code}\n' -X POST -H 'Content-Type: application/json' -d '{}' https://shanonsimon.alwaysdata.net/api/v1/prototype-device/v1/session/
    ```

    Expect features200, MTN_SANDBOX/EUR, loans=false, all seven features=false,
    physical_delivery=false; purchases/repayments depend on valid configuration.
    Lab POST must be503 in MTN mode. This tests denial, not a device session.
    No payment POST should be sent as a smoke test. Install the reviewed APK with
    `adb install -r` and check login, selected meter, separate ledger/history reads,
    clear loan/repayment/lab policy reasons and logout. Actual MTN transaction tests
    and physical board tests remain separate, explicitly authorized milestones.
