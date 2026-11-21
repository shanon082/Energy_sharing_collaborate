# Consumer capability parity and UGX workflow handoff — 21 November 2026

Local implementation and mocked tests only. No upload, hosted migration, payment
initiation, device operation or phone test was performed. This document supersedes
older capability/rollout descriptions, not the current device diagnostics.

## Verified mismatch and authoritative paths

The public HTTPS `features/` response read during this work advertised MTN_SANDBOX,
EUR/MTN_SANDBOX, purchases=true, repayments=true, loans=false, physical_delivery=false,
and SANDBOX/GPAWA_PZEM_V2 AC_LAB with physical_output=false. It contained **no lending
object**. The current checkout's FeatureAvailabilityView always returns that object,
even when disabled. Thus the running hosted code differs from this checkout; no
private hosted record was inspected. Existing credentials/binding must be retained.

Both clients use `sandboxCapabilities(features.sandbox)`, not `mobile_actions`, for
this workflow. That exact hosted response parses purchases/repayments as available.
The personal reason for a particular installed button cannot be established from a
public capability response alone. This build surfaces its actual prerequisite:

| Step / source | Exact blocker / result |
|---|---|
| Public contract / `backend/features.py`, shared `lib/sandbox.ts` | Invalid/missing enabled, provider/currency domain or physical_delivery=false fails closed. New loans use explicit UGX lending metadata; legacy EUR loans=false does not override it. Missing lending metadata now says to deploy the matching backend. |
| Selected meter / `sandbox-mobile-view.tsx` | Must select a sandbox_inventory meter; Django further requires active, owned and authorized self-declared/reviewed inventory. No first-meter reassignment. |
| Setup / `finance-setup.ts`, `sandbox-consumer.tsx` | Previously one failed assessment aborted the combined assessment/history/payment read and marked all actions unresolved. Loan setup and purchase terms now have independent settled results using the existing assessment endpoint; ledger/recovery failure still blocks new financial submissions. No synthetic price/score fallback. |
| Stored assessment / `meter-credit.ts`, `loan/demo_assessment.py` | Pending/missing/failed is not zero. Selected-meter score >=80%, eligibility, exact current limit and debt gates are all required. The backend rechecks at quote and application. |
| Quote / `sandbox_service.create_quote`, `apply_loan` | Policy min/max, admin tariff, amount precision, owner/meter, terms hash, expiry, fresh eligibility, explicit consent and durable request ID. Tariff/month/policy changes require fresh terms. |
| Purchase / `demo_config.require_new_mtn_payments`, `sandbox_payments.create_payment` | Pause, missing dedicated MTN configuration, absent EUR pricing, unavailable token service or unresolved prior request blocks initiation. Purchase availability is independent of loan assessment/legacy loan flag. |
| Repayment / `loan_record`, `sandbox_payments.create_payment` | Requires owned active debt matching payment currency/environment. In MTN mode EUR receipts cannot service UGX loans; the specific loan message remains visible. Partial same-currency repayment remains supported. |
| UI review/confirmation | Busy, refresh, offline, unreadable financial history/recovery, pending payment, unloaded terms, setup failure, pricing, invalid amount, score/eligibility, consent, expired quote and missing MTN test number have visible explanations. Review-button disablement uses the same reason function. |
| Payment recovery / shared controller | Both historical providers/environments remain readable/recoverable; request IDs survive navigation/restart. Status GET is read-only; reconciliation POST/schedule asks Django. HTTP202, HTTP200 or a countdown never indicates settlement. |

Next.js now refreshes capability reads on Refresh/focus, and disables new actions
while that read fails/is pending without unmounting the finance controller. Android
shows capability-fetch errors instead of silently clearing availability. The old
web wrapper no longer keys the controller by view. Domain/capability changes clear
stale quote consent, never durable retry handles. Missing assessments do not require
a questionnaire: registration/enrollment and idempotent owner initialization reuse
stored `DemoCreditAssessment` / the existing scoring service.

### UGX lending implemented independently

`SANDBOX_UGX_LOANS_ENABLED=true` in the alwaysdata sandbox advertises
`lending={enabled:true,currency:UGX,environment:UGX_DEMO,energy_environment:SANDBOX,
policy:DEMO-UGX-ACLAB-v1}` when token service prerequisites are ready. Repayment
availability is **not** a prerequisite for parsing that loan capability. Legacy
`sandbox.loans` remains false. Explicit `loan_contract=UGX-PROTOTYPE-SANDBOX-v1`
requests use the selected meter's stored simulated score and existing UGX rules:
whole UGX, >=80%, current debt/limits, configured DOMESTIC tariffs with owner-level
bands/service charge, frozen terms and fresh application checks. No rates changed.
Approved disbursement grants exactly one source-linked SANDBOX allocation/token;
repayments grant neither energy nor tokens. Old UGX_DEMO/EUR/CORE records retain
original domains. See `UGX_LENDING_AND_TOKEN_DIAGNOSTICS.md` for inherited policy
values and domain-source verification. This is prototype lending, not real lending.

