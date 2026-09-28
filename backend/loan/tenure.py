"""Loan tenure rules — shared across web, mobile, and USSD."""

from __future__ import annotations

from datetime import datetime, timedelta

LOAN_TENURE_MIN_MONTHS = 1
LOAN_TENURE_MAX_MONTHS = 12
LOAN_MONTH_DAYS = 30

TENURE_PROMPT = (
    f"Enter months to repay ({LOAN_TENURE_MIN_MONTHS}-{LOAN_TENURE_MAX_MONTHS}, "
    f"each month = {LOAN_MONTH_DAYS} days from borrowing):"
)


def validate_tenure_months(value) -> int:
    try:
        months = int(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"Tenure must be a whole number between "
            f"{LOAN_TENURE_MIN_MONTHS} and {LOAN_TENURE_MAX_MONTHS} months."
        ) from None
    if months < LOAN_TENURE_MIN_MONTHS or months > LOAN_TENURE_MAX_MONTHS:
        raise ValueError(
            f"Tenure must be between {LOAN_TENURE_MIN_MONTHS} and "
            f"{LOAN_TENURE_MAX_MONTHS} months."
        )
    return months


def loan_due_date(disbursement_datetime: datetime, tenure_months: int) -> datetime:
    months = validate_tenure_months(tenure_months)
    return disbursement_datetime + timedelta(days=LOAN_MONTH_DAYS * months)
