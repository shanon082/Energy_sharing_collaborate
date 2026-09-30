# Verified payment containment

New phone purchases and self-repayments use `PaymentIntent` (`transactions` migration
`0007`) to bind one owner, amount in whole UGX, currency, provider reference, provider
external ID and purpose to one purchase or repayment. Initiation stores a pending
record before the provider call. Provider polling happens outside a database
transaction; settlement locks the intent row, checks terminal provider evidence,
and applies one financial effect. The purchase purpose creates one source-bound
`EnergyAllocation` and credits the legacy `UnitBalance` projection in kWh. The
repayment purpose reduces loan debt through a successful `LoanRepayment`;
it does not create energy. A browser session is not needed for reconciliation:
Celery beat schedules `transactions.tasks.reconcile_pending_payments` every five
minutes. Both beat and a worker must run in deployment.

The verified flow is available only when production MTN Collection credentials,
a production HTTPS base URL and UGX mode are configured. Sandbox/simulated payments
cannot settle these records. No live provider or device was contacted in tests.
Deployers must apply the additive migration through their controlled deployment
process; this change did not migrate the operational database.

Legacy direct purchases (`/api/v1/transactions/buy-units/`), direct loan
repayments (`/api/v1/loans/repay/<id>/` and `/active/`) and wallet-funded
purchases/repayments reject new mutations. Existing pending provider requests,
tokens and credits are preserved. Historical requests without `PaymentIntent`
need an operator-led comparison of provider statements, purchase/repayment rows,
unit balances and meter ledger before any adjustment. No automatic refund,
replay or cancellation is performed. Pending intents whose provider initiation
was uncertain also require monitoring and, if necessary, manual reconciliation.

Unauthenticated token redemption, direct token loading and unvalidated STS token
generation are unavailable until firmware and backend agree on authenticated
device identity, meter/allocation binding, idempotent command IDs,
acknowledgements and reconciliation. Approved loans create a source-bound
allocation and still credit the legacy unit balance; physical delivery is
deferred. `LoanDisbursement.token` remains
in the existing schema for history but is not exposed as a usable keypad code.
Test pushes require DEBUG, a mock
gateway and a simulation meter. Meter balances, historical scores and decisions
were not converted.

Own-meter AMI loading now reserves attributable new allocation for the isolated
simulator; it never spends an ambiguous historical balance or claims physical
delivery. Purchases and new loans require an explicit owned `meter_no`.
`ENERGY_ALLOCATION_SIMULATOR.md` defines the new authority, command lifecycle,
simulator API, and historical reconciliation needs. The old automatic legacy
AMI retry schedule is disabled; existing pending obligations are preserved.

Before enabling production payment collection, operators must provision
`SECRET_KEY`, database/SMTP credentials, a nonempty ThingsBoard webhook secret,
the MTN production credentials and endpoint, and Celery beat/worker. Rotate the
previously embedded Django signing key and SMTP app password; reset any staff
accounts created with the former shared default password. Review the database
credential and webhook/provider credentials for exposure and rotate as needed.
No rotation has been performed by this code change. Re-enabling the seven
deferred features still requires the correctness work in `FEATURE_FLAGS.md`.
