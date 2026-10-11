# alwaysdata Free testing deployment

This is an opt-in backend profile, not a live financial deployment. Render's
profile, Next.js server features, accounting policies, and the existing APK
build are retained. No deployment or hosted migration was performed locally.
The operator confirmed Python 3.12.15, an installed base requirements set with
`pip check` passing, a 155 MB virtualenv, and successful PostgreSQL connectivity.
Local Python is 3.14; running the checks below with hosted 3.12 remains necessary.
This profile is now **app-first**: Next.js hosting is not required. Django serves
email confirmation and password-reset completion over the assigned backend
HTTPS hostname. After completion, users return to the Android app manually.
No deep links, financial policy changes or APK rebuild are part of this update.
The operator confirmed PostgreSQL `sslmode=require` with TLS 1.3; this is
operator-reported evidence, not a new hosted connection performed by this change.

## Upload from WSL

Run from the repository root. This copies backend source only, preserves remote
extra files (no `--delete`), and never uploads the developer's environment,
virtualenv, logs, media, database data, or generated static files. Review the
dry-run before removing `--dry-run`; these are instructions, not executed steps.

```bash
rsync -avn --exclude='.env' --exclude='.env.*' --exclude='venv/' --exclude='venv_old/' --exclude='__pycache__/' --exclude='*.pyc' --exclude='*.log' --exclude='logs/' --exclude='media/' --exclude='mediafiles/' --exclude='staticfiles/' --exclude='*.sqlite3*' --exclude='*.sql' --exclude='*.dump' --exclude='*.pem' --exclude='*.key' backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
rsync -av --exclude='.env' --exclude='.env.*' --exclude='venv/' --exclude='venv_old/' --exclude='__pycache__/' --exclude='*.pyc' --exclude='*.log' --exclude='logs/' --exclude='media/' --exclude='mediafiles/' --exclude='staticfiles/' --exclude='*.sqlite3*' --exclude='*.sql' --exclude='*.dump' --exclude='*.pem' --exclude='*.key' backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
ssh shanonsimon@ssh-shanonsimon.alwaysdata.net
```

Remote layout is **the contents of local `backend/`**, so `manage.py` is directly
in `/home/shanonsimon/energy-sharing`. This layout matters for the WSGI path.
Do not upload frontend/mobile directories to the WSGI directory. The small
frontend/mobile auth-message changes can be released through their own builds
later; the current APK still embeds the LAN API URL, not the hosted HTTPS URL.

## Private environment on the host

Use a private file outside the uploaded source and static paths. WSGI and
management commands both load it through `backend.alwaysdata_settings`.
The file must be owned by the SSH account, mode **0600**, inside an owned
**0700** directory. Missing/insecure files cause startup to fail. Symlink files
are rejected. Existing process environment wins over file entries; remove any
stale panel variables rather than maintaining two sets of secrets. Values are
dotenv strings, not shell expressions; `${...}` is not expanded.

```bash
umask 077
mkdir -p /home/shanonsimon/.config/energy-sharing
chmod 700 /home/shanonsimon/.config/energy-sharing
cp /home/shanonsimon/energy-sharing/alwaysdata.env.example /home/shanonsimon/.config/energy-sharing/backend.env
chmod 600 /home/shanonsimon/.config/energy-sharing/backend.env
/home/shanonsimon/energy-venv/bin/python - <<'PY'
from pathlib import Path
import secrets
p = Path('/home/shanonsimon/.config/energy-sharing/backend.env')
p.write_text(p.read_text().replace('<fresh-random-deployment-secret-at-least-50-characters>', secrets.token_urlsafe(48)))
PY
nano /home/shanonsimon/.config/energy-sharing/backend.env
export DJANGO_SETTINGS_MODULE=backend.alwaysdata_settings
export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
cd /home/shanonsimon/energy-sharing
```

The `cp` and secret-generation commands are for first setup only: do not overwrite a populated private
file on subsequent uploads. Enter database and SMTP passwords in the editor,
not in shell commands, screenshots, Git, chat, or logs. Do not print the file.
Generate a **new deployment secret**; never reuse a previously embedded key.
For an existing private file, edit it with the same `nano` command; retain the
fresh deployment secret and database password. Remove `FRONTEND_URL` and
`PRODUCTION_ORIGIN` when no web app is hosted. Enter the new Gmail app password
only in `EMAIL_HOST_PASSWORD`, then save and check permissions with
`stat -c '%a %n' /home/shanonsimon/.config/energy-sharing/backend.env` (reports mode/path,
not contents). Do not overwrite the private file with the example template.

