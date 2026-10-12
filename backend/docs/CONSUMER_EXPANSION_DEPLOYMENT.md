# Consumer expansion deployment preparation

Prepared locally; no upload, hosted query/migration or deployment was executed.
Existing authentication, strict-origin CSRF fix, Django-hosted verification/reset
pages and scheduled email outbox are retained. Next.js is not needed on this host.

## Exact source upload

The explicit allowlist is `backend/deploy/consumer-expansion.files`. Paths are
relative to **backend/**, which maps directly to `/home/shanonsimon/energy-sharing/`.
It lists changed runtime files and the account/hosting baseline dependencies to
preserve. Test files remain local; no new Python package is required for consumers.
Do not replace this list with a whole-repository upload or use `--delete`.

From the repository root, validate the list and inspect the dry-run before upload:

```bash
python3 - <<'PY'
from pathlib import Path
root = Path('backend').resolve()
files = Path('backend/deploy/consumer-expansion.files').read_text().splitlines()
for name in files:
    path = root / name
    assert path.is_file() and path.resolve().is_relative_to(root), name
    assert not any(part.startswith('.') or part in {'venv', 'venv_old', '__pycache__', 'staticfiles', 'media', 'logs'} for part in Path(name).parts), name
    assert path.suffix in {'.py', '.html', '.css', '.md', '.example', '.files'}, name
    print(name)
print(f'{len(files)} reviewed files; no secret/database/build artifacts selected')
PY
rsync -avn --files-from=backend/deploy/consumer-expansion.files --exclude='.env*' --exclude='venv*/' --exclude='__pycache__/' --exclude='*.pyc' --exclude='*.log' --exclude='logs/' --exclude='media/' --exclude='mediafiles/' --exclude='staticfiles/' --exclude='*.sqlite3*' --exclude='*.db' --exclude='*.sql' --exclude='*.dump' --exclude='*.pem' --exclude='*.key' backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
# Only after reviewing the dry-run:
rsync -av --files-from=backend/deploy/consumer-expansion.files --exclude='.env*' --exclude='venv*/' --exclude='__pycache__/' --exclude='*.pyc' --exclude='*.log' --exclude='logs/' --exclude='media/' --exclude='mediafiles/' --exclude='staticfiles/' --exclude='*.sqlite3*' --exclude='*.db' --exclude='*.sql' --exclude='*.dump' --exclude='*.pem' --exclude='*.key' backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
```

The public `.env.example`-suffix templates contain placeholders only; the local
`.env` and remote private environment are never selected. The allowlist assumes
the existing backend/migrations are already deployed. If a migration dependency
is absent on disk, stop and compare the full migration tree before proceeding;
do not fake migrations or overwrite unrelated host files.

## Schema and private configuration

Both original expansion migrations are preserved:

| Migration | Additive effect | Dependencies |
| --- | --- | --- |
| `meter.0026_meterenrollmentrequest` | Owner/number-unique pending declarations | `meter.0025_meterdelivery_request_id`, user model |
| `loan.0022_purchasescoreexclusion` | Protected scoring-only reversal/uncertainty markers; scoring remains off | `loan.0021_loanrepayment_applied_excess`, `transactions.0010_paymentintent_client_request_id`, user model |
| **New** `meter.0027_meterenrollmentreview` | One protected final decision per request, reviewer, private evidence reference, optional assigned meter and consumer explanation | `meter.0026`, user model |

The third migration is necessary because the existing implementation had no
staff review record/workflow. None converts balances, changes scores, assigns
existing requests or replays obligations. Existing users/meters remain unchanged.
The previously deployed `accounts.0018_account_email_delivery` and JWT blacklist
schema must also remain present; the hosted plan determines whether any older
migrations are still pending. Never roll back by dropping populated tables.

On the host, privately edit (do not copy the local `.env`):

```bash
ssh shanonsimon@ssh-shanonsimon.alwaysdata.net
chmod 700 /home/shanonsimon/.config/energy-sharing
chmod 600 /home/shanonsimon/.config/energy-sharing/backend.env
nano /home/shanonsimon/.config/energy-sharing/backend.env
```

Preserve the fresh secret, SMTP credentials, trusted hostname/origin, database
credentials, `DB_SSLMODE=require` and existing settings. Ensure:

```dotenv
PURCHASE_HISTORY_SCORING_ENABLED=false
MOBILE_METER_STALE_SECONDS=120
MOBILE_PAYMENT_ACTIONS_ENABLED=false
SIMULATED_METER_ENABLED=false
CELERY_TASK_ALWAYS_EAGER=false
MTN_USE_SIMULATED_PAYMENTS=false
FEATURE_PEER_SHARING_ENABLED=false
FEATURE_METER_TRANSFERS_ENABLED=false
FEATURE_THIRD_PARTY_REPAYMENT_ENABLED=false
FEATURE_USSD_ENABLED=false
FEATURE_WALLET_DEPOSITS_ENABLED=false
FEATURE_WALLET_WITHDRAWALS_ENABLED=false
FEATURE_EXTERNAL_CRB_ENABLED=false
```

No purchase-score cap/basis/policy ID is approved. Do not enter proposed values.
Keep the existing scheduled `drain_account_emails --send --limit 5` job unchanged;
no reconciliation, simulator delivery, Celery or Redis worker is added.

## Operator database checks, plan review and deployment

These are commands for the operator, **not executed by this change**. Use a short
maintenance window to avoid requests running between schema and code activation.

```bash
cd /home/shanonsimon/energy-sharing
export DJANGO_SETTINGS_MODULE=backend.alwaysdata_settings
export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
/home/shanonsimon/energy-venv/bin/python --version
/home/shanonsimon/energy-venv/bin/python -m pip check
/home/shanonsimon/energy-venv/bin/python manage.py check_alwaysdata_database
/home/shanonsimon/energy-venv/bin/python manage.py audit_phone_formats
/home/shanonsimon/energy-venv/bin/python manage.py showmigrations meter loan transactions accounts token_blacklist
/home/shanonsimon/energy-venv/bin/python manage.py migrate --plan
/home/shanonsimon/energy-venv/bin/python manage.py sqlmigrate meter 0026
/home/shanonsimon/energy-venv/bin/python manage.py sqlmigrate loan 0022
/home/shanonsimon/energy-venv/bin/python manage.py sqlmigrate meter 0027
```

The target check refuses configuration other than host
`postgresql-shanonsimon.alwaysdata.net`, database `shanonsimon_energy_test`, user
`shanonsimon`, and verifies the connected identity. Require its `encrypted=True`
result. The audit prints IDs/counts only. Back up the **testing database** using
alwaysdata's database backup facility and review every pending migration; older
pending migrations are not assumed additive. Stop on an unexpected target/plan.

Only after this review and backup, execute on the confirmed testing database:

```bash
/home/shanonsimon/energy-venv/bin/python manage.py migrate --noinput
/home/shanonsimon/energy-venv/bin/python manage.py collectstatic --noinput
/home/shanonsimon/energy-venv/bin/python manage.py check --deploy
```

In **Web → Sites**, keep the existing Python WSGI site:
application `/home/shanonsimon/energy-sharing/backend/alwaysdata_wsgi.py`, working
directory `/home/shanonsimon/energy-sharing`, virtualenv
`/home/shanonsimon/energy-venv`, Python 3.12.15. Keep the two environment variable
names exported above and HTTPS redirect enabled. Click the site's **Restart**
button; no runserver, global eager mode or new daemon. WhiteNoise serves collected
static files. Deployment mechanics follow the
[official alwaysdata Python configuration](https://help.alwaysdata.com/en/docs/web-hosting/languages/python/configuration/).
Deliberate testing HSTS warnings are documented in `ALWAYSDATA_TESTING.md`.

Credential-free HTTPS checks after restart:

```bash
curl -i https://shanonsimon.alwaysdata.net/api/v1/features/
curl -i -X OPTIONS https://shanonsimon.alwaysdata.net/api/v1/auth/login/ -H 'Origin: http://localhost' -H 'Access-Control-Request-Method: POST' -H 'Access-Control-Request-Headers: content-type'
curl -i -X POST https://shanonsimon.alwaysdata.net/api/v1/auth/login/ -H 'Origin: http://localhost' -H 'Content-Type: application/json' --data '{}'
curl -i https://shanonsimon.alwaysdata.net/api/v1/meter/mobile-onboarding/
curl -i https://shanonsimon.alwaysdata.net/admin-panel/meter-link-requests/
```

Expect features 200, empty login 400 with readable configured-origin CORS,
unauthenticated onboarding 401 and staff page redirect to admin login. Debug
APK origin is **http://localhost**, release origin **https://localhost**; both
remain explicitly allowed, no wildcard. Verify account-page GET is nonconsuming,
CSRF-protected POST works with the same HTTPS origin and security headers remain.
Do not paste account links, tokens, request bodies or staff evidence into logs.

## Permitted routes and staff workflow

| Flow | Hosted access / restrictions |
| --- | --- |
| Registration, login, refresh/logout, verification/reset | Existing `/api/v1/auth/` and HTTPS Django account pages; outbox scheduler retained |
| `GET meter/mobile-onboarding/`, `POST meter/mobile-meter-requests/`, legacy `POST meter/register/` | Verified consumer only; retries reuse one declaration; pending/rejected grants no access |
| `GET loans/mobile-eligibility/` | Authoritative score read; no disbursement or purchase contribution; incomplete profile score unavailable |
| `GET meter/mobile-meters/`, `mobile-meters/<id>/`, `mobile-consumption/`, `mobile-deliveries/` | Existing assignment required; owner-bound stored reads, no provider/device query |
| Purchase/loan provisional quote POSTs | Side-effect-free estimates allowed; current tariff/profile may be missing |
| `/admin-panel/meter-link-requests/` GET/POST | New narrow session-based operator/admin review, CSRF and transactional audit |
| General admin writes, loan submission/disbursement, purchase/repayment initiation, delivery, provider/device probes | Existing restrictions unchanged; testing-operation error, no financial/device calls |

Staff procedure, with no hosted Next.js required:

1. Use an **existing active staff account** (`is_staff=True`, role `OPERATOR` or
   `ADMIN`), verified email, no suspension or required initial password change.
   Log in at `https://shanonsimon.alwaysdata.net/admin-panel/login/`, then open
   `/admin-panel/meter-link-requests/`. Consumer/customer-service/superuser-only
   accounts without the required role do not qualify; no permissions are granted
   automatically. Staff identity/provisioning is an operator prerequisite.
