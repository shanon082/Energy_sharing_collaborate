# Consumer expansion: implemented scope and remaining gates

For the opt-in sandbox profile, immediate SELF_DECLARED meter enrollment now
supersedes this document's mandatory consumer staff-review journey. Use
[CONSUMER_SANDBOX.md](CONSUMER_SANDBOX.md) and Meter0029. Physical/core enrollment
continues to use the stricter workflow below; historical decisions are retained.

This change preserves the Next.js server application and uses the separate
React/TypeScript + Capacitor build. Capacitor differs from the methodology's
named Kotlin implementation. No financial policy is approved by this change.
Existing working-tree account-page CSRF and mobile authentication work is retained.

Deployment preparation now includes a narrow Django-hosted staff review page.
See [CONSUMER_EXPANSION_DEPLOYMENT.md](CONSUMER_EXPANSION_DEPLOYMENT.md) for the
exact upload allowlist, database/plan checks and ordered phone test. No deployment
or hosted migration has been executed. The two original expansion migrations
remain unchanged; missing staff review persistence requires additional
`meter.0027_meterenrollmentreview`.

## Traced authority and scope

| Flow | Existing authority | Result in this phase |
| --- | --- | --- |
| Registration and phone | `accounts.api.serializers.CreateUserSerializer`; web `createAccountSchema`; mobile `Access` | Three Ugandan formats canonicalize to `+256…`; both clients reuse the pure TS helper. Provider initiation validates the same formats. Format is not phone ownership. Historical phone rows/unique constraint unchanged. |
| Meter identity | `meter.models.Meter.user`, staff/operator provisioning and reassignment in `admin.views` | The old consumer `MeterRegisterView` granted ownership from input alone. It now records an owner-bound request, as does the new mobile endpoint. Existing staff provisioning is preserved; a request is not proof and cannot transfer an existing meter. |
| Score and eligibility | `loan.services.get_loan_eligibility` / `resolve_user_loan_access`, `loan.scoring`, `loan.trust_ladder` | Mobile reports this authoritative lending score, factors, calculation time, evidence update time, profile estimate and explicit starter-policy floor. Incomplete new profiles have no score/history. Refresh does not earn points. |
| Loans | `loan.api.views.LoanApplicationView`, `loan.services.disburse_loan`, `LoanApplication.intended_meter` | Current web application may auto-approve/disburse; no mobile reuse of that mutation. Mobile quote is provisional and submission fails closed before creating an application. |
| Paid purchase / own repayment | `transactions.api.payment_views`, `transactions.payment_settlement` / `PaymentIntent` | Existing guarded initiation/idempotency and trusted settlement remain. Recovery reads the saved request identity beyond paginated history; it cannot collect, settle or replay. Repayments never allocate energy. |
| Energy / delivery | `EnergyAllocation`, `MeterDelivery`, durable outbox and simulator contract | Available, reserved/unresolved, acknowledged application, stored payment and source allocation are separate. No historical UnitBalance conversion or token replay. |
| Monitoring | `meter.api.mobile_views`, `meter.simulator_service` | Owner-bound exact Wh, contact freshness and simulator relay feedback. Foreground polling serializes reads, backs off (15–120 seconds), pauses hidden/native background and resumes without replaying writes. Physical remaining credit is unavailable. |

The older `accounts.api.views.CreditScoreView` adds behavioral factors different
from the lending service. Legacy purchase/sharing/wallet event helpers also
contain per-event bonuses. Mobile does not call these paths or represent them
as its authority. Reconcile this discrepancy before approving a web scoring
policy change; historical scores and decisions are not rewritten.

## New contracts (paths relative to /api/v1)

- `GET meter/mobile-onboarding/`: authorized assigned meters, `needs_meter`,
  own pending declarations. `LINKED` is derived only from an active assignment;
  the request itself never updates `Meter.user`. Maximum 30 displayed requests.
  Rejection returns `REJECTED` and a consumer-safe explanation; a previously
  approved but no longer assigned meter returns `ASSIGNMENT_UNAVAILABLE`.
- `POST meter/mobile-meter-requests/` and legacy `POST meter/register/`:
  `{ "meter_no": "<printed-number>" }` → HTTP 202, `status=PENDING`, request ID.
  Same owner/number retries, including simultaneous connections, return one
  declaration. Foreign and unknown inventory receive the same response.
  Extra old client fields are ignored, never accepted as device configuration.
- `GET loans/mobile-eligibility/`: lending score/factors plus `calculated_at`,
  `evidence_updated_at`, `starter_policy_floor_applied`, dormant purchase
  contribution. No loan-status reconciliation or disbursement during this read.