Set the public/confirmed fields to:

| Variable | Value / parser |
| --- | --- |
| `SECRET_KEY` | Required literal string; rejects blanks/placeholders, `django-insecure-`, fewer than 50 characters or fewer than 5 distinct characters. Freshness requires operator generation; cannot be proved from syntax. |
| `ALWAYSDATA_HOSTNAME` | `shanonsimon.alwaysdata.net`; validated hostname, no scheme, port or wildcard. |
| `FRONTEND_URL` | **Optional; omit for this app-first deployment.** Empty/missing uses the backend HTTPS origin. If present, a validated HTTPS URL without credentials/query/fragment for future web CORS configuration. Account email links always use Django, even when this variable is set. Remove the old placeholder rather than substituting a fictional Next.js address. Render still requires its existing web URL. |
| `DB_HOST` | `postgresql-shanonsimon.alwaysdata.net`, required string. |
| `DB_NAME` | `shanonsimon_energy_test`, required string. |
| `DB_USER` | `shanonsimon`, required string. |
| `DB_PASSWORD` | Private required string; significant whitespace retained. |
| `DB_PORT` | Integer 1–65535; default `5432`. |
| `DB_SSLMODE` | Set **`require`**, as successfully tested with TLS 1.3 by the operator. Parser retains supported libpq choices; `require` requests encryption, and is not a claim of hostname verification. |
| `DB_SSLROOTCERT` | Optional absolute CA path for certificate verification. |
| `EMAIL_HOST` | `smtp.gmail.com`; required string, no SMTP connections on startup. |
| `EMAIL_HOST_USER`, `DEFAULT_EMAIL_SENDER` | `shanonsimon082@gmail.com`; required strings. Public mailbox configuration, not a secret. |
| `EMAIL_HOST_PASSWORD` | **New Gmail app password**, required literal private string. Enter only in the private environment file, never the template or a shell command. No embedded/default password is used by this profile. |
| `EMAIL_PORT` | `587`, parsed integer 1–65535. |
| `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | `true` / `false`: STARTTLS, not implicit TLS. Explicit boolean parsing, exactly one true. |
| `EMAIL_TIMEOUT` | Integer seconds, default 10, range 1–30. SMTP socket-operation timeout, not a guarantee of total wall-clock execution time. |
| `BASE_URL` | Optional validated HTTPS URL; default `https://shanonsimon.alwaysdata.net/api/v1`. |
| `PRODUCTION_ORIGIN` | Optional one exact HTTPS web origin, no path/trailing slash; defaults to backend origin when `FRONTEND_URL` is absent. Does not change account email link destinations. |
| `EXTRA_ALLOWED_HOSTS` | Optional comma-separated explicit hostnames, trimmed and validated. No localhost/LAN hosts inherited. |

Booleans accept case-insensitive `true/1/yes/on` and `false/0/no/off/empty`;
unknown strings fail. `MTN_USE_SIMULATED_PAYMENTS` retains its separate legacy
parser: only `false/0/no` accepted, without surrounding whitespace. The template
contains placeholders for secrets/assigned database addresses, the confirmed
public Gmail SMTP configuration, and safe policy constants.
The profile rejects enabling DEBUG, eager execution, simulator, mobile financial
actions or any of the seven deferred features. It rejects real MTN/ThingsBoard
credentials and non-mock AMI/non-no-op CRB classes.

Ignored deployment inputs include `DATABASE_URL`, `ALLOWED_HOSTS`,
`EMAIL_BACKEND`, arbitrary CORS origins, Redis and broker URLs. Use the names
above. The current APK is `http://localhost` (Capacitor debug androidScheme),
while `mobile/capacitor.config.ts` uses `https://localhost` by default for
release. Both **exact** origins plus the backend origin (or configured future web origin) are allowed; API
requests still require HTTPS. CORS is not authentication. Only GET, POST, PATCH,
OPTIONS and `authorization`, `content-type` are permitted. Native origins are
not added to cookie-based CSRF trusted origins. JWT rotation, blacklist,
verification gates and secure cookies remain intact.

## Dependencies, database checks, and migration plan

alwaysdata supplies managed uWSGI: no Gunicorn service or global Gradle/Node
setup is needed. Add just the same WhiteNoise pin already used by Render:

