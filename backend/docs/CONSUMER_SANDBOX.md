# Consumer sandbox: implementation and testing deployment

> Current deployment: use [METER_CREDIT_TARIFFS.md](METER_CREDIT_TARIFFS.md). The old EUR/starter/fixed-price tables below are historical v1 policy descriptions, not new-loan authorization rules. MTN remains paused.

**Current mode:** the prototype now defaults to `LOCAL_DEMO` with a distinct
UGX DEMO policy. Follow [LOCAL_PAYMENT_DEMO.md](LOCAL_PAYMENT_DEMO.md) for the
current deployment, scheduler and APK steps. The EUR/MTN material below is
retained for future resumption and historical interpretation; do not provision
MTN or run its reconciliation job while local demo mode is active.

This is an opt-in **SANDBOX TEST POLICY / NO REAL MONEY**, not approved lending
terms or a live deployment. The ordinary alwaysdata profile remains read-only.
Next.js and Android use the same Django services and the shared React form in
`frontend/src/components/sandbox-consumer.tsx`. Capacitor remains distinct from
the methodology's named Kotlin approach. No provider/device secret enters either client.

## Boundaries and authoritative records

The existing alwaysdata middleware, `MOBILE_PAYMENT_ACTIONS_ENABLED=false` and
production-UGX-only adapter blocked the requested test transactions. A separate
`backend.alwaysdata_sandbox_settings` profile now permits only the exact sandbox
POST paths below. Authentication, owner binding, email verification, CSRF pages,
scheduled account emails and all seven deferred features remain intact. General
admin financial writes, old provider polling, callbacks, physical commands and
hosted simulator delivery remain blocked. Existing Render/default settings retain
their behavior. Production/legacy MTN credential variables and noncanonical MTN
endpoints cause a startup error; the adapter always calls the literal HTTPS
sandbox endpoint with `X-Target-Environment: sandbox` and no redirects. Secrets
are opaque: code cannot prove which portal issued a key. Dedicated sandbox
provisioning and the fixed sandbox destination prevent routing to production.

MTN's [official test scenarios](https://momodeveloper.mtn.com/content/html_widgets/z0smm.html)
specify **EUR**, not UGX. There is no exchange rate. The old adapter's fixed EUR
1 conversion and simulation fallback are never used by this workflow.

| Record | Authority and isolation |
| --- | --- |
| `SandboxQuote` | Accepted terms/hash, owner, meter, price, policy and expiry; single application/purchase use |
| `SandboxLoan` | EUR principal, frozen total, assessment/decision, due date and closure; unique client ID and at most one active test loan per owner |
| `PaymentIntent` (`MTN_SANDBOX`, EUR) | Durable collection reference, source/purpose, private payer, submission and reconciliation state; existing global provider-transaction uniqueness |
| `SandboxSettlement` | Full EUR received = debt applied + excess + energy billed + purchase residual, exact to six decimals; one ledger per intent |
| `EnergyAllocation` (`accounting_environment=SANDBOX`) | Exact 0.01 kWh/10 Wh increments, unique paid-purchase or sandbox-loan source and intended meter |
| `SandboxMeterEnrollment` | SELF_DECLARED owner/time and optional explicitly retried pending request; never utility/staff evidence |
| Existing delivery/telemetry | Independent acknowledgement/consumption evidence. No new physical or simulated acknowledgement is fabricated |

Old UGX loans/repayments/wallets/`UnitBalance`, real score history and legacy logs
are not converted, replayed or written by sandbox settlement. Old receipt APIs
exclude EUR sandbox records to avoid a misleading `amount_ugx` representation.
CORE is the previous accounting domain, not a claim that all historical records
are verified real payments. New sandbox allocations do not affect core tariff
bands. Test-meter inventory defaults false on existing meters; no relabelling.
Core loan/purchase allocation refuses sandbox inventory, and hosted test delivery
cannot issue physical commands. Development-only simulator guards remain.

## Versioned test lending policy

Defaults are configurable exact decimals/integers with bounded validation in
`backend/sandbox_config.py`; change `SANDBOX_POLICY_VERSION` for policy changes.
Already accepted terms, debt and decisions remain frozen after configuration changes.