2. Match the request and consumer ID to independently checked identity and usage
   authorization: utility-confirmed customer/meter assignment, or checked occupancy
   proof plus owner's authorization. Keep documents in a private case system;
   store only its reference. The software records the authorized staff attestation;
   it cannot establish authenticity of external evidence itself.
3. Select request UUID, approve/reject and a consumer-safe explanation. Approval
   requires evidence type/reference and explicit verified checkbox. Rejection
   needs an explanation and never assigns a meter. A configured staff TOTP needs
   a fresh code; missing optional `pyotp` fails closed (check with `python -m pip
   show pyotp`; dependency setup/2FA enrolment is not performed by this change).
4. Approve only active **pre-provisioned** inventory that is unowned and has no
   linked historical records/balances, deleted-number history or prior meter audit.
   Already-assigned-to-this-consumer meters remain compatible. Foreign-owned,
   inactive, deleted, missing or historically used unowned meters are refused.
   No inventory creation/transfer/history erasure or device-key setup is exposed.
5. Decision and `AuditLog` commit together; audit failure rolls back assignment.
   Same-decision retries do not write twice. Conflicting decisions cannot overwrite
   the first; distinct consumer claims serialize on the meter. Evidence references
   stay private. Consumer reads receive only status and explanation.

**Inventory blocker:** missing inventory needs an independently authorized
provisioning process before approval. General provisioning POSTs are still blocked
on Free; do not temporarily disable middleware to resolve this. Historical meter
tenancy attribution remains unavailable (`consumer_attribution_available=false`)
on legacy monitoring; this workflow refuses new access to such unowned inventory.
Existing users' assignments/history are preserved, not retroactively certified.

