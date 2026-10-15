"""Currency-isolated prototype payments using the shared settlement authority."""
from datetime import timedelta
from decimal import Decimal
import uuid

from django.db import transaction
from django.utils import timezone
from django.conf import settings
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied

from backend.demo_config import test_domain, LOCAL_DEMO, require_demo, require_mtn_sandbox
from accounts.models import User
from loan.models import SandboxLoan
from loan.sandbox_service import require_sandbox, money, request_uuid, accepted_quote, owned_test_meter, verified_consumer
from meter.allocation_service import authorize_purchase_allocation
from mtn_momo.sandbox import MTNSandbox, test_msisdn
from transactions.models import PaymentIntent, SandboxSettlement
from transactions.payment_settlement import PaymentSettlementError, settle_from_provider_evidence


def create_payment(owner, data):
    require_sandbox()
    currency, environment, provider = test_domain()
    demo = provider == LOCAL_DEMO
    if demo:
        require_demo()
        if any(name in data for name in ("pin", "momo_pin", "mobile_money_pin")):
            raise ValidationError({"code": "NO_PIN_REQUIRED", "message": "Demo payments never require a PIN."})
    else:
        require_mtn_sandbox()
        MTNSandbox()  # fail before recording/collection when credentials are absent
    key = request_uuid(data.get("client_request_id"))
    msisdn = None if demo else test_msisdn(data.get("msisdn"))
    purpose = data.get("purpose")
    if purpose not in {"PURCHASE", "LOAN_REPAYMENT"}:
        raise ValidationError({"purpose": "Use PURCHASE or LOAN_REPAYMENT."})
    with transaction.atomic():
        owner = User.objects.select_for_update().get(pk=owner.pk)
        verified_consumer(owner)
        prior = PaymentIntent.objects.filter(client_request_id=key).first()
        if prior:
            expected_binding = str(data.get("quote_id")) if purpose == "PURCHASE" else str(data.get("loan_id"))
            recorded_binding = str(prior.sandbox_quote_id) if purpose == "PURCHASE" else str(prior.sandbox_loan_id)
            if (prior.owner_id != owner.pk or prior.provider != provider or prior.purpose != purpose
                    or expected_binding != recorded_binding or prior.sandbox_context.get("msisdn") != msisdn
                    or (purpose == "LOAN_REPAYMENT" and money(data.get("amount")) != prior.amount)
                    or (purpose == "PURCHASE" and data.get("terms_hash") != prior.sandbox_quote.terms_hash)):
                raise ValidationError({"code": "REQUEST_ID_CONFLICT"})
            return prior, False
        if PaymentIntent.objects.filter(owner=owner, provider=provider, status="PENDING").exists():
            raise ValidationError({"code": "PAYMENT_PENDING_RECONCILIATION", "message": "Reconcile the existing sandbox request before initiating another."})
        loan = None
        if purpose == "PURCHASE":
            if data.get("accept_test_terms") is not True:
                raise ValidationError({"accept_test_terms": "Accept the quoted sandbox purchase/remainder terms."})
            quote = accepted_quote(owner, data.get("quote_id"), data.get("terms_hash"), "PURCHASE")
            if PaymentIntent.objects.filter(sandbox_quote=quote).exists():
                raise ValidationError({"code": "QUOTE_ALREADY_USED"})
            amount = quote.amount
        else:
            try:
                loan = SandboxLoan.objects.select_for_update().get(pk=uuid.UUID(str(data.get("loan_id"))), owner=owner)
            except (ValueError, SandboxLoan.DoesNotExist):
                raise NotFound("Sandbox loan not found.") from None
            # Existing debt remains payable if the original test meter is later
            # retired/reassigned. This changes debt only, never energy/devices.
            if loan.currency != currency or loan.environment != environment:
                raise ValidationError({"code": "TEST_CURRENCY_MISMATCH", "message": "Demo UGX and EUR test loans cannot repay each other."})
            if not loan.meter.sandbox_inventory:
                raise ValidationError({"loan_id": "Repayment requires an existing matching test-loan source."})
            amount = money(data.get("amount"))
            if loan.status != "DISBURSED" or loan.outstanding <= 0 or amount > loan.outstanding:
                raise ValidationError({"amount": "Repay a positive matching test amount no greater than the current test debt."})
            # Persist the accepted repayment terms just like a purchase quote.
            # Repayment amounts may be below the loan/purchase minimum.
            from loan.models import SandboxQuote
            from hashlib import sha256
            terms = {"policy": loan.terms["policy"], "purpose": purpose, "loan_id": str(loan.pk),
                     "amount": str(amount), "currency": currency, "environment": environment, "excess_policy": "Preserved for reconciliation; no automatic refund or energy."}
            import json
            quote = SandboxQuote.objects.create(owner=owner, meter=loan.meter, purpose=purpose, amount=amount, currency=currency, environment=environment, terms=terms,
                terms_hash=sha256(json.dumps(terms, sort_keys=True).encode()).hexdigest(), expires_at=timezone.now()+timedelta(minutes=15))
            if data.get("accept_test_terms") is not True:
                raise ValidationError({"accept_test_terms": "Accept the test repayment/excess terms."})
        reference = uuid.uuid4()
        now = timezone.now()
        eligible = now + timedelta(seconds=5) if demo else None
        return PaymentIntent.objects.create(owner=owner, purpose=purpose, amount=amount, currency=currency, provider=provider,
            initiated_at=now, demo_eligible_at=eligible, reconcile_after=eligible or now,
            provider_reference=reference, provider_external_id=f"sandbox-{purpose.lower()}-{reference}",
            client_request_id=key, sandbox_quote=quote, meter=quote.meter if purpose == "PURCHASE" else None,
            sandbox_loan=loan, sandbox_context={"version": 2 if demo else 1, "currency": currency, "environment": environment, "purpose": purpose, "owner_id": owner.pk,
                "meter_id": quote.meter_id, "terms": quote.terms, "msisdn": msisdn}, submission_state="DEMO_PENDING" if demo else "NEW"), True


