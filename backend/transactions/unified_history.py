from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from django.db.models import Q

from accounts.models import Wallet as AccountWallet
from loan.models import LoanApplication, LoanDisbursement, LoanRepayment
from meter.models import Transaction as MeterLedgerTransaction
from share.models import ShareTransaction
from transactions.models import Transaction as PaymentTransaction
from transactions.models import TransactionLog, TransactionType

MAX_PER_SOURCE = 500

METER_LEDGER_TYPE_MAP = {
    MeterLedgerTransaction.TYPE_PURCHASE: TransactionType.UNIT_PURCHASE,
    MeterLedgerTransaction.TYPE_GENERATE_TOKEN: TransactionType.TOKEN_GENERATE,
    MeterLedgerTransaction.TYPE_TRANSFER_OUT: TransactionType.UNIT_SHARE,
    MeterLedgerTransaction.TYPE_TRANSFER_IN: TransactionType.UNIT_SHARE,
    MeterLedgerTransaction.TYPE_REPAYMENT_AUTO: TransactionType.LOAN_REPAYMENT,
    MeterLedgerTransaction.TYPE_REPAYMENT_DIRECT: TransactionType.LOAN_REPAYMENT,
    MeterLedgerTransaction.TYPE_CREDIT: TransactionType.UNIT_PURCHASE,
    MeterLedgerTransaction.TYPE_REFUND: TransactionType.UNIT_PURCHASE,
}

TYPE_DISPLAY = dict(TransactionType.choices)
TYPE_DISPLAY.update(
    {
        TransactionType.TOKEN_GENERATE: "STS Token Generated",
        TransactionType.WALLET_LOAD_AMI: "Wallet Load (AMI)",
    }
)


def _channel_label(channel: str | None) -> str:
    mapping = {
        "USSD": "USSD",
        "MOBILE_APP": "Mobile App",
        "WEB_PORTAL": "Web",
        "WEB": "Web",
        "ADMIN": "Admin",
        "MOBILE_MONEY": "Mobile Money",
    }
    if not channel:
        return "Web"
    return mapping.get(channel.upper(), channel.replace("_", " ").title())


def _normalize_entry(
    *,
    entry_id: str,
    transaction_type: str,
    created_at,
    status: str = "COMPLETED",
    amount=None,
    units=None,
    reference_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    details = dict(details or {})
    channel = details.get("channel")
    return {
        "id": entry_id,
        "transaction_type": transaction_type,
        "transaction_type_display": TYPE_DISPLAY.get(transaction_type, transaction_type.replace("_", " ").title()),
        "amount": float(amount) if amount is not None else None,
        "units": float(units) if units is not None else None,
        "status": status,
        "reference_id": reference_id,
        "details": details,
        "channel": channel,
        "channel_display": _channel_label(channel),
        "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S") if created_at else None,
        "_sort_at": created_at,
    }


def _seen_add(seen: set[str], ref: str | None) -> bool:
    if not ref:
        return False
    key = str(ref).strip()
    if not key or key in seen:
        return True
    seen.add(key)
    return False


def _infer_channel_from_text(text: str | None) -> str | None:
    if not text:
        return None
    upper = text.upper()
    if "USSD" in upper:
        return "USSD"
    return None


