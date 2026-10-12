# Consumer mobile parity and release gates

The Android app is a separate Capacitor/Vite bundle. It calls Django directly and does not change the Next.js server-rendered web build. The methodology named Kotlin; Capacitor is the requested prototype choice. Statuses below describe this code, not production approval.

The unauthenticated preview entry was removed. Authentication and connected
screens call Django; no sample balances or scores stand in for account data.
Email verification and password recovery use the Django-hosted HTTPS pages;
return to Android manually, with no hosted Next.js dependency or deep link.

Current consumer expansion and its deployment gates are documented in
[`CONSUMER_EXPANSION.md`](CONSUMER_EXPANSION.md) and
[`backend/docs/CONSUMER_EXPANSION.md`](../backend/docs/CONSUMER_EXPANSION.md).

| Consumer task | Mobile status | Django authority / boundary |
| --- | --- | --- |
| Register, email verification/resend, password reset/change, login/refresh/logout | Available | Existing account routes and mobile JWT revocation; token expiry and one-use are validated by Django. Hosted testing uses Django account pages and manual return to Android; App Links are deferred. |
| Profile and loan assessment | Available | Server whitelists profile edits. A score is hidden until required profile evidence exists. Staff role, limits, verification and meter ownership are not editable. |
| Select meter, entitlement, consumption, loan/debt and repayment history | Available | Owner-bound reads; unknown values remain unavailable and existing records are not converted. |
| Alerts and transaction/payment receipts | Available | Owner-bound history. A receipt's `PENDING` status never means settled. Recovery/refresh reads stored verified settlement. Worker absence on alwaysdata is explicit. |
| Pending meter verification | Implemented | Typing a number records a request; staff assignment is required before access. Historical meters are not transferred. |
| Loan eligibility and quote | Informational | Current tariff and stored scoring rules; a quote is nonbinding. |
| Loan application | Blocked | Existing `/loans/apply/` can auto-disburse, lacks a mobile request ID and uses provisional/fallback calculation rules. Create an idempotent service with stored final terms after policy decisions. |
| Paid purchase and self-repayment | Guarded, disabled by default | Separate mobile initiation routes require a verified consumer, unique `client_request_id`, no competing pending intent, and a configured real provider. Django alone settles PaymentIntents from trusted evidence. `MOBILE_PAYMENT_ACTIONS_ENABLED=false` until finance/operator approval. |
| Load own attributable energy | Simulator only | `meter/deliver/` reserves new source-linked entitlement with a durable command and retry ID. Only a matching simulated-device acknowledgement establishes application. No physical control is enabled. |
| Peer sharing, consumer meter transfer, pay-for-someone, USSD, wallet deposit/withdrawal, external CRB | Deferred | Seven existing Django flags default to false; no mobile action screens. |

## New backend entry points and migrations

Account, meter, loan and receipt routes are listed in `mobile/README.md` and their app `api/urls.py` files. Mobile payment initiation uses `POST meter/mobile-buy-units/` and `POST loans/mobile-repay/momo/<loan_id>/`. Both are closed by default and do not accept a client-supplied flag. They require a UUID request ID; a retry with the same owner/purpose/amount/phone/meter or loan returns the existing intent without a new provider collection. A changed binding returns 409. The provider call happens after the intent transaction commits. An interrupted call returns 502 `PAYMENT_INITIATION_UNCONFIRMED` with a reference and leaves the intent for reconciliation.

The additive `transactions.0010_paymentintent_client_request_id` migration adds the globally unique, nullable request ID. `meter.0025_meterdelivery_request_id` adds retry identity to delivery rows. Existing rows remain untouched. The project also requires SimpleJWT's `token_blacklist` package migrations for mobile logout. Never run these against an unconfirmed operational database. On a disposable development database, first inspect `python manage.py showmigrations transactions meter token_blacklist`, then apply the reviewed pending migrations with `python manage.py migrate`.

The mobile rollout flag is scoped to the new mobile initiation URLs. Web and Android currently use the same Django login credentials and JWT contract, so a technically capable client can still call an existing canonical web purchase or loan-application URL. The mobile flag is therefore a rollout control, not a global financial authorization boundary. If policy requires **all** new transactions to stop, enforce that policy on the canonical Django services/routes as well; do not rely on app navigation or the mobile-only flag.

## Unresolved decisions before real transactions

- Agree how whole-UGX collection closes debt with fractional two-decimal charges, including excess receipts and when overdue charges stop after completion. The existing overdue-after-completion test is an expected failure.
- Agree the fate of purchase money remaining after energy is floored to 0.01 kWh. The full amount received and residual are recorded; the quote can differ from settlement because the tariff band may change.
- Decide whether loans may be offered without a stored tariff and remove the current UGX 500/kWh fallback only through an approved accounting change. Store the exact approved calculation policy with each obligation.
- Define loan application idempotency and final quote validity before exposing submission on Android. The current web path uses floating-point conversions and an interest-rate fallback; it must not be reused for an unreviewed mobile mutation.
- Validate the production provider's reference, amount, currency, terminal status and callback/reconciliation operations. A phone prompt is not evidence of payment. Keep simulations separate from real-provider records.
- Review firmware identity, acknowledgements, telemetry and gateway behavior before enabling any physical meter command. The simulator is not evidence of radio reliability or meter accuracy.

The app stores no backend secrets, provider keys or device credentials. The debug build embeds only its development API address and permits HTTP only in debug; release builds require HTTPS.
