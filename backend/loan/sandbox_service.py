"""Shared sandbox application/pricing authority, independent of real UGX lending."""
from datetime import timedelta
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_EVEN
from hashlib import sha256
import json
import uuid

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound

from accounts.models import User
from admin.models import AuditLog
from backend.sandbox_config import sandbox_configuration
from loan.models import LoanApplication, SandboxLoan, SandboxQuote
from loan.scoring import FACTOR_WEIGHTS, FACTOR_SUBFACTORS, derive_signal_values_from_user, profile_scoring_fields_complete
from meter.models import Meter
from transactions.models import PaymentIntent, SandboxSettlement


def require_sandbox():
    if getattr(settings, "CONSUMER_SANDBOX_ENABLED", False) is not True:
        raise PermissionDenied({"code": "SANDBOX_DISABLED", "message": "The sandbox deployment profile is not enabled."})


def verified_consumer(owner):
    from accounts.models import Profile
    if (not owner.is_active or owner.is_suspended or owner.is_staff or owner.is_superuser
            or owner.user_role != User.CLIENT or owner.must_change_password
            or not Profile.objects.filter(user=owner, email_verified=True).exists()):
        raise PermissionDenied("An active verified consumer is required for the sandbox workflow.")


def policy():
    return getattr(settings, "SANDBOX_POLICY", None) or sandbox_configuration({})[0]


def money(raw):
    try:
        value = Decimal(str(raw))
        if not value.is_finite() or value <= 0 or value > 10000 or value != value.quantize(Decimal("0.01")):
            raise ValueError
        return value
    except (ValueError, ArithmeticError):
        raise ValidationError({"amount": "Use a positive EUR TEST amount in cents, at most 10000."}) from None