def collect_unified_history(user) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen_refs: set[str] = set()

    for log in TransactionLog.objects.filter(user=user).order_by("-created_at")[:MAX_PER_SOURCE]:
        details = dict(log.details or {})
        if "channel" not in details:
            inferred = _infer_channel_from_text(str(details.get("message", "")))
            if inferred:
                details["channel"] = inferred
        entries.append(
            _normalize_entry(
                entry_id=f"log-{log.id}",
                transaction_type=log.transaction_type,
                created_at=log.created_at,
                status=log.status,
                amount=log.amount,
                units=log.units,
                reference_id=log.reference_id,
                details=details,
            )
        )
        _seen_add(seen_refs, log.reference_id)

    account_wallets = AccountWallet.objects.filter(user=user)
    payment_qs = PaymentTransaction.objects.filter(wallet__in=account_wallets).order_by("-create_date")[:MAX_PER_SOURCE]
    for pt in payment_qs:
        ref = pt.transaction_reference or f"PAY-{pt.id}"
        if _seen_add(seen_refs, ref):
            continue
        channel = _infer_channel_from_text(pt.message) or "WEB_PORTAL"
        entries.append(
            _normalize_entry(
                entry_id=f"pay-{pt.id}",
                transaction_type=TransactionType.UNIT_PURCHASE,
                created_at=pt.create_date,
                status=(pt.status or "PENDING").upper(),
                amount=pt.amount,
                reference_id=ref,
                details={
                    "channel": channel,
                    "phone_number": str(pt.phone_number),
                    "message": pt.message,
                    "source": "momo_payment",
                },
            )
        )

    for mt in MeterLedgerTransaction.objects.filter(user=user).order_by("-create_date")[:MAX_PER_SOURCE]:
        ref = mt.payment_reference or str(mt.transaction_id)
        if _seen_add(seen_refs, ref):
            continue
        tx_type = METER_LEDGER_TYPE_MAP.get(mt.transaction_type, TransactionType.UNIT_PURCHASE)
        entries.append(
            _normalize_entry(
                entry_id=f"meter-{mt.transaction_id}",
                transaction_type=tx_type,
                created_at=mt.create_date,
                status=mt.status,
                amount=mt.amount_ugx or None,
                units=mt.amount_kwh or None,
                reference_id=ref or None,
                details={
                    "channel": mt.channel,
                    "meter_no": mt.meter.meter_no if mt.meter_id else mt.destination,
                    "destination": mt.destination,
                    "source": mt.source,
                    "sts_token": mt.sts_token or None,
                    "meter_event_type": mt.transaction_type,
                },
            )
        )

    share_qs = (
        ShareTransaction.objects.filter(status="COMPLETED")
        .filter(Q(sender=user) | Q(receiver=user))
        .select_related("meter_send", "meter_receive", "sender", "receiver")
        .order_by("-create_date")[:MAX_PER_SOURCE]
    )
    for share in share_qs:
        ref = share.share_transaction_id
        if _seen_add(seen_refs, ref):
            continue
        channel = _infer_channel_from_text(share.message) or "WEB_PORTAL"
        is_sender = share.sender_id == user.id
        entries.append(
            _normalize_entry(
                entry_id=f"share-{share.id}",
                transaction_type=TransactionType.UNIT_SHARE,
                created_at=share.verified_at or share.create_date,
                status=share.status,
                units=share.units,
                reference_id=ref,
                details={
                    "channel": channel,
                    "direction": "OUT" if is_sender else "IN",
                    "counterparty": share.receiver.email if is_sender else share.sender.email,
                    "receiver_meter": share.meter_receive.meter_no if share.meter_receive_id else None,
                    "sender_meter": share.meter_send.meter_no if share.meter_send_id else None,
                    "message": share.message,
                },
            )
        )

    for repayment in (
        LoanRepayment.objects.filter(loan__user=user, payment_status="SUCCESS")
        .select_related("loan")
        .order_by("-payment_date")[:MAX_PER_SOURCE]
    ):
        if _seen_add(seen_refs, repayment.payment_reference):
            continue
        channel = repayment.payment_method or "WEB_PORTAL"
        if repayment.momo_external_id:
            channel = "MOBILE_MONEY"
        entries.append(
            _normalize_entry(
                entry_id=f"loanrepay-{repayment.id}",
                transaction_type=TransactionType.LOAN_REPAYMENT,
                created_at=repayment.payment_date,
                status="COMPLETED",
                amount=repayment.amount_paid,
                units=repayment.units_paid,
                reference_id=repayment.payment_reference,
                details={
                    "channel": channel,
                    "loan_id": repayment.loan.loan_id,
                    "payment_method": repayment.payment_method,
                    "auto_from_purchase": "buy_units" in (repayment.payment_reference or "").lower(),
                },
            )
        )

    for loan in LoanApplication.objects.filter(user=user).order_by("-created_at")[:MAX_PER_SOURCE]:
        if TransactionLog.objects.filter(
            user=user,
            transaction_type=TransactionType.LOAN_APPLICATION,
            reference_id=loan.loan_id,
        ).exists():
            continue
        entries.append(
            _normalize_entry(
                entry_id=f"loanapp-{loan.id}",
                transaction_type=TransactionType.LOAN_APPLICATION,
                created_at=loan.created_at,
                status=loan.status,
                amount=loan.amount_requested,
                reference_id=loan.loan_id,
                details={
                    "amount_approved": float(loan.amount_approved) if loan.amount_approved else None,
                    "purpose": loan.purpose,
                    "loan_tier": loan.loan_tier,
                },
            )
        )

    for disb in (
        LoanDisbursement.objects.filter(loan_application__user=user)
        .select_related("loan_application", "meter")
        .order_by("-created_at")[:MAX_PER_SOURCE]
    ):
        ref = disb.loan_application.loan_id
        if TransactionLog.objects.filter(
            user=user,
            transaction_type=TransactionType.LOAN_DISBURSEMENT,
            reference_id=ref,
        ).exists():
            continue
        entries.append(
            _normalize_entry(
                entry_id=f"loandisb-{disb.id}",
                transaction_type=TransactionType.LOAN_DISBURSEMENT,
                created_at=disb.created_at,
                status="COMPLETED",
                amount=disb.disbursed_amount,
                units=disb.units_disbursed,
                reference_id=ref,
                details={
                    "loan_id": ref,
                    "meter_no": disb.meter.meter_no if disb.meter_id else None,
                },
            )
        )

    entries.sort(key=lambda item: item["_sort_at"] or datetime.min, reverse=True)
    for item in entries:
        item.pop("_sort_at", None)
    return entries


