# Billing and loan-accounting policy inventory

This is the implemented prototype policy, not a claim that current regulator
rates or contract terms have been approved. The supplied methodology (pp. 4–6,
sections 4.2–4.4) requires credit scoring, billing, repayment and validation;
it does not specify tariffs, interest, penalties, money rounding or repayment
allocation. Confirm those with the project owner before live financial use.

## Current rules and authority

| Rule | Current source |
| --- | --- |
| Domestic cumulative **purchases** determine tariff blocks; measured consumption and meter delivery do not | `loan.models.TariffBlock`, `utils.billing._energy_cost_for_units`; seed values in `loan.tariff_utils` |
| Active versioned domestic tariff chosen by date, otherwise latest active domestic; if no blocks, flat UGX 756.20/kWh | `utils.billing.get_active_domestic_tariff`, `_energy_cost_for_units` |
| Seeded Q4 2025 values: 15 kWh lifeline at 250, next to 80 at 756.20, next to 150 at 412, above at 756; 3,360 monthly service charge and 18% VAT | `loan.tariff_utils`, `utils.billing` constants; **date-specific example, not a current-rate assertion** |
| Service charge charged on first counted purchase of calendar month; configured zero means zero; VAT on energy plus service | `utils.billing._service_charge`, `calculate_bill_for_units` |
| Loan annual simple interest = principal × stored annual percent × tenure/12; due date = disbursement time + 30 days × tenure months | `loan.financial`, `loan.tenure`; stored `LoanApplication` terms |
| After due date, 0.1% principal per whole overdue day; combined interest and penalty capped by principal × `MAX_CUMULATIVE_CHARGES_MULTIPLIER` (default 1.0) | `loan.financial.loan_charges`, `backend.settings` |
| Successful applied repayments reduce debt; provider receipt may exceed debt and excess stays identified for review | `LoanApplication.amount_paid`, `loan.financial`, `transactions.payment_settlement._settle_repayment` |

New `PaymentIntent` plus its `EnergyAllocation` is the purchase identity for
tariff counting. The `meter.Transaction` purchase row, `UnitTransaction`
self-credit and `TransactionLog` emitted by the same settlement are audit or
compatibility representations, not additional purchases. Historical completed
meter purchase rows are counted once per nonempty payment reference, or once
per row if no reference exists. This weaker historical provenance is reported
for reconciliation; historical rows and bills are not rewritten. Loan
allocations, meter loads and measured consumption never enter purchase bands.
Settlements for a consumer serialize pricing by locking that consumer row,
including purchases for distinct meters.

Money received by Mobile Money is positive **whole UGX**. Existing money
columns store two decimal places. Energy cost is summed across bands before
rounding to 0.01 UGX, VAT is then rounded to 0.01 UGX, and loan combined
interest plus accrued penalty is capped then rounded once to 0.01 UGX. These
charge calculations explicitly use decimal half-even rounding, matching the
prior implicit `Decimal.quantize` behavior in billing; the loan implementation
previously used binary floats and had no stated rounding. The project owner
must confirm whether final UGX charges should instead round to whole UGX and
which tie-breaking rule is contractual. No historical charge is rewritten.

The maximum purchased energy is **truncated downward** to the existing 0.01
kWh = 10 Wh allocation increment, then the bill is recalculated for precisely
that grant. This prevents crediting more energy than the whole-UGX payment can
buy. The provider is asked for the original whole-UGX `PaymentIntent.amount`
before this truncation; it is **not** reduced to the later energy bill. New
settled purchases retain `purchase_billed_ugx` and
`purchase_residual_ugx`, whose sum equals the full receipt. The residual is
labelled for operator reconciliation and is not silently converted to energy,
refunded, or credited to a wallet. For a verified amount too small to buy even
0.01 kWh, the full receipt is residual and no allocation is created. The
`purchase_calculation` JSON snapshot records the pricing date, tariff ID and
block rates, fallback and VAT rates, prior monthly purchases, lifeline
eligibility, rounded bill components, and energy granted. This preserves the
new settlement's calculation inputs for audit; old purchases have no such
snapshot and cannot be reconstructed reliably by applying today's tariff.
Cumulative simulated consumption remains integer Wh, not rounded per
reading. A new verified `LoanRepayment.amount_paid` stores the full received
amount. `amount_applied_ugx` is the part that reduces debt and `excess_ugx`
holds the rest pending manual reconciliation. The fields sum to the received
amount. Historical successful rows have NULL applied amount and retain their
legacy interpretation as fully applied; they are not backfilled. The smallest
whole-UGX payment that can clear a fractional remaining debt is its ceiling;
the fractional excess is retained, not refunded or converted to energy.

`LoanApplication.outstanding_balance` and `loan.financial.outstanding_debt`
are the debt authority for settlement, eligibility and API responses. `LoanStatsView`
sums these `Decimal` values and emits a decimal string for web display. The
web may convert that string to a JavaScript number **only for presentation**;
the server revalidates whole-UGX payments. `UnitBalance` remains an ambiguous
legacy projection, never an authority for new meter delivery. New entitlement
and reservations remain in `EnergyAllocation` and `MeterDelivery`.
For loans with a stored tariff, the loan-application quote and disbursement use
that same tariff, service-charge and VAT engine instead of a separate float
block split. Loans with **no stored tariff** retain the older `amount / 500`
disbursement rule; their response deliberately has no VAT-inclusive cost
breakdown. This existing conflict with the purchase fallback rate needs a
policy decision before new no-tariff loans can be treated as validated bills.
Quotes are current calculations, not backfilled historical invoices.

## Known policy and historical decisions

- The PDF provides no financial rates or rounding policy. The Q4 2025 tariff
  seed, fallback rate, VAT, late penalty, charge cap, starter tier and other
  stored loan-tier terms require dated approval. `get_active_domestic_tariff`
  currently falls back to the latest active record if no date range matches;
  decide whether a gap should instead block purchase.
- `LoanApplication.save()` still sets the interest rate from the current score
  tier while an application is pending/approved/rejected. Disbursed and later
  states now retain the stored rate on unrelated saves. Decide whether terms
  should lock earlier at approval; historical rate provenance needs review.
- `total_amount_due` is scheduled principal plus interest, while
  `outstanding_balance` includes accrued overdue penalties and the charge cap.
  Late charges can continue to appear after a loan marked completed because
  there is no immutable debt-close timestamp. Decide a closure/freeze rule
  before backfilling or correcting old loans.
- Old `UnitBalance` entries may mix UGX and kWh. Legacy meter purchases with
  missing or duplicated references and historical successful repayments without
  an intent cannot be proven from current rows alone. No old balance, bill,
  score, decision, token or payment is automatically replayed or changed.

Run `python manage.py reconcile_financial_history` against an authorized
database to get a **read-only dry-run** JSON inventory. It reports internal
IDs/counts/totals and never prints personal contact data, tokens, provider
transaction IDs or credentials. `--limit N` limits identifier samples. Review
flagged records against provider statements and meter evidence before any
manual adjustment. Do not run this on operational data without normal access
approval and data-handling controls.
