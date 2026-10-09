# Render backend testing deployment

This is an **opt-in, isolated authentication/read-only testing deployment**, not
a live financial or physical-meter deployment. Use `backend.render_settings`.
The existing `backend.settings` remains the local/web baseline. No Next.js
static export, Android conversion, accounting change or database migration is
part of this preparation. Never point this profile at existing funded accounts
or copy operational records into it: its periodic reconciliation is deliberately
not scheduled. Existing settlement/reconciliation code and records are retained.

## Render configuration checklist

1. Create a fresh testing PostgreSQL database, web service and Key Value service
   in the **same Render region/workspace**. Use synthetic accounts only. Confirm
   the database identity before any schema operation. Do not upload `.env`.
2. Web service: Python runtime; **Root Directory `backend`**;
   **Build Command `bash deploy/render-build.sh`**;
   **Start Command `bash deploy/render-start.sh`**;
   **Health Check Path `/`**. Set `PYTHON_VERSION=3.12.15` rather than inheriting
   Render's Python default. This preserves the project's Django 5.2 pin.
3. Set variables individually using [render.env.example](../render.env.example).
   Replace every angle-bracket placeholder. Use a new strong `SECRET_KEY`, new
   SMTP credentials, and Render-issued testing DB/Key Value credentials. Do not
   reuse production provider/device keys. `RENDER_EXTERNAL_HOSTNAME` is supplied
   automatically by Render; it is a hostname, not a URL.
4. Before deploying authentication, configure email and a background worker.
   Worker Root Directory: `backend`; build command:
   `python -m pip install -r requirements-render.txt`; start command:
   `celery -A backend:celery_app worker --loglevel=info --concurrency=1`.
   Set the **same application environment** and `DJANGO_SETTINGS_MODULE` on
   the worker. Share the private Key Value URL; prefer persistent storage and
   `noeviction` for the broker. Do not start Celery Beat for this profile.
5. Only after independently confirming a **fresh testing database**, review
   `python manage.py showmigrations` and `python manage.py migrate --plan` with
   this profile. A fresh database needs the full project migration graph,
   including `token_blacklist` for refresh/logout revocation. Migration execution
   is a separate operator action; build/start scripts never run it. Do not apply
   just blacklist migrations while leaving application dependencies unapplied.
6. Verify `/`, `/api/v1/features/`, login's empty-body 400 and unauthenticated
   mobile-account's 401 over HTTPS. Check their actual CORS response headers.
   Test registration/verification with synthetic accounts and inspect worker
   delivery without logging tokens, passwords or verification URLs.
7. Rebuild the phone APK with
   `VITE_API_BASE_URL=https://<assigned-backend-name>.onrender.com/api/v1`
   using the existing mobile `android:sync:debug` script, then the Android
   project's `./gradlew assembleDebug` with its required Java/SDK environment.
   Installing an existing LAN
   APK will still use its embedded LAN API address. No APK was changed here.

## Exact environment contract

The Render profile never loads `backend/.env`, even if that file exists.
`DJANGO_LOAD_LOCAL_ENV=false` is enforced before importing base settings.
Base local settings now load dotenv before their first Redis/URL lookup; OS
environment values retain precedence (`override=False`). Missing required
variables and placeholders abort startup with the **variable name only**.