| Rule | SANDBOX-TEST-v1 |
| --- | --- |
| Currency / quote amount | EUR TEST, cents; EUR 1.00–20.00 |
| Incomplete profile | Starter limit EUR 2.00; score **null**, not fabricated creditworthiness |
| Complete profile threshold | 75/100; self-reported profile, not verified consumption/history |
| Complete profile limits | Score ≥90: EUR20; ≥85: EUR15; ≥80: EUR10; otherwise EUR5 (then threshold check); these scale with configured maximum |
| Interest / fees / term | One flat 5% principal charge, EUR0 fee, seven days from approved submission |
| Overdue charges | 0%; outstanding principal+frozen interest/fee less applied repayments. Full repayment closes permanently; no new accrual before or after closure |
| Existing debt | Any active sandbox loan or unclosed core obligation blocks new test borrowing; overdue decision reason explicit |
| Rounding | EUR loan interest half-even at cents once; payments positive cents; energy floored to 10 Wh once at accepted quote; billed/residual retained exactly to six decimal places |
| Excess / residual | Preserved for reconciliation, no automatic refund, write-off or energy creation |
| Quote validity | 15 minutes, immutable accepted hash, explicit acceptance required |
| Purchase bonus | floor(total eligible settled **billed** sandbox EUR / 10), cap10; added only to a complete profile score, overall cap100 |

Profile categories and subfactor rules reuse `loan/scoring.py`: payment history,
energy consumption and financial capacity have major weights 1:2:3. For each
category, calculate exact Decimal subfactor weighted sum and half-even round to
an integer; then the major weighted average/6, rounded half-even. Category maps,
weights, factors, input-source label, base score, purchase contribution, maximum,
decision and policy are saved in the assessment. No `UserCreditSignal` or real
score-history write occurs. Profile answers can still be self-reported test inputs;
this is not external CRB evidence or physical-meter validation.

Purchase contribution counts unique settled PaymentIntent/SandboxSettlement
sources, excludes review markers, never counts a loan/delivery/failed payment,
and aggregates billed value before rounding points. Splitting equal total billed
spend does not multiply points; flooring energy can reduce billed value, never
increase it. Refreshes and retries do not write score events.

Example starter loan: EUR2.00 → 2.00 test kWh, EUR0.10 interest, EUR2.10 debt.
Repay EUR1.01 then EUR1.09 → permanently completed. If two already-funded EUR2.10
repayments arrive concurrently, full EUR4.20 received is recorded, EUR2.10 applied
and EUR2.10 excess retained. A test price EUR1.23/kWh and payment EUR1.00 yields
0.81 kWh, billed EUR0.996300 and residual EUR0.003700. Provider requested amount
stays EUR1.00; there is no discarded remainder or invented conversion.

The pre-existing completed-core-loan overdue expected failure remains visible.
Fixing new sandbox loans does not silently recalculate historical UGX obligations.

## API and recovery

All consumer endpoints require an active verified CLIENT and no suspension/required
password change. New loans/purchases require an owned active sandbox meter. New
prototype enrollment explicitly **assumes the entered number belongs to the user**:
no utility customer database, staff approval, pre-created inventory or simulator
is required. Existing approved sandbox assignments remain compatible; they are
not relabelled SELF_DECLARED. Physical/core enrollment retains independent staff review.
Self-repayment of an already-approved owned test loan remains available if its
original test meter is later retired or reassigned: repayment changes only debt,
never that meter's entitlement. New borrowing/purchases still require current
authorized ownership. A funded purchase whose meter binding has become invalid
stays unresolved for review; it is not redirected, cancelled or automatically replayed.

| `/api/v1/sandbox/` path | Methods and effect |
| --- | --- |
| `assessment/` | GET score explanation, starter allowance and current policy, no score writes |
| `quotes/` | POST `{purpose: LOAN or PURCHASE, meter_id, amount: "2.00"}` → quote ID/hash/frozen terms/expiry |
| `loans/` | POST `{quote_id, terms_hash, accept_test_terms: true, client_request_id: UUID}` → stored actual automatic decision/allocation; GET owned history |
| `loan-recovery/<client_uuid>/` | GET owned stored decision, including beyond first 100 history entries |
| `payments/` | POST purchase `{purpose: PURCHASE, quote_id, terms_hash, accept_test_terms:true, msisdn, client_request_id}` or repayment `{purpose: LOAN_REPAYMENT, loan_id, amount, msisdn, accept_test_terms:true, client_request_id}`; GET history plus all pending |
| `payments/<provider_uuid>/` | GET stored receipt; POST trusted MTN status reconciliation, server lease/backoff applies, never accepts a success flag |
| `payment-recovery/<client_uuid>/` | GET stored owner-bound receipt; no automatic collection replay |
| `staff/decisions/` | GET authorized verified operator/admin visibility via JWT, no manual override |

