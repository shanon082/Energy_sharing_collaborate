"""Consumer endpoints share exactly the same sandbox service for web and Android."""
import uuid
from django.db import transaction
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, NotFound

from accounts.permissions import ConsumerAccountPermission
from transactions.demo_payments import complete_demo_payment
from backend.demo_config import LOCAL_DEMO
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
    def post(self, request):
        from loan.sandbox_service import verified_consumer, owned_test_meter
        from loan.demo_assessment import complete_demo_assessment
        verified_consumer(request.user)
        if set(request.data) != {'meter_id'}:
            raise ValidationError({'code': 'ASSESSMENT_INPUT_FORBIDDEN', 'message': 'Only the owned meter may be selected. Assessment inputs come from the server.'})
        meter = owned_test_meter(request.user, request.data.get('meter_id'))
        complete_demo_assessment(request.user, meter)
        return self.get(request, meter_id=meter.pk, lending=True)

    def get(self, request, meter_id=None, lending=False):
        from loan.prototype_lending import lending_policy, enabled as ugx_enabled
        lending = lending or request.query_params.get('lending') == 'ugx'
        cfg = lending_policy() if lending else policy()
        if request.query_params.get('purpose') == 'PURCHASE':
            from loan.sandbox_service import verified_consumer, owned_test_meter
            verified_consumer(request.user)
            selected = meter_id or request.query_params.get('meter_id')
            if selected is not None:
                owned_test_meter(request.user, selected)
            # Pricing a purchase requires no loan assessment or questionnaire.
            result = None
        else:
            result = assessment(request.user, None if lending and ugx_enabled() else cfg, meter_id=meter_id or request.query_params.get("meter_id"))
        pricing = {"available": True, "message": ""}
        if cfg.get("currency") == "EUR":
            from loan.sandbox_service import eur_pricing_available
            pricing = {"available": eur_pricing_available(cfg), "message": "" if eur_pricing_available(cfg) else "EUR test pricing unavailable; a versioned EUR policy is required."}
        if cfg.get("environment") == "UGX_DEMO":
            from loan.demo_tariffs import pricing_inputs, fingerprint
            try:
                inputs = pricing_inputs(request.user)
                pricing = {"available": True, "message": "", "revision": fingerprint(inputs), "tariff_code": inputs["tariff"]["code"]}
            except ValidationError as exc:
                pricing = {"available": False, "message": str(exc.detail.get("message", "Tariff unavailable"))}
        from loan.sandbox_service import eur_pricing_available
        purchase_cfg = policy()
        purchase_pricing = pricing if purchase_cfg['currency'] == cfg['currency'] else {
            'available': eur_pricing_available(purchase_cfg), 'message': '' if eur_pricing_available(purchase_cfg) else 'EUR test pricing unavailable.'}
        return Response({"assessment": result, "policy": cfg, "pricing": pricing,
                         'purchase_policy': purchase_cfg, 'purchase_pricing': purchase_pricing})


class SandboxQuoteView(SandboxConsumerView):
    def post(self, request):
        purpose = request.data.get("purpose")
        if purpose not in {"LOAN", "PURCHASE"}:
            raise ValidationError({"purpose": "Use LOAN or PURCHASE."})
        from loan.prototype_lending import enabled as ugx_enabled, CONTRACT
        if purpose == 'LOAN' and ugx_enabled() and request.data.get('loan_contract') != CONTRACT:
            raise ValidationError({'code': 'LOAN_CONTRACT_REQUIRED', 'message': 'Use the updated UGX prototype loan flow. EUR loan origination remains unavailable.'})
        meter_id = request.data.get("meter_id")
        if not isinstance(meter_id, int) or isinstance(meter_id, bool) or not 0 < meter_id < 2**63:
            raise ValidationError({"meter_id": "Select a positive test meter ID."})
        quote = create_quote(request.user, meter_id, request.data.get("amount"), purpose)
        return Response({"id": str(quote.pk), "terms_hash": quote.terms_hash, "terms": quote.terms,
                         "expires_at": quote.expires_at.isoformat()}, status=201)


class SandboxLoanView(SandboxConsumerView):
    def get(self, request):
        from loan.consumer_summary import loans_with_applied
        rows = loans_with_applied(SandboxLoan.objects.filter(owner=request.user)).select_related("energy_allocation")
        recent = list(rows.order_by("-created_at", "-pk")[:100])
        # An older outstanding obligation must remain visible/repayable even
        # when more recent historical decisions fill the bounded history.
        older_active = list(rows.filter(status="DISBURSED").exclude(pk__in=[row.pk for row in recent]))
        visible = sorted(recent + older_active, key=lambda row: row.created_at, reverse=True)
        return Response({"loans": [loan_record(row) for row in visible],
                         "history": {"recent_limit": 100, "includes_older_active": bool(older_active)}})

    def post(self, request):
        if request.data.get("accept_test_terms") is not True:
            raise ValidationError({"accept_test_terms": "Review and explicitly accept the sandbox test terms."})
        loan, created = apply_loan(request.user, request.data.get("quote_id"), request.data.get("terms_hash"), request.data.get("client_request_id"))
        return Response({"loan": loan_record(loan), "reused": not created}, status=201 if created else 200)