| Variable | Render testing value / parsing |
| --- | --- |
| `DJANGO_SETTINGS_MODULE` | Exactly `backend.render_settings`; use on web, worker and management commands. Scripts set it explicitly. |
| `PYTHON_VERSION` | Render runtime selector, fully qualified `3.12.15`; not a Django variable. |
| `DEBUG` | False only. Strict boolean parser; profile normalizes to `False` for base settings. |
| `DJANGO_LOAD_LOCAL_ENV` | Profile forces `false`. Local profile default `true`, strict boolean parser. |
| `SECRET_KEY` | Required nonblank string; use a newly generated value, at least 50 characters with sufficient randomness. Not logged. |
| `RENDER_EXTERNAL_HOSTNAME` | Required assigned Render hostname; strip/lowercase; schemes, ports and wildcards rejected. |
| `EXTRA_ALLOWED_HOSTS` | Optional comma-separated additional hostnames, trimmed, individually validated; no URLs or wildcards. Default empty. Local/LAN default hosts are **not** inherited. |
| `BASE_URL` | HTTPS URL, no credentials/query/fragment; trailing slash removed. Defaults to `https://<RENDER_EXTERNAL_HOSTNAME>/api/v1`. |
| `FRONTEND_URL` | Required HTTPS URL for the **existing Next.js website**, used in verification/reset links. Do not use the Django API URL here. |
| `PRODUCTION_ORIGIN` | One exact HTTPS web origin, no path/trailing slash/comma list. Defaults to the origin of `FRONTEND_URL`. CORS and web CSRF trust. |
| `MOBILE_APP_ORIGIN` | One origin. Current debug APK: **`http://localhost`** (default). Release APK: `https://localhost`. Only the precise debug localhost origin may use HTTP; remote API remains HTTPS. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` | All required nonblank strings; credentials preserve significant whitespace. Copy individual fields from the **testing** database connection details. No local DB defaults in this profile. |
| `DB_PORT` | Integer; default `5432`. |
| `DB_SSLMODE` | Required libpq mode: `disable`, `allow`, `prefer`, `require`, `verify-ca` or `verify-full`. Use `prefer` for Render's private same-region internal connection; use `require` or stricter for external connections. `verify-ca/full` also require a valid trusted CA configuration. |
| `CELERY_BROKER_URL` | Required `redis://` or `rediss://` URL, hostname required; internal Key Value connection recommended. |
| `REDIS_URL` | Same URL for admin Redis diagnostics; defaults to `CELERY_BROKER_URL`. |
| `CELERY_RESULT_BACKEND` | Redis URL; defaults to broker. Current tasks ignore results, so application workflows do not rely on result persistence. |
| `CELERY_TASK_ALWAYS_EAGER` | False only. Enforced asynchronous dispatch for deployment. |
| `CELERY_TIMEZONE` | String, default `Africa/Nairobi`. |
| `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_EMAIL_SENDER` | All required strings; sender must be permitted by the SMTP provider. No embedded SMTP password fallback. Backend remains Django SMTP. |
| `EMAIL_PORT` | Integer, default `587`. |
| `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | Strict booleans, defaults `true` / `false`. Exactly one must be true; e.g. STARTTLS 587 or implicit TLS 465. Profile also sets `EMAIL_TIMEOUT=15`. |
| `PORT` | Render supplies listener port; start script defaults to `10000`. |
| `WEB_CONCURRENCY` | Gunicorn worker count, default `1`; choose against service memory and database connection limits. |

Strict booleans accept `true/1/yes/on` and `false/0/no/off/empty`, ignoring case
and surrounding whitespace; invalid strings fail. In the **base** local settings,
`DEBUG`, SMTP TLS/SSL and Celery eager instead use exact comparison with `"True"`.
This difference is deliberately handled by the Render profile, not silently
changed for existing web/development settings.

These names must remain disabled; the Render profile **rejects** enabled values:

| Flag | Default |
| --- | --- |
| `FEATURE_PEER_SHARING_ENABLED` | `false` |
| `FEATURE_METER_TRANSFERS_ENABLED` | `false` |
| `FEATURE_THIRD_PARTY_REPAYMENT_ENABLED` | `false` |
| `FEATURE_USSD_ENABLED` | `false` |
| `FEATURE_WALLET_DEPOSITS_ENABLED` | `false` |
| `FEATURE_WALLET_WITHDRAWALS_ENABLED` | `false` |
| `FEATURE_EXTERNAL_CRB_ENABLED` | `false` |
| `MOBILE_PAYMENT_ACTIONS_ENABLED` | `false` |
| `SIMULATED_METER_ENABLED` | `false`; the simulator remains development-only |
| `MTN_USE_SIMULATED_PAYMENTS` | Explicit `false`; different legacy parser: case-insensitive `false/0/no`, **without** whitespace stripping. Missing values normally auto-select simulation if keys are absent; Render explicitly prevents that fallback. |

`AMI_GATEWAY=utils.ami_gateway.MockAMIGateway` and
`CRB_PROVIDER=loan.crb.NoOpCreditBureauProvider` are required defaults for this
testing profile. They are dotted Python paths, not booleans. Re-enabling deferred
features requires their known correctness issues to be resolved and a separately
reviewed deployment profile; this one must not be used for real payments.

Do **not** provision `MTN_SUBSCRIPTION_KEY`, `PRIMARY_KEY`, `SECONDARY_KEY`,
`MTN_API_USER_ID`, `MTN_API_KEY`, `THINGSBOARD_TENANT_PASSWORD` or
`THINGSBOARD_WEBHOOK_SECRET`: startup rejects nonempty values. Existing MTN
aliases `MTN_CALLBACK_HOST`/`CALLBACK_HOST`, `MTN_ENVIRONMENT`/`ENVIRONMENT`, and
`MTN_BASE_URL` are not needed here. Production settlement still requires trusted
production configuration and verified provider evidence; no credentials or
payment simulations are enabled by this preparation.

Other inherited settings are **not required for this testing deployment**:

| Name(s) | Existing parsing / preserved behavior |
| --- | --- |
| `MAX_MONTHLY_INTEREST_RATE_PCT`, `MAX_CUMULATIVE_CHARGES_MULTIPLIER` | Decimal string parsing, current code defaults `2.8` and `1.0`. Not approved new policy; no rate or financial calculation changes here. Review configured policy before any financial testing beyond mocks. |
| `REDIS_HOST`, `REDIS_PORT` | String / integer, local defaults `127.0.0.1` / `6379`; supplying the full Redis URLs avoids using the constructed local URL. |
| `DEFAULT_HTTP_PROTOCOL`, `DOMAIN_NAME` | Base strings, overridden in this profile by HTTPS and the configured frontend hostname for legacy link helpers. |
| `THINGSBOARD_BASE_URL`, `THINGSBOARD_INTERNAL_BASE_URL` | Overridden to a deliberately unreachable `.invalid` host / empty internal URL. |
| `THINGSBOARD_TIMEOUT_SECONDS`, `THINGSBOARD_USAGE_TELEMETRY_KEY`, `THINGSBOARD_TENANT_USERNAME` | Integer / strings, inherited; no credentials or scheduled physical integration. |
| `THINGSBOARD_VERIFY_SSL` | Existing true tokens `1/true/yes/on` after trimming; other values become false. Unchanged and not needed for the disabled integration. |
| `AMI_LOW_UNITS_THRESHOLD_KWH`, `AMI_LOW_UNITS_POLL_SECONDS`, `AMI_LOW_UNITS_ALERT_COOLDOWN_HOURS` | Existing float / integers, unchanged alert thresholds; physical polling is not scheduled. |
| `USSD_SESSION_TIMEOUT_SECONDS` | Integer, irrelevant while USSD is disabled. |

`DATABASE_URL`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `EMAIL_BACKEND`, and
`CELERY_BEAT_SCHEDULE` are **not environment variables parsed by this project**.
Setting them in Render's dashboard does not configure those Django settings.
Use the names above. There is no automatic database URL parser.

## Verified code paths and boundaries

- **Gunicorn**: WSGI `backend.wsgi:application`; deployment-only requirements
  add Gunicorn 26.2.0 and WhiteNoise 6.12.0 without upgrading existing application
  pins. Use Render's port and a single worker initially. Access log format logs
  method/path/status/duration, not query strings, tokens, headers or bodies.
- **Static files**: `collectstatic` plus compressed manifest storage. WhiteNoise
  follows SecurityMiddleware; CORS precedes CommonMiddleware so error responses
  remain readable. Admin static assets work with `DEBUG=False`. User uploads are
  **not** served by WhiteNoise; Render's ephemeral filesystem is not durable
  media storage. Persistent/private media storage needs a separate decision.
- **PostgreSQL**: existing psycopg driver, `ATOMIC_REQUESTS=True`, connection age
  60 seconds, 10-second connection timeout and `custom,public` search path are
  preserved. No schema creation/conversion is automatic. On a fresh DB without
  `custom`, PostgreSQL normally resolves to `public`; confirm privileges and
  migration plan. Hosted reachability/TLS cannot be verified without the actual
  testing service credentials; no hosted DB was contacted.
- **HTTPS**: Render terminates TLS. Django trusts `X-Forwarded-Proto: https`,
  redirects plain HTTP and uses secure session/CSRF/auth cookies. Gunicorn trusts
  forwarded headers only in this intended Render-edge deployment. Do not reuse
  this public listener configuration behind an untrusted proxy/direct ingress.
  HSTS remains zero for disposable testing domains, so `check --deploy` reports
  its intentional HSTS warning; no checks are suppressed.
- **Android CORS**: inspected actual APK `assets/capacitor.config.json` has
  `androidScheme: http` and default `hostname: localhost`, hence
  **`http://localhost`**. Its remote API URL is independent of this origin.
  API CORS grants only the configured web/mobile origins; methods
  `GET, POST, PATCH, OPTIONS`; headers `authorization, content-type`.
  CORS is not authentication; JWT/role checks and session CSRF remain intact.
