import logging
from decimal import Decimal
from typing import Any

from transactions.models import TransactionLog, TransactionType

logger = logging.getLogger(__name__)


def record_transaction_log(
    user,
    transaction_type: str,
    *,
    amount=None,
    units=None,
    status: str = "COMPLETED",
    reference_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> TransactionLog | None:
    """Create a user-visible transaction log entry (idempotent on reference_id when provided)."""
    if reference_id:
        existing = TransactionLog.objects.filter(
            user=user,
            reference_id=reference_id,
            transaction_type=transaction_type,
        ).first()
        if existing:
            return existing

    try:
        return TransactionLog.objects.create(
            user=user,
            transaction_type=transaction_type,
            amount=Decimal(str(amount)) if amount is not None else None,
            units=Decimal(str(units)) if units is not None else None,
            status=status,
            reference_id=reference_id,
            details=details or {},
        )
    except Exception:
        logger.exception("Failed to record transaction log for user %s", user.id)
        return None