### Immediate prototype meter enrollment

POST `/api/v1/meter/sandbox-meter-enrollment/` with `{"meter_no":" 00001234 "}`
returns HTTP201 (HTTP200 on same-owner retry), status SELF_DECLARED, a meter ID,
the unchanged number `00001234`, ownership_provenance SELF_DECLARED, enrolled_at
and hardware_connection PENDING. Android and the web sandbox page automatically
select this returned ID. Registry numbers remain case-sensitive strings, trimmed
at the ends, 1–100 characters, no control characters. Existing formats include
numeric and alphanumeric test IDs; there is no invented utility digit count.
No conversion to integer or removal of leading zeros occurs. The existing unique
database index on Meter.meter_no and transactions arbitrate concurrent claims;
same-owner calls serialize, distinct owners get one winner and generic HTTP409
METER_UNAVAILABLE. Existing physical/core, unowned pre-created, inactive/deleted,
renamed historical or foreign records cannot be claimed or reassigned. Known
string-keyed core balance collisions are also refused, without exposing an owner.

The legacy `meter/register/` and `meter/mobile-meter-requests/` aliases use this
service only in the opt-in sandbox profile. Other profiles keep reviewed requests.
`features/` reports consumer_capabilities.sandbox_self_enrollment and
sandbox.self_declared_meter_enrollment; `mobile-onboarding/` reports the actual
mode. Client parameters never enable it. A pending request grants no access:
the user explicitly retries its number; if clean/unclaimed, a new enrollment
records prior_request and transition time. The old request remains, without a
fabricated approval/audit. Prior rejection returns PRIOR_ENROLLMENT_REJECTED and
requires support review; there is no bulk approval or silent bypass. Converted
requests are excluded from the pending staff queue. Existing reviews remain immutable.

UI wording: “Meter linked for prototype testing. Ownership and live readings are
not verified with the electricity provider.” Physical balance, actual consumption,
relay state, last contact and application acknowledgements remain unavailable
without device evidence. Cloud test-energy allocation is separate and does not
assert that electricity was loaded onto hardware. No simulator is required for
loan/purchase/repayment testing. No financial-policy or currency change is made.

Browser staff can still use `/admin-panel/login/`, then
`/admin-panel/meter-link-requests/` for audited ownership review and
`/admin-panel/sandbox-decisions/` for read-only decisions/audit. Existing reviewer
roles/verification/CSRF and configured TOTP rules remain. This is an optional
legacy/future evidence-review workflow, not a new sandbox enrollment prerequisite. For old synthetic inventory,
independently check consumer identity and test assignment consent, select **Verified
synthetic inventory authorization**, record the private case reference and confirm
the checkbox. Household ownership evidence is not claimed. Test evidence cannot
authorize physical inventory; rejection never grants meter access.

Android stores only account-bound retry UUIDs in ordinary storage; refresh
credentials remain in Android Keystore-backed storage. It performs recovery GETs
after restarts and does not replay financial POSTs automatically. Pending outcomes
block another payment for that account. The backend persists intent and submission
claim **before** calling MTN, then uses the same provider UUID for status queries.
Only trusted successful terminal evidence with matching provider, reference,
external purpose identity, amount, currency, payer, accepted terms and unique
`financialTransactionId` can settle. Missing evidence remains pending/unresolved.

Network I/O happens outside row-lock transactions, including under ATOMIC_REQUESTS.
Lost collection response and worker restart lead to status queries, not reissue.
A 404 after an uncertain submission is retained for operator/MTN investigation,
never assumed failed, refunded or safe to retry with a fresh identity.

## Exact upload and private setup (not executed)

`backend/deploy/consumer-sandbox.files` is the complete incremental allowlist,
including the earlier consumer/authentication/CSRF/email baseline. Paths are
relative to backend, mapped directly to the existing remote backend directory.
Assumes older core migrations/runtime already present. Stop if migration files
referenced by the plan are missing; never fake migrations. No dependency upgrade.

From repository root, review the dry-run, then upload during a maintenance window:

```bash
rsync -avn --files-from=backend/deploy/consumer-sandbox.files --exclude='.env*' --exclude='venv*/' --exclude='__pycache__/' --exclude='*.pyc' --exclude='*.log' --exclude='logs/' --exclude='media*/' --exclude='staticfiles/' --exclude='*.sqlite3*' --exclude='*.db' --exclude='*.sql' --exclude='*.dump' --exclude='*.pem' --exclude='*.key' backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
rsync -av --files-from=backend/deploy/consumer-sandbox.files --exclude='.env*' --exclude='venv*/' --exclude='__pycache__/' --exclude='*.pyc' --exclude='*.log' --exclude='logs/' --exclude='media*/' --exclude='staticfiles/' --exclude='*.sqlite3*' --exclude='*.db' --exclude='*.sql' --exclude='*.dump' --exclude='*.pem' --exclude='*.key' backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
ssh shanonsimon@ssh-shanonsimon.alwaysdata.net
chmod 700 /home/shanonsimon/.config/energy-sharing
chmod 600 /home/shanonsimon/.config/energy-sharing/backend.env
nano /home/shanonsimon/.config/energy-sharing/backend.env
```

Use `alwaysdata-sandbox.env.example` as a placeholder-only guide, preserving the
working private SECRET_KEY/DB/SMTP entries; do not replace them with placeholders
or upload local `.env`. `FRONTEND_URL` remains optional. Both the WSGI profile and
management commands load the same absolute private file. Keep DB_SSLMODE=require
and every original financial/device/optional flag false. New sandbox policy
variables are exact decimals/integers, not float, and accept no request overrides.