```bash
/home/shanonsimon/energy-venv/bin/python --version
/home/shanonsimon/energy-venv/bin/python -m pip install -r requirements-alwaysdata.txt
/home/shanonsimon/energy-venv/bin/python -m pip check
/home/shanonsimon/energy-venv/bin/python manage.py check_alwaysdata_database
/home/shanonsimon/energy-venv/bin/python manage.py check --deploy
/home/shanonsimon/energy-venv/bin/python manage.py showmigrations --plan
/home/shanonsimon/energy-venv/bin/python manage.py migrate --plan
```

The database check refuses any target other than the confirmed testing
host/name/user **before connecting**. It checks connected database/user, TLS,
and whether the existing `custom` schema exists, without reading personal or
financial rows. Existing `search_path=custom,public` is preserved; absent custom
schema falls back to public. Inspect the plan against this isolated testing
database, never the development or operational database. Existing JWT
`token_blacklist` migrations are required for refresh/logout. Exactly which
old migrations are unapplied cannot be known without the hosted plan.

New migration **accounts.0018_account_email_delivery** only creates the
account-email outbox and its status index; no data rewrite or financial change.
It must be applied before registration on this profile. After confirming the
target and reviewing/backing up this test database and its plan, the operator
may run:

```bash
/home/shanonsimon/energy-venv/bin/python manage.py migrate --noinput
/home/shanonsimon/energy-venv/bin/python manage.py collectstatic --noinput
```

No automatic migration is embedded in WSGI, upload, or site restart. For an
existing database, review prior removal/data migrations in the plan; do not
assume this single additive migration is all that is pending.
If rolling this backend code to another hosting profile later, review/apply the
same additive schema migration there as well; it adds a user relationship even
when the email-outbox feature is off. This change does not migrate Render.

## Web → Sites configuration

| Field | Exact setting |
| --- | --- |
| Address | `shanonsimon.alwaysdata.net` |
| Type | **Python WSGI** (managed uWSGI), not User program/Gunicorn |
| Application path | `/home/shanonsimon/energy-sharing/backend/alwaysdata_wsgi.py` |
| Working directory | `/home/shanonsimon/energy-sharing` |
| Python version | **3.12.15**, matching the existing virtualenv; confirm the panel's 3.12 selector resolves to this installed patch version. |
| Virtualenv directory | `/home/shanonsimon/energy-venv` (not its `bin/python` file) |
| Environment variables | `DJANGO_SETTINGS_MODULE=backend.alwaysdata_settings` and `ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env`, one per line; no secrets in the panel required. |
| SSL | Enable **Redirect HTTP to HTTPS**; the account hostname uses the platform's `*.alwaysdata.net` certificate. |
| HTTP cache | Disabled for this API; never cache authenticated balances or token responses. |
| Static files | WhiteNoise serves collected `/static/` from `/home/shanonsimon/energy-sharing/staticfiles`. No separate Static files site, media mapping, or extra uWSGI static directive required. |
| Reload | **Restart** button beside the site after code/environment/static updates. Do not use Django runserver or autoreload. |

The profile trusts the platform's `X-Forwarded-Proto: https` and enables Django
HTTPS redirects/secure cookies. Trust applies only behind the managed platform
proxy; do not expose this WSGI app via an untrusted direct server. HSTS is left
at zero for testing, so `check --deploy` can report the deliberate HSTS warning.
uWSGI error log: `/home/shanonsimon/admin/logs/uwsgi/<site-id>.log`; HTTP/site logs
are under `admin/logs/http/` and `admin/logs/sites/`. Do not enable body/header
logging of passwords, Authorization, tokens, or full verification query strings.
Platform access logs may include query strings: restrict their access and
configure a format that omits sensitive authentication-link queries where the
panel supports it. Application SMTP exceptions are redacted.

## Account email without persistent workers

Account links are constructed by `accounts/account_actions.py` from
`ACCOUNT_PAGES_ORIGIN = https://ALWAYSDATA_HOSTNAME`, a validated deployment
setting, never `request.get_host()`, `Host`, `X-Forwarded-Host`, `BASE_URL`, or
an arbitrary request parameter. Example paths (actual UID/token only in email):

```text
https://shanonsimon.alwaysdata.net/account/verify-email/?uid=<uid>&token=<token>
https://shanonsimon.alwaysdata.net/account/reset-password/?uid=<uid>&token=<token>
```

