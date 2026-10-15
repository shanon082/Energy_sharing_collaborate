"""Stored automatic demo assessment, using loan.scoring's existing calculation."""
from decimal import Decimal, ROUND_DOWN
from types import SimpleNamespace
from copy import deepcopy

from django.conf import settings
from django.db import transaction
from django.db.models import Sum, Count
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from accounts.models import User
from backend.demo_config import require_demo
from loan.models import DemoCreditAssessment
from loan.account_data import account_data_provider, AccountDataUnavailable, SCENARIOS, PROVIDER_ID, SCORING_VERSION
from loan.scoring import FACTOR_WEIGHTS, FACTOR_SUBFACTORS, get_factor_breakdown, calculate_weighted_credit_score

LABEL = "Demo assessment — simulated account information"


def initialize_demo_assessment(owner, *, scenario=None):
    require_demo()
    if owner.user_role != User.CLIENT or owner.is_staff or owner.is_superuser:
        raise PermissionDenied("Demo consumer assessment only.")
    scenario = scenario or getattr(settings, "DEMO_ACCOUNT_PROFILE", "APPROVAL_V1")
    if scenario not in SCENARIOS:
        raise AccountDataUnavailable("Unsupported demo profile configuration")
    with transaction.atomic():
        User.objects.select_for_update().get(pk=owner.pk)
        return DemoCreditAssessment.objects.get_or_create(owner=owner, environment="UGX_DEMO",
            defaults={"scenario": scenario, "provider": PROVIDER_ID, "scoring_policy_version": SCORING_VERSION})


