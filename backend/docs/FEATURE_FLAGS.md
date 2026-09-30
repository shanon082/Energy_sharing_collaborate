# Deferred feature flags

All flags below are deployment-owned environment variables and default to `false`. Copy `backend/feature-flags.env.example` into the deployment configuration as needed. Django parses `true/1/yes/on` and `false/0/no/off` (case-insensitive); any other value prevents startup. Request parameters cannot change them. `GET /api/v1/features/` publishes their availability for the existing Next.js web application. Django remains authoritative: disabled new activity returns HTTP 403 with `code: FEATURE_DISABLED` and a `feature` key.

| Variable | New activity disabled by default |
| --- | --- |
| `FEATURE_PEER_SHARING_ENABLED` | Peer sharing, receiver preview, and legacy meter send/receive |
| `FEATURE_METER_TRANSFERS_ENABLED` | Consumer meter-to-meter transfers, including OTP confirmation |
| `FEATURE_THIRD_PARTY_REPAYMENT_ENABLED` | Pay-for-someone and recipient lookup |
| `FEATURE_USSD_ENABLED` | Public USSD entry and simulator helper routes |
| `FEATURE_WALLET_DEPOSITS_ENABLED` | General-purpose money-wallet deposits |
| `FEATURE_WALLET_WITHDRAWALS_ENABLED` | General-purpose money-wallet withdrawals |
| `FEATURE_EXTERNAL_CRB_ENABLED` | External CRB provider selection/calls; internal scoring remains available |

The flags block **new optional activity**. They do not remove models, migrations, balances, or historical records. Existing authorized history, payment-status/reconciliation paths, own-meter wallet loading, token activation, self-repayment, authentication, alerts, staff meter assignment, and meter diagnostics remain available. Pending payments, tokens, and credits are not automatically cancelled, refunded, replayed, or discarded. Operators must reconcile already-funded obligations through trusted existing paths.

Keep these flags disabled until the associated correctness and security issues are resolved and separately tested. In particular, resolve unfunded credit paths and UGX/kWh balance mixing before sharing or transfers; verify payments with the provider and enforce idempotent disbursement before expanding payment flows; secure token/device operations before physical deployment. Third-party repayment needs an auditable funding source. External CRB remains a stub and needs a real provider agreement, data mapping, consent, and validation before use. USSD needs authentication, session, and payment flow review. Re-enabling a flag makes its old endpoint available, so deploy it only with a reviewed implementation and migration/reconciliation plan for any affected pending records.