- **Health**: `/` serves a constant response without an atomic transaction. It
  checks process availability, not database/Redis health. Do not add authenticated
  user queries or secret values to the public health response.
- **Celery**: task decorators use `backend:celery_app`. The alternate
  `backend.celery:app` names an uninstalled `django_celery_beat` scheduler; it is
  not the worker entry point here. No new scheduler package/migrations needed.
  Registration email is asynchronous; password reset currently sends email
  synchronously from the web process. Thus **both web and worker need SMTP
  access**. Existing synchronous dispatch fallback does not replace a durable
  queue. Redis is not currently configured as Django's general cache.
- **Beat**: not required for auth/read-only testing. Base schedule includes real
  payment reconciliation and physical AMI polling. A later funded deployment
  requires a reviewed browser-independent payment reconciliation service and
  gated device jobs before scheduling anything. Do not drop pending obligations
  by swapping an existing operational service to this empty testing schedule.

## Operator actions and remaining limitations

- Rotate the SMTP credential previously embedded in **both** base and legacy
  email-settings source. Removing its fallback does not rotate it or remove it
  from Git history. No credential value is reproduced here. Use Render secrets
  and keep local `.env` ignored.
- Choose an SMTP-capable web plan. Render **free web services block outbound
  SMTP ports 25/465/587**; registration/reset email cannot be declared functional
  there with this backend. Free PostgreSQL also expires and has no backup; free
  Key Value is not a durable broker. An HTTP mail API would require separately
  implemented and tested email delivery, not a dashboard variable alone.
