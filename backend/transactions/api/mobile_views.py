"""Exact, owner-bound payment receipts for the consumer app."""

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import ConsumerAccountPermission
from backend.mobile_reads import read_page
from transactions.models import PaymentIntent, TransactionLog


def receipt_record(intent):
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
        "initiated_at": intent.initiated_at.isoformat(),
        "settled_at": intent.settled_at.isoformat() if intent.settled_at else None,
    }


def owned_receipts(user):
    return PaymentIntent.objects.filter(owner=user).select_related("meter", "repayment", "repayment__loan")


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
