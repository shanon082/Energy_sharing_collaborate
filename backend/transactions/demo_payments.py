"""Server-timed local simulator. No network, PIN, phone prompt or device delivery."""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound

from backend.demo_config import require_demo, LOCAL_DEMO, DEMO_ENVIRONMENT
from loan.sandbox_service import verified_consumer
from transactions.models import PaymentIntent
from transactions.payment_settlement import (
    PaymentSettlementError, _DEMO_AUTHORITY, _demo_evidence, _settle_locked,
)


class DemoNotReady(APIException):
    status_code = 409
    default_code = "DEMO_NOT_READY"
    default_detail = {"code": "DEMO_NOT_READY", "message": "Demo authorization is still processing. No settlement has occurred."}


def validate_demo_intent(intent):
    require_demo()
    verified_consumer(intent.owner)
    ctx = intent.sandbox_context or {}
    if (intent.provider != LOCAL_DEMO or intent.currency != "UGX"
            or ctx.get("version") != 2 or ctx.get("environment") != DEMO_ENVIRONMENT
            or ctx.get("currency") != "UGX" or ctx.get("owner_id") != intent.owner_id
            or ctx.get("purpose") != intent.purpose or intent.amount <= 0
            or intent.amount != intent.amount.to_integral_value()):
        raise PaymentSettlementError("Demo currency/environment/owner/purpose does not match.")
    if not intent.demo_eligible_at or intent.demo_eligible_at < intent.initiated_at + timedelta(seconds=5):
        raise PaymentSettlementError("Demo authorization deadline is invalid.")
    if timezone.now() < intent.demo_eligible_at:
        raise DemoNotReady()
    quote = intent.sandbox_quote
    if (not quote or quote.owner_id != intent.owner_id or quote.purpose != intent.purpose
            or quote.currency != "UGX" or quote.environment != DEMO_ENVIRONMENT or quote.amount != intent.amount
            or quote.meter_id != ctx.get("meter_id") or quote.terms != ctx.get("terms")
            or quote.terms.get("policy", {}).get("currency") != "UGX"
            or quote.terms.get("policy", {}).get("environment") != DEMO_ENVIRONMENT):
        raise PaymentSettlementError("Demo accepted terms/source binding does not match.")
    if intent.purpose == "PURCHASE":
        if (intent.sandbox_loan_id or not intent.meter_id or quote.meter_id != intent.meter_id
                or intent.purchase_id or intent.repayment_id):
            raise PaymentSettlementError("Demo purchase source binding is invalid.")
        terms = ctx["terms"]
        energy, billed, residual = map(Decimal, (terms["energy_kwh"], terms["billed"], terms["residual"]))
        if "pricing" in terms:
            from loan.demo_tariffs import validate_frozen_pricing
            try:
                valid = validate_frozen_pricing(intent.amount, terms)
            except (ValueError, KeyError, TypeError, ArithmeticError, APIException):
                valid = False
            if not valid:
                raise PaymentSettlementError("Demo tariff snapshot does not reproduce accepted pricing.")
        else:
            # Existing funded v1 obligations retain their original fixed terms.
            price = Decimal(terms["policy"]["rate_per_kwh"])
            if (energy <= 0 or energy != energy.quantize(Decimal("0.01")) or price <= 0
                    or billed != energy * price or billed + residual != intent.amount
                    or not Decimal(0) <= residual < price * Decimal("0.01")):
                raise PaymentSettlementError("Demo purchase pricing does not conserve money/energy.")
    elif intent.purpose == "LOAN_REPAYMENT":
        if (not intent.sandbox_loan_id or intent.meter_id or intent.purchase_id or intent.repayment_id
                or quote.terms.get("loan_id") != str(intent.sandbox_loan_id)):
            raise PaymentSettlementError("Demo repayment source binding is invalid.")
    else:
        raise PaymentSettlementError("Unknown demo purpose.")


def complete_demo_payment(intent_id, *, owner=None):
    """Explicit POST or bounded job only. Status GET never calls this operation."""
    require_demo()
    with transaction.atomic():
        rows = PaymentIntent.objects.select_for_update().filter(pk=intent_id, provider=LOCAL_DEMO)
        if owner is not None:
            rows = rows.filter(owner=owner)
        intent = rows.first()
        if intent is None:
            raise NotFound("Demo payment not found.")
        # Validation and settlement share the lock, including deadline and identity.
        return _settle_locked(intent.pk, _demo_evidence(intent), _demo_authority=_DEMO_AUTHORITY)