class ConsumerSummaryView(SandboxConsumerView):
    def get(self, request):
        from backend.demo_config import test_domain
        from django.shortcuts import get_object_or_404
        from meter.models import Meter
        from loan.consumer_summary import consumer_summary
        environment = request.query_params.get("environment", test_domain()[1])
        if environment not in {"UGX_DEMO", "MTN_SANDBOX"}:
            raise ValidationError({"environment": "Select UGX_DEMO or MTN_SANDBOX; CORE is a separate ledger."})
        meter = None
        meter_id = request.query_params.get("meter_id")
        if meter_id is not None:
            if len(meter_id) > 19 or not meter_id.isascii() or not meter_id.isdigit() or not 0 < int(meter_id) < 2**63:
                raise ValidationError({"meter_id": "Select an owned meter."})
            meter = get_object_or_404(Meter, pk=int(meter_id), user=request.user)
        response = Response(consumer_summary(request.user, environment, meter))
        response["Cache-Control"] = "private, no-store"
        return response


class SandboxLoanRecoveryView(SandboxConsumerView):
    def get(self, request, request_id):
        loan = SandboxLoan.objects.filter(owner=request.user, client_request_id=request_id).first()
        return Response({"loan": loan_record(loan) if loan else None})


class SandboxPaymentView(SandboxConsumerView):
    def get(self, request):
        rows = PaymentIntent.objects.filter(owner=request.user, provider__in=["MTN_SANDBOX", LOCAL_DEMO]).select_related(
            "sandbox_settlement", "energy_allocation").order_by("-initiated_at")[:100]
        # Pending records are fetched independently, even after 100 historical receipts.
        pending = PaymentIntent.objects.filter(owner=request.user, provider__in=["MTN_SANDBOX", LOCAL_DEMO], status="PENDING")
        return Response({"payments": [receipt(row) for row in rows], "pending": [receipt(row) for row in pending]})

    def post(self, request):
        try:
            intent, created = create_payment(request.user, request.data)
            if created and intent.provider != LOCAL_DEMO:
                intent, _ = reconcile_sandbox_payment(intent.pk)
        except PaymentSettlementError as exc:
            return Response({"code": "MTN_SANDBOX_UNAVAILABLE", "message": str(exc)}, status=503)
        return Response({"payment": receipt(intent), "reused": not created}, status=202 if created else 200)


class SandboxPaymentStatusView(SandboxConsumerView):
    def get(self, request, reference):
        row = PaymentIntent.objects.filter(owner=request.user, provider__in=["MTN_SANDBOX", LOCAL_DEMO], provider_reference=reference).first()
        if not row:
            raise NotFound("Sandbox payment not found.")
        return Response({"payment": receipt(row)})

    def post(self, request, reference):
        row = PaymentIntent.objects.filter(owner=request.user, provider__in=["MTN_SANDBOX", LOCAL_DEMO], provider_reference=reference).first()
        if not row:
            raise NotFound("Sandbox payment not found.")
        try:
            result, _ = complete_demo_payment(row.pk, owner=request.user) if row.provider == LOCAL_DEMO else reconcile_sandbox_payment(row.pk)
        except PaymentSettlementError as exc:
            return Response({"code": "TEST_SETTLEMENT_UNAVAILABLE", "message": str(exc)}, status=409)
        return Response({"payment": receipt(result)})


class SandboxPaymentRecoveryView(SandboxConsumerView):
    def get(self, request, request_id):
        row = PaymentIntent.objects.filter(owner=request.user, provider__in=["MTN_SANDBOX", LOCAL_DEMO], client_request_id=request_id).first()
        return Response({"payment": receipt(row) if row else None})


class SandboxStaffDecisionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from meter.enrollment_review import require_reviewer
        from admin.models import AuditLog
        require_sandbox(); require_reviewer(request.user)
        loans = SandboxLoan.objects.order_by("-created_at")[:100]
        audit = AuditLog.objects.filter(details__environment__in=["MTN_SANDBOX", "UGX_DEMO"]).order_by("-timestamp")[:100]
        return Response({"loans": [loan_record(row) for row in loans],
            "audit": [{"id": row.pk, "at": row.timestamp.isoformat(), "details": row.details} for row in audit],
            "manual_override_available": False})
