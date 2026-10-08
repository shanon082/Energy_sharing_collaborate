# Consumer app backend stages

The checkpoint before this stage is commit `76d5769`. The Next.js application, seven deferred feature defaults, verified settlement, source-linked allocations and isolated simulator are retained. The mobile interface already calls Django for authentication; its independent design preview still uses sample data and sends no backend requests.

## Stage 1: registration, authentication and consumer authorization

Implemented using the existing `/api/v1/auth/` routes. No new database migration or operational database change is part of this stage.

| Task | Contract and enforced boundary |
| --- | --- |
| Registration | `POST register/`: first/last name, email, phone, model-defined gender, password and confirmation. Creates a consumer, unverified profile and account details atomically. Submitted roles/staff/verification fields cannot grant privileges. Password fields are write-only; passwords are not silently trimmed. Existing length/complexity rules remain. Database uniqueness races return 400 rather than a 500. |
| Email verification | Existing `GET verify-email/?uid=…&token=…`; Django validates expiry and one-use. New-registration verification dispatch waits until database commit, so a rolled-back account cannot receive a valid registration email. Dispatch is not evidence of successful email delivery. |
| Login | `POST login/`: credentials and existing `remember_me` BooleanField. Authentication occurs once. Invalid/inactive/unverified accounts mint no token; staff two-factor requests return the existing challenge without minting a JWT. A successful consumer response keeps `access`, `refresh` and `user` for both clients. |
| Refresh | `POST refresh/token/`: refresh credential only. Checks account existence/activity, consumer verification and password revocation; locks the outstanding-token row and revalidates before rotation. A concurrent/replayed refresh cannot rotate the same credential twice. No network calls occur under that lock. |
| Account bootstrap | `GET mobile-account/`: verified active consumer only. A required-password-change consumer can read identity and see the requirement. Staff/superuser privileges are rejected even if `user_role` says CLIENT. |
| Password change/recovery | Existing mobile-password, required-password-change and reset-password flows. Password change/reset invalidates previously issued access/refresh credentials. Completing a valid password reset clears the first-login password-change requirement. Reset passwords are not silently trimmed. |
| Logout | `POST mobile-logout/`: authenticated consumer, refresh token must belong to that consumer. Allowed while a password change or verification is needed. Blacklists that refresh credential and the app clears its local credentials/private view. |
| Protected mobile account/profile, meter/consumption/delivery/quote, loan/quote and receipt APIs | Central `ConsumerAccountPermission` enforces active, verified consumer and required-password-change status independently of the frontend. JWT account-state checks also cover the shared meter/history/financial routes used by the app, so hiding a form is not the authorization boundary. Existing owner/meter/loan binding checks remain. |

`AccountJWTAuthentication` preserves the existing JWT and SessionAuthentication setup. For consumer JWT requests, the required-password-change bootstrap exceptions are a fixed server-side path set: mobile-account, mobile-password, mobile-logout, get-user-config and change-required-password. Requests cannot supply an exemption. Unverified consumers can only use authenticated mobile logout; verification/recovery remain public token-validated flows. Native simulator messages continue to use their separate device credentials and simulation restrictions.

The custom JWT checks cover JWT requests. Shared legacy Django SessionAuthentication routes with explicitly overridden permissions still need their own review before claiming a complete authorization audit of every web/admin route. Dedicated mobile endpoints have explicit permissions for either authentication mechanism. Django's `is_active` is the authentication authority; the separate historical `account_is_active` field is not reinterpreted here.

### Rollout and remaining authentication limits

- `SIMPLE_JWT.CHECK_REVOKE_TOKEN=True` uses the library's password-revocation claim; [official Simple JWT settings](https://django-rest-framework-simplejwt.readthedocs.io/en/stable/settings.html#check-revoke-token). **JWTs issued before this setting need a fresh sign-in once the backend restarts.** Existing access/refresh URLs and response shapes remain unchanged. No credential values are logged or committed.
- Existing SimpleJWT `token_blacklist` migrations must already be applied on a confirmed development database. This stage introduces no migration. Its tests apply migrations only in a disposable PostgreSQL test database.
- Login/refresh lifetime configuration stays at 30-minute access and one-day refresh. The existing Remember me setting extends the initial refresh to 30 days; rotation continues using the existing configured refresh lifetime. The token registry now stores the same expiry as the extended credential.
- Logout revokes the submitted refresh, not all previously issued access tokens. An already-issued access credential can remain usable until its 30-minute expiry unless a password changes or account restrictions apply. Offline logout cannot revoke a remote refresh. A session-family/revocation policy needs a later explicit design.
- The existing resend-verification GET exposes different results for absent/already-verified accounts; rate limiting and account enumeration resistance need review. Production must add shared-cache/proxy abuse controls for login, registration and email requests. This stage does not invent deployment-specific throttle limits.
- Verification dispatch uses the existing task mechanism, not a durable email outbox. Configure the development email sender/worker and test actual delivery separately. No live email provider is contacted by the regression suite. Production Android App Links require an agreed domain; copied links remain the local prototype mechanism.
- No financial policy is approved by these changes. The overdue-after-completion expected failure stays visible. Transactions remain guarded and deferred unit sharing stays disabled.