GET/HEAD only validate and display a form. Verification requires an explicit
checkbox and **CSRF-protected POST**; reset requires matching validated passwords
and CSRF-protected POST. Form actions omit the URL query. Successful pages
contain no token/password and tell users to return to Android manually. No
automatic login, Next.js page, JavaScript, third-party asset or deep link is used.
CSS is served by WhiteNoise from this backend after `collectstatic`.

Responses, including token errors and CSRF failures, carry `Cache-Control:
no-store, private`, `Referrer-Policy: no-referrer`, no-index and restrictive CSP
headers. Keep platform HTTP caching disabled. Initial email URLs still enter
browser history/platform access logs; restrict log access and omit query strings
where supported. Do not paste live links into curl, logs or chat. GET does not
write account/session state or invalidate a token.

Existing `PASSWORD_RESET_TIMEOUT` and token hash rules remain unchanged.
Mutations share a service with the API; user/profile row locks re-check tokens
at consumption to serialize simultaneous confirmations. Verification invalidates
verification tokens; password changes invalidate reset tokens and existing JWTs.
Reset retains the existing email-based account-verification behavior, required
password-change handling, 8–128 character bounds, complexity validation and
matching-password requirement from `ResetPasswordConfirmSerializer`.
Expired/used/invalid/inactive links receive the same generic error.

On **alwaysdata only**, legacy `/api/v1/auth/verify-email/` GET returns 405
`ACCOUNT_CONFIRMATION_REQUIRED`, with browser instructions and no mutation.
The old APK's paste-link API shortcut cannot complete verification on this
profile; use the emailed browser form, then sign in normally. Existing Next.js
and Render API/link behavior is preserved. Reset API GET remains validation-only;
its existing explicit PATCH is retained and uses the shared single-use service.

Registration, verification resend, password-reset requests, and account security
codes enqueue **only account mail** in PostgreSQL. Registration and its initial
mail job share the transaction; neither survives a rollback. Responses say
queued, not delivered. Unknown password-reset addresses return the identical
generic response without creating an email job. Existing token generators,
expiry and one-time invalidation are used; no token/password/message body is
stored in this new queue. Stale account/password/email states and expired or
already-verified jobs are skipped. Existing active settings codes are referenced
by ID and must still be active/unexpired at send time.

Advanced → Scheduled tasks, **Command**, every minute, SSH account shanonsimon:

```bash
DJANGO_SETTINGS_MODULE=backend.alwaysdata_settings ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env /home/shanonsimon/energy-venv/bin/python /home/shanonsimon/energy-sharing/manage.py drain_account_emails --send --limit 5
```

This is a finite scheduled invocation, not a persistent service. If the Free
account cannot schedule at that frequency, use its supported interval or invoke
the identical command manually; email remains queued until invocation. A drain
claims jobs under a short database lock, commits, then calls SMTP outside locks.
Concurrent invocations skip claimed jobs. `SENT` means SMTP **accepted**, not
arrival in the inbox. A timeout/exception records `OUTCOME_UNKNOWN` and returns
a nonzero command result. A crash leaves `SENDING`; neither state is retried
automatically. Review mailbox/provider history before requesting a fresh link;
never reset uncertain jobs en masse. Scheduled logs contain job IDs/statuses,
not addresses, passwords, codes or tokens.

Read-only report (default; no SMTP):

```bash
/home/shanonsimon/energy-venv/bin/python manage.py drain_account_emails
```

## Redis/Celery inventory and unavailable operations