- Supply the actual backend hostname, web origin/verification frontend URL,
  testing database/Key Value fields, service plan and SMTP configuration.
- Verify existing Django 5.2 dependency patch/security support before exposing
  the service broadly; this preparation preserves its application pin rather
  than upgrading unrelated dependencies.
- Known overdue-after-completion financial expected failure remains. No change
  to tariffs, debt, rounding, allocations, payment settlement or device protocol.
- No operational records inspected; no migration applied; no live payment
  provider, physical device or Render service contacted. Android's LAN URL and
  web font-download/build limitations are independent of this backend setup.

## Local validation results

Validation used synthetic environment values, in-memory email and blocked
unmocked provider/device HTTP requests. Deployment packages were installed in
`/tmp/gpawa-render-validation/vendor`, not into the application's virtualenv.
The local interpreter is Python 3.14; Python **3.12 dependency resolution** was
checked separately. Actual Render runtime/build and hosted TLS remain untested.

| Check | Result |
| --- | --- |
| Render configuration + existing feature-flag tests | 28 passed; HTTPS/proxy, host rejection, exact CORS preflight, readable login 400/account 401, disabled flags and credential guards |
| Full relevant backend suite | 122 tests, OK; **one known expected failure** for overdue-after-completion, unchanged |
| Static collection / WhiteNoise | Temporary `collectstatic` succeeded; hashed admin CSS HTTP 200 |
| Gunicorn | `--check-config` passed; isolated loopback WSGI health/static HTTP 200, invalid host 400; DB access blocked in this smoke process |
| PostgreSQL | New PostgreSQL 18 cluster, loopback port 55441; parent `gpawa_render_regressions` and Django-created/deleted `test_gpawa_render_regressions`. Render's SSL/options accepted by psycopg; `SELECT 1` passed; search path preserved. Real middleware with `ATOMIC_REQUESTS=True` returned login 400/account 401/features 200 with readable narrow CORS. This does not verify hosted TLS. |
| Celery registration | `backend:celery_app` registers verification task, eager false, built-in scheduler, empty testing beat schedule; no Redis/SMTP connection attempted |
| Requirements | `pip install --dry-run --ignore-installed --python-version 3.12 --only-binary=:all: -r backend/requirements-render.txt` resolved all pins without changing installed application packages |
| Deploy checks | `check --deploy`: only intentional `security.W004` HSTS-zero warning; shell syntax and `git diff --check` passed |