MTN operator setup:
1. Sign up at the official MTN developer portal, subscribe to **Collections** for
   Sandbox; obtain its subscription key privately. Provision a **sandbox API user
   and API key**, not an existing production/partner GUI account, following
   [official getting started](https://momodeveloper.mtn.com/content/html_widgets/0wwlz.html).
2. Either use the official provisioning collection and privately enter the three
   dedicated MTN_SANDBOX variables, or run the narrowly scoped helper below.
   The helper prompts for the subscription key without echo, calls only the
   literal sandbox provisioning endpoints and atomically stores keys in the
   existing 0600 private file, without printing them. It refuses existing dedicated
   entries: remove placeholder lines privately first. It neither collects payments
   nor migrates the database. **Do not run with a production subscription.**

```bash
/home/shanonsimon/energy-venv/bin/python /home/shanonsimon/energy-sharing/deploy/provision-mtn-sandbox.py --env-file /home/shanonsimon/.config/energy-sharing/backend.env --provision
```

### Helper diagnostics and recovery

Upload only the helper from the repository root (no site restart needed):

```bash
scp backend/deploy/provision-mtn-sandbox.py shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/deploy/provision-mtn-sandbox.py
```

Failures report `stage=API-user creation` or `stage=API-key creation`, a category,
HTTP status (or `unavailable` for transport failures), and an exact allowlisted
provider code. Unknown codes, free-text messages, headers, credentials and raw
bodies are withheld. TLS errors, network timeouts and connection failures are
separate categories; HTTP redirects are not followed. A 201 key response with
missing/malformed key data is reported as an invalid success response.
The allowlist follows [MTN's official error codes](https://momodeveloper.mtn.com/content/html_widgets/1vu7v.html).
An unavailable code does not establish a cause; check the status and the active
Collections sandbox subscription in the [official profile](https://momodeveloper.mtn.com/profile).
Do not disable TLS verification or enable HTTP debug logging.

**Recover before retrying.** An unchanged private environment file says nothing
about remote creation. A lost API-user response can leave a remote user; a failed
API-key request or invalid 201 response can leave both a user and a key.
The helper does not automatically retry either POST. Before its first request it
creates a 0600 `.mtn-sandbox-provisioning.json` beside the private environment file,
containing the API-user reference and conservative remote state. Its presence
blocks another run. Inspect it only in a private editor; never paste its reference
or any keys into chat, shared logs, or command arguments.

1. For the **old generic failure**, no recovery record/reference was retained.
   Check the official subscription and ask MTN support to establish whether the
   failed attempt created a sandbox user/key. Do not blindly rerun the helper:
   a new UUID may create another user. Uploading this diagnostic patch makes no
   provisioning calls and cannot reconstruct the old attempt.
2. For a **new failure**, use the privately retained reference and the official
   [sandbox provisioning API](https://momodeveloper.mtn.com/API-collections)
   to inspect that user with authenticated `GET /v1_0/apiuser/{reference}`, or
   ask official MTN support to resolve its state. Use a private client with
   credentials entered securely and request/response logging disabled. Do not
   print headers or bodies. A transport failure or authorization rejection during
   inspection is still inconclusive; it does not prove that the user is absent.
3. If the user exists, recover that user rather than creating another. Resolve
   whether a key was issued; generating another key may rotate/invalidate the
   previous one. Follow MTN's documented process/support guidance before doing
   that. Store the recovered subscription/user/key privately in only the three
   dedicated `MTN_SANDBOX_*` entries, preserving all other environment entries.
   The helper refuses existing dedicated entries and has no automatic resume or
   remote-delete mode. Retain the record until recovery is complete.
4. Only after remote absence or provider-guided cleanup is established, archive
   the recovery record privately outside its blocking filename (keep mode 0600).
   If environment saving failed, privately inspect any `.backend.env.sandbox-*`
   temporary file: it may contain keys. Resolve those credentials before removing
   it. If valid dedicated entries were saved, do not provision again.
5. Once recovery is resolved and the active Collections sandbox subscription or
   network/TLS cause is corrected, an intentional fresh attempt uses:

```bash
ssh shanonsimon@ssh-shanonsimon.alwaysdata.net
/home/shanonsimon/energy-venv/bin/python /home/shanonsimon/energy-sharing/deploy/provision-mtn-sandbox.py --env-file /home/shanonsimon/.config/energy-sharing/backend.env --provision
```

Enter `SANDBOX` and the subscription key at the hidden prompt. Do not put the key
in the command, shell history or environment exports. Leave Django/WSGI, database,
SMTP and scheduled-job settings as they are; this helper-only repair needs no
migration, service restart, or profile switch.

No credentials were supplied or used here; actual provisioning/payment results
are not claimed. Missing keys truthfully disable purchase/repayment capabilities,
while loans remain enabled in the opt-in test profile.

## Database review, migration, profile switch

Four sandbox schema migrations (no data migration/replay/conversion):
`loan.0023_sandboxquote_sandboxloan`,
`meter.0028_remove_energyallocation_allocation_one_source_and_more`,
`transactions.0011_sandboxsettlement_and_more`,
`meter.0029_sandboxmeterenrollment` (new in this revision).
They add test records/nullable links/default-false inventory/reconciliation metadata
and expand existing source constraints. Meter0029 adds only the provenance table
with protected owner/meter/history references; it changes no existing meter or
decision. Its dependency is Meter0028. Their dependencies include the previously
prepared `loan.0022`, `meter.0026` and `meter.0027` consumer migrations. Existing
account outbox and JWT blacklist migrations must remain. Inspect the **whole plan**;
additive intent does not eliminate possible schema locks on populated tables.

On the host, before any migration:

```bash
cd /home/shanonsimon/energy-sharing
export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
export DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings
/home/shanonsimon/energy-venv/bin/python --version
/home/shanonsimon/energy-venv/bin/python -m pip check
/home/shanonsimon/energy-venv/bin/python manage.py check_alwaysdata_database
/home/shanonsimon/energy-venv/bin/python manage.py showmigrations loan meter transactions accounts token_blacklist
/home/shanonsimon/energy-venv/bin/python manage.py migrate --plan
/home/shanonsimon/energy-venv/bin/python manage.py sqlmigrate loan 0023
/home/shanonsimon/energy-venv/bin/python manage.py sqlmigrate meter 0028
/home/shanonsimon/energy-venv/bin/python manage.py sqlmigrate meter 0029
/home/shanonsimon/energy-venv/bin/python manage.py sqlmigrate transactions 0011
```

Require target host postgresql-shanonsimon.alwaysdata.net, database
shanonsimon_energy_test, user shanonsimon and encrypted=True. Review every pending
migration and take a **testing database** backup using alwaysdata. Stop on an
unexpected target, missing dependency or unreviewed older migration. Only after
that operator review/backup, run:

```bash
/home/shanonsimon/energy-venv/bin/python manage.py migrate --noinput
/home/shanonsimon/energy-venv/bin/python manage.py collectstatic --noinput
/home/shanonsimon/energy-venv/bin/python manage.py check --deploy
```

No create_sandbox_meter command or staff enrollment step is needed for new users.
The old inventory command remains for developer diagnostics, not for preparing a
number a consumer intends to self-enroll.

In Web → Sites, change **application path** to
`/home/shanonsimon/energy-sharing/backend/alwaysdata_sandbox_wsgi.py`, retain WSGI,
Python3.12.15, virtualenv `/home/shanonsimon/energy-venv`, working directory
`/home/shanonsimon/energy-sharing`, trusted hostname shanonsimon.alwaysdata.net,
HTTPS redirect and static handling. Site environment: ALWAYSDATA_ENV_FILE above
and DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings. Click **Restart**.
Changing only an environment variable is insufficient: old WSGI pins the ordinary
profile. Reverting the site to old WSGI stops new sandbox writes but **does not**
cancel pending receipts/loans. Keep sandbox reconciliation scheduled for already
submitted test requests; do not roll back populated tables or discard outcomes.

## Finite reconciliation without Celery/Redis

Alwaysdata [supports scheduled commands](https://help.alwaysdata.com/en/docs/web-hosting/tasks/),
including intervals and job logs. In Advanced → Scheduled tasks, add Command,
every minute, using the virtualenv's absolute executable (not `source activate`):

```bash
DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env /home/shanonsimon/energy-venv/bin/python /home/shanonsimon/energy-sharing/manage.py reconcile_sandbox_payments --run --limit 2 --max-seconds 50
```

First run it **without --run** for dry-run IDs, no provider call. Unix wall-clock
alarm enforces the command budget; HTTP connect/read timeouts are (3s,7s), database
connection5s, statement10s/lock5s. Durable 90s lease protects overlapping web/jobs,
backoff30s→3600s; dry-run is default. Deadline/process interruption preserves
SUBMITTING/pending state for subsequent status reconciliation. Jobs print only
intent IDs and non-sensitive statuses/effects/errors. No Celery eager mode.
With limits2 there may be a backlog; monitor oldest pending and job completion,
not just schedule creation. Actual Free-plan quota/network behavior requires
hosted verification; no concrete unsupported-service assumption is made.

**Keep the existing account-email scheduled command unchanged**:

```bash
DJANGO_SETTINGS_MODULE=backend.alwaysdata_settings ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env /home/shanonsimon/energy-venv/bin/python /home/shanonsimon/energy-sharing/manage.py drain_account_emails --send --limit 5
```

Scheduled reconciliation is new and must be configured: a capability saying
credentials are configured is not proof a scheduler ran. General core reconciliation,
email statements/Celery work and physical delivery remain unavailable on this profile.

## Hosted and phone acceptance (outstanding)

After operator deployment, perform credential-free HTTPS checks:

```bash
curl -i https://shanonsimon.alwaysdata.net/api/v1/features/
curl -i -X OPTIONS https://shanonsimon.alwaysdata.net/api/v1/auth/login/ -H 'Origin: http://localhost' -H 'Access-Control-Request-Method: POST' -H 'Access-Control-Request-Headers: content-type'
curl -i -X POST https://shanonsimon.alwaysdata.net/api/v1/auth/login/ -H 'Origin: http://localhost' -H 'Content-Type: application/json' --data '{}'
curl -i https://shanonsimon.alwaysdata.net/api/v1/sandbox/loans/
```

Expect feature seven=false, sandbox=true/EUR/physical_delivery=false,
purchase/repayment ready only with dedicated keys; preflight readable origin,
empty login400, unauthenticated loans401. Repeat with release origin
https://localhost; no wildcard CORS. Verification/reset links remain same-host
Django HTTPS pages, explicit CSRF POST with strict-origin, no hosted Next.js.

Ordered physical-phone test: update signed APK → register canonical Ugandan phone
→ scheduled verification email → Django confirmation → login → Add your meter
with an unclaimed string (test leading zeros) → immediate SELF_DECLARED link and
automatic selection → read starter/score explanation → review/accept quote → actual automatic
approval/rejection → exactly one test allocation, physical application unconfirmed
→ initiate EUR sandbox repayment → close/reopen app → scheduled trusted settlement
→ completed debt stays zero → buy test electricity → receipt/residual/allocation
→ exercise MTN failure/ongoing/delayed scenarios → Back/offline/expiry/logout.
Never paste credentials, account links, tokens or sensitive request bodies into logs.

MTN publishes test MSISDN scenarios: 46733123450 failed; ...451 rejected;
...452 expired; ...453 ongoing; ...454 delayed. Other test-only numbers (for
example 46733123499) are documented as success scenarios, but actual status/evidence
must still be verified. No real user number/PIN is required in the sandbox form.

Implementation/mock regressions, actual MTN sandbox, hosted deployment and physical
phone testing are separate evidence categories. See `SANDBOX_VALIDATION.md` for
actual local results/APK. Production financial policy, physical firmware/radio
validation, reconciliation of old ambiguous balances, operator credential rotation,
release signing and live payment readiness are outside this test policy.
