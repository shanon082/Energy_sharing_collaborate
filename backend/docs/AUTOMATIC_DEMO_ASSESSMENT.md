# Automatic demo credit assessment — simulated account information

This is prototype evidence, not real third-party verification, credit advice,
utility ownership confirmation or demonstrated prediction accuracy. All seven
optional flags remain false, especially FEATURE_EXTERNAL_CRB_ENABLED. No provider
network request, PIN collection, physical-device command or new Celery dependency.
The same deployment package and APK contain this change and the LOCAL_DEMO payments.

## Verified audit and reused authority

- Registration: accounts/api/views.py:CreateUserAPIView, accounts/api/serializers.py,
  accounts/signals.py create user/Profile/AccountDetails and the scheduled email
  outbox transactionally. loan/signals.py previously created CreditScoreFactors;
  registration and LoginAPIView also initialized UserCreditSignal.
- loan/scoring.py:calculate_weighted_credit_score/get_factor_breakdown is the
  existing three-factor calculation used by loan/services.py core eligibility.
  Payment, energy, financial major weights are 1:2:3, with existing category maps
  and granular subfactor weights. No independent formula was added. The old random
  dummy helper is superseded by the final deterministic alias in that file.
- loan/credit_score_service.py and legacy CreditScoreView behavior bonuses are
  separate historical core paths (including obsolete wallet/sharing bonuses),
  not the authority selected for this prototype. Core trust floors and core loan
  limits are not imported into demo lending.
- mobile/src/Profile.tsx actively rendered “Loan assessment profile”, fetching
  and PATCHing auth/mobile-profile/. loan/sandbox_service.py:assessment also used
  profile completeness/answers, recreating the questionnaire dependency. The
  mobile eligibility endpoint required profile answers. No utility/bank account
  provider abstraction existed; UserCreditSignal was storage, not an integration.
- Web dashboard questionnaire onboarding had already been removed; unused old
  popup/modal files remain preserved. Loans still rendered the core application
  form alongside sandbox; prototype now points to the shared automatic flow.
  The web score modal and legacy score GETs use stored demo evidence in LOCAL_DEMO.
  Core monetary statistics remain labelled CORE, without new core score creation.
  Questionnaire writes are rejected in LOCAL_DEMO only; ordinary account preferences
  and historical reads remain. Other hosting/core/EUR behavior remains available.

## Authority, provenance and events

DemoCreditAssessment is unique per owner + UGX_DEMO, PROTECT linked to owner and
assessment meter. It never updates UserCreditSignal/CreditScoreHistory or old loan
snapshots. Signup initializes PENDING with null scores idempotently under the owner
row lock, within registration's transaction. It needs no worker. No provider lookup
at signup. After verification, immediate owned active self-declared meter enrollment
completes it synchronously from the pure local provider; meter enrollment is not
utility verification. Missing/malformed provider data gives UNAVAILABLE and null
scores/limit; it does not reject a loan as genuine zero risk or invent an allowance.
An explicit owned-meter enrollment retry or reviewed operator command retries it.
A READY assessment is not redirected or rescored by additional meter enrollment.

loan/account_data.py defines AccountDataProvider separately from scoring and selects
SimulatedAccountDataProvider only. It accepts a named server fixture, not identity
or user-submitted financial answers. No names, email, phone prefixes, arbitrary
hashes, random selection or outside personal-information query determines risk.

Persisted evidence includes provider SIMULATED_ACCOUNT_V1, provenance
SIMULATED_ACCOUNT_INFORMATION, verified_external_records:false, fixture categories,
assessment timestamp, DEMO-SCORE-v1, copied existing weight/category/rounding tables,
base score, frozen demo purchase-contribution policy and source count/totals.
Existing calculation rounds integer subfactor means and the integer major weighted
mean using half-even. These scoring weights are reused; all monetary arithmetic
remains Decimal and the payment/energy rules remain in LOCAL_PAYMENT_DEMO.md.

| Controlled synthetic fixture | Payment | Energy | Financial | Base score | Default outcome for a 1,000-UGX request |
| --- | --- | --- | --- | --- | --- |
| APPROVAL_V1 (default) | GOOD / 92 | MODERATE / 71 | STRONG / 92 | 85 | Approve if current debt/limits permit; 37,500-UGX limit |
| REJECTION_V1 | POOR / 39 | ERRATIC / 41 | WEAK / 41 | 41 | Reject below threshold75; no allocation |