| Dependency / entry points | Free profile behaviour |
| --- | --- |
| `backend/__init__.py`, `backend/celery.py` Celery apps; Redis broker/result settings; `utils.general.dispatch_task` | No broker/result/Redis configured, eager false. Exact account-mail allowlist queues locally; every other dispatch raises `BACKGROUND_TASK_UNAVAILABLE` before publishing or synchronous fallback. Task `.delay`/`.apply_async` and app `.send_task` also reject. |
| `accounts/tasks.py` verification/security, share/transfer/wallet/token notifications, low-units alerts, payment receipts, loan application/disbursement/repayment and third-party emails, demo/retry tasks | Only verification/security email requests adapted to the outbox. Financial/notification/demo tasks do not run automatically or use the mail drain. |
| `accounts/signals.py`, `accounts/api/views.py` initial/resend/security mail, password recovery | Durable account mail, no Redis; reset no longer returns a delivery claim on this profile. |
| `transactions/tasks.py` reconcile pending payments; statement PDF emails / `transactions/api/views.py` | No worker, polling or statement-email job; stored receipt/history reads remain. |
| `meter/tasks.py` AMI balance snapshots, daily usage aggregation, pending AMI retries, simulated delivery outbox, low-unit polling / `meter/low_units_alerts.py` | No schedule/worker. Neither physical AMI nor simulator delivery runs on hosted Free. Development simulator code/tests remain locally available. |
| `loan/services.py`, `loan/api/views.py`, `meter/buy_units_payment.py`, `share/flow.py`, `share/views.py`, `ussd/views.py` task producers (including legacy direct `.delay`) | Financial/device mutations blocked by testing middleware; the seven deferred flags also remain false. No new provider calls/device commands or financial email activity. |
| `share/middlemare.py` optional sharing counters via Django cache | Feature disabled; cache is explicit process-local LocMem, not Redis and not a reliable distributed rate limit. |
| `admin/health_checks.py` Redis/Celery/provider probes | Report unavailable/AMBER without probing external systems or pretending memory queue acceptance means a worker is running. PostgreSQL/core health reads retained. |

`backend/partials/celery_settings.py` also contains unused Redis/queue settings;
the active base profile does not import those partials. The installed
`redis`/`django-redis` libraries are retained but no shared Redis cache is enabled.
`django-celery-beat` is not in the installed base requirements; the unused
`backend/celery.py` scheduler reference is another reason not to start Beat.
The private hosted profile's beat schedule is empty. Disabled features remain:
peer sharing, meter transfers, third-party repayment/lookup, USSD, wallet
deposits, wallet withdrawals, external CRB. Core scoring is unchanged.

This host deliberately permits authentication/account changes, local consumer
meter metadata registration, notification read markers, and authenticated
read-only history. It does not permit purchase, repayment, loan application or
admin financial mutations, provisioning, webhook/device writes, delivery,
statement emailing, or legacy GET provider/meter polls/retries. Unsupported
calls return a clear 503 `TESTING_OPERATION_UNAVAILABLE`; no view side effects
occur. Admin sign-in/read screens remain, admin model write actions are blocked
on this testing profile. Existing financial records/models are not converted,
deleted, refunded, replayed, or cancelled. **Do not move funded/pending live
obligations onto this deployment**: payment reconciliation, daily aggregation,
meter delivery and automatic alerts cannot be claimed operational without a
separately reviewed worker-capable deployment. The completed-loan overdue
expected failure and financial-policy decisions remain open.

## HTTPS checks after operator deployment

These checks contain no credentials and initiate no payments:

```bash
curl -I http://shanonsimon.alwaysdata.net/
curl -i https://shanonsimon.alwaysdata.net/
curl -i https://shanonsimon.alwaysdata.net/static/admin/css/base.css
curl -i https://shanonsimon.alwaysdata.net/account/verify-email/
curl -i https://shanonsimon.alwaysdata.net/account/reset-password/
curl -i -H 'Origin: http://localhost' https://shanonsimon.alwaysdata.net/api/v1/features/
curl -i -X OPTIONS -H 'Origin: http://localhost' -H 'Access-Control-Request-Method: POST' -H 'Access-Control-Request-Headers: content-type' https://shanonsimon.alwaysdata.net/api/v1/auth/login/
curl -i -H 'Origin: http://localhost' -H 'Content-Type: application/json' --data '{}' https://shanonsimon.alwaysdata.net/api/v1/auth/login/
curl -i -H 'Origin: https://localhost' -H 'Content-Type: application/json' --data '{}' https://shanonsimon.alwaysdata.net/api/v1/auth/login/
```

Expect HTTP redirect, HTTPS health/static 200, all seven features/mobile actions
false, preflight allowing only required headers/methods, and **readable login
400** for empty data with the exact matching CORS origin. The two account pages
without a token should return generic 400 HTML with no-store/no-referrer/CSP
headers, not a Next.js redirect. Authenticated account
reads require real verified testing accounts; never paste passwords/JWTs into
diagnostic logs. Test registration → scheduled SMTP acceptance → verification →
explicit browser confirmation → login/refresh/logout/password reset with an isolated tester before changing APK
configuration in a later phase. Also check an unrelated Origin is not allowed.

