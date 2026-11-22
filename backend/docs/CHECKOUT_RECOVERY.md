# Five-minute sandbox checkout recovery

Implemented locally, completed 22 November 2026. Not deployed. No hosted payments, account
changes, firmware flashes or physical commands were performed.

## Confirmed causes and evidence boundaries

The shared `sandbox-mobile-view.tsx` hid amount forms with `!p.pending`; the shared
controller also included every pending payment and recovery failure in one
account-wide `blocked` flag. `create_payment()` separately rejected any pending
LOCAL_DEMO/MTN_SANDBOX payment for the owner. A completed receipt could therefore
appear beside a different, older pending record which actually blocked the form.
There was no checkout deadline. Reconciliation correctly preserved uncertain MTN
outcomes, but the UI treated this as an indefinite account lock.

Finance refresh used one `Promise.all`: failure in loan/payment history or a
retry-handle lookup prevented unrelated reads from being displayed. Initial failed
reads left `fetched=null`, which the view interpreted as still loading. Browser,
mobile and summary reads also had no total response/body deadline. These paths now
finish with explicit errors, independently loaded assessment/pricing/history and
20-second request deadlines. A timed-out mutation retains its recovery identity;
it is never automatically resubmitted as a new charge. Background status polling has its own in-flight guard, so it cannot silently consume an unrelated form click.

An attempted read-only hosted report was denied by SSH authentication
(`Permission denied (publickey,password,keyboard-interactive)`). **The exact hosted
blocking reference is not confirmed.** Do not infer that the visible completed
receipt is the blocking record. Run the preview report below and compare its
reference/request ID with the owner's receipt and authenticated recovery endpoint.
No passwords, phone numbers, keypad tokens, provider bodies or credentials appear
in the report. Browser evidence uses clearly synthetic references and HTTPS API.

## Lifecycle and invariant

* Deadline is always `PaymentIntent.initiated_at + 300 seconds`. Idempotent request
  reuse, refresh, navigation and restart do not extend it. Client countdowns are
  presentation only; actions depend on fresh server checkout metadata.
* `SandboxCheckout` is metadata for the existing PaymentIntent pipeline, not a new
  accounting/payment system. Root/replacement links identify one frozen business
  operation. New migration `transactions.0014_sandboxcheckout` creates only this
  table and its constraints. No historical balances/instructions are rewritten.
* Pure status/history/recovery GETs compute timeout presentation without creating
  metadata, settling, cancelling or calling a provider. Explicit POST or the existing
  finite reconciliation command persists expiry, including when apps are closed.
* Expiry and provider submission serialize on the intent lock. Only MTN `NEW` with
  zero attempts, no current/stale submission lease and the server-persisted PRE_IO_CHECKOUT-v1 marker is provably never submitted. Legacy records without that proof stay uncertain, even if labelled NEW; they receive status lookup only, including while new payments are paused.
  Such initiation can be closed locally; all workers check closure before sending.
  Uncompleted LOCAL_DEMO has no provider request and can close locally too.
* ACCEPTED, SUBMITTING, OUTCOME_UNKNOWN or ambiguous NEW records keep their exact
  reference/provider/status. Timeout does **not** set FAILED/CANCELLED. An expired
  ambiguous NEW is status-only, never resubmitted. No provider cancellation API is
  invoked. Message: “Request timed out; payment confirmation is still being checked”.
* Explicit authenticated `POST sandbox/payments/<reference>/retry/` accepts only
  `client_request_id` and `accept_test_terms=true`. It requires an expired, unresolved
  approved UGX-MTN-TEST-AUTH-v1 instruction and the configured alwaysdata sandbox
  capability. It copies the original accepted pricing/amount/terms without
  recalculating or extending the original quote. Each new attempt has its own
  five-minute deadline, immutable instruction, EUR1 authorization and new reference.
  One replacement per attempt and durable request IDs prevent duplicate initiation.
* Existing settlement locks owner + operation root. The first validated successful
  authorization fulfills the operation once. Later successes retain their full
  actual EUR provider receipt as unallocated test evidence, with
  `ADDITIONAL_AUTHORIZATION_REVIEW`. They create no additional UGX effect,
  allocation, token or debt reduction. An unsubmitted replacement is closed locally
  if the operation is fulfilled before dispatch. In-flight/uncertain attempts are
  never assumed cancelled. Repayment still reduces owned matching UGX debt only;
  partial/full closure, excess conservation and no-repayment-energy rules remain.
