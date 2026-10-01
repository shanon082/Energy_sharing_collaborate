"""Exact, owner-bound payment receipts for the consumer app."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from transactions.models import PaymentIntent


class MobilePaymentReceiptsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.user_role != User.CLIENT:
            return Response({"code": "CONSUMER_ONLY"}, status=403)
        intents = PaymentIntent.objects.filter(owner=request.user).select_related(
            "meter", "repayment", "repayment__loan",
        ).order_by("-initiated_at")[:50]
        return Response({"receipts": [{
            "external_id": str(intent.provider_reference),
            "purpose": intent.purpose, "status": intent.status,
            "amount_ugx": str(intent.amount), "currency": intent.currency,
            "meter_no": intent.meter.meter_no if intent.meter else None,
            "loan_id": intent.repayment.loan.loan_id if intent.repayment_id else None,
            "purchase_id": intent.purchase_id,
            "purchase_billed_ugx": str(intent.purchase_billed_ugx) if intent.purchase_billed_ugx is not None else None,
            "purchase_residual_ugx": str(intent.purchase_residual_ugx) if intent.purchase_residual_ugx is not None else None,
            "initiated_at": intent.initiated_at.isoformat(),
            "settled_at": intent.settled_at.isoformat() if intent.settled_at else None,
        } for intent in intents]})