These are test assumptions, not inferred facts about consumers. Controlled tests
set DEMO_ACCOUNT_PROFILE before account creation. For a dedicated hosted rejection
tester, an operator can deliberately set REJECTION_V1 for new registrations in a
controlled testing window and restart, create that tester, then restore APPROVAL_V1
and restart. Existing stored scenarios do not change. Do not change an established
assessment to force a historical loan result. --scenario is available only for an
explicit older user with *no* demo assessment; it cannot overwrite existing rows.
Do not delete assessments to bypass this restriction.

Reassessment events: initial meter enrollment, explicit retry for pending/failed
provider, committed eligible purchase settlement and explicitly reviewed purchase
exclusion reconciliation. GET/login do not fetch data or award points. Settled
LOCAL_DEMO purchases with matching UGX/UGX_DEMO ledger/allocation and no exclusion
contribute once via stable one-to-one receipt identity: one point per frozen
10,000 billed UGX, capped10. Pending, failed, EUR/core purchases, loan allocation,
repayment and meter delivery contribute nothing. A receipt retry has no new effect.
assessed_at records initial base evidence; updated_at records changed purchase
contribution. Exclusions are reflected by explicit --refresh-purchases, not GET.
Policy version mismatch gives unavailable until an operator plans an explicit
versioned reassessment; GET does not reinterpret stored inputs. New policy changes
must have a new version and reviewed migration/reassessment process.

Loan quotes snapshot assessment and full policy. Submission reads stored evidence
again under owner locking using the current eligibility policy, checking current
debt, limit, meter ownership and terms. Accepted pricing stays frozen; an old quote
cannot supply a fallback score after an assessment-policy change;
client score/approved/history fields cannot influence the decision. Missing evidence
blocks submission; established below-threshold evidence produces a recorded rejection.
No questionnaire is a prerequisite for UGX demo loans. EUR test history and core
obligations remain in their original domains; UGX demo cannot repay them.

## Upload and additive migration — instructions, not executed

Use the exact rsync dry-run/upload, private-file editing, target checks, maintenance
window/backup and scheduled commands in [LOCAL_PAYMENT_DEMO.md](LOCAL_PAYMENT_DEMO.md).
The allowlist includes changed auth/score/enrollment services, provider/model,
initialization command and all four additive migrations. It excludes local secrets,
virtualenvs, databases, generated artifacts and signing keys; do not use --delete.
The shared existing loan/scoring.py is included so hosted category maps match.

Private backend.env additions (keep directory700/file600; never Git):

```dotenv
PROTOTYPE_PAYMENT_PROVIDER=LOCAL_DEMO
DEMO_ACCOUNT_PROFILE=APPROVAL_V1
DEMO_POLICY_VERSION=DEMO-UGX-v1
FEATURE_EXTERNAL_CRB_ENABLED=false
```

Keep all other seven false flags, account-page HTTPS/strict-origin CSRF configuration,
SMTP app password and scheduled drain_account_emails unchanged. No eager Celery.
WSGI/management commands use backend.alwaysdata_sandbox_settings and the same private
ALWAYSDATA_ENV_FILE. Before migrations, verify testing target:

```bash
cd /home/shanonsimon/energy-sharing
export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
export DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings
/home/shanonsimon/energy-venv/bin/python manage.py check_alwaysdata_database
/home/shanonsimon/energy-venv/bin/python manage.py showmigrations loan meter transactions accounts token_blacklist
/home/shanonsimon/energy-venv/bin/python manage.py migrate --plan
/home/shanonsimon/energy-venv/bin/python manage.py sqlmigrate loan 0025
```

Expected new schema: loan0024, meter0030, transactions0012 and loan0025. loan0025
creates only the isolated assessment table/constraints, with no automatic data
backfill. Stop on unexpected target/plan. After backup/review in maintenance:

```bash
/home/shanonsimon/energy-venv/bin/python manage.py migrate --noinput
/home/shanonsimon/energy-venv/bin/python manage.py collectstatic --noinput
/home/shanonsimon/energy-venv/bin/python manage.py check --deploy
```