Exact local runner commands were:

```sh
backend/venv/bin/python /tmp/gpawa-render-validation/validate.py
backend/venv/bin/python /tmp/gpawa-render-validation/gunicorn_smoke.py
backend/venv/bin/python /tmp/gpawa-render-validation/postgres_smoke.py
backend/venv/bin/python /tmp/gpawa-render-validation/regressions.py
```

These temporary runners explicitly disable local dotenv and isolate data. The
full runner covers `accounts.tests_mobile_profile_meters`,
`accounts.tests_authentication`, `accounts.tests_mobile_api`,
`accounts.tests_mobile_cors`, `backend.tests_feature_flags`,
`transactions.tests_payment_settlement`, `meter.tests_allocation_delivery`,
`loan.tests_financial_correctness` and
`backend.tests_render_config.RenderEnvironmentTests`; email is in-memory,
password hashing is test-only MD5, and unmocked `requests` calls fail.
Its first run omitted `MOBILE_APP_ORIGIN=http://localhost` while intentionally
ignoring local `.env`, causing one CORS assertion to fail. Explicitly configuring
the actual APK origin fixed the test environment; no authentication/CORS test
was suppressed or loosened. The final combined result is the 122-test pass above.
Only isolated test databases received schema creation; **no operational or
hosted migration was run**. The disposable PostgreSQL process was stopped.

To run the committed DB-free deployment tests with a complete synthetic Render
environment and deployment dependencies installed:

```sh
cd backend
DJANGO_SETTINGS_MODULE=backend.render_settings python manage.py test \
  backend.tests_render_config backend.tests_feature_flags
```

## Official references

- [Render Django deployment](https://render.com/docs/deploy-django)
- [Render Python version selection](https://render.com/docs/python-version)
- [Python 3.12.15 release](https://www.python.org/downloads/release/python-31215/)
- [Render PostgreSQL connection strings](https://render.com/tutorials/postgres-on-render/connection-strings)
- [Render Celery deployment](https://render.com/docs/deploy-celery)
- [Render free-service limitations](https://render.com/docs/free)
- [WhiteNoise Django setup](https://whitenoise.readthedocs.io/en/stable/django.html)
- [Django trusted HTTPS proxy header](https://docs.djangoproject.com/en/5.2/ref/settings/#secure-proxy-ssl-header)
- [Gunicorn settings](https://gunicorn.org/reference/settings/)
