"""
Shared loan business logic — single source of truth for web API and USSD.

All channels must call these helpers so loan detection, blocking rules, and
mutations stay aligned with the web portal (`loan.api.views`).
"""
from __future__ import annotations

from backend.features import require_feature

import logging
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from accounts.models import generate_random_string
from loan.models import ElectricityTariff, LoanApplication, LoanDisbursement, LoanRepayment, get_tier_by_score
from loan.scoring import calculate_weighted_credit_score, get_or_create_credit_signal
from loan.trust_ladder import (
    STARTER_MAX_LOAN,
    apply_trust_to_score,
    compute_repayment_trust,
    effective_max_loan,
)
from meter.models import Meter, MeterNotification
from meter.allocation_service import authorize_loan_allocation, quantize_source_kwh
from meter.notifications import create_system_notification
from transactions.models import TransactionLog, TransactionType, UnitTransaction
from utils.general import dispatch_task
from loan.tenure import validate_tenure_months
from utils.billing import calculate_units_from_payment, get_active_domestic_tariff
from wallet.models import UnitBalance
from accounts.tasks import (
    handle_send_loan_application_email,
    handle_send_loan_disbursed_email,
    handle_send_loan_repayment_email,
    handle_send_third_party_loan_payment_to_owner,
    handle_send_third_party_loan_payment_to_payer,
)

logger = logging.getLogger(__name__)

# Status sets aligned with `LoanApplicationView.create` and purchase blocking.
APPLY_BLOCK_STATUSES = ("PENDING", "APPROVED", "DISBURSED")
TERMINAL_LOAN_STATUSES = ("COMPLETED", "REJECTED")
DEBT_LOAN_STATUSES = ("DISBURSED", "DEFAULTED")

PURCHASE_BLOCK_MESSAGE = (
    "You cannot buy units while you have a pending or incomplete loan. "
    "Please clear your loan first."
)
APPLY_BLOCK_MESSAGE = (
    "You already have an active loan. Please complete repayment before applying for a new one."
)

PLATFORM_MAX_LOAN = 200_000
MIN_LOAN_AMOUNT = 5_000
MIN_LOAN_CREDIT_SCORE = 75


