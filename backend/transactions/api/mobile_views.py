"""Exact, owner-bound payment receipts for the consumer app."""

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import ConsumerAccountPermission
from backend.mobile_reads import read_page
from transactions.models import PaymentIntent, TransactionLog
from rest_framework.exceptions import ValidationError
import uuid


def receipt_record(intent):
    from decimal import Decimal
    from meter.api.mobile_views import application_confirmed
    allocation = getattr(intent, "energy_allocation", None)
    # A receipt and a meter acknowledgement represent different business events.
    applied = sum((row.amount_kwh for row in allocation.deliveries.select_related("allocation", "simulated_command__device")
                   if application_confirmed(row)), Decimal("0")) if allocation else None
    return {
        "external_id": str(intent.provider_reference),
        "client_request_id": str(intent.client_request_id) if intent.client_request_id else None,
        "purpose": intent.purpose, "status": intent.status,
        "amount_ugx": str(intent.amount), "currency": intent.currency,
        "meter_no": intent.meter.meter_no if intent.meter_id else None,
        "loan_id": intent.repayment.loan.loan_id if intent.repayment_id else None,
        "purchase_id": intent.purchase_id,
        "purchase_billed_ugx": str(intent.purchase_billed_ugx) if intent.purchase_billed_ugx is not None else None,
        "purchase_residual_ugx": str(intent.purchase_residual_ugx) if intent.purchase_residual_ugx is not None else None,
        "repayment_applied_ugx": str(intent.repayment.amount_applied_ugx)
            if intent.repayment_id and intent.repayment.amount_applied_ugx is not None else None,
        "repayment_excess_ugx": str(intent.repayment.excess_ugx)
            if intent.repayment_id and intent.repayment.amount_applied_ugx is not None else None,
        "environment": "SIMULATOR" if intent.provider == "SIMULATED" else
            "PROVIDER" if intent.provider == "MTN_PRODUCTION" else "UNCONFIRMED",
        "settlement_recorded": intent.status == PaymentIntent.SETTLED and intent.settled_at is not None,
        "allocated_energy_kwh": str(allocation.amount_kwh) if allocation else None,
        "delivery_confirmed_kwh": str(applied) if applied is not None else None,
        "initiated_at": intent.initiated_at.isoformat(),
        "settled_at": intent.settled_at.isoformat() if intent.settled_at else None,
    }


def owned_receipts(user):
    return PaymentIntent.objects.filter(owner=user).exclude(provider__in=["MTN_SANDBOX", "LOCAL_DEMO"]).select_related("meter", "repayment", "repayment__loan")


class MobilePaymentReceiptsView(APIView):
    permission_classes = [IsAuthenticated, ConsumerAccountPermission]

    def get(self, request):
        if request.user.user_role != User.CLIENT:
            return Response({"code": "CONSUMER_ONLY"}, status=403)
        rows, page = read_page(owned_receipts(request.user), request.query_params)
        return Response({"receipts": [receipt_record(row) for row in rows], "pagination": page})


class MobilePaymentReceiptView(APIView):
    permission_classes = [IsAuthenticated, ConsumerAccountPermission]

    def get(self, request, reference):
        intent = get_object_or_404(owned_receipts(request.user), provider_reference=reference)
        return Response({"receipt": receipt_record(intent)})


class MobilePaymentRecoveryView(APIView):
    """Stored status only, including old pending intents beyond receipt pagination."""
    permission_classes = [IsAuthenticated, ConsumerAccountPermission]

    def get(self, request):
        from meter.models import Meter
        from loan.models import LoanApplication
        purpose = request.query_params.get("purpose")
        rows = owned_receipts(request.user)
        if purpose == PaymentIntent.PURCHASE:
            meter = get_object_or_404(Meter, user=request.user,
                                     meter_no=request.query_params.get("meter_no"), is_deleted=False)
            bound = rows.filter(purpose=purpose, meter=meter)
            pending = rows.filter(purpose=purpose, status=PaymentIntent.PENDING).exists()
        elif purpose == PaymentIntent.LOAN_REPAYMENT:
            loan = get_object_or_404(LoanApplication, user=request.user,
                                    loan_id=request.query_params.get("loan_id"))
            bound = rows.filter(purpose=purpose, repayment__loan=loan)
            pending = bound.filter(status=PaymentIntent.PENDING).exists()
        else:
            raise ValidationError({"purpose": "Use PURCHASE or LOAN_REPAYMENT."})
        reference = request.query_params.get("client_request_id")
        intent = None
        if reference:
            try:
                reference = uuid.UUID(reference)
            except (ValueError, TypeError):
                raise ValidationError({"client_request_id": "Use a UUID."}) from None
            intent = bound.filter(client_request_id=reference).first()
        response = Response({"pending": pending, "receipt": receipt_record(intent) if intent else None,
                             "status_source": "STORED_VERIFIED_SETTLEMENT",
                             "provider_polled": False})
        response["Cache-Control"] = "no-store"
        return response


class MobileTransactionHistoryView(APIView):
    """Historical log as recorded. Ambiguous units are never presented as money."""
    permission_classes = [IsAuthenticated, ConsumerAccountPermission]

    def get(self, request):
        rows, page = read_page(TransactionLog.objects.filter(user=request.user), request.query_params)
        return Response({"transactions": [{
            "id": row.pk, "transaction_type": row.transaction_type,
            "transaction_type_display": row.get_transaction_type_display(),
            "status": row.status, "recorded_amount": str(row.amount) if row.amount is not None else None,
            "recorded_units": str(row.units) if row.units is not None else None,
            "units_confirmed": False, "source": "TRANSACTION_LOG",
            "created_at": row.created_at.isoformat(),
        } for row in rows], "pagination": page})