def request_uuid(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError({"client_request_id": "A UUID request ID is required."}) from None


def owned_test_meter(owner, meter_id, *, lock=False):
    from meter.sandbox_enrollment import sandbox_meter_authorized
    rows = Meter.objects.select_for_update() if lock else Meter.objects
    meter = rows.filter(pk=meter_id, user=owner, sandbox_inventory=True, status=Meter.STATUS_ACTIVE).first()
    if not meter or not sandbox_meter_authorized(meter, owner):
        raise PermissionDenied({"code": "AUTHORIZED_TEST_METER_REQUIRED", "message": "Add or select an active prototype meter linked to your account."})
    return meter


def assessment(owner, test_policy=None):
    require_sandbox()
    verified_consumer(owner)
    cfg = test_policy or policy()
    complete = profile_scoring_fields_complete(owner)
    factors = None
    profile_score = None
    if complete:
        categories = derive_signal_values_from_user(owner)
        factors = {}
        for key, factor in FACTOR_SUBFACTORS.items():
            scores = factor["scores"][categories[key]]
            weighted = sum((Decimal(str(weight)) * Decimal(scores[sub]) for sub, weight in factor["weights"].items()), Decimal(0))
            factors[key] = int(weighted.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
        profile_score = int((sum((Decimal(factors[key]) * weight for key, weight in FACTOR_WEIGHTS.items()), Decimal(0)) /
                             sum(FACTOR_WEIGHTS.values())).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
    qualifying = SandboxSettlement.objects.filter(intent__owner=owner, intent__provider="MTN_SANDBOX",
        intent__currency="EUR", intent__status="SETTLED", intent__purpose="PURCHASE",
        intent__energy_allocation__accounting_environment="SANDBOX").exclude(intent__score_exclusion__isnull=False)
    total = qualifying.aggregate(total=Sum("billed"))["total"] or Decimal(0)
    points = min(cfg["purchase_score_cap"], int(total // Decimal(cfg["purchase_per_point"])))
    score = min(100, profile_score + points) if complete else None
    maximum = Decimal(cfg["starter_limit"]) if not complete else (
        Decimal(cfg["maximum"]) * Decimal("1.00" if score >= 90 else "0.75" if score >= 85 else "0.50" if score >= 80 else "0.25"))
    maximum = maximum.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    reason = "Starter test allowance; no established credit score." if not complete else "Profile-based test assessment."
    eligible = not complete or score >= cfg["score_threshold"]
    if not eligible:
        reason = "Test profile score is below the configured threshold."
    active = SandboxLoan.objects.filter(owner=owner, status="DISBURSED").first()
    if active:
        eligible = False
        reason = "Existing overdue test debt must be repaid." if active.due_at < timezone.now() else "Repay the existing test loan before borrowing again."
    if LoanApplication.objects.filter(user=owner).exclude(status__in=["REJECTED", "COMPLETED"]).exists():
        eligible = False; reason = "Existing core-account obligations require separate review; EUR sandbox cannot repay them."
    return {"eligible": eligible, "reason": reason, "score": score, "profile_score": profile_score,
        "input_source": "SELF_REPORTED_PROFILE" if complete else "STARTER_NO_HISTORY",
        "categories": derive_signal_values_from_user(owner) if complete else None,
        "formula": {"major_weights": FACTOR_WEIGHTS,
                    "subfactors": {key: {"weights": {sub: str(weight) for sub, weight in row["weights"].items()},
                                           "scores": row["scores"]} for key, row in FACTOR_SUBFACTORS.items()},
                    "rounding": "Half-even integer factor scores, then half-even weighted mean; capped aggregate purchase bonus"},
        "factors": factors, "starter": not complete, "purchase_points": points, "qualifying_billed_eur": str(total),
        "purchase_source_count": qualifying.count(), "maximum": str(maximum), "calculated_at": timezone.now().isoformat(),
        "policy_id": cfg["id"], "currency": "EUR", "environment": "MTN_SANDBOX"}


def energy_price(amount, cfg):
    units = (amount / Decimal(cfg["rate_per_kwh"])).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    billed = units * Decimal(cfg["rate_per_kwh"])
    return units, billed, amount - billed


def create_quote(owner, meter_id, raw_amount, purpose):
    require_sandbox()
    verified_consumer(owner)
    meter = owned_test_meter(owner, meter_id)
    amount = money(raw_amount)
    cfg = policy()
    if amount < Decimal(cfg["minimum"]) or amount > Decimal(cfg["maximum"]):
        raise ValidationError({"amount": f"Test quotes must be between EUR {cfg['minimum']} and {cfg['maximum']}."})
    units, billed, residual = energy_price(amount, cfg)
    if units <= 0:
        raise ValidationError({"amount": "The test price produces less than 10 Wh."})
    interest = (amount * Decimal(cfg["interest_percent"]) / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    terms = {"policy": cfg, "purpose": purpose, "owner_id": owner.pk, "meter_id": meter.pk,
        "amount": str(amount), "energy_kwh": str(units), "billed": str(billed), "residual": str(residual),
        "interest": str(interest if purpose == "LOAN" else Decimal("0.00")), "fee": cfg["fee"] if purpose == "LOAN" else "0.00",
        "total_due": str(amount + interest + Decimal(cfg["fee"])) if purpose == "LOAN" else "0.00",
        "assessment": assessment(owner, cfg) if purpose == "LOAN" else None}
    hashed = sha256(json.dumps(terms, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return SandboxQuote.objects.create(owner=owner, meter=meter, purpose=purpose, amount=amount, terms=terms,
        terms_hash=hashed, expires_at=timezone.now() + timedelta(minutes=cfg["quote_minutes"]))


def accepted_quote(owner, quote_id, terms_hash, purpose):
    try:
        quote = SandboxQuote.objects.select_for_update().get(pk=uuid.UUID(str(quote_id)), owner=owner, purpose=purpose)
    except (ValueError, SandboxQuote.DoesNotExist):
        raise NotFound("Quote not found.") from None
    if quote.terms_hash != terms_hash:
        raise ValidationError({"code": "TERMS_MISMATCH", "message": "Review and accept the exact server quote."})
    if quote.expires_at <= timezone.now():
        raise ValidationError({"code": "QUOTE_EXPIRED", "message": "Get a new quote before submission."})
    owned_test_meter(owner, quote.meter_id, lock=True)
    return quote


def apply_loan(owner, quote_id, terms_hash, client_request_id):
    require_sandbox()
    request_id = request_uuid(client_request_id)
    with transaction.atomic():
        owner = User.objects.select_for_update().get(pk=owner.pk)
        verified_consumer(owner)
        prior = SandboxLoan.objects.filter(client_request_id=request_id).first()
        if prior:
            if prior.owner_id != owner.pk or str(prior.quote_id) != str(quote_id) or prior.quote.terms_hash != terms_hash:
                raise ValidationError({"code": "REQUEST_ID_CONFLICT"})
            return prior, False
        quote = accepted_quote(owner, quote_id, terms_hash, "LOAN")
        existing = SandboxLoan.objects.filter(quote=quote).first()
        if existing:
            raise ValidationError({"code": "QUOTE_ALREADY_USED", "message": "This quote already has an application."})
        result = assessment(owner, quote.terms["policy"])
        approved = result["eligible"] and quote.amount <= Decimal(result["maximum"])
        reason = "Approved under SANDBOX TEST POLICY; test entitlement allocated, meter application unconfirmed." if approved else (
            result["reason"] if not result["eligible"] else "Requested principal exceeds your current test limit.")
        loan = SandboxLoan.objects.create(owner=owner, meter=quote.meter, quote=quote, client_request_id=request_id,
            principal=quote.amount, total_due=Decimal(quote.terms["total_due"]) if approved else 0,
            terms=quote.terms, assessment=result, status="DISBURSED" if approved else "REJECTED", decision_reason=reason,
            due_at=timezone.now() + timedelta(days=quote.terms["policy"]["due_days"]))
        if approved:
            from meter.allocation_service import authorize_sandbox_loan_allocation
            authorize_sandbox_loan_allocation(loan, Decimal(quote.terms["energy_kwh"]))
        AuditLog.objects.create(action_type=AuditLog.ACTION_LOAN_APPROVE if approved else AuditLog.ACTION_LOAN_REJECT,
            target_type=AuditLog.TARGET_LOAN, target_id=str(loan.pk),
            details={"environment": "MTN_SANDBOX", "automatic": True, "owner_id": owner.pk,
                     "quote_id": str(quote.pk), "policy": quote.terms["policy"], "assessment": result,
                     "decision": loan.status, "reason": reason})
        return loan, True


def loan_record(loan):
    allocation = getattr(loan, "energy_allocation", None)
    return {"id": str(loan.pk), "client_request_id": str(loan.client_request_id), "meter_id": loan.meter_id,
        "status": loan.status, "reason": loan.decision_reason, "currency": "EUR", "environment": "MTN_SANDBOX",
        "principal": str(loan.principal), "total_due": str(loan.total_due), "outstanding": str(loan.outstanding),
        "due_at": loan.due_at.isoformat(), "closed_at": loan.closed_at.isoformat() if loan.closed_at else None,
        "created_at": loan.created_at.isoformat(), "terms": loan.terms, "assessment": loan.assessment,
        "allocation_id": allocation.pk if allocation else None,
        "allocated_kwh": str(allocation.amount_kwh) if allocation else None,
        "meter_application_confirmed": False}
