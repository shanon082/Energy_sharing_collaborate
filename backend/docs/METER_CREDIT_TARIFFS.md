# Meter credit and configured tariffs — testing deployment

**Deploy this backend, review/apply the two new migrations, and initialize existing
test meters before testing the new APK against alwaysdata.** Nothing in this
change was uploaded or executed on the host. Authentication, Django account-page
CSRF, scheduled account mail, seven disabled optional features, physical-device
restrictions and dormant MTN integration remain unchanged.

## Assessment and eligibility authority

`loan.sandbox_models.DemoCreditAssessment` now distinguishes `METER` records from
`ACCOUNT_LEGACY`. Migration 0026 labels every existing assessment legacy while
preserving its score, factors, inputs, timestamps and meter reference. It replaces
the owner-only uniqueness constraint with partial owner/environment/meter
uniqueness and one unbound pending signup record. Migration 0027 changes only the
default scoring-version identifier for future rows. Existing core scores,
assessments embedded in loans, decisions and obligations are not rewritten.
These new meter-bound rules apply to consumer prototype activity. Legacy CORE
lending remains blocked by the testing profile; its old account-wide scoring
and threshold/trust-floor helpers are not a supported alternative route. Before
enabling CORE lending, adopt the meter-evidence/80% policy there under a separate
review while honoring already approved obligations.

Registration still initializes pending evidence synchronously, without Celery.
Immediate verified-owner enrollment completes evidence for that specific meter
through `loan.demo_assessment.complete_demo_assessment`, the existing
`loan.scoring` calculator and explicitly simulated `loan.account_data` provider.
Each meter receives its own stored inputs/binding/version/time. The fixed
APPROVAL_V1 categories give 85%; REJECTION_V1 gives 41%. Equal synthetic factors
can legitimately give equal scores on different meters. Scores are not copied
from a user's previous assessment or varied using names, addresses, phone
prefixes, hashes or randomness. No external records were retrieved.

`sandbox/assessment/?meter_id=<owned-id>` and the mobile/legacy eligibility reads
are owner-bound. Omitting meter_id returns pending/unavailable score context;
it never selects the first meter. Legacy account assessments remain historical.
Only active authorized sandbox inventory may acquire new demo evidence; core
physical inventory is not relabelled or enrolled into demo accounting.

New quotes require a stored score **at least 80%**, current eligibility and an
amount within the current limit. Submission rechecks current assessment, debt,
ownership and limits. A changed assessment/policy requires a new quote. A
previously quoted application can still be rejected for debt that appeared
after quoting. There is no starter-loan exception, including the dormant EUR
test service. Account-wide active UGX demo debt still blocks borrowing on another
meter; changing meters cannot evade the one-active-loan constraint.

Purchase points use unique settled LOCAL_DEMO purchase sources, matching both
the intended meter and allocation meter. Only that meter's current assessment
changes; pending/failed payments, loans, delivery and screen refreshes earn no
points. The existing bonus rule uses **billed total**, including configured
charges/tax, excluding residuals and scoring exclusions. Legacy aggregate
assessment values are retained, not redistributed.

## Tariff authority and exact accounting

- Models: `loan.models.ElectricityTariff`, `TariffBlock`. Existing configuration
  APIs are `admin.views.TariffsView`, `TariffDetailView`, `TariffActivateView`;
  activation helpers are in `loan.tariff_utils`.
- Calculation: existing `utils.billing.calculate_units_from_payment` and
  `calculate_bill_for_units`. New `loan.demo_tariffs` supplies strict frozen
  inputs to that engine; it contains no second pricing formula.
- Applicability: the current pilot has one globally active DOMESTIC schedule,
  with no meter-to-tariff-class field. The user confirmed reuse of its **owner-level
  monthly bands and service charge**, within a separate UGX_DEMO ledger. Physical
  utility/customer-class applicability remains future integration work.
- Effective_from/effective_to are inclusive. A legacy schedule with no
  effective_from uses its existing effective_date. Exactly one effective active
  schedule and complete, ordered, positive-rate bands are required. Future,
  expired, missing, ambiguous or incomplete configuration returns
  `TARIFF_UNAVAILABLE`. No fixed-price or non-lifeline fallback is permitted.
- Monthly progress sums unique settled LOCAL_DEMO purchase allocations in that
  calendar month by allocation creation date, matching the existing engine's
  posting rule. EUR/CORE, loan allocations, consumption, delivery and wallet
  mirrors are excluded. Monthly service is due only before the first paid demo
  purchase, across all the owner's meters. Loans do not advance this position.
