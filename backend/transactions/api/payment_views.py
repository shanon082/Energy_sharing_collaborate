"""New verified Mobile Money entry points for purchases and self-repayment."""

from decimal import Decimal, InvalidOperation, ROUND_CEILING
import uuid

from django.db import transaction as db_transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Wallet as AccountWallet
from loan.models import LoanApplication, LoanRepayment
from meter.models import Meter
from transactions.models import PaymentIntent, Transaction
from transactions.payment_settlement import (
    PaymentSettlementError, create_purchase_intent, create_repayment_intent,
    reconcile_payment, request_payment, require_real_ugx_provider,
)
from wallet.models import UnitBalance


def _positive_amount(raw):
    try:
        amount = Decimal(str(raw))
        # MTN's production request sends whole UGX. Reject fractions rather
        # than silently charging less than the amount recorded in the intent.
        if not amount.is_finite() or amount <= 0 or amount != amount.to_integral_value():
            raise ValueError
        return amount
    except (InvalidOperation, TypeError, ValueError):
        return None


def _unavailable(exc):
    return Response({"code": "VERIFIED_PAYMENT_UNAVAILABLE", "message": str(exc)}, status=503)


def _request_result(intent, phone):
    # The request to the payment provider must run after the intent is committed.
    result = request_payment(intent, phone)
    if result.get("status") != "PENDING":
        return Response({
            "code": "PAYMENT_INITIATION_UNCONFIRMED",
            "message": "Payment request was not confirmed. No balance changed; status will be reconciled.",
            "external_id": str(intent.provider_reference),
        }, status=502)
    return Response({
        "status": "PENDING",
        "message": "Approve the Mobile Money request, then check payment status.",
        "external_id": str(intent.provider_reference),
        "transaction_id": intent.purchase_id,
        "payment_reference": str(intent.provider_reference),
        "payment_mode": "momo",
    })


@method_decorator(db_transaction.non_atomic_requests, name="dispatch")
class VerifiedPurchaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if str(request.data.get("payment_source", "PHONE")).upper() not in {"PHONE", "MOBILE_MONEY"}:
            return Response({"code": "WALLET_PROVENANCE_UNKNOWN", "message": "Wallet spending is unavailable until money-balance provenance is reconciled."}, status=409)
        try:
            require_real_ugx_provider()
        except PaymentSettlementError as exc:
            return _unavailable(exc)
        amount = _positive_amount(request.data.get("amount"))
        phone = str(request.data.get("phone_number") or "").strip()
        if amount is None or not phone:
            return Response({"error": "A positive UGX amount and phone number are required."}, status=400)
        from loan.services import user_can_purchase_units
        can_buy, reason = user_can_purchase_units(request.user)
        if not can_buy:
            return Response({"error": reason}, status=409)
        meter_no = str(request.data.get("meter_no") or "").strip()
        if not meter_no:
            return Response({"error": "Select the intended meter explicitly."}, status=400)
        meter = Meter.objects.filter(
            user=request.user, is_deleted=False, status=Meter.STATUS_ACTIVE,
            meter_no=meter_no,
        ).first()
        if meter is None:
            return Response({"error": "Select one active meter assigned to your account."}, status=400)
        with db_transaction.atomic():
            wallet = AccountWallet.objects.filter(user=request.user).order_by("-create_date").first()
            if wallet is None:
                wallet = AccountWallet.objects.create(user=request.user)
            reference = uuid.uuid4()
            purchase = Transaction.objects.create(
                wallet=wallet, amount=amount, phone_number=phone,
                status="PENDING", transaction_reference=str(reference),
                message="Pending verified Mobile Money electricity purchase",
            )
            intent = create_purchase_intent(
                owner=request.user, meter=meter, transaction=purchase, amount=amount,
                reference=reference,
            )
        return _request_result(intent, phone)


@method_decorator(db_transaction.non_atomic_requests, name="dispatch")
class VerifiedPurchaseStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        purchase_id = request.data.get("transaction_id")
        try:
            purchase_id = int(purchase_id)
        except (TypeError, ValueError):
            return Response({"error": "Payment not found."}, status=404)
        intent = PaymentIntent.objects.filter(
            purchase_id=purchase_id, owner=request.user, purpose=PaymentIntent.PURCHASE,
        ).first()
        if intent is None:
            return Response({"error": "Payment not found or requires manual legacy reconciliation."}, status=404)
        try:
            intent, _ = reconcile_payment(intent.pk)
        except PaymentSettlementError as exc:
            return Response({"code": "PAYMENT_VERIFICATION_FAILED", "message": str(exc)}, status=409)
        payload = {"status": "SUCCESS" if intent.status == PaymentIntent.SETTLED else intent.status,
                   "transaction_id": intent.purchase_id}
        if intent.status == PaymentIntent.SETTLED:
            log = intent.owner.transaction_logs.filter(
                transaction_type="UNIT_PURCHASE", reference_id=str(intent.provider_reference),
            ).first()
            payload["units_purchased"] = float(log.units) if log and log.units else 0
            payload["amount_received_ugx"] = str(intent.amount)
            payload["purchase_billed_ugx"] = str(intent.purchase_billed_ugx) if intent.purchase_billed_ugx is not None else None
            payload["purchase_residual_ugx"] = str(intent.purchase_residual_ugx) if intent.purchase_residual_ugx is not None else None
            payload["requires_reconciliation"] = intent.purchase_residual_ugx is None or intent.purchase_residual_ugx > 0
            payload["wallet_balance"] = float(UnitBalance.objects.filter(user=request.user).values_list("balance", flat=True).first() or 0)
            payload["transaction"] = {
                "amount": str(intent.amount),
                "timestamp": intent.settled_at.isoformat() if intent.settled_at else None,
            }
            payload["message"] = (
                "Payment received but no energy could be allocated; the full amount requires reconciliation."
                if payload["units_purchased"] == 0 else
                "Verified payment settled; the remaining UGX requires reconciliation."
                if payload["requires_reconciliation"] else
                "Verified payment settled into your unit balance."
            )
        else:
            payload["message"] = "No energy has been credited; payment is still being verified." if intent.status == PaymentIntent.PENDING else "Payment failed; no energy was credited."
        return Response(payload)