class LoanOperationError(Exception):
    """Raised when a loan action is not allowed or fails validation."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def incomplete_loans_queryset(user):
    return LoanApplication.objects.filter(user=user).exclude(status__in=TERMINAL_LOAN_STATUSES)


def reconcile_user_loan_statuses(user) -> int:
    """
    Persist the derived terminal state for loans that were fully paid but still
    carry an old active status, and retry disbursement for loans stranded at
    APPROVED (e.g. a prior auto-disbursement attempt failed). Runs on every
    loan list/stats fetch so approved credit never stays stuck waiting on a
    customer action - there isn't one.
    """
    updated = 0

    for loan in LoanApplication.objects.filter(user=user, status="APPROVED"):
        try:
            disburse_loan(user, loan.id, channel="RECONCILE")
            updated += 1
        except Exception:
            logger.exception("Retry auto-disbursement failed for loan %s", loan.loan_id)

    loans = LoanApplication.objects.filter(
        user=user,
        status__in=DEBT_LOAN_STATUSES,
    ).prefetch_related("repayments")

    for loan in loans:
        if loan.outstanding_balance <= 0:
            loan.status = "COMPLETED"
            loan.save(update_fields=["status", "updated_at"])
            updated += 1

    return updated


def get_blocking_loan_state(user) -> dict:
    """
    Single source of truth for whether loans should block unit purchases.
    Pending applications block because they are unresolved; paid loans do not.
    """
    reconcile_user_loan_statuses(user)

    loans = LoanApplication.objects.filter(user=user)
    pending_applications = loans.filter(status="PENDING").count()
    debt_loans = []
    outstanding_balance = Decimal("0")

    for loan in loans.filter(status__in=DEBT_LOAN_STATUSES).prefetch_related("repayments"):
        balance = loan.outstanding_balance
        if balance > 0:
            debt_loans.append(loan)
            outstanding_balance += balance

    return {
        "pending_applications": pending_applications,
        "active_loans": len(debt_loans),
        "outstanding_balance": outstanding_balance,
        "has_blocking_loan": pending_applications > 0 or outstanding_balance > 0,
    }


def user_can_apply_for_loan(user) -> tuple[bool, str]:
    reconcile_user_loan_statuses(user)
    if LoanApplication.objects.filter(user=user, status__in=APPLY_BLOCK_STATUSES).exists():
        return False, APPLY_BLOCK_MESSAGE
    return True, ""


def user_can_purchase_units(user) -> tuple[bool, str]:
    state = get_blocking_loan_state(user)
    if state["has_blocking_loan"]:
        return False, PURCHASE_BLOCK_MESSAGE
    return True, ""


def get_loan_eligibility(user) -> dict:
    """Credit score, tier, and amount caps used by web, USSD, and stats API."""
    from accounts.models import User
    from loan.scoring import profile_scoring_fields_complete

    user = User.objects.filter(pk=user.pk).first() or user
    access = resolve_user_loan_access(user)
    access["profile_complete_for_scoring"] = profile_scoring_fields_complete(user)
    return access


def resolve_user_loan_access(user) -> dict:
    """
    Unified loan access: starter 30k for everyone in good standing; trust ladder
    raises cap/score after on-time repayments.
    """
    credit_signal = get_or_create_credit_signal(user)
    profile_score = max(0, min(calculate_weighted_credit_score(credit_signal), 100))
    trust = compute_repayment_trust(user)
    credit_score = apply_trust_to_score(profile_score, trust)
    tier_info = _determine_loan_tier(credit_score)

    if tier_info:
        loan_tier, tier_max, interest_rate = tier_info
    else:
        loan_tier, tier_max, interest_rate = "STARTER", float(STARTER_MAX_LOAN), 12.0

    max_eligible = effective_max_loan(tier_max, trust, PLATFORM_MAX_LOAN)
    is_eligible = max_eligible >= MIN_LOAN_AMOUNT and credit_score >= MIN_LOAN_CREDIT_SCORE

    return {
        "credit_score": credit_score,
        "profile_score": profile_score,
        "loan_tier": loan_tier,
        "max_eligible_amount": max_eligible,
        "platform_max_loan": PLATFORM_MAX_LOAN,
        "starter_max_loan": STARTER_MAX_LOAN,
        "min_loan_amount": MIN_LOAN_AMOUNT,
        "min_credit_score": MIN_LOAN_CREDIT_SCORE,
        "is_loan_eligible": is_eligible,
        "interest_rate": float(interest_rate) if interest_rate is not None else None,
        "credit_signal_source": getattr(credit_signal, "source", None),
        "trust_level": trust.trust_level,
        "trust_cap": trust.trust_cap,
        "loans_completed_on_time": trust.on_time_completions,
        "loans_completed_late": trust.late_completions,
        "loans_defaulted": trust.defaulted_count,
        "loan_overdue": trust.active_overdue,
    }


def get_user_loan_stats(user) -> dict:
    """Same payload as ``GET /api/v1/loans/stats/``."""
    reconcile_user_loan_statuses(user)
    loans = LoanApplication.objects.filter(user=user)

    blocking_state = get_blocking_loan_state(user)
    pending_applications = blocking_state["pending_applications"]
    active_loans = blocking_state["active_loans"]
    approved_loans = loans.filter(status="APPROVED").count()
    total_loans = loans.count()

    total_borrowed = (
        loans.filter(status__in=["APPROVED", "DISBURSED", "COMPLETED", "DEFAULTED"])
        .aggregate(total=Sum("amount_approved"))["total"]
        or Decimal("0.00")
    )

    total_repayments = (
        LoanRepayment.objects.filter(loan__user=user, payment_status="SUCCESS")
        .aggregate(total=Sum("amount_paid"))["total"]
        or Decimal("0.00")
    )

    outstanding_balance = blocking_state["outstanding_balance"]

    eligibility = get_loan_eligibility(user)
    repayable = get_repayable_loan(user)

    return {
        "active_loans": active_loans,
        "pending_applications": pending_applications,
        "approved_loans": approved_loans,
        "total_loans": total_loans,
        "total_borrowed": total_borrowed,
        "total_repayments": total_repayments,
        "outstanding_balance": outstanding_balance,
        "has_blocking_loan": blocking_state["has_blocking_loan"],
        "repayable_loan": serialize_repayable_loan(repayable),
        **eligibility,
    }


def get_disbursed_loan_balances(user):
    """Mirrors ``BuyUnitsView._get_active_loan_balances``."""
    reconcile_user_loan_statuses(user)
    loans_with_balance = []
    total_outstanding = Decimal("0")
    for loan in LoanApplication.objects.filter(user=user, status="DISBURSED").order_by(
        "created_at"
    ):
        balance = loan.outstanding_balance
        if balance > 0:
            loans_with_balance.append((loan, balance))
            total_outstanding += balance
    return loans_with_balance, total_outstanding


def get_repayable_loan(user):
    """Most recent disbursed or overdue loan with an outstanding balance."""
    reconcile_user_loan_statuses(user)
    for loan in LoanApplication.objects.filter(user=user, status__in=DEBT_LOAN_STATUSES).order_by(
        "-created_at"
    ):
        if loan.outstanding_balance > 0:
            return loan
    return None


def serialize_repayable_loan(loan: LoanApplication | None) -> dict | None:
    if not loan:
        return None
    return {
        "id": loan.id,
        "loan_id": loan.loan_id,
        "outstanding_balance": float(loan.outstanding_balance),
        "amount_approved": float(loan.amount_approved or 0),
        "due_date": loan.due_date.isoformat() if loan.due_date else None,
    }


def format_repay_loan_menu_ussd(loan: LoanApplication) -> str:
    balance = round(float(loan.outstanding_balance), 2)
    return (
        f"Repay loan\n"
        f"Ref: {loan.loan_id}\n"
        f"Outstanding: UGX {balance:,.2f}\n"
        f"1. Pay full amount\n"
        f"2. Pay partial amount"
    )


def _determine_loan_tier(score):
    tier_info = get_tier_by_score(score)
    if tier_info:
        return tier_info["name"], tier_info["max_amount"], tier_info["interest_rate"]
    return None


def create_loan_application(
    user,
    *,
    amount_requested,
    purpose: str,
    tenure_months: int = 6,
    channel: str = "WEB",
    meter_no: str | None = None,
) -> LoanApplication:
    """
    Same rules as ``LoanApplicationView.create`` (web loan apply).
    """
    can_apply, msg = user_can_apply_for_loan(user)
    if not can_apply:
        raise LoanOperationError(msg)

    meter = Meter.objects.filter(
        user=user, meter_no=meter_no, status=Meter.STATUS_ACTIVE,
    ).first() if meter_no else None
    if meter is None:
        raise LoanOperationError("Select an active meter assigned to your account before applying.")

    try:
        amount_requested = Decimal(str(amount_requested))
    except (InvalidOperation, TypeError, ValueError):
        raise LoanOperationError("Invalid amount.")

    if (not amount_requested.is_finite() or
            amount_requested != amount_requested.to_integral_value()):
        raise LoanOperationError("Use a whole UGX loan amount.")
    if amount_requested < Decimal("5000") or amount_requested > Decimal("200000"):
        raise LoanOperationError("Amount out of range. Use 5000 to 200000.")

    try:
        tenure_months = validate_tenure_months(tenure_months)
    except ValueError as exc:
        raise LoanOperationError(str(exc)) from exc

    tariff = get_active_domestic_tariff()
    access = resolve_user_loan_access(user)
    credit_score = access["credit_score"]
    max_eligible = access["max_eligible_amount"]
    tier_name = access["loan_tier"]
    interest_rate = access["interest_rate"] or 12.0

    if not access["is_loan_eligible"]:
        raise LoanOperationError(
            f"Loan limit is UGX {max_eligible:,}. "
            "Repay any overdue loan to restore your borrowing limit."
        )

    amount_approved = min(Decimal(str(max_eligible)), amount_requested)

    status_value = "APPROVED" if amount_approved > 0 else "REJECTED"
    rejection_reason = "" if amount_approved > 0 else "Amount below minimum or limit exceeded"

    loan = LoanApplication.objects.create(
        user=user,
        intended_meter=meter,
        purpose=purpose,
        amount_requested=amount_requested,
        amount_approved=amount_approved if amount_approved > 0 else None,
        tenure_months=tenure_months,
        credit_score=int(credit_score),
        loan_tier=str(tier_name).upper() if tier_name else None,
        interest_rate=interest_rate,
        tariff=tariff,
        status=status_value,
        rejection_reason=rejection_reason,
    )

    TransactionLog.objects.create(
        user=user,
        transaction_type=TransactionType.LOAN_APPLICATION,
        amount=amount_requested,
        status=loan.status,
        reference_id=loan.loan_id,
        details={
            "channel": channel,
            "purpose": purpose,
            "tenure_months": tenure_months,
            "credit_score": credit_score,
            "loan_tier": tier_name,
            "amount_approved": float(amount_approved) if amount_approved else 0,
        },
    )
    create_system_notification(
        user=user,
        notification_type=MeterNotification.TYPE_LOAN_APPLICATION,
        message=(
            f"Loan application {loan.loan_id}: {loan.status}. "
            f"Requested UGX {float(amount_requested):,.2f}, "
            f"approved UGX {float(amount_approved):,.2f}."
        ),
        units_kwh=Decimal("0"),
    )
    dispatch_task(
        handle_send_loan_application_email,
        user.id,
        loan.loan_id,
        loan.status,
        float(amount_requested),
        float(amount_approved or 0),
    )

    if loan.status == "APPROVED":
        try:
            disburse_loan(user, loan.id, channel=channel)
            loan.refresh_from_db()
        except Exception:
            # Leave the loan APPROVED rather than failing the application -
            # it can be disbursed later (e.g. via the admin panel).
            logger.exception("Auto-disbursement failed for loan %s", loan.loan_id)

    return loan


def _resolve_loan_for_disburse(user, loan_id=None):
    if loan_id in (None, "", "0", 0):
        loan = (
            LoanApplication.objects.filter(user=user, status="APPROVED")
            .order_by("-created_at")
            .first()
        )
    else:
        try:
            loan = LoanApplication.objects.get(id=int(loan_id), user=user)
        except (ValueError, LoanApplication.DoesNotExist):
            raise LoanOperationError("Loan not found.") from None
    return loan


def disburse_loan(user, loan_id=None, *, channel: str = "WEB", meter_no: str | None = None) -> dict:
    """Same rules as ``LoanDisbursementView.post``."""
    loan = _resolve_loan_for_disburse(user, loan_id)
    if not loan:
        raise LoanOperationError("No approved loan found.")

    with transaction.atomic():
        # Lock the row so two concurrent disbursement attempts (e.g. the apply
        # request racing a reconcile-triggered retry) can't both pass the
        # APPROVED check and double-credit the wallet.
        loan = LoanApplication.objects.select_for_update().get(pk=loan.pk)
        if loan.status != "APPROVED":
            raise LoanOperationError(f"Loan is {loan.status}. Only APPROVED loans can be disbursed.")
        if not loan.amount_approved or loan.amount_approved <= 0:
            raise LoanOperationError("Loan amount not approved.")
        if Decimal(str(loan.amount_approved)) != Decimal(str(loan.amount_approved)).to_integral_value():
            raise LoanOperationError("Approved loan principal must be whole UGX before disbursement.")

        meter = loan.intended_meter
        if meter is None and meter_no:
            meter = Meter.objects.filter(
                user=user, meter_no=meter_no, status=Meter.STATUS_ACTIVE,
            ).first()
            if meter is not None:
                loan.intended_meter = meter
                loan.save(update_fields=["intended_meter", "updated_at"])
        if meter is None:
            raise LoanOperationError("An explicit owned meter selection is required before disbursement.")
        if (meter.user_id != user.pk or meter.status != Meter.STATUS_ACTIVE or
                meter.is_deleted or (meter_no and meter.meter_no != meter_no)):
            raise LoanOperationError("The selected loan meter is no longer assigned and active.")

        if loan.tariff:
            # Use the tariff stored on the loan, matching its quote even if a
            # newer tariff became active before disbursement.
            calculated_units, _ = calculate_units_from_payment(
                Decimal(str(loan.amount_approved)), user, tariff=loan.tariff,
                apply_deductions=False,
            )
            units_to_disburse = quantize_source_kwh(calculated_units)
        else:
            units_to_disburse = quantize_source_kwh(Decimal(loan.amount_approved) / Decimal("500"))

        disbursement = LoanDisbursement.objects.create(
            loan_application=loan,
            disbursed_amount=loan.amount_approved,
            units_disbursed=units_to_disburse,
            meter=meter,
        )

        loan.status = "DISBURSED"
        loan.save()

        allocation = authorize_loan_allocation(disbursement, units_to_disburse)

        # An approved loan authorizes energy before repayment. Store the
        # allocation in kWh; the legacy Wallet.balance is labelled UGX and
        # cannot safely hold energy. Physical delivery needs a bound device
        # acknowledgement protocol and is intentionally deferred.
        unit_balance, _ = UnitBalance.objects.select_for_update().get_or_create(user=user)
        unit_balance.add_units(
            units_to_disburse,
            description=f"Loan {loan.loan_id} disbursement",
            reference=loan.loan_id,
        )
        push_ok = False
        push_msg = "Allocation recorded; physical meter delivery awaits a validated device protocol."

        TransactionLog.objects.create(
            user=user,
            transaction_type=TransactionType.LOAN_DISBURSEMENT,
            amount=loan.amount_approved,
            units=units_to_disburse,
            status="COMPLETED",
            reference_id=loan.loan_id,
            details={
                "channel": channel,
                "units_disbursed": float(units_to_disburse),
                "meter_push": {"status": "DEFERRED", "message": push_msg},
            },
        )

        UnitTransaction.objects.create(
            sender=user,
            receiver=user,
            units=units_to_disburse,
            direction="IN",
            status="COMPLETED",
            message=f"Loan disbursement to wallet - {loan.loan_id}",
        )
    create_system_notification(
        user=user,
        notification_type=MeterNotification.TYPE_LOAN_DISBURSEMENT,
        meter=meter,
        message=(
            f"Loan {loan.loan_id} disbursed: {round(float(units_to_disburse), 2):.2f} kWh "
            f"credited to wallet."
        ),
        units_kwh=Decimal("0"),
    )
    dispatch_task(
        handle_send_loan_disbursed_email,
        user.id,
        loan.loan_id,
        float(loan.amount_approved or 0),
        float(units_to_disburse),
    )

    return {
        "loan_id": loan.loan_id,
        "loan_pk": loan.id,
        "units_disbursed": round(float(units_to_disburse), 2),
        "allocation_id": allocation.pk,
        "meter_no": meter.meter_no,
        "meter_push_ok": push_ok,
        "meter_push_message": push_msg,
    }


def _payment_on_time(loan) -> bool:
    if not loan.due_date:
        return True
    return timezone.now() <= loan.due_date


def _resolve_loan_for_repay(user, loan_id=None):
    if loan_id in (None, "", "0", 0):
        loan = get_repayable_loan(user)
        if not loan:
            raise LoanOperationError("No active loan to repay.")
        return loan
    try:
        return LoanApplication.objects.get(id=int(loan_id), user=user)
    except (ValueError, LoanApplication.DoesNotExist):
        raise LoanOperationError("Loan not found.") from None


def repay_loan(
    user,
    loan_id,
    amount,
    *,
    channel: str = "WEB",
    payment_method: str = "CASH",
    paid_by_user=None,
    is_anonymous: bool = False,
) -> dict:
    """Same rules as ``LoanRepaymentView.post`` (web repayment)."""
    # Only new third-party activity is gated; own repayment remains available.
    if is_anonymous or (paid_by_user is not None and paid_by_user.pk != user.pk):
        require_feature("third_party_repayment")
    loan = _resolve_loan_for_repay(user, loan_id)

    # This legacy service records SUCCESS without proof of funds. New repayments
    # are handled by transactions.payment_settlement after provider verification.
    raise LoanOperationError("Unverified repayment is disabled; use verified Mobile Money repayment.")

    if loan.status != "DISBURSED":
        raise LoanOperationError("Loan is not disbursed or already completed")

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise LoanOperationError("Invalid amount.")

    if amount <= 0:
        raise LoanOperationError("Invalid amount")

    current_balance = loan.outstanding_balance
    if amount > current_balance:
        raise LoanOperationError(
            f"Amount exceeds outstanding balance of {current_balance} UGX"
        )

    if loan.tariff:
        units_equivalent = loan.calculate_units_from_amount(amount)
    else:
        units_equivalent = round(amount / 500, 2)

    with transaction.atomic():
        payment_ref = generate_random_string(12)
        LoanRepayment.objects.create(
            loan=loan,
            amount_paid=amount,
            units_paid=units_equivalent,
            payment_reference=payment_ref,
            is_on_time=_payment_on_time(loan),
            payment_method=payment_method,
            payment_status="SUCCESS",
            paid_by=paid_by_user,
            is_anonymous=is_anonymous,
        )

        meter = Meter.objects.filter(user=user, is_deleted=False).first()
        if not meter:
            raise LoanOperationError("Meter not found")
        meter.units += Decimal(str(units_equivalent))
        meter.save()

        TransactionLog.objects.create(
            user=user,
            transaction_type=TransactionType.LOAN_REPAYMENT,
            amount=amount,
            units=units_equivalent,
            status="COMPLETED",
            reference_id=loan.loan_id,
            details={
                "channel": channel,
                "payment_reference": payment_ref,
                "units_added": float(units_equivalent),
                "loan_id": loan.loan_id,
                "payment_method": payment_method,
            },
        )

        try:
            UnitTransaction.objects.create(
                sender=user,
                receiver=user,
                units=units_equivalent,
                meter=meter,
                direction="IN",
                status="COMPLETED",
                message=f"Loan repayment for {loan.loan_id}",
            )
        except Exception as exc:
            logger.warning("UnitTransaction creation failed during repayment: %s", exc)

        loan.refresh_from_db()
        message = "Payment successful"
        if loan.outstanding_balance <= 0:
            loan.status = "COMPLETED"
            loan.save()
            TransactionLog.objects.create(
                user=user,
                transaction_type=TransactionType.LOAN_COMPLETION,
                amount=0,
                status="COMPLETED",
                reference_id=loan.loan_id,
                details={"message": "Loan fully repaid", "channel": channel},
            )
            message = "Loan fully repaid! Thank you."

    loan.refresh_from_db()
    is_fully_repaid = loan.status == "COMPLETED"
    is_third_party = paid_by_user is not None and paid_by_user.id != user.id

    if is_third_party:
        payer_name = (
            f"{paid_by_user.first_name} {paid_by_user.last_name}".strip()
            or paid_by_user.email
        )
        payer_display = "an anonymous benefactor" if is_anonymous else payer_name
        owner_name = f"{user.first_name} {user.last_name}".strip() or user.email
        verb = "fully repaid" if is_fully_repaid else "partially paid"
        owner_msg = (
            f"Hello {user.first_name or 'there'}, your loan {loan.loan_id} has been "
            f"{verb} by {payer_display}."
        )
        payer_msg = (
            f"You {verb} {owner_name}'s loan {loan.loan_id} of UGX {amount:,.2f}."
        )
        create_system_notification(
            user=user,
            notification_type=MeterNotification.TYPE_LOAN_REPAYMENT,
            message=owner_msg,
            units_kwh=Decimal(str(units_equivalent)),
        )
        create_system_notification(
            user=paid_by_user,
            notification_type=MeterNotification.TYPE_LOAN_REPAYMENT,
            message=payer_msg,
            units_kwh=Decimal("0"),
        )
        dispatch_task(
            handle_send_third_party_loan_payment_to_owner,
            user.id,
            loan.loan_id,
            amount,
            payer_display,
            is_fully_repaid,
        )
        dispatch_task(
            handle_send_third_party_loan_payment_to_payer,
            paid_by_user.id,
            owner_name,
            loan.loan_id,
            amount,
            is_fully_repaid,
        )
    else:
        repayment_message = (
            f"Loan {loan.loan_id} fully repaid. Outstanding balance: UGX 0.00."
            if is_fully_repaid
            else f"Loan {loan.loan_id} repayment of UGX {amount:,.2f} received. Remaining: UGX {loan.outstanding_balance:,.2f}."
        )
        create_system_notification(
            user=user,
            notification_type=MeterNotification.TYPE_LOAN_REPAYMENT,
            message=repayment_message,
            units_kwh=Decimal(str(units_equivalent)),
        )
        dispatch_task(
            handle_send_loan_repayment_email,
            user.id,
            loan.loan_id,
            amount,
            float(loan.outstanding_balance),
            is_fully_repaid,
        )
    return {
        "message": message,
        "loan_id": loan.loan_id,
        "units_added": round(float(units_equivalent), 2),
        "outstanding_balance": loan.outstanding_balance,
        "loan_status": loan.status,
        "payment_reference": payment_ref,
    }


def format_loan_stats_ussd(stats: dict) -> str:
    blocking = "Yes" if stats.get("has_blocking_loan") else "No"
    score = stats.get("credit_score", 0)
    tier = stats.get("loan_tier") or "None"
    eligible = stats.get("max_eligible_amount", 0)
    platform_max = stats.get("platform_max_loan", PLATFORM_MAX_LOAN)
    return (
        f"Loan stats\n"
        f"Credit score: {score}/100\n"
        f"Tier: {tier}\n"
        f"Your limit: UGX {eligible:,}\n"
        f"Platform max: UGX {platform_max:,}\n"
        f"Pending: {stats['pending_applications']}\n"
        f"Active: {stats['active_loans']}\n"
        f"Outstanding: UGX {round(stats['outstanding_balance'], 2)}\n"
        f"Blocking purchases: {blocking}"
    )


def format_loan_apply_preview_ussd(stats: dict) -> str:
    score = stats.get("credit_score", 0)
    min_score = stats.get("min_credit_score", MIN_LOAN_CREDIT_SCORE)
    tier = stats.get("loan_tier") or "None"
    eligible = stats.get("max_eligible_amount", 0)
    platform_max = stats.get("platform_max_loan", PLATFORM_MAX_LOAN)
    trust = stats.get("trust_level", "starter")

    if not stats.get("is_loan_eligible"):
        if stats.get("loan_overdue") or stats.get("trust_level") == "at_risk":
            profile_hint = "Repay overdue loan to restore limit."
        else:
            profile_hint = "Contact support if this persists."
        return (
            f"Apply for loan\n"
            f"Score: {score}/100 (min {min_score})\n"
            f"Not eligible yet.\n"
            f"{profile_hint}"
        )

    trust_note = ""
    if trust == "starter":
        trust_note = f" (starter UGX {eligible:,})"
    elif trust == "building":
        trust_note = " (trust building)"

    return (
        f"Apply for loan\n"
        f"Score: {score}/100\n"
        f"Tier: {tier}\n"
        f"Your limit: UGX {eligible:,}{trust_note}\n"
        f"Platform max: UGX {platform_max:,}\n"
        f"Enter amount UGX ({MIN_LOAN_AMOUNT}-{eligible}):"
    )


def format_wallet_loan_summary(stats: dict) -> str:
    if not stats.get("has_blocking_loan"):
        return "Loans: none active"
    parts = []
    if stats["pending_applications"]:
        parts.append(f"{stats['pending_applications']} pending")
    if stats["active_loans"]:
        parts.append(f"{stats['active_loans']} active")
    label = ", ".join(parts) if parts else "open"
    return f"Loans: {label}\nOutstanding: UGX {round(stats['outstanding_balance'], 2)}"
