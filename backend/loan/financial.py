"""Exact calculations for the loan rules stored on each application.

The existing money columns have two decimal places. Round the combined charge
once to that scale (Decimal's existing half-even default, now explicit), then
apply received repayments. This is a technical compatibility rule pending a
formal tariff/loan rounding policy; it does not change a rate or historical row.
"""

from decimal import Decimal, ROUND_HALF_EVEN

from django.conf import settings
from django.utils import timezone


UGX_CENT = Decimal("0.01")


def money(value):
    return Decimal(str(value)).quantize(UGX_CENT, rounding=ROUND_HALF_EVEN)


def interest_charge(loan):
    principal = Decimal(loan.amount_approved or 0)
    return principal * Decimal(loan.interest_rate) / Decimal(100) * Decimal(loan.tenure_months) / Decimal(12)


def loan_charges(loan, *, as_of=None):
    if not loan.amount_approved:
        return Decimal("0.00")
    principal = Decimal(loan.amount_approved)
    as_of = as_of or timezone.now()
    due = loan.due_date
    days_late = max(0, (as_of - due).days) if due and as_of > due else 0
    penalty = principal * Decimal("0.001") * Decimal(days_late)
    cap = principal * Decimal(str(getattr(settings, "MAX_CUMULATIVE_CHARGES_MULTIPLIER", "1.0")))
    return money(min(interest_charge(loan) + penalty, cap))


def applied_repayments(loan):
    # NULL means a historical row predating the explicit received/applied split.
    return sum((
        row.amount_applied_ugx if row.amount_applied_ugx is not None else row.amount_paid
        for row in loan.repayments.filter(payment_status="SUCCESS")
    ), Decimal("0.00")) if loan.pk else Decimal("0.00")


def outstanding_debt(loan, *, as_of=None):
    if not loan.amount_approved:
        return Decimal("0.00")
    due = Decimal(loan.amount_approved) + loan_charges(loan, as_of=as_of)
    return max(Decimal("0.00"), due - applied_repayments(loan))