## Unapproved policy decision: one test-authorization mapping

**Not implemented or enabled.** No setting currently makes UGX MTN payments work.
The existing adapter sends actual EUR amounts and validates reference, external ID,
amount, currency, payer, terminal SUCCESSFUL evidence and provider transaction ID.
`SandboxSettlement` enforces received=applied+excess+billed+residual in one currency;
it cannot store UGX debt application against a EUR receipt. Renaming EUR or setting
MTN_SANDBOX_CURRENCY=UGX would be incorrect. MTN's published sandbox answer says
EUR only; country currencies such as UGX belong to production:
https://momodevelopercommunity.mtn.com/momo-api-sand-box-q-a-6/currency-not-supported-invalid-currency-258

Proposed single versioned policy **UGX-MTN-TEST-AUTH-v1** (requires your decision):

* A whole-UGX purchase or own-loan repayment instruction freezes owner, meter/loan,
  purpose, amount, quote/hash and policy. It is noncash prototype accounting.
* Exactly one **EUR 1.00 TEST** MTN request authorizes exactly that instruction,
  independent of UGX amount. This is a fixed test challenge, **not an exchange rate**,
  not UGX money received and not usable in CORE or production. Disclose both amounts
  before consent and on receipts; do not claim a UGX Mobile Money charge occurred.
* Keep the existing EUR PaymentIntent/provider settlement as the authoritative EUR
  evidence, with its original provider/ref/external ID/currency/amount/transaction ID.
  Bind one uniquely constrained typed UGX test-authorization record to that source
  and instruction. Do not create an ordinary purchased-energy allocation from the
  EUR challenge as well as the UGX instruction. Adapt the existing settlement service
  atomically; do not introduce a second independent payment pipeline.
* PENDING/FAILED/unknown/mismatched evidence grants nothing. A retry recovers the
  same reference; neither another test challenge nor another financial effect.
* Purchase effect uses its frozen **UGX** admin-tariff terms; one SANDBOX allocation
  and one meter-bound token. Preserve UGX billed/residual in the instruction; the EUR
  challenge is not priced through the UGX tariff. Contributions, if policy permits,
  must use the one UGX business source exactly once, not also the EUR challenge.
* Repayment effect uses `min(UGX instruction, remaining UGX debt)` under owner/loan
  locks; record UGX excess separately. Preserve the complete EUR receipt. Full debt
  closes permanently; repayment issues **no allocation or keypad token**.

Example receipts under that proposed policy (illustrative values, not new tariffs):

```json
{"purpose":"PURCHASE","business":{"amount":"10000","currency":"UGX","environment":"UGX_DEMO","billed":"10000","residual":"0"},"provider":{"provider":"MTN_SANDBOX","amount":"1.00","currency":"EUR","status":"SUCCESSFUL","reference":"example-purchase-reference","transaction_id":"example-provider-purchase"},"authorization_policy":"UGX-MTN-TEST-AUTH-v1","energy":{"environment":"SANDBOX","amount_wh":10000,"source":"one-ugx-instruction","token_issued":true,"device_saved":false},"real_money":false}
{"purpose":"LOAN_REPAYMENT","business":{"amount":"4000","currency":"UGX","environment":"UGX_DEMO","applied":"4000","excess":"0","debt_before":"10500","debt_after":"6500"},"provider":{"provider":"MTN_SANDBOX","amount":"1.00","currency":"EUR","status":"SUCCESSFUL","reference":"example-repayment-reference","transaction_id":"example-provider-repayment"},"authorization_policy":"UGX-MTN-TEST-AUTH-v1","energy":null,"token_issued":false,"real_money":false}
```

Purchase example assumes a **test fixture** of UGX1000/kWh and no other charges,
not a tariff to install: actual Wh/billed/residual must come from the configured
billing engine. For UGX11000 repayment against UGX10500 debt, preserve applied10500,
excess500; no automatic refund, write-off or energy. In all examples the EUR1.00
remains EUR1.00; it never becomes UGX10000/4000/11000. Old EUR/LOCAL_DEMO pending
records retain their original settlement path and must not be retroactively mapped.