## Changed files

The app-first update specifically changes/adds: `accounts/account_actions.py`,
`accounts/account_pages.py`, `accounts/api/views.py`, `accounts/email_outbox.py`,
`accounts/templates/accounts/account_action.html`,
`accounts/static/accounts/account-pages.css`, `accounts/tests_account_pages.py`,
`backend/alwaysdata_settings.py`, `backend/alwaysdata_urls.py`,
`backend/hosting_middleware.py`, `backend/tests_alwaysdata.py`,
`deploy/test-hosting.py`, `alwaysdata.env.example`, and this runbook.
All other uncommitted work from the previous hosting phase is retained.

The following inventory includes that earlier hosting work as well:

- Hosting profiles/configuration: `backend/alwaysdata_settings.py`,
  `backend/alwaysdata_wsgi.py`, `backend/hosting_environment.py`,
  `backend/hosting_middleware.py`, `backend/render_config.py`,
  `alwaysdata.env.example`, `requirements-alwaysdata.txt` (paths relative to
  the backend upload directory).
- Account mail: `accounts/models.py`, `accounts/email_outbox.py`,
  `accounts/signals.py`, `accounts/api/views.py`,
  `accounts/migrations/0018_account_email_delivery.py`,
  `accounts/management/commands/drain_account_emails.py`,
  `accounts/management/commands/check_alwaysdata_database.py`.
- App-first account actions: `accounts/account_actions.py`,
  `accounts/account_pages.py`, `accounts/templates/accounts/account_action.html`,
  `accounts/static/accounts/account-pages.css`, `backend/alwaysdata_urls.py`,
  `accounts/tests_account_pages.py`. No new migration for these pages.
- Worker/probe safety: `utils/hosting_tasks.py`, `utils/general.py`,
  `utils/email.py`, `backend/__init__.py`, `backend/celery.py`,
  `admin/health_checks.py`.
- Tests/runbook: `backend/tests_alwaysdata.py`, `deploy/test-hosting.py`,
  `docs/ALWAYSDATA_TESTING.md`.
- Web auth messaging (repo-relative):
  `frontend/src/app/(authentication)/auth/register/register.tsx`,
  `frontend/src/app/(authentication)/auth/register/_components/form.tsx`,
  `frontend/src/app/(authentication)/auth/forgot-password/forgot-password.ts`,
  `frontend/src/app/(authentication)/auth/forgot-password/_components/form.tsx`;
  mobile messaging: `mobile/src/Access.tsx`. No APK/build configuration change.

## Local verification

Use a disposable PostgreSQL cluster, never the hosted database. The local test
harness refuses to start unless the account-owned `/tmp/gpawa-alwaysdata/pg`
cluster is running on **55445**, uses only role `gpawa_alwaysdata_test`, clears
inherited environment variables, mocks email, and blocks external HTTP. These
are WSL commands using the installed PostgreSQL 18 binaries; initialize only a
new directory, not an existing development cluster:

```bash
mkdir -p /tmp/gpawa-alwaysdata
/usr/lib/postgresql/18/bin/initdb -D /tmp/gpawa-alwaysdata/pg -U gpawa_alwaysdata_test --auth=trust
/usr/lib/postgresql/18/bin/pg_ctl -D /tmp/gpawa-alwaysdata/pg -l /tmp/gpawa-alwaysdata/postgresql.log -o '-h 127.0.0.1 -p 55445 -k /tmp/gpawa-alwaysdata' start
backend/venv/bin/python backend/deploy/test-hosting.py backend.tests_alwaysdata.PrivateEnvironmentTests backend.tests_alwaysdata.AccountMailOutboxTests accounts.tests_authentication accounts.tests_mobile_api accounts.tests_mobile_cors accounts.tests_mobile_profile_meters accounts.tests_mobile_activity backend.tests_feature_flags backend.tests_render_config.RenderEnvironmentTests transactions.tests_payment_settlement meter.tests_allocation_delivery loan.tests_financial_correctness
backend/venv/bin/python backend/deploy/test-hosting.py --profile accounts.tests_account_pages backend.tests_alwaysdata.AlwaysdataProfileTests backend.tests_alwaysdata.AlwaysdataAuthenticationFlowTests
backend/venv/bin/python backend/deploy/test-hosting.py --render backend.tests_render_config
/usr/lib/postgresql/18/bin/pg_ctl -D /tmp/gpawa-alwaysdata/pg stop
```