- Lifeline input is the existing `Profile.lifeline_eligible` pilot flag, not
  measured or externally verified eligibility. Service charge and energy bands
  come from the tariff models. VAT is the existing engine constant **18%**, not
  an admin-configurable tariff field. No new tax or fee was invented.
- Payments/principal remain whole UGX; engine charges use Decimal and existing
  half-even rounding to 0.01 UGX. Energy is floored once to **0.01 kWh = 10 Wh**.
  Billed total + exact residual = full payment. The residual is retained, never
  discarded, refunded or implicitly converted to more energy. Existing loan
  interest/fee/term rules remain in accepted policy snapshots.
- The adapter passes `apply_deductions=False`: a demo purchase never repays CORE
  debt or a demo loan implicitly. Self-repayment remains a separate purpose and
  creates no energy. Cloud allocations never claim physical meter application.

New quote terms store tariff IDs/code/effective dates/blocks, engine version,
month, prior paid units, lifeline input/source, VAT, rounding, complete breakdown,
input fingerprint, owner/meter, policy and assessment. The quote hash covers all
of those terms. Tariff, policy, month, band position or lifeline changes **before
initiation/submission** reject the quote; the client clears stale consent on
refresh/meter/amount/evidence changes. Quote expiry still applies.

Once a payment is durably pending, settlement reproduces its **frozen snapshot**,
even if the tariff, VAT, calendar month or current policy later changes. A
cross-month pending purchase retains its accepted pricing month and joins the
settlement/allocation month's purchase position under the existing posting rule.
Previously initiated v1 fixed-price payments use their original evidence path.
No uncertain payment is automatically cancelled/refunded or initiated again.
Future engine changes must retain compatible reproduction of funded snapshots.

## Upload and configure (commands for the operator; not executed here)

Use a short maintenance window: prevent new HTTP activity and temporarily pause
the finite demo-completion schedule while code/schema are inconsistent. Keep its
pending records and keep the account-email schedule configured. Back up the
testing database and current code privately before applying migrations.

From the local repository root, preview then upload the allowlist (no --delete):

```bash
rsync -avnc --files-from=backend/deploy/consumer-sandbox.files --exclude='.env*' --exclude='*.env' --exclude='venv*/' --exclude='.venv/' --exclude='__pycache__/' --exclude='*.pyc' --exclude='*.log' --exclude='logs/' --exclude='media*/' --exclude='staticfiles/' --exclude='*.sqlite3*' --exclude='*.db' --exclude='*.sql' --exclude='*.dump' --exclude='*.pem' --exclude='*.key' backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
rsync -avc --files-from=backend/deploy/consumer-sandbox.files --exclude='.env*' --exclude='*.env' --exclude='venv*/' --exclude='.venv/' --exclude='__pycache__/' --exclude='*.pyc' --exclude='*.log' --exclude='logs/' --exclude='media*/' --exclude='staticfiles/' --exclude='*.sqlite3*' --exclude='*.db' --exclude='*.sql' --exclude='*.dump' --exclude='*.pem' --exclude='*.key' backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
```

The allowlist includes every changed backend runtime module and both migrations;
it excludes the mobile bundle, signing keys, local environments, databases,
virtualenvs and generated artifacts. No dependency upgrade is required.

On the host:

```bash
ssh shanonsimon@ssh-shanonsimon.alwaysdata.net
cd /home/shanonsimon/energy-sharing
export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
export DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings
chmod 700 /home/shanonsimon/.config/energy-sharing
chmod 600 "$ALWAYSDATA_ENV_FILE"
nano "$ALWAYSDATA_ENV_FILE"
```

Privately update these non-secret settings; do not replace the environment file
with a local copy or print its contents:

```dotenv
PROTOTYPE_PAYMENT_PROVIDER=LOCAL_DEMO
DEMO_POLICY_VERSION=DEMO-UGX-v2
DEMO_SCORE_THRESHOLD=80
DEMO_ACCOUNT_PROFILE=APPROVAL_V1
```

Keep all seven FEATURE_* flags false, MOBILE_PAYMENT_ACTIONS_ENABLED=false,
PURCHASE_HISTORY_SCORING_ENABLED=false, MTN_USE_SIMULATED_PAYMENTS=false,
SIMULATED_METER_ENABLED=false and CELERY_TASK_ALWAYS_EAGER=false. Existing SMTP,
private credentials, DB_SSLMODE=require, trusted HTTPS/CSRF settings and the
APK's http://localhost CORS origin must remain intact. DEMO_RATE_PER_KWH is no
longer a price source. DEMO_STARTER_LIMIT is compatibility metadata only; it
cannot grant a loan without the threshold.

