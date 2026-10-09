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

## Stage 2: consumer profile and assigned-meter dashboard

The mobile screens use dedicated consumer endpoints rather than the legacy web account-details read (which can create a missing record) and meter list (which includes legacy balances and device configuration). Existing Next.js contracts are preserved.

| Endpoint | Behaviour |
| --- | --- |
| `GET/PATCH /api/v1/auth/mobile-account-details/` | Owner-bound values and model-defined choices. Only address, energy preference and payment method are editable. Account number, owner, role and verification cannot be supplied. Missing details return `details_available: false` with `values: null`; PATCH returns 409 `ACCOUNT_DETAILS_MISSING` and creates nothing. Reads never repair historical records. |
| `GET/PATCH /api/v1/auth/mobile-profile/` | Existing assessment fields and choices. Profile edits and the existing deterministic credit-signal synchronization share a transaction and owner row lock. Historical score records and loan decisions are unchanged. Meter-sharing history is a self-reported assessment field, not an enabled energy-sharing operation. |
| `GET /api/v1/meter/mobile-meters/` | Current, nondeleted assignments to the authenticated consumer: stable database ID, number, label, architecture and status. No automatic primary selection, legacy units, IP address or device credential is returned. Suspended meters remain available for reading records. |
| `GET /api/v1/meter/mobile-meters/<meter_id>/` | Owner-bound dashboard using the existing `EnergyAllocation`/`MeterDelivery` summary. Exact decimal energy strings, 0.01 kWh quantum, distinct available/reserved/applied quantities, nullable last contact and explicit simulator contact source. Reassigned/deleted/foreign IDs return 404. Existing allocations retain their source, owner and meter; a new owner does not inherit their entitlement. |

All these endpoints enforce `ConsumerAccountPermission` for JWT and Django session authentication. Verified consumers must complete a required password change first; staff/anonymous/unverified requests cannot use the endpoints. This covers mobile profile/meter entry points, not a complete audit of legacy web/admin SessionAuthentication routes. Those routes remain unchanged and the mobile no longer depends on their profile/meter reads.

The app validates response shapes before display and uses Django's choices. Explicit meter selection binds ID and number. A changed assignment or replacement clears selected energy and consumption; a late read cannot restore the old selection. Older reads cannot overwrite newer reads or a cleared account. Profile fetch failures retain displayed data with its fetch time and a stale label, disable stale editing, and offer refresh; missing data stays unavailable. Samples remain isolated in the labelled preview. No persistent balance cache, offline financial mutation, feature re-enablement, accounting conversion or new migration is introduced.

Validation: the final combined PostgreSQL suite ran **113 tests, OK (one known overdue-after-completion expected failure)** in 133.301 seconds, including nine new Stage 2 tests and malformed-profile-body checks. It used an isolated database, in-memory email, blocked external HTTP and a test-only fast password hasher; production hashing is unchanged. Mobile type checking, 14 session tests and four profile/meter contract tests passed. Web type checking passed; the previous production-build timeout remains unresolved and no Next.js source/dependency was changed. Staff assignment/replacement is simulated using isolated meter records; no operational assignment or physical-device test is claimed.

The debug Vite build and Capacitor sync passed. `JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 ANDROID_HOME=/home/shanon/Android/Sdk GRADLE_USER_HOME=<repo>/mobile/.gradle-user ./gradlew --offline --no-daemon assembleDebug` passed using the project wrapper (153 tasks, 27 executed). APK: `mobile/android/app/build/outputs/apk/debug/app-debug.apk`, 4,543,216 bytes; SHA-256 `20e826bb979192ca5d1e8c23e2194e5231882e544fe78b60d7f8c6f31ac20e7f`. Its packaged main bundle matches the current Vite build and contains both Stage 2 endpoint paths. Embedded API: `http://192.168.193.107:8000/api/v1`; app ID `org.gpawa.consumer.prototype`, version 1.0/code 1, min SDK 24. HTTP is permitted only by the debug manifest; release still requires HTTPS. Reload Django before installing this APK. Browser and physical-phone results remain separate from APK assembly.

`mobile/tests-ui/consumer-ui.mjs` passed **14 Chromium scenarios**, intercepting every `/api/v1/` request with synthetic data. These cover authentication, preview isolation, live profile editing, stale/offline editing restrictions and recovery, missing details, explicit meter choice, replacement/reassignment invalidation, zero meters, navigation, responsive layouts and logout. The test server was loopback-only and stopped afterward; the disposable PostgreSQL cluster was stopped too. The backend command was `backend/venv/bin/python /tmp/gpawa-stage2-pg/tests.py`, whose runner explicitly overrides all DB settings, blocks unmocked HTTP, uses in-memory mail and runs the Stage 1 labels above plus `accounts.tests_mobile_profile_meters`. Physical-phone checks remain outstanding: reload Django, install the updated debug APK, verify zero/multiple assigned meters and profile saves, disconnect/reconnect and refresh, then log out. Actual verification-email delivery remains a separate configured-mail test.

## Subsequent stages

| Stage | Scope | Acceptance criteria |
| --- | --- | --- |
| 2 (implemented) | Consumer profile and assigned-meter dashboard integration | Dedicated owner-bound reads and constrained profile edits, explicit ID-bound selection, zero/multiple/missing/reassigned cases, stale display and JWT/session boundary tests. Physical-phone checks and legacy session-route review remain separate. |
| 3 | Consumption, delivery state, receipts and notifications | Consumption is distinct from entitlement/delivery. Simulator data is labelled. Ownership checks and requested-versus-applied status survive refresh/restart. Review the existing recoverable MeterBalance signal conflict separately. |
| 4 | Electricity-credit application and read-only debt details | Agree stored terms and calculation policy first; add idempotent source-linked application/disbursement. No fallback score, changed historical loan or duplicated energy. |
| 5 | Verified purchases and self-repayment | Resolve whole-UGX/fractional-debt, excess/residual and overdue questions. Keep mobile initiation disabled until approved provider/reconciliation testing; conserve money and preserve uncertain obligations. |
| 6 | Own-meter simulator loading, then hardware review | Durable command identity, exact entitlement reservations and matching application acknowledgement. Physical protocol/radio validation is separate and requires hardware agreement. |

The staged plan does not re-enable peer sharing, consumer meter transfers, third-party repayment, USSD, wallet deposits/withdrawals or external CRB.
