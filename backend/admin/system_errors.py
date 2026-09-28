"""
Aggregate recent failures for the admin error log and optional persistence.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


def _infer_component(message: str, transaction_type: str = "", source: str = "") -> str:
    text = f"{message} {transaction_type} {source}".upper()
    if "THINGSBOARD" in text or "AMI" in text:
        return "ThingsBoard / AMI"
    if "CVS" in text or "STS" in text or "TOKEN" in text:
        return "CVS/STS API"
    if "MTN" in text or "MOMO" in text or "MOBILE MONEY" in text or "PAYMENT" in text:
        return "MTN MoMo API"
    if "AIRTEL" in text:
        return "Airtel Money API"
    if "USSD" in text or "AFRICA" in text or "SMS" in text:
        return "Africa's Talking"
    if "FIREBASE" in text or "PUSH" in text:
        return "Firebase"
    if "REDIS" in text or "CELERY" in text:
        return "Redis / Celery"
    if "DATABASE" in text or "POSTGRES" in text:
        return "PostgreSQL"
    return source or "System"


def record_system_error(
    component: str,
    message: str,
    *,
    user=None,
    reference_id: str = "",
    details: dict | None = None,
) -> None:
    from admin.models import SystemErrorEvent

    try:
        SystemErrorEvent.objects.create(
            component=component[:80],
            message=message[:2000],
            user=user if getattr(user, "pk", None) else None,
            reference_id=(reference_id or "")[:100],
            details=details or {},
        )
    except Exception:
        # Never break the request path because logging failed.
        pass


def collect_recent_errors(limit: int = 50) -> list[dict]:
    from admin.models import SystemErrorEvent
    from loan.models import LoanRepayment
    from meter.models import Transaction as MeterTransaction
    from share.models import ShareTransaction
    from transactions.models import Transaction as PaymentTransaction
    from transactions.models import TransactionLog, UnitTransaction

    entries: list[dict] = []

    for event in SystemErrorEvent.objects.select_related("user").order_by("-created_at")[:limit]:
        entries.append(
            {
                "timestamp": event.created_at.isoformat(),
                "component": event.component,
                "message": event.message,
                "user": event.user.email if event.user else "—",
                "transaction_id": event.reference_id or "",
                "source": "system",
            }
        )

    for t in MeterTransaction.objects.filter(status=MeterTransaction.STATUS_FAILED).select_related("user").order_by("-create_date")[:limit]:
        entries.append(
            {
                "timestamp": t.create_date.isoformat(),
                "component": _infer_component(t.failure_reason or "", t.transaction_type),
                "message": t.failure_reason or f"{t.transaction_type} failed",
                "user": t.user.email,
                "transaction_id": str(t.transaction_id),
                "source": "meter_transaction",
            }
        )

    for log in TransactionLog.objects.filter(status="FAILED").select_related("user").order_by("-created_at")[:limit]:
        detail_msg = ""
        if isinstance(log.details, dict):
            detail_msg = str(log.details.get("error") or log.details.get("message") or "")
        message = detail_msg or f"{log.transaction_type} failed"
        entries.append(
            {
                "timestamp": log.created_at.isoformat(),
                "component": _infer_component(message, log.transaction_type),
                "message": message,
                "user": log.user.email,
                "transaction_id": log.reference_id or "",
                "source": "transaction_log",
            }
        )

    for t in PaymentTransaction.objects.filter(status="FAILED").select_related("wallet__user").order_by("-create_date")[:limit]:
        user = t.wallet.user if t.wallet_id else None
        message = t.message or "Payment transaction failed"
        entries.append(
            {
                "timestamp": t.create_date.isoformat(),
                "component": _infer_component(message),
                "message": message,
                "user": user.email if user else "—",
                "transaction_id": t.transaction_reference or t.transaction_id or "",
                "source": "payment_transaction",
            }
        )

    for t in UnitTransaction.objects.filter(status="FAILED").select_related("sender").order_by("-create_date")[:limit]:
        entries.append(
            {
                "timestamp": t.create_date.isoformat(),
                "component": _infer_component(t.message or ""),
                "message": t.message or "Unit transfer failed",
                "user": t.sender.email,
                "transaction_id": t.transaction_id or "",
                "source": "unit_transaction",
            }
        )

    for t in ShareTransaction.objects.filter(status="FAILED").select_related("sender").order_by("-create_date")[:limit]:
        entries.append(
            {
                "timestamp": t.create_date.isoformat(),
                "component": "Share / Transfer",
                "message": t.message or "Share transaction failed",
                "user": t.sender.email,
                "transaction_id": t.share_transaction_id or "",
                "source": "share_transaction",
            }
        )

    for repayment in (
        LoanRepayment.objects.filter(payment_status__in=["FAILED", "CANCELLED"])
        .select_related("loan__user")
        .order_by("-created_at")[:limit]
    ):
        user = repayment.loan.user if repayment.loan_id else None
        entries.append(
            {
                "timestamp": repayment.created_at.isoformat(),
                "component": "MTN MoMo API",
                "message": f"Loan repayment {repayment.payment_status.lower()} (ref {repayment.payment_reference})",
                "user": user.email if user else "—",
                "transaction_id": repayment.payment_reference or "",
                "source": "loan_repayment",
            }
        )

    entries.sort(key=lambda e: e["timestamp"], reverse=True)
    return entries[:limit]