Check the exact testing target and review the entire migration plan:

```bash
/home/shanonsimon/energy-venv/bin/python manage.py check_alwaysdata_database
/home/shanonsimon/energy-venv/bin/python manage.py showmigrations loan
/home/shanonsimon/energy-venv/bin/python manage.py migrate --plan
/home/shanonsimon/energy-venv/bin/python manage.py sqlmigrate loan 0026
/home/shanonsimon/energy-venv/bin/python manage.py sqlmigrate loan 0027
```

The target must be shanonsimon_energy_test / shanonsimon at
postgresql-shanonsimon.alwaysdata.net, with encrypted=True. Stop on any mismatch
or unexpected pending baseline migration. The two new migration names are:

1. `loan.0026_remove_democreditassessment_one_demo_assessment_per_owner_and_more`
2. `loan.0027_alter_democreditassessment_scoring_policy_version`

After backup/plan review, apply only the reviewed target and collect static:

```bash
/home/shanonsimon/energy-venv/bin/python manage.py migrate loan 0027 --noinput
/home/shanonsimon/energy-venv/bin/python manage.py collectstatic --noinput
/home/shanonsimon/energy-venv/bin/python manage.py check --deploy
```

Inspect tariff configuration without reading consumer records (no auto-seeding,
rate changes or general admin writes are enabled by this patch):

```bash
/home/shanonsimon/energy-venv/bin/python manage.py shell -c "from loan.models import ElectricityTariff; print(list(ElectricityTariff.objects.filter(is_active=True).values('id','tariff_code','tariff_type','effective_from','effective_to','service_charge')))"
```

Ensure an appropriate current, complete DOMESTIC schedule exists using authorized
operator configuration. Never treat the repository's old seed as confirmed
current utility pricing. If configuration is missing, the app must show Tariff
unavailable and stop new purchases/loan quotes.

Preview existing-meter initialization, review the IDs, then apply the same bounded
selection (substitute reviewed integer IDs if selecting a specific owner/meter):

```bash
/home/shanonsimon/energy-venv/bin/python manage.py initialize_demo_assessments --limit 50
/home/shanonsimon/energy-venv/bin/python manage.py initialize_demo_assessments --user-id <OWNER_ID> --meter-id <METER_ID>
/home/shanonsimon/energy-venv/bin/python manage.py initialize_demo_assessments --apply --user-id <OWNER_ID> --meter-id <METER_ID>
# Or apply the reviewed bounded batch; repeat preview to see remaining candidates:
/home/shanonsimon/energy-venv/bin/python manage.py initialize_demo_assessments --apply --limit 50
```

These operations create/complete missing METER evidence or retry unavailable
evidence for verified owners. They do not approve old ownership requests,
overwrite ready scenarios, alter CORE scores, replace legacy assessments or replay
energy. --refresh-purchases is an explicit current-meter contribution refresh.
For a deliberately controlled rejection fixture on a **MISSING** assessment,
preview/apply the same explicit owner/meter filters with --scenario REJECTION_V1.
Never delete or overwrite ready evidence to obtain a desired decision.

Keep the existing site at Python 3.12.15, virtualenv
`/home/shanonsimon/energy-venv`, WSGI
`/home/shanonsimon/energy-sharing/backend/alwaysdata_sandbox_wsgi.py`, private
ALWAYSDATA_ENV_FILE and static alias `/static/` →
`/home/shanonsimon/energy-sharing/staticfiles/`. Click **Restart** in Web → Sites
after the schema and initialization are ready; restore HTTP service. Do not
reverse populated migrations to roll back the interface.

Resume the existing finite simulator schedule (every minute; no Celery/Redis):

```bash
ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings /home/shanonsimon/energy-venv/bin/python /home/shanonsimon/energy-sharing/manage.py complete_demo_payments --run --limit 20 --max-seconds 50
```

Keep the old MTN reconciliation job paused. The trusted account-email outbox job
continues independently; no global eager mode is introduced.

## HTTPS and phone acceptance