def validate_sandbox_evidence(intent, evidence):
    require_sandbox()
    require_mtn_sandbox()
    ctx = intent.sandbox_context or {}
    if (intent.provider != "MTN_SANDBOX" or evidence.get("provider") != "MTN_SANDBOX"
            or intent.currency != "EUR" or evidence.get("currency") != "EUR"
            or str(evidence.get("reference_id")) != str(intent.provider_reference)
            or evidence.get("external_id") != intent.provider_external_id
            or ctx.get("purpose") != intent.purpose or ctx.get("owner_id") != intent.owner_id):
        raise PaymentSettlementError("Sandbox provider/reference/currency/purpose does not match.")
    try:
        amount = Decimal(str(evidence.get("amount")))
        if not amount.is_finite() or amount != intent.amount:
            raise ValueError
    except (ValueError, ArithmeticError):
        raise PaymentSettlementError("Sandbox amount does not match.") from None
    if evidence.get("payer") != ctx.get("msisdn"):
        raise PaymentSettlementError("Sandbox payer does not match.")
    if evidence.get("status") == "SUCCESS" and not str(evidence.get("transaction_id") or "").strip():
        raise PaymentSettlementError("Sandbox successful status lacks a financial transaction identity; reconcile with MTN.")
    if (not intent.sandbox_quote_id or (intent.purpose == "PURCHASE" and (not intent.meter_id or intent.sandbox_loan_id))
            or (intent.purpose == "LOAN_REPAYMENT" and (not intent.sandbox_loan_id or intent.meter_id))):
        raise PaymentSettlementError("Sandbox source binding is invalid.")
    quote = intent.sandbox_quote
    if (quote.owner_id != intent.owner_id or quote.purpose != intent.purpose or quote.amount != intent.amount
            or quote.meter_id != ctx.get("meter_id") or quote.terms != ctx.get("terms")
            or (intent.purpose == "PURCHASE" and quote.meter_id != intent.meter_id)
            or (intent.purpose == "LOAN_REPAYMENT" and quote.terms.get("loan_id") != str(intent.sandbox_loan_id))):
        raise PaymentSettlementError("Sandbox accepted terms/source binding does not match.")


def apply_sandbox_settlement(intent):
    currency = "UGX" if intent.provider == LOCAL_DEMO else "EUR"
    environment = "UGX_DEMO" if intent.provider == LOCAL_DEMO else "MTN_SANDBOX"
    if intent.currency != currency:
        raise PaymentSettlementError("Test settlement currency mismatch.")
    User.objects.select_for_update().get(pk=intent.owner_id)
    ctx = intent.sandbox_context
    if intent.purpose == "PURCHASE":
        owned_test_meter(intent.owner, intent.meter_id, lock=True)
        terms = ctx["terms"]
        billed, residual = Decimal(terms["billed"]), Decimal(terms["residual"])
        if billed + residual != intent.amount or min(billed, residual) < 0:
            raise PaymentSettlementError("Sandbox purchase receipt does not conserve received test money.")
        authorize_purchase_allocation(intent, Decimal(terms["energy_kwh"]))
        SandboxSettlement.objects.create(intent=intent, currency=currency, environment=environment, received=intent.amount, billed=billed, residual=residual)
        if intent.provider == LOCAL_DEMO:
            from loan.demo_assessment import refresh_demo_purchase_contribution
            refresh_demo_purchase_contribution(intent.owner, intent.meter)
    else:
        loan = SandboxLoan.objects.select_for_update().get(pk=intent.sandbox_loan_id, owner=intent.owner)
        if loan.currency != currency or loan.environment != environment or loan.status not in {"DISBURSED", "COMPLETED"} or loan.meter_id != ctx["meter_id"]:
            raise PaymentSettlementError("Sandbox repayment loan/owner/meter does not match.")
        applied = min(intent.amount, loan.outstanding)
        SandboxSettlement.objects.create(intent=intent, currency=currency, environment=environment, received=intent.amount, applied=applied, excess=intent.amount-applied)
        if loan.outstanding == 0 and loan.status != "COMPLETED":
            loan.status = "COMPLETED"; loan.closed_at = timezone.now()
            loan.save(update_fields=["status", "closed_at"])