* Existing EUR/LOCAL_DEMO records retain original provider, terms and recovery.
  Historical currency domains are not converted into new UGX instructions.
  Linked replacement is limited to the approved v1 contract, not legacy EUR or
  LOCAL_DEMO operations. An independently quoted new UGX purchase is a new operation,
  not a conversion/replacement of historical EUR debt or energy. Review uncertain
  legacy operations under their original provider; do not replay/reset old tokens.
* Only pending purchases for the same meter or repayments for the same loan
  conflict. Loan applications are not blocked by a purchase/payment-read failure;
  stored score >=80%, debt, limit, meter ownership, quote and consent still apply.
  Forms remain visible with exact reasons, including unavailable capabilities.

Receipt additions (example, not hosted data):

```json
{"checkout":{"expires_at":"2026-11-21T10:05:00Z","expired":true,"state":"EXPIRED","classification":"SUBMITTED","provider_cancelled":false,"operation_reference":"00000000-0000-4000-8000-000000000001","replaces_reference":null,"fulfilled_reference":null,"business_effect":"NONE","retry_available":true,"message":"Request timed out; payment confirmation is still being checked."},"status":"PENDING"}
```

## Exact operator rollout — not executed

Use the existing checkout, private environment and approved authorization profile.
Review [the previous coordinated runbook](UGX_MTN_TEST_AUTHORIZATION.md) for the
private pg_dump/source/credential backup commands. Do not upload .env, keys, local
database/static files, virtualenvs or firmware private headers. No new environment
variable, provider key, tariff, lending rate or credential rotation is required.

1. From local repository root, preview **before** upload/schema changes:

   ```bash
   rsync -avnic --files-from=backend/deploy/checkout-recovery.files backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
   python3 backend/deploy/preview_combined_migrations.py
   ```

   The latter uses existing SSH authentication and read-only TLS-verified hosted
   migration metadata, never DDL or provider HTTP. It includes local 0014. It may
   require the operator's interactive SSH authentication. No remote preview ran
   successfully here. Stop on unknown migrations/DB/TLS. Back up privately before
   applying changes. Pause financial schedules briefly during code/schema rollout;
   preserve queued rows and the account-email schedule.

2. Upload current source, with no `--delete`:

   ```bash
   rsync -avic --files-from=backend/deploy/checkout-recovery.files backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
   ```

   This curated overlay includes latest diagnostics, meter0032/0033, transactions
   0013 and new0014; it excludes the unchanged local base settings/secret fallback.
   Keep the existing safe hosted base settings and all private configuration.

3. Hosted terminal; verify exact testing DB and review plans before applying:

   ```bash
   cd /home/shanonsimon/energy-sharing
   export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
   export DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings
   export PATH=/home/shanonsimon/energy-venv/bin:$PATH
   python manage.py check_alwaysdata_database
   python manage.py showmigrations transactions meter loan token_blacklist
   python manage.py migrate --plan
   python manage.py sqlmigrate transactions 0014
   ```

   Require host `postgresql-shanonsimon.alwaysdata.net`, database
   `shanonsimon_energy_test`, user `shanonsimon`, `sslmode=require`, and actual
   encrypted connection. Only after reviewing backup/target/plan:

   ```bash
   python manage.py migrate --noinput
   python manage.py collectstatic --noinput
   python manage.py check --deploy
   python manage.py review_sandbox_checkouts --limit 30
   python manage.py review_sandbox_checkouts --reference <pending-reference>
   python manage.py review_sandbox_checkouts --request-id <stored-request-id>
   ```

   The report defaults to dry-run, including already settled records selected by
   reference/request ID. Compare both the pending and visible completed references.
   Classification is NEVER_SUBMITTED, SUBMITTED, SUBMISSION_UNKNOWN, local simulator
   not completed or terminal provider outcome; no terminal outcome is invented.
   Only after reviewing the report, persist local timeout metadata (no provider
   call/settlement) for the selected reference:

   ```bash
   python manage.py review_sandbox_checkouts --reference <pending-reference> --expire
   ```

   Do not delete records or erase browser storage. Open/refresh the client so its
   owner-bound `payment-recovery/<request-id>/` and payment list reconcile handles
   with server state. Missing recovery rows remain unknown, not presumed failed.