```bash
curl --fail --silent --show-error https://shanonsimon.alwaysdata.net/api/v1/features/
curl --silent --show-error --output /dev/null --write-out '%{http_code}\n' https://shanonsimon.alwaysdata.net/api/v1/sandbox/assessment/
```

Expect the unchanged seven false flags, LOCAL_DEMO capabilities and 401 for an
unauthenticated assessment request. Authenticated reads must include an explicitly
selected owned meter and return its binding, percentage/eligibility and pricing
availability. Do not paste tokens/passwords into shared logs.

Only then install the new same-signature APK described in mobile/VALIDATION.md.
Check registration/verification/login, unique meter enrollment, two-meter score
selection and stable inputs; 79/80/85 backend boundary cases and a controlled
below-80 phone fixture; visible reasons for pending/debt/limit restrictions;
quote/consent clearing after meter/amount/evidence/tariff changes; configured
tariff breakdown and missing-tariff blocking; demo purchase and partial/full
repayment; receipts/reconnect recovery; keyboard/Back/logout. No header demo badge
is shown, but payment confirmation/receipts still disclose no real money and no
physical delivery. Live usage/balance remain unavailable without device evidence.

Local test results and APK verification are in mobile/VALIDATION.md. Hosted
deployment and new-APK phone testing remain operator work. The existing core
completed-loan/overdue expected failure, live payment approval and physical
firmware/ownership integration remain unresolved. Future scoring-policy changes
need a reviewed versioned reassessment path preserving prior evidence; this
deployment deliberately does not overwrite ready assessments.


## Local validation commands and results

Final standard suite: **257 tests, OK (skipped=19, expected failures=1)** in
230.733 seconds. The skips are hosting-only account-page/profile cases; the
separate HTTPS-aware alwaysdata suite passed **131 tests**, no failures, in
89.154 seconds. The expected failure remains the existing core completed-loan
subsequent-overdue calculation. No financial policy was changed to hide it.

From the local repository root:

```bash
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py loan.tests_meter_credit_tariffs loan.tests_demo_assessment transactions.tests_demo_payments loan.tests_sandbox meter.tests_sandbox_enrollment meter.tests_enrollment_review accounts.tests_account_pages accounts.tests_authentication accounts.tests_mobile_api accounts.tests_mobile_cors accounts.tests_mobile_profile_meters accounts.tests_mobile_activity backend.tests_feature_flags transactions.tests_payment_settlement meter.tests_allocation_delivery loan.tests_financial_correctness backend.tests_render_config.RenderEnvironmentTests
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --sandbox-profile backend.tests_alwaysdata.AlwaysdataProfileTests backend.tests_alwaysdata.AlwaysdataAuthenticationFlowTests accounts.tests_account_pages loan.tests_meter_credit_tariffs loan.tests_demo_assessment transactions.tests_demo_payments loan.tests_sandbox meter.tests_sandbox_enrollment backend.tests_feature_flags
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --check-migrations
```

The launcher verifies the local /tmp PostgreSQL18 cluster/role on port 55445 and
uses disposable test data. External HTTP is prohibited and email is mocked.
Migration drift check returned no changes. All old scores/inputs/timestamps and
version identifiers were checked across the actual 0025→0027 migration.

Mobile: **55 unit tests**, strict TypeScript, **15 financial + 9 authentication
mocked browser scenarios**, bundle/sync and signed debug APK build passed. Web:
standalone strict TypeScript, touched-code lint and **3 feature/navigation tests**
passed. Production Next.js compilation succeeded in both bounded attempts but
full builds timed out during Next's TypeScript stage (180 and 360 seconds,
exit 124). No type-check bypass was added; production-build completion is not
claimed. See mobile/VALIDATION.md for exact artifact identity and commands.

An exploratory hosting run incorrectly combined generic HTTP-only auth/CORS
fixtures with the HTTPS-only profile: 16 failures + 3 errors were 301 redirects
or attempts to read JSON/CORS headers from those redirects. These fixture and
HTTPS-enforcement files were unchanged against HEAD; their normal-profile tests
pass in the 257-test suite. Dedicated HTTPS-aware tests cover login, narrow CORS,
proxy/host handling and account CSRF with HTTPS enforcement retained. This
invocation mismatch was documented rather than hidden by disabling SSL checks.

Pre-existing wallet/meter mirror signals also log duplicate meter-balance
warnings for synthetic fixtures; they are not new failed assertions. No source
balance, operational record, hosted migration, live provider or hardware was
accessed by these tests. New-APK physical-phone and hosted rollout checks remain
outstanding.