Restart existing alwaysdata site using sandbox WSGI, retain the email schedule,
pause old MTN job, configure finite complete_demo_payments as in payment runbook.

## Preview-first existing-user repair

No real assessment, wallet, amount, historical decision, meter assignment or loan
is overwritten. The command defaults to preview and reports IDs/status only, limit
1–100; it never runs provider/network/queued jobs. Review every proposed user:

```bash
/home/shanonsimon/energy-venv/bin/python manage.py initialize_demo_assessments --limit 50
/home/shanonsimon/energy-venv/bin/python manage.py initialize_demo_assessments --user-id <REVIEWED_TEST_USER_ID>
# Only after review, for that user:
/home/shanonsimon/energy-venv/bin/python manage.py initialize_demo_assessments --apply --user-id <REVIEWED_TEST_USER_ID>
```

Only active nonstaff consumers are candidates. An unverified user stays pending.
For exactly one eligible owned test meter, completion can bind it; multiple meters
require explicit --meter-id after preview, rather than taking the first. With none,
retain pending until consumer adds/retries their unique meter. Existing READY rows
are unchanged. --scenario REJECTION_V1 requires explicit --user-id with no existing
demo record. --refresh-purchases is a separate preview/--apply review of test receipt
contributions/exclusions under frozen policy; it does not replay money or energy.

## Phone test sequence — outstanding, not performed

Register without assessment answers -> scheduled verification email -> HTTPS page
CSRF POST confirm -> sign in -> Add unique meter -> linked SELF_DECLARED notice ->
completed labelled demo score/categories -> loan quote -> automatic decision ->
repay partial/full or buy whole UGX using five-second demo -> receipt and cloud
allocation/debt -> restart/offline recovery -> logout. Test rejection with the
controlled rejection fixture. Without device evidence physical balance, consumption,
relay state and device contact remain unavailable. Keep old EUR history readable.
The APK must be updated alongside this backend package; no hosted/phone execution
is claimed by local tests/builds.


Updated APK verified locally: mobile/android/app/build/outputs/apk/debug/app-debug.apk,
4,466,333 bytes; SHA-256
a4ebc1c6283692906d6207bbe70cc7e612acac76cc7bdf96d86cad527483ebfe.
Existing debug certificate SHA-256
e9fb53040e78b6a525b67462cc5cc72a656de66ebe6c55061714e785eae86b4c;
org.gpawa.consumer.prototype v1.0/code1, minimum Android7/API24, target36.
Embedded API is https://shanonsimon.alwaysdata.net/api/v1; debug origin
http://localhost; release origin code remains https://localhost. APK assets match
final mobile/dist, contain demo payment/assessment labels and omit
"auth/mobile-profile/" and "Loan assessment profile". No device test was run.

From WSL, install on a USB-debugging device available to adb:

```bash
adb install -r /home/shanon/projects/next_projects/Energy-sharing-project/mobile/android/app/build/outputs/apk/debug/app-debug.apk
```

Or copy with Explorer from
\\wsl.localhost\<DISTRO>\home\shanon\projects\next_projects\Energy-sharing-project\mobile\android\app\build\outputs\apk\debug\app-debug.apk
and open on the phone. This is a testing APK, not a signed production release.


Final local verification: 259 combined backend tests passed with four existing
profile-specific skips and the known completed-core-loan overdue expected failure;
118 tests passed under actual alwaysdata sandbox settings. Commands are in
LOCAL_PAYMENT_DEMO.md. PostgreSQL concurrency tests exercise initialization,
enrollment, duplicate settlements and distinct repayments with mocks only.
Mobile strict type check + 42 tests passed; web strict type check, targeted modified
component lint and three feature/navigation tests passed. Vite debug build,
Capacitor sync, offline Gradle assembly and APK signature/assets verification passed.
Next.js production build again timed out after180 seconds during optimization;
no specific font or code error was reported in that run. No type/build checking
bypass was enabled, and the APK build is independent. Existing core financial
policy questions and the overdue-after-completion expected failure remain blockers
for live financial deployment. No hosted migrations/deployment or phone testing.