def filter_history(
    entries: list[dict[str, Any]],
    *,
    transaction_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    filtered = entries
    if transaction_type:
        filtered = [e for e in filtered if e["transaction_type"] == transaction_type]
    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        filtered = [
            e for e in filtered
            if e.get("created_at") and datetime.strptime(e["created_at"], "%Y-%m-%d %H:%M:%S") >= start_dt
        ]
    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        filtered = [
            e for e in filtered
            if e.get("created_at") and datetime.strptime(e["created_at"], "%Y-%m-%d %H:%M:%S") <= end_dt
        ]
    return filtered


def paginate_history(entries: list[dict[str, Any]], page: int, page_size: int) -> tuple[list[dict[str, Any]], int]:
    total = len(entries)
    start = (page - 1) * page_size
    end = start + page_size
    return entries[start:end], total


def summarize_history(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute statement-style totals for a filtered transaction set."""
    money_in = Decimal("0")
    money_out = Decimal("0")
    units_in = Decimal("0")
    units_out = Decimal("0")

    for entry in entries:
        tx_type = str(entry.get("transaction_type") or "")
        direction = str((entry.get("details") or {}).get("direction") or "").upper()
        amount = entry.get("amount")
        units = entry.get("units")
        amount_dec = Decimal(str(amount)) if amount is not None else Decimal("0")
        units_dec = Decimal(str(units)) if units is not None else Decimal("0")

        if tx_type in {"LOAN_DISBURSEMENT"}:
            money_in += amount_dec
        elif tx_type in {"UNIT_PURCHASE", "LOAN_REPAYMENT"}:
            money_out += amount_dec

        if tx_type == "UNIT_SHARE":
            if direction == "IN":
                units_in += units_dec
            elif direction == "OUT":
                units_out += units_dec
        elif tx_type in {"UNIT_PURCHASE", "LOAN_DISBURSEMENT"}:
            units_in += units_dec
        elif tx_type in {"TOKEN_GENERATE", "WALLET_LOAD_AMI", "LOAN_REPAYMENT"}:
            units_out += units_dec

    return {
        "transactions_count": len(entries),
        "money_in_ugx": float(money_in),
        "money_out_ugx": float(money_out),
        "money_net_ugx": float(money_in - money_out),
        "units_in_kwh": float(units_in),
        "units_out_kwh": float(units_out),
        "units_net_kwh": float(units_in - units_out),
    }