The profile runner deliberately omits `FRONTEND_URL` and collects the new CSS
into a temporary directory to exercise production manifest/WhiteNoise rendering.
No test reads hosted records or sends SMTP. The hosting-profile tests need WhiteNoise available. Locally it was downloaded
into `/tmp/gpawa-alwaysdata-deps` without changing existing dependencies; commands
used `HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps` before the test runner.
Alternatively use a dedicated test virtualenv with `requirements-alwaysdata.txt`.
The initial combined run used the equivalent temporary runner
`/tmp/gpawa-alwaysdata/run_tests.py`; the repository harness reproduces its
synthetic settings, mock transport and isolation controls.

The app-first update reran the combined 142-test suite, the 16 hosted-profile
tests and the 14 Render tests below. The separate WSGI/migration/web/mobile
checks listed afterward are retained evidence from the preceding hosting phase,
not newly performed checks or a rebuilt APK. Production manifest/CSS serving is
also exercised by the current hosted-profile tests.

- Combined authentication/hosting, payments, allocations, simulator, financial
  and feature regressions: **142 tests, OK, one known expected failure** for
  overdue-after-completion. PostgreSQL concurrent mail drains confirmed one
  SMTP call, with no database lock held during send.
- Existing Render settings suite: **14 tests passed**.
- App-first alwaysdata profile: **16 tests passed**, including no-Next.js
  startup, trusted-origin links, non-consuming GET/HEAD, CSRF/missing-checkbox
  rejection, password validation, token expiry/purpose/replay, reset JWT
  invalidation and verification/login/account/refresh/logout. Parallel
  verification and reset submissions each produced one completion and one
  rejection on isolated PostgreSQL. Email mocked; no external requests.
- Temporary `collectstatic`, WSGI initialization and health/features/admin CSS
  responses: **200**, with database access blocked during smoke requests.
- `makemigrations --check --dry-run`: no model drift. `check --deploy`: only the
  deliberate HSTS warning. The app-first runner now collects static files
  temporarily; the unchanged Render unit suite still warns about absent local
  staticfiles. No deployment directories are created by these tests.
- Next.js `npx tsc --noEmit`: passed. Relevant ESLint: zero errors, two existing
  unused `LabelInputContainer` warnings. A touched unescaped apostrophe was
  corrected; no broad lint rewrite or strict-check bypass.
- Mobile `npm run typecheck` and `npm test`: passed (three test files). No APK
  rebuild/device deployment. Next.js production build was not rerun; the prior
  font-download limitation is independent of this backend deployment.
- Final outbox dry-run/report and no-replay test: passed after adding bounded
  job identifiers/statuses to the read-only report.

Historical fixture tests still emit pre-existing wallet meter-balance conflict
logs; the regressions pass without changing those models/signals or suppressing
the known financial expected failure. Hosted Python 3.12.15, SMTP delivery,
resource consumption, browser/phone login and actual HTTPS hosting remain
operator smoke checks, not claimed as performed.

## Official references reviewed

- [alwaysdata Python/WSGI configuration](https://help.alwaysdata.com/en/docs/web-hosting/languages/python/configuration/)
- [HTTP proxy headers](https://help.alwaysdata.com/en/docs/web-hosting/sites/http-stack/)
- [Scheduled tasks](https://help.alwaysdata.com/en/docs/web-hosting/tasks/)
- [Plans and persistent-service eligibility](https://help.alwaysdata.com/en/docs/admin-billing/billing/choose-its-paas/)
- [Site restart](https://help.alwaysdata.com/en/docs/web-hosting/sites/restart-a-site/)
- [Account-hostname TLS certificates](https://help.alwaysdata.com/en/docs/web-hosting/sites/ssl-tls/lets-encrypt/)
- [WhiteNoise Django configuration](https://whitenoise.readthedocs.io/en/stable/django.html)
- [Django CSRF-protected forms and testing](https://docs.djangoproject.com/en/5.2/howto/csrf/)

Remaining operator blockers: privately entered new Gmail app password, reviewed hosted
migration plan, scheduled drain configuration, hosted Python 3.12/static/account-page/API
smoke checks, and later APK endpoint update. Previously embedded SMTP and any
reused deployment/provider secrets require operator rotation; no rotation was
performed. Free plan resources and process-local throttling are testing limits,
not evidence of readiness for live funds/hardware.