def reconcile_sandbox_payment(intent_id):
    """Lease persists across process restarts; external I/O never holds DB locks."""
    require_sandbox()
    require_mtn_sandbox()
    now = timezone.now()
    lease = uuid.uuid4()
    with transaction.atomic():
        intent = PaymentIntent.objects.select_for_update().get(pk=intent_id, provider="MTN_SANDBOX", currency="EUR")
        if intent.status != "PENDING" or (intent.reconcile_lease_until and intent.reconcile_lease_until > now):
            return intent, False
        if intent.reconcile_after > now:
            return intent, False
        submit = intent.submission_state == "NEW"
        intent.reconcile_lease_id = lease; intent.reconcile_lease_until = now + timedelta(seconds=90)
        intent.reconcile_attempts += 1
        if submit:
            intent.submission_state = "SUBMITTING"
        intent.save(update_fields=["reconcile_lease_id", "reconcile_lease_until", "reconcile_attempts", "submission_state"])
    effect = False
    error = ""
    try:
        adapter = MTNSandbox()
        if submit:
            state = adapter.initiate(intent)
            PaymentIntent.objects.filter(pk=intent.pk, reconcile_lease_id=lease).update(submission_state=state)
            # Poll in a subsequent bounded run; initiation is not settlement.
        else:
            evidence = adapter.status(intent)
            intent, effect = settle_from_provider_evidence(intent.pk, evidence)
            if evidence.get("status") == "UNKNOWN":
                error = "STATUS_UNAVAILABLE"
    except (PaymentSettlementError, PermissionDenied):
        error = "PROVIDER_OR_EVIDENCE_UNAVAILABLE"
    finally:
        if error and submit:
            PaymentIntent.objects.filter(pk=intent.pk, reconcile_lease_id=lease).update(submission_state="OUTCOME_UNKNOWN")
        delay = min(3600, 30 * 2 ** min(intent.reconcile_attempts-1, 7))
        PaymentIntent.objects.filter(pk=intent.pk, reconcile_lease_id=lease).update(
            reconcile_lease_until=None, reconcile_lease_id=None, reconciliation_error=error,
            reconcile_after=timezone.now()+timedelta(seconds=delay))
    return PaymentIntent.objects.get(pk=intent.pk), effect


def receipt(intent):
    ledger = getattr(intent, "sandbox_settlement", None)
    allocation = getattr(intent, "energy_allocation", None)
    return {"id": intent.pk, "reference": str(intent.provider_reference), "client_request_id": str(intent.client_request_id),
        "purpose": intent.purpose, "status": intent.status, "currency": intent.currency, "environment": "UGX_DEMO" if intent.provider == LOCAL_DEMO else "MTN_SANDBOX",
        "provider": intent.provider, "label": "UGX DEMO / NO REAL MONEY" if intent.provider == LOCAL_DEMO else "EUR TEST / MTN SANDBOX",
        "demo_eligible_at": intent.demo_eligible_at.isoformat() if intent.demo_eligible_at else None, "server_time": timezone.now().isoformat(),
        "amount": str(intent.amount), "meter_id": (intent.meter_id or (intent.sandbox_context or {}).get("meter_id")),
        "loan_id": str(intent.sandbox_loan_id) if intent.sandbox_loan_id else None,
        "billed": str(ledger.billed) if ledger else None, "residual": str(ledger.residual) if ledger else None,
        "applied": str(ledger.applied) if ledger else None, "excess": str(ledger.excess) if ledger else None,
        "allocated_kwh": str(allocation.amount_kwh) if allocation else None, "meter_application_confirmed": False,
        "initiated_at": intent.initiated_at.isoformat(), "settled_at": intent.settled_at.isoformat() if intent.settled_at else None,
        "submission_state": intent.submission_state, "reconciliation_error": intent.reconciliation_error,
        "next_check_at": intent.reconcile_after.isoformat(), "pricing": (intent.sandbox_context or {}).get("terms", {}).get("pricing")}