## Ordered phone test (synthetic accounts only)

1. Register: supported Ugandan phone formats canonicalize; malformed/duplicate
   aliases rejected. Phone formatting is not proof of ownership.
2. Wait for scheduled delivery; open Django HTTPS verification link, explicitly
   confirm by CSRF POST, return to Android. GET/repeated token does not verify twice.
3. Sign in; verify actual HTTPS API/origin, unverified denial and refresh handling.
4. Request a meter; retry same number → one request. Pending cannot select that
   meter or read another consumer's dashboard/usage/delivery; financial writes stay blocked.
5. Authorized staff independently verifies evidence and approves clean inventory,
   or rejects with safe explanation. Test unauthorized staff/consumer denial,
   missing evidence, foreign ownership and CSRF rejection. Do not use real device commands.
6. Refresh assignment; select the authorized meter (explicit choice for multiple).
   Existing assignment removal clears stale selection without redirecting to another meter.
7. Read score explanation/timestamps: incomplete evidence → unavailable, starter
   floor explicitly labelled, refresh gives no purchase points or loan approval.
8. Read entitlement, reserved/unresolved and acknowledged application separately.
   Fresh inventory with no telemetry shows unavailable contact/usage, not invented
   readings. **Stored simulator** data is labelled simulator; daily source/time is
   preserved. No live hardware, radio reliability or physical accuracy claim.