Smallest next implementation after approval: additive uniquely-bound instruction /
authorization model + frozen mapping policy; explicit purpose handling in the
existing settlement transaction, debt/summary/reconciliation readers, both-client
consent/receipts; cross-intent/concurrency/source tests; additive migration review.
No approved FX rate is needed, but this explicit noncash accounting exception must
be approved. Until then the **complete UGX purchase/repayment journey is unavailable**.
Eligible EUR testing remains honest EUR where explicitly enabled; UGX loans/tokens
can be exercised independently with the repayment limitation disclosed in terms.

## Coordinated deployment (operator only; not performed)

Use this checkout's `deploy/ugx-capability-parity.files`, including current diagnostic
code and all additive meter migrations through0033. Never overlay an older diagnostic
patch/release. All `.env` files/examples, private keys/headers, virtualenvs, DB/media,
static/build artifacts and APKs are excluded. The unchanged hosted base settings file
is retained; its legacy local-development credential fallback must not be exported.
No `--delete`. Source manifest checksums are provided in the local release package.

1. From repository root, inspect the allowlist, then **dry-run and read-only plan**:

   ```bash
   rsync -avnic --files-from=backend/deploy/ugx-capability-parity.files backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
   python3 backend/deploy/preview_combined_migrations.py
   ```

   Preview uses the local migration graph against read-only hosted schema metadata,
   checks exact testing database identity/TLS and blocks provider HTTP. Stop on
   unavailable SSH, schema divergence, wrong DB/TLS or unexpected migrations.

2. Before upload, privately back up database, current code, environment, device/key
   files. Exact guarded backup commands are in
   `UGX_LENDING_AND_TOKEN_DIAGNOSTICS.md` → Ordered alwaysdata rollout. No credentials
   or backup contents belong in chat/Git/the public release. Do not restore older
   balances automatically over newer payments.

3. After review/backup, upload current code only:

   ```bash
   rsync -avic --files-from=backend/deploy/ugx-capability-parity.files backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
   ```

4. On host, privately edit `/home/shanonsimon/.config/energy-sharing/backend.env`
   (parent0700/file0600). Keep existing secrets, MTN credentials, ENERGY_TOKEN keys,
   device binding, email settings and jobs. Required profile/non-secret settings:

   ```dotenv
   PROTOTYPE_PAYMENT_PROVIDER=MTN_SANDBOX
   MTN_SANDBOX_BASE_URL=https://sandbox.momodeveloper.mtn.com
   MTN_SANDBOX_CURRENCY=EUR
   SANDBOX_UGX_LOANS_ENABLED=true
   DB_SSLMODE=require
   MOBILE_PAYMENT_ACTIONS_ENABLED=false
   MTN_USE_SIMULATED_PAYMENTS=false
   SIMULATED_METER_ENABLED=false
   FEATURE_THIRD_PARTY_REPAYMENT_ENABLED=false
   FEATURE_USSD_ENABLED=false
   FEATURE_WALLET_DEPOSITS_ENABLED=false
   FEATURE_WALLET_WITHDRAWALS_ENABLED=false
   FEATURE_EXTERNAL_CRB_ENABLED=false
   ```

   Sharing and consumer transfers remain hard-retired (cannot be re-enabled by env).
   Explicit boolean parsing accepts true/false,1/0,yes/no,on/off; invalid values fail
   startup. `SANDBOX_NEW_PAYMENTS_ENABLED=false` remains the shipped pause default.
   Preserve the host's existing explicit value: **true permits new EUR TEST** purchases
   and matching EUR repayments only; false pauses them while preserving submitted
   recovery. Neither value enables UGX MTN payments. Do not change it to claim UGX
   support. Keep existing versioned EUR policy and UGX DEMO_* terms; admin-configured
   DOMESTIC tariff is required for UGX loans. No tariff/rate was installed in this work.
   Preserve separately opted-in existing AC_LAB identity. Physical relay output is
   hard-false; no new device provisioning, token/key reset or physical switching.

