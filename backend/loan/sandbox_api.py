"""Consumer endpoints share exactly the same sandbox service for web and Android."""
import uuid
from django.db import transaction
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, NotFound

from accounts.permissions import ConsumerAccountPermission
from loan.models import SandboxLoan
from loan.sandbox_service import require_sandbox, policy, assessment, create_quote, apply_loan, loan_record
from transactions.models import PaymentIntent
from transactions.sandbox_payments import create_payment, reconcile_sandbox_payment, receipt
from transactions.payment_settlement import PaymentSettlementError


@method_decorator(transaction.non_atomic_requests, name="dispatch")
class SandboxConsumerView(APIView):
    permission_classes = [IsAuthenticated, ConsumerAccountPermission]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_sandbox()


class SandboxAssessmentView(SandboxConsumerView):
    def get(self, request):
        return Response({"assessment": assessment(request.user), "policy": policy()})


class SandboxQuoteView(SandboxConsumerView):
    def post(self, request):
        purpose = request.data.get("purpose")
        if purpose not in {"LOAN", "PURCHASE"}:
            raise ValidationError({"purpose": "Use LOAN or PURCHASE."})
        meter_id = request.data.get("meter_id")
        if not isinstance(meter_id, int) or isinstance(meter_id, bool) or not 0 < meter_id < 2**63:
            raise ValidationError({"meter_id": "Select a positive test meter ID."})
        quote = create_quote(request.user, meter_id, request.data.get("amount"), purpose)
        return Response({"id": str(quote.pk), "terms_hash": quote.terms_hash, "terms": quote.terms,
                         "expires_at": quote.expires_at.isoformat()}, status=201)


class SandboxLoanView(SandboxConsumerView):
    def get(self, request):
        rows = SandboxLoan.objects.filter(owner=request.user).select_related("energy_allocation").order_by("-created_at")[:100]
        return Response({"loans": [loan_record(row) for row in rows]})

    def post(self, request):
        if request.data.get("accept_test_terms") is not True:
            raise ValidationError({"accept_test_terms": "Review and explicitly accept the sandbox test terms."})
        loan, created = apply_loan(request.user, request.data.get("quote_id"), request.data.get("terms_hash"), request.data.get("client_request_id"))
        return Response({"loan": loan_record(loan), "reused": not created}, status=201 if created else 200)


class SandboxLoanRecoveryView(SandboxConsumerView):
    def get(self, request, request_id):
        loan = SandboxLoan.objects.filter(owner=request.user, client_request_id=request_id).first()
        return Response({"loan": loan_record(loan) if loan else None})


class SandboxPaymentView(SandboxConsumerView):
    def get(self, request):
        rows = PaymentIntent.objects.filter(owner=request.user, provider="MTN_SANDBOX").select_related(
            "sandbox_settlement", "energy_allocation").order_by("-initiated_at")[:100]
        # Pending records are fetched independently, even after 100 historical receipts.
        pending = PaymentIntent.objects.filter(owner=request.user, provider="MTN_SANDBOX", status="PENDING")
        return Response({"payments": [receipt(row) for row in rows], "pending": [receipt(row) for row in pending]})

    def post(self, request):
        try:
            intent, created = create_payment(request.user, request.data)
            if created:
                intent, _ = reconcile_sandbox_payment(intent.pk)
        except PaymentSettlementError as exc:
            return Response({"code": "MTN_SANDBOX_UNAVAILABLE", "message": str(exc)}, status=503)
        return Response({"payment": receipt(intent), "reused": not created}, status=202 if created else 200)


class SandboxPaymentStatusView(SandboxConsumerView):
    def get(self, request, reference):
        row = PaymentIntent.objects.filter(owner=request.user, provider="MTN_SANDBOX", provider_reference=reference).first()
        if not row:
            raise NotFound("Sandbox payment not found.")
        return Response({"payment": receipt(row)})

    def post(self, request, reference):
        row = PaymentIntent.objects.filter(owner=request.user, provider="MTN_SANDBOX", provider_reference=reference).first()
        if not row:
            raise NotFound("Sandbox payment not found.")
        result, _ = reconcile_sandbox_payment(row.pk)
        return Response({"payment": receipt(result)})


class SandboxPaymentRecoveryView(SandboxConsumerView):
    def get(self, request, request_id):
        row = PaymentIntent.objects.filter(owner=request.user, provider="MTN_SANDBOX", client_request_id=request_id).first()
        return Response({"payment": receipt(row) if row else None})


class SandboxStaffDecisionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from meter.enrollment_review import require_reviewer
        from admin.models import AuditLog
        require_sandbox(); require_reviewer(request.user)
        loans = SandboxLoan.objects.order_by("-created_at")[:100]
        audit = AuditLog.objects.filter(details__environment="MTN_SANDBOX").order_by("-timestamp")[:100]
        return Response({"loans": [loan_record(row) for row in loans],
            "audit": [{"id": row.pk, "at": row.timestamp.isoformat(), "details": row.details} for row in audit],
            "manual_override_available": False})