9. Background/offline/reconnect shows stale fetch time without replaying writes;
   logout clears local account data and revokes the session as documented.

Existing expansion APK supports pending requests/assigned reads. The new rejection
and assignment-unavailable labels require rebuilding/installing an updated APK;
no APK rebuild or phone runtime test was performed in this deployment-preparation
change. Without update an old APK can misleadingly label rejection as pending.
Live funds, purchase scoring, completed-loan overdue closure policy, reconciliation
workers and reviewed physical firmware remain unresolved/gated.

## Local verification results

Isolated PostgreSQL on port 55445 through the guarded runner; external HTTP is
forbidden and email/providers/devices are mocked. No hosted database was used.

```bash
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py meter.tests_enrollment_review accounts.tests_consumer_expansion backend.tests_alwaysdata.PrivateEnvironmentTests backend.tests_alwaysdata.AccountMailOutboxTests accounts.tests_authentication accounts.tests_mobile_api accounts.tests_mobile_cors accounts.tests_mobile_profile_meters accounts.tests_mobile_activity backend.tests_feature_flags backend.tests_render_config.RenderEnvironmentTests transactions.tests_payment_settlement meter.tests_allocation_delivery loan.tests_financial_correctness
```

**177 tests, OK (2 skipped, 1 expected failure), 127.076 seconds.** The skipped
tests require real hosted-profile middleware/URLs and pass in the following run:

```bash
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --profile meter.tests_enrollment_review accounts.tests_account_pages backend.tests_alwaysdata.AlwaysdataProfileTests backend.tests_alwaysdata.AlwaysdataAuthenticationFlowTests
```

**36 tests pass, 17.983 seconds.** Includes exact hosted route restrictions,
session CSRF, strict-origin/no-store headers, owner-only history, proof validation,
configured TOTP denial/ mocked verifier contract, rollback on audit failure,
duplicate concurrent review and competing-consumer assignment using separate
database connections. `makemigrations --check --dry-run` reports no missing model
migrations. Known expected failure remains
`loan.tests_financial_correctness.test_completed_loan_stays_closed_when_overdue_clock_advances`.
Pre-existing caught fixture/signal `wallet_meterbalance_meter_number_key` errors
still appear in isolated regression logs; there are no new failed assertions.

From `mobile/`: `npm run typecheck` and
`node --test --test-isolation=none --test-reporter=spec tests/*.test.mjs` pass:
**31 tests**, including final request labels. The existing warning about the web
package's pure TS ESM helper remains; no module-type/strict-check bypass was added.
`git diff --check` passes. All changed backend runtime Python files are covered
by the 45-file validated upload allowlist. Tests ran with local Python 3.14;
hosted Python 3.12.15, browser/device runtime and actual deployment remain operator
verification steps. No Next.js code changed in this follow-up; the prior
independent production-build timeout remains documented in the mobile report.