@method_decorator(db_transaction.non_atomic_requests, name="dispatch")
class VerifiedLoanRepaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, loan_id=None):
        try:
            require_real_ugx_provider()
        except PaymentSettlementError as exc:
            return _unavailable(exc)
        if loan_id is None:
            from loan.services import get_repayable_loan
            loan = get_repayable_loan(request.user)
        else:
            loan = LoanApplication.objects.filter(pk=loan_id, user=request.user).first()
        if loan is None or loan.status not in {"DISBURSED", "DEFAULTED"}:
            return Response({"error": "No repayable loan belonging to your account was found."}, status=404)
        amount = _positive_amount(request.data.get("amount"))
        phone = str(request.data.get("phone_number") or "").strip()
        if amount is None or not phone or loan.outstanding_balance <= 0 or amount > loan.outstanding_balance.to_integral_value(rounding=ROUND_CEILING):
            return Response({"error": "A valid UGX amount within your outstanding debt and a phone number are required."}, status=400)
        with db_transaction.atomic():
            loan = LoanApplication.objects.select_for_update().get(pk=loan.pk)
            pending = PaymentIntent.objects.filter(
                repayment__loan=loan, purpose=PaymentIntent.LOAN_REPAYMENT,
                status=PaymentIntent.PENDING,
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
            available = loan.outstanding_balance - pending
            if loan.status not in {"DISBURSED", "DEFAULTED"} or available <= 0 or amount > available.to_integral_value(rounding=ROUND_CEILING):
                return Response({"error": "Amount exceeds debt available after pending repayments."}, status=409)
            repayment = LoanRepayment.objects.create(
                loan=loan, amount_paid=amount, units_paid=0,
                payment_reference=f"REPAY-{uuid.uuid4().hex[:32]}",
                payment_method="MOBILE_MONEY", payment_status="PENDING",
                momo_phone_number=phone,
                is_on_time=not loan.due_date or timezone.now() <= loan.due_date,
            )
            intent = create_repayment_intent(owner=request.user, repayment=repayment)
            repayment.momo_external_id = str(intent.provider_reference)
            repayment.save(update_fields=["momo_external_id"])
        return _request_result(intent, phone)


@method_decorator(db_transaction.non_atomic_requests, name="dispatch")
class VerifiedLoanPaymentStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, external_id):
        try:
            external_id = uuid.UUID(external_id)
        except (TypeError, ValueError):
            return Response({"error": "Payment not found."}, status=404)
        intent = PaymentIntent.objects.filter(
            provider_reference=external_id, owner=request.user,
            purpose=PaymentIntent.LOAN_REPAYMENT,
        ).first()
        if intent is None:
            return Response({"error": "Payment not found or requires manual legacy reconciliation."}, status=404)
        try:
            intent, _ = reconcile_payment(intent.pk)
        except PaymentSettlementError as exc:
            return Response({"code": "PAYMENT_VERIFICATION_FAILED", "message": str(exc)}, status=409)
        loan = LoanApplication.objects.get(pk=intent.repayment.loan_id, user=request.user)
        return Response({
            "payment_status": "SUCCESS" if intent.status == PaymentIntent.SETTLED else intent.status,
            "amount": str(intent.amount),
            "amount_applied_ugx": str(intent.repayment.amount_applied_ugx if intent.repayment.amount_applied_ugx is not None else intent.repayment.amount_paid) if intent.status == PaymentIntent.SETTLED else None,
            "excess_ugx": str(intent.repayment.excess_ugx) if intent.status == PaymentIntent.SETTLED else None,
            "transaction_id": intent.provider_transaction_id or None,
            "outstanding_balance": str(loan.outstanding_balance),
            "loan_status": loan.status,
            "message": ("Repayment verified; any excess requires reconciliation." if intent.repayment.excess_ugx else "Repayment verified and debt reduced.") if intent.status == PaymentIntent.SETTLED else "No debt reduction until provider verification succeeds.",
        })