### Validation

Run on an **isolated** PostgreSQL database with overridden DB settings, in-memory Django email and a mocked/blocked HTTP transport. The combined test labels are:

```text
accounts.tests_authentication accounts.tests_mobile_api accounts.tests_mobile_cors
backend.tests_feature_flags transactions.tests_payment_settlement
meter.tests_allocation_delivery loan.tests_financial_correctness
```

Authentication tests include privilege injection, invalid choices/passwords, rollback without email dispatch, concurrent duplicate registration, one token pair per login, staff challenges, direct JWT route restrictions, password/reset revocation, inactive/deleted accounts, and concurrent refresh (one HTTP 200, one HTTP 401). Existing mobile tests use verified owner fixtures when testing authorized business reads. Denied staff methods return 403 before method dispatch; an authorized consumer still receives 405 for an unsupported method.

Final combined result: **104 tests, OK (one known expected failure)** in 286.589 seconds. The expected failure is overdue charges after loan completion; it remains unresolved. The final runner used a test-only MD5 password hasher; an earlier combined run also passed the authentication tests with the production password hasher. PostgreSQL ran in a disposable local cluster on port 55439, with an empty `gpawa_auth_tests` parent database and Django-created `test_gpawa_auth_tests`; operational database settings were overridden. The test process blocked all unmocked `requests` HTTP calls and used in-memory email. No operational migration or live provider/device call occurred.

Concurrency evidence: duplicate registration produced one 201 and one 400 with one account/email dispatch; two refresh requests produced one 200 and one 401 with one replacement token. Settlement/allocation concurrency and financial regressions ran in the same final suite. An existing repayment-status test needed a missing pending-provider mock, and authorized delivery-history fixtures needed verified profiles; those were corrected before the final run.

Mobile checks: `npm run typecheck` and `node tests/session.test.mjs` from `mobile` passed (14 session tests). Web `./node_modules/.bin/tsc --noEmit` passed. Production compilation stalled: both `timeout 180 npm run build` and `timeout 180 npm run build -- --webpack` exited 124 without a compiler error. The cause of this build blocker is unconfirmed; this run does not establish production-build success. No strict checking bypass or web source/dependency change was introduced. Independent APK rebuilding is unnecessary for these unchanged API shapes; no physical-device retest was performed in this stage.

## Subsequent stages

| Stage | Scope | Acceptance criteria |
| --- | --- | --- |
| 2 | Consumer profile and assigned-meter dashboard integration | Real owner-bound data replaces preview fixtures only in authenticated screens; unknown values stay unavailable. Verify zero/multiple meters, staff assignment, missing profiles, account isolation, offline/stale display and shared legacy session-route permissions. |
| 3 | Consumption, delivery state, receipts and notifications | Consumption is distinct from entitlement/delivery. Simulator data is labelled. Ownership checks and requested-versus-applied status survive refresh/restart. Review the existing recoverable MeterBalance signal conflict separately. |
| 4 | Electricity-credit application and read-only debt details | Agree stored terms and calculation policy first; add idempotent source-linked application/disbursement. No fallback score, changed historical loan or duplicated energy. |
| 5 | Verified purchases and self-repayment | Resolve whole-UGX/fractional-debt, excess/residual and overdue questions. Keep mobile initiation disabled until approved provider/reconciliation testing; conserve money and preserve uncertain obligations. |
| 6 | Own-meter simulator loading, then hardware review | Durable command identity, exact entitlement reservations and matching application acknowledgement. Physical protocol/radio validation is separate and requires hardware agreement. |

The staged plan does not re-enable peer sharing, consumer meter transfers, third-party repayment, USSD, wallet deposits/withdrawals or external CRB.