- `POST loans/mobile-quote/`: owned active meter, whole-UGX principal, existing
  tenure validation and current tariff required. Nonbinding estimates only;
  terms acceptance/submission must not be implemented until the gates below.
- `POST loans/mobile-apply/`: HTTP 409 `LOAN_POLICY_APPROVAL_REQUIRED`, no
  application on any retry. On alwaysdata financial-write middleware returns
  HTTP 503 first. This containment is **not** a completed idempotent submission
  implementation; future acceptance must persist request identity and immutable
  accepted terms before exposing a Confirm application button.
- `GET transactions/mobile-payment-recovery/?purpose=PURCHASE&meter_no=…&client_request_id=…`
  or `purpose=LOAN_REPAYMENT&loan_id=…`: own binding only; stored receipt or null,
  `pending`, `provider_polled=false`. Purchase pending detection spans all own
  meters; repayment pending detection is per owned loan. No provider call.
- Receipts add `allocated_energy_kwh` and `delivery_confirmed_kwh`. Null means
  no recorded allocation; zero application means none acknowledged. Only a
  matching durable simulated application record qualifies; not an HTTP receipt.

Existing dashboard/consumption routes keep stable meter ID and owner checks.
Physical `meter_reported_remaining_wh` is null. Simulator remaining is applied
Wh minus the **accepted consumption delta ledger**, never purchases minus an
arbitrary counter. Initial nonzero baselines, resets or discontinuities withhold
remaining credit and flag reconciliation. Relay reports `OPEN`, `CLOSED` or
`UNKNOWN` from stored simulator feedback; requested state is never shown as
feedback. `MOBILE_METER_STALE_SECONDS=120` is a display freshness threshold,
not a reliability guarantee. Last measurement time is shown separately.

The existing physical interface is still proposed, not deployed firmware:
separate device authentication, immutable device/meter binding, versioned
command ID/exact amount, durable application deduplication and matching ACK,
event ID/boot ID/sequence/cumulative integer Wh and measured/received times.
See `ENERGY_ALLOCATION_SIMULATOR.md` for replay/reset/gap behavior. No LoRa,
LoRaWAN, ESP32 or ThingsBoard control is added; device secrets never enter APKs.

## Dormant purchase scoring proposal — approval required

**Proposal only**: award one point per UGX 50,000 of aggregated lifetime
qualifying billed purchase money, floor once on the total and cap at 10 points.
This makes splitting the same spend into multiple payments give no extra bonus.
The cap, basis, aggregation window and treatment of purchase frequency require
business approval; these example numbers are not configured defaults.

Qualifying identity: one real-provider (`MTN_PRODUCTION`), UGX, successful
settled `PaymentIntent`, with a nonempty provider transaction identity, positive
billed amount and source-linked allocation to the same owner and intended
meter. Excludes pending, failed, simulated, unsupported/no-allocation records,
loan/repayment/delivery records and marked reversals/uncertain sources. Residual
money earns no points. Counting uses intents, not duplicate audit representations.
`PurchaseScoreExclusion` is a protected, reviewed scoring-only marker for a
reversal or uncertain source. It does not refund, alter settlement or remove
energy. A trusted reversal feed/operator reconciliation procedure is still
needed; no automatic reversal processing is claimed.

Settings: explicit boolean `PURCHASE_HISTORY_SCORING_ENABLED=false`. Only after
approval: `PURCHASE_HISTORY_POLICY_ID`, integer `PURCHASE_HISTORY_SCORE_CAP`
(1–100) and positive Decimal `PURCHASE_HISTORY_UGX_PER_POINT`. There are no
numeric defaults. Render and alwaysdata testing profiles reject enabling this
contribution. Existing base score/weights/trust policy remain unchanged while
it is disabled; enabling would affect future eligibility, not stored decisions.

## Hosting and business blockers

Alwaysdata permits authentication/account pages, owner-bound reads, pending
meter declarations and side-effect-free quotes. Quotes may return policy/
eligibility errors if the test database lacks a current tariff/profile. GET
loan reconciliation is suppressed on this profile; shared disbursement also
rejects before allocation. Financial writes, delivery and legacy provider/device
GET probes remain blocked. No worker is fabricated: payment reconciliation and
delivery are unavailable here. `features.consumer_capabilities` distinguishes
metadata/quotes/reads from physical hardware and simulator environment;
`background_processing_configured` does not prove a running worker.