4. Keep private config unchanged: `PROTOTYPE_PAYMENT_PROVIDER=MTN_SANDBOX`, approved
   v1 policy, UGX authorization/new-payment/lending opt-ins, actual MTN currency EUR,
   HTTPS, existing dedicated keys, account CSRF/email and all seven disabled flags.
   No production action, global eager mode, physical output or relay enablement.
   Restart **alwaysdata → Web → Sites → existing site → Restart**. Read-only check:

   ```bash
   curl --fail --silent --show-error https://shanonsimon.alwaysdata.net/api/v1/features/ | python3 -m json.tool
   ```

5. Preserve/restore finite jobs, **Advanced → Scheduled tasks**, e.g. every minute.
   Preview first (no `--run`), then keep this existing command:

   ```bash
   ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings /home/shanonsimon/energy-venv/bin/python /home/shanonsimon/energy-sharing/manage.py reconcile_sandbox_payments --run --limit 2 --max-seconds 50
   ```

   It expires up to20 overdue checkouts, then reconciles due MTN references, under
   the same total deadline. New-local-cancelled records cannot starve status recovery.
   With the MTN status-checking patch, accepted submission is due for lookup after
   5s, ordinary PENDING after15s, and errors back off30–300s. Large backlogs require
   subsequent finite runs. See `MTN_STATUS_CHECKING.md` for safe targeted inspection
   and status-only recovery of old references without resubmitting a charge.
   UI timeout appears from server time at300s; persisted expiry waits for the next
   scheduled run (normally up to about another minute, longer on a missed run).
   No persistent worker/Celery/Redis is introduced. Preserve account-email job
   `drain_account_emails --send --limit 5` unchanged and historical LOCAL_DEMO
   `complete_demo_payments --run --limit 20 --max-seconds 50`; each retains its
   original provider. No command here starts a new hosted payment automatically
   merely because checkout time elapsed.

6. **Vercel separately:** review/commit/push the current web source yourself; no
   commit/push performed here. Existing project → Settings → root `frontend`, Next.js,
   install `npm ci`, build `npm run build -- --webpack`, server `API_URL` set to
   `https://shanonsimon.alwaysdata.net/api/v1`. Preserve existing authentication,
   HTTPS and environment variables. Deploy the new commit through the configured
   branch; redeploying the old commit does not upload these changes. Verify the
   deployed commit/build and authenticated `/dashboard/buy-units/`,
   `/dashboard/request-loan/`, `/dashboard/loans/`. An APK does not update Vercel.

7. Install the signed APK with `adb install -r` from the build report. Verify login,
   selection, visible pending forms, independent loan eligibility, timeout notice,
   explicit retry consent, restart recovery, one successful operation/token, partial
   and full repayment and logout. Actual MTN/phone/board tests remain operator work;
   local mocked tests are not physical validation. Do not re-provision or erase NVS.

See `mobile/CHECKOUT_BUILD.md` and `docs/review/payment-checkout/` for final artifacts,
commands, test results and explicitly local synthetic screenshots.

## Local verification

Combined isolated PostgreSQL:198 tests passed (18 checkout cases). Final current-code
guard suite:30 tests passed. Core93-case regression passed with the existing
CORE overdue-after-completion expected failure retained. Mobile90 tests/15 files,
web41 tests/14 files, strict types, focused lint, production Next49-page build and
signed debug APK passed. Final browser QA passed five checkout and nine existing
UGX scenarios, zero runtime errors, synthetic HTTPS APIs only. No physical-phone,
actual-provider or board test occurred. See mobile/CHECKOUT_BUILD.md for commands.

A late original success before explicit retry now produces a durable never-submitted
closed attempt for that retry ID and winning reference. Owner-bound recovery can
resolve its primary handle from server closure evidence; a missing record remains
unknown. Earlier invalid overlapping test-DB runs were rerun sequentially; no hosted
or operational DB was involved. Memory pressure slowed local checks, not suppressed
them. The exact hosted blocking reference still needs the preview report because
SSH authentication was denied.