def _purchase_totals(row):
    from transactions.models import SandboxSettlement
    sources = SandboxSettlement.objects.filter(currency="UGX", environment="UGX_DEMO", intent__owner=row.owner,
        intent__provider="LOCAL_DEMO", intent__currency="UGX", intent__purpose="PURCHASE", intent__status="SETTLED",
        intent__energy_allocation__owner=row.owner, intent__energy_allocation__accounting_environment="UGX_DEMO",
        intent__score_exclusion__isnull=True)
    evidence = sources.aggregate(total=Sum("billed"), count=Count("pk"))
    total = evidence["total"] or Decimal(0)
    points = min(row.bonus_policy["purchase_score_cap"], int(total // Decimal(row.bonus_policy["purchase_per_point"])))
    return total, points, evidence["count"]


def _update_purchases(row):
    total, points, count = _purchase_totals(row)
    score = min(100, row.base_score + points)
    if (total, points, count, score) != (row.qualifying_billed_ugx, row.purchase_points, row.purchase_source_count, row.score):
        row.qualifying_billed_ugx = total; row.purchase_points = points; row.purchase_source_count = count; row.score = score
        row.save(update_fields=["qualifying_billed_ugx", "purchase_points", "purchase_source_count", "score", "updated_at"])
    return row


def complete_demo_assessment(owner, meter):
    require_demo()
    from loan.sandbox_service import owned_test_meter, policy
    with transaction.atomic():
        owner = User.objects.select_for_update().get(pk=owner.pk)
        owned_test_meter(owner, meter.pk, lock=True)
        row, _ = initialize_demo_assessment(owner)
        row = DemoCreditAssessment.objects.select_for_update().get(pk=row.pk)
        if row.status == "READY":
            return row  # Enrollment retry does not rescore or redirect its evidence binding.
        try:
            evidence = account_data_provider().fetch(row.scenario)
            if not isinstance(evidence, dict) or not isinstance(evidence.get("categories"), dict):
                raise AccountDataUnavailable("Invalid provider evidence")
            categories = evidence["categories"]
            if (evidence.get("provider") != PROVIDER_ID or evidence.get("provenance") != "SIMULATED_ACCOUNT_INFORMATION"
                    or evidence.get("scenario") != row.scenario or evidence.get("verified_external_records") is not False
                    or set(categories) != set(FACTOR_SUBFACTORS)
                    or any(not isinstance(categories[key], str) or categories[key] not in FACTOR_SUBFACTORS[key]["scores"] for key in categories)):
                raise AccountDataUnavailable("Invalid provider evidence")
            signal = SimpleNamespace(**categories)
            row.base_score = calculate_weighted_credit_score(signal)
            row.factors = get_factor_breakdown(signal)
            row.inputs = evidence
            row.formula = {"major_weights": deepcopy(FACTOR_WEIGHTS), "subfactors": deepcopy(FACTOR_SUBFACTORS),
                           "rounding": "Existing loan.scoring: round factor weighted means to integer, then round the major weighted mean (half-even)."}
            row.bonus_policy = deepcopy(policy())
            row.score = row.base_score
            row.status = "READY"; row.error_code = ""; row.assessed_at = timezone.now(); row.meter = meter
        except (AccountDataUnavailable, OSError, TimeoutError):
            row.status = "UNAVAILABLE"; row.error_code = "SIMULATED_PROVIDER_UNAVAILABLE"
            row.base_score = None; row.score = None; row.assessed_at = None
        row.save()
        return _update_purchases(row) if row.status == "READY" else row


def refresh_demo_purchase_contribution(owner):
    """Settlement event or explicit operator review only; never GET/login refresh."""
    require_demo()
    with transaction.atomic():
        User.objects.select_for_update().get(pk=owner.pk)
        row = DemoCreditAssessment.objects.select_for_update().filter(owner=owner, environment="UGX_DEMO", status="READY").first()
        return _update_purchases(row) if row else None


def stored_demo_eligibility(owner, cfg):
    """Stored evidence + fresh debt/limits. No provider or scoring writes on GET."""
    require_demo()
    from loan.models import SandboxLoan, LoanApplication
    row = DemoCreditAssessment.objects.filter(owner=owner, environment="UGX_DEMO").first()
    ready = row is not None and row.status == "READY" and row.bonus_policy.get("id") == cfg["id"]
    state = row.status if row else "PENDING"
    if row and row.status == "READY" and not ready:
        state = "UNAVAILABLE"
    score = row.score if ready else None
    maximum = (Decimal(cfg["maximum"]) * Decimal("1" if score >= 90 else ".75" if score >= 85 else ".50" if score >= 80 else ".25")).quantize(Decimal(1), rounding=ROUND_DOWN) if ready else None
    eligible = ready and score >= cfg["score_threshold"]
    reason = "Automatic demo assessment using simulated account information." if eligible else (
        "Demo score is below the configured test threshold." if ready else
        "Demo assessment unavailable; retry your owned meter enrollment or contact prototype support." if state == "UNAVAILABLE" else
        "Demo assessment pending. Add your meter to complete automatic assessment.")
    if SandboxLoan.objects.filter(owner=owner, environment="UGX_DEMO", currency="UGX", status="DISBURSED").exists():
        eligible = False; reason = "Repay your existing UGX demo loan before borrowing again."
    if LoanApplication.objects.filter(user=owner).exclude(status__in=["REJECTED", "COMPLETED"]).exists():
        eligible = False; reason = "Existing core obligations require separate review."
    return {"eligible": bool(eligible), "reason": reason, "score": score, "base_score": row.base_score if ready else None,
        "profile_score": row.base_score if ready else None, "starter": False, "assessment_status": state,
        "label": LABEL, "input_source": "SIMULATED_ACCOUNT_INFORMATION", "provider": row.provider if row else PROVIDER_ID,
        "categories": row.inputs.get("categories") if ready else None, "factors": row.factors.get("factor_scores") if ready else None,
        "subfactor_scores": row.factors.get("subfactor_scores") if ready else None, "formula": row.formula if ready else None,
        "purchase_points": row.purchase_points if ready else None, "qualifying_billed_test": str(row.qualifying_billed_ugx) if ready else None,
        "purchase_source_count": row.purchase_source_count if ready else None, "maximum": str(maximum) if maximum is not None else None,
        "policy_id": cfg["id"], "scoring_policy_version": row.scoring_policy_version if row else SCORING_VERSION,
        "assessed_at": row.assessed_at.isoformat() if row and row.assessed_at else None,
        "evidence_updated_at": row.updated_at.isoformat() if row else None, "calculated_at": timezone.now().isoformat(),
        "currency": "UGX", "environment": "UGX_DEMO", "assessment_id": row.pk if row else None}