Seven deferred features remain off. `MOBILE_PAYMENT_ACTIONS_ENABLED=false`.
The email outbox still needs the documented scheduled `drain_account_emails`
job; verification/password-reset pages remain Django-hosted HTTPS with CSRF.

Before enabling submission or live financial operations, approve:

| Decision | Why it blocks submission/live use |
| --- | --- |
| Whole UGX vs fractional final debt, half-even rounding and excess | Cannot silently choose a write-off, collection amount or refund. Full receipts/applied/excess remain recorded. |
| Closing overdue charges after full repayment | Existing expected failure is retained; completed loans can accrue again without immutable closure accounting. |
| No-tariff UGX 500/kWh loan fallback vs other tariff paths | Current fallback is preserved for history; not approved for new mobile offers. |
| Immutable accepted tariff/rate/fees/term/calculation policy and quote validity | Current configuration must not change accepted obligations. Provisional quotes are not contract snapshots. |
| Purchase residual after 10 Wh flooring | Original provider amount is requested; residual is accounted for, not silently converted/refunded. |
| Purchase-score formula/cap/window and reversal handling | Contribution stays disabled until approved. |
| Staff meter verification evidence and historical tenancy access | Narrow hosted review now records independent proof checks, decisions and an atomic audit. Missing inventory, foreign ownership or historically used unowned meters remain blocked; evidence must be verified operationally, never inferred from a number. General provisioning POSTs remain blocked. |
| Provider configuration, reconciliation workers and reviewed firmware | Alwaysdata Free cannot supply the persistent processing needed for real settlement/delivery. |

## Additive migration and reviewed deployment plan

Original expansion migrations: `meter.0026_meterenrollmentrequest` and
`loan.0022_purchasescoreexclusion` (depends on existing transactions.0010).
Deployment preparation adds `meter.0027_meterenrollmentreview` for the audited
staff workflow; it does not modify either original migration.
They add pending declarations and scoring exclusion records, with protected
references/uniqueness; no existing balances, phones, scores or obligations are
converted. Do not roll back by dropping these tables once populated. Disable
entry points/UI if rollback is needed; retain records.

No host changes or hosted migrations were run. The remote directory contains
**contents** of local `backend/`. From the repository root, review then upload
using the exclusion list in `ALWAYSDATA_TESTING.md` (never copy local .env).
After confirming the named testing database and reviewing its pending plan:

```bash
ssh shanonsimon@ssh-shanonsimon.alwaysdata.net
cd /home/shanonsimon/energy-sharing
export DJANGO_SETTINGS_MODULE=backend.alwaysdata_settings
export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
/home/shanonsimon/energy-venv/bin/python manage.py check_alwaysdata_database
/home/shanonsimon/energy-venv/bin/python manage.py audit_phone_formats
/home/shanonsimon/energy-venv/bin/python manage.py showmigrations meter loan transactions token_blacklist
/home/shanonsimon/energy-venv/bin/python manage.py migrate --plan
# Only after backup/target/plan review on the confirmed test database:
/home/shanonsimon/energy-venv/bin/python manage.py migrate --noinput
/home/shanonsimon/energy-venv/bin/python manage.py collectstatic --noinput
/home/shanonsimon/energy-venv/bin/python manage.py check --deploy
```

Audit prints identifiers/counts only; review alias collisions and invalid
historical formats without automatically rewriting them. Private environment
remains mode 0600 in a mode 0700 directory. Add the disabled scoring setting
and optional freshness setting privately; never set numeric proposed scoring
values as if approved. Restart the Web → Sites WSGI site after deployment.
Then check HTTPS features, empty login POST (400), restrictive localhost CORS,
verification POST/CSRF and owner-bound onboarding. Retain the scheduled email
job and all financial/device restrictions. See the runbook for exact commands.

## Testing and smallest next sequence

1. Deploy reviewed additive schema/code to the **confirmed test database**;
   test verification/reset and pending meter requests with synthetic accounts.
2. Authorized staff reviews independent evidence on the Django-hosted page and assigns clean, pre-provisioned synthetic inventory;
   test single/multiple meter selection, account isolation and stale monitoring.
3. Approve accounting/score/ownership policies and design immutable accepted
   terms; implement idempotent pending loan applications without auto-approval.
4. Test transaction screens against isolated mocked/sandbox provider evidence,
   including restart recovery and independent reconciliation. Do not enable on
   alwaysdata Free to make buttons work.
5. Hardware review and suitable workers/hosting precede physical integration.

Local test evidence and APK metadata are recorded in `mobile/CONSUMER_EXPANSION.md`.
No actual phone runtime, live payment, physical accuracy or radio test is claimed.