5. In hosted terminal, verify database and review actual pending plan **before migrate**:

   ```bash
   cd /home/shanonsimon/energy-sharing
   export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
   export DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings
   export PATH=/home/shanonsimon/energy-venv/bin:$PATH
   python manage.py check_alwaysdata_database
   python manage.py showmigrations meter loan transactions token_blacklist
   python manage.py migrate --plan
   ```

   Exact expected DB: postgresql-shanonsimon.alwaysdata.net / shanonsimon_energy_test /
   shanonsimon, actual encrypted TLS. No new schema migration in this change.
   Prerequisites include additive `meter.0032_prototypedevice_prototypecommand_prototypeboot_and_more`
   and `meter.0033_ac_lab_sandbox_environment`, plus earlier current graph. Review all
   unapplied prerequisites; never fake a migration or convert historical domains.

   Only after confirming target/backups/plan:

   ```bash
   python manage.py migrate --noinput
   python manage.py collectstatic --noinput
   python manage.py check --deploy
   python manage.py initialize_demo_assessments --user-id 3 --meter-id 3
   ```

   Last command is **preview only**. If it reports missing/pending evidence, inspect
   before adding --apply; do not overwrite an existing real/ready assessment.

6. Restart existing alwaysdata **Web → Sites → Restart**. Keep current Python3.12,
   `/home/shanonsimon/energy-venv`, sandbox WSGI/environment settings, CORS
   `http://localhost` for the current debug APK and HTTPS/CSRF account pages.
   Check HTTPS features without credentials:

   ```bash
   curl --fail --silent --show-error https://shanonsimon.alwaysdata.net/api/v1/features/ | python3 -m json.tool
   ```

   Expect capability_version GPAWA-CONSUMER-v2; legacy loans=false, explicit UGX
   lending.enabled consistent with settings/token readiness; exact action_reasons,
   ugx_payments.enabled=false in MTN mode, physical_output=false, seven flags false.
   Refresh both clients; use the same owner/selected meter. No payment is needed
   for capability/assessment/quote inspection. Do not share tokens or request bodies.

7. Preserve account-email schedule **unchanged**. Existing finite reconciliation job:

   ```bash
   ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings /home/shanonsimon/energy-venv/bin/python /home/shanonsimon/energy-sharing/manage.py reconcile_sandbox_payments --limit 2 --max-seconds 50
   ```

   Above is dry-run. Existing scheduled mutating job retains `--run` after operator
   review (e.g. each minute; no persistent worker required). Keep old
   `complete_demo_payments --run --limit 20 --max-seconds 50` only for old LOCAL_DEMO
   obligations, and `drain_account_emails --send --limit 5` as already scheduled.
   Never-submitted uncertain records remain for review; no automatic cancellation,
   resubmission, conversion or new provider fallback.

8. Web: build/deploy this same frontend source through the existing Next.js workflow;
   keep server features and the existing Django proxy URL/secure-cookie contract.
   No mobile environment/key belongs in the Next server bundle. Android installation
   and final build evidence are in `mobile/CAPABILITY_PARITY_BUILD.md`.

## Untested and preserved

The original hosted token rejection root cause is still unconfirmed. Current
`meter/diagnostics.py`, `meter/api/prototype_views.py`, `meter/prototype_device.py`,
`backend/hosting_middleware.py`, firmware/private headers and NVS remain unchanged.
Use their request-ID/fixed-code diagnostics for one authorized attempt; no second
purchase, replacement token, reprovision or erase is necessary. Credit saved on
device, token issued, purchase settled and physical output remain distinct.

See the mobile build report for exact local tests/build/signature evidence. Device,
phone, hosted rollout and actual MTN tests are separate outstanding work. The known
CORE overdue-after-completion expected failure is not a declaration of policy
correctness and remains visible; current sandbox closure has separate regressions.

## Final isolated backend commands and results

```bash
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --sandbox-profile --slow-test-cleanup loan.tests_ugx_lab loan.tests_mtn_transition loan.tests_sandbox loan.tests_demo_assessment transactions.tests_demo_payments meter.tests_mtn_device meter.tests_credit_only meter.tests_device_diagnostics backend.tests_combined_rollout backend.tests_feature_flags accounts.tests_account_pages
# 161 tests, 95.048s, OK. External HTTP blocked except explicit mocks.
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --slow-test-cleanup transactions.tests_payment_settlement meter.tests_allocation_delivery loan.tests_financial_correctness backend.tests_feature_flags accounts.tests_authentication
# 93 tests, 962.578s, OK (expected failures=1); known CORE overdue case retained.
```

Only local127.0.0.1:55445 / test_gpawa_* DBs with the isolated test role are used.
The slow-cleanup option extends test DB lifecycle/flush limits, not financial
request locks/timeouts or hosted settings. Core fixture logs retain caught legacy
wallet duplicate/missing-tariff messages; these were not new suite failures.
Same-currency UGX partial/full closure was tested with isolated LOCAL_DEMO evidence
only; no UGX MTN settlement exists or is claimed.
