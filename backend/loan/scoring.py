import random
from types import SimpleNamespace

from django.db.utils import OperationalError, ProgrammingError
from loan.models import UserCreditSignal


# Major factor weights
FACTOR_WEIGHTS = {
    "payment_history": 1,
    "energy_consumption": 2,
    "financial_capacity": 3,
}

# Each major factor is now composed of granular sub-factors.
# Scores are on a 0-100 scale; they are intentionally conservative on mid/low categories.
FACTOR_SUBFACTORS = {
    "payment_history": {
        "weights": {"on_time_ratio": 0.5, "arrears_frequency": 0.3, "disconnection_events": 0.2},
        "scores": {
            "GOOD": {"on_time_ratio": 95, "arrears_frequency": 90, "disconnection_events": 90},
            "FAIR": {"on_time_ratio": 75, "arrears_frequency": 60, "disconnection_events": 55},
            "POOR": {"on_time_ratio": 45, "arrears_frequency": 35, "disconnection_events": 30},
        },
    },
    "energy_consumption": {
        "weights": {"usage_stability": 0.4, "peak_variation": 0.35, "seasonality": 0.25},
        "scores": {
            "STABLE": {"usage_stability": 95, "peak_variation": 90, "seasonality": 90},
            "MODERATE": {"usage_stability": 75, "peak_variation": 70, "seasonality": 65},
            "ERRATIC": {"usage_stability": 45, "peak_variation": 40, "seasonality": 35},
        },
    },
    "financial_capacity": {
        "weights": {"income_stability": 0.4, "expense_buffer": 0.35, "repayment_capacity": 0.25},
        "scores": {
            "STRONG": {"income_stability": 95, "expense_buffer": 90, "repayment_capacity": 90},
            "AVERAGE": {"income_stability": 75, "expense_buffer": 70, "repayment_capacity": 65},
            "WEAK": {"income_stability": 45, "expense_buffer": 40, "repayment_capacity": 35},
        },
    },
}

PROFILE_SIGNAL_FIELDS = (
    "payment_consistency",
    "disconnection_history",
    "consumption_level",
    "purchase_frequency",
    "monthly_income",
    "income_stability",
)

# All loan-assessment answers required before scoring uses profile data (not defaults).
LOAN_PROFILE_FIELDS = (
    "monthly_expenditure",
    "purchase_frequency",
    "payment_consistency",
    "disconnection_history",
    "meter_sharing",
    "monthly_income",
    "income_stability",
    "consumption_level",
)


def _derive_payment_history(user) -> str:
    payment = (getattr(user, "payment_consistency", None) or "").strip()
    disconnections = (getattr(user, "disconnection_history", None) or "").strip()

    if payment in ("Mostly late", "Never paid"):
        return "POOR"
    if disconnections in ("3–4 disconnections", ">4 disconnections", "Frequently disconnected"):
        return "POOR"
    if payment == "Always on time" and disconnections in ("", "No disconnections"):
        return "GOOD"
    if payment in ("Often on time", "Sometimes late") or disconnections == "1–2 disconnections":
        return "FAIR"
    return "FAIR"


def _derive_energy_consumption(user) -> str:
    consumption = (getattr(user, "consumption_level", None) or "").strip()
    frequency = (getattr(user, "purchase_frequency", None) or "").strip()

    if consumption in ("High (>200 kWh)", "Extremely high (>300 kWh)") and frequency in (
        "Weekly",
        "Biweekly",
    ):
        return "STABLE"
    if consumption in ("Very low (<50 kWh)",) and frequency in ("Rarely",):
        return "ERRATIC"
    if consumption or frequency:
        return "MODERATE"
    return "MODERATE"


def _derive_financial_capacity(user) -> str:
    income = (getattr(user, "monthly_income", None) or "").strip()
    stability = (getattr(user, "income_stability", None) or "").strip()

    if income in (">1,000,000 UGX", "500,000–999,999 UGX"):
        return "STRONG"
    if income == "200,000–499,999 UGX" and stability in ("Fixed and stable", "Regular but variable"):
        return "STRONG"
    if income in ("<100,000 UGX",) or stability in ("Unstable income", "Seasonal income"):
        return "WEAK"
    if income or stability:
        return "AVERAGE"
    return "AVERAGE"


def _user_has_profile_signals(user) -> bool:
    return any((getattr(user, field, None) or "").strip() for field in PROFILE_SIGNAL_FIELDS)


def profile_scoring_fields_complete(user) -> bool:
    """True when every loan-assessment field on the user record is filled."""
    return all((getattr(user, field, None) or "").strip() for field in LOAN_PROFILE_FIELDS)


def derive_signal_values_from_user(user) -> dict:
    """Map onboarding/profile answers to credit signal categories (deterministic)."""
    has_profile = _user_has_profile_signals(user)
    return {
        "payment_history": _derive_payment_history(user),
        "energy_consumption": _derive_energy_consumption(user),
        "financial_capacity": _derive_financial_capacity(user),
        "source": "PROFILE" if has_profile else "DEFAULT",
    }


def sync_credit_signal_from_profile(user) -> UserCreditSignal | SimpleNamespace | None:
    """Refresh stored credit signal after profile updates."""
    values = derive_signal_values_from_user(user)
    try:
        signal, _ = UserCreditSignal.objects.get_or_create(
            user=user,
            defaults=values,
        )
        changed = False
        for key, value in values.items():
            if getattr(signal, key) != value:
                setattr(signal, key, value)
                changed = True
        if changed:
            signal.save()
        return signal
    except (OperationalError, ProgrammingError):
        return SimpleNamespace(**values)


# def get_or_create_credit_signal(user):
#     """
#     Build credit signals from profile data when available; otherwise use neutral defaults.
#     Always re-syncs from the user record when the loan assessment is complete.
#     """
#     if profile_scoring_fields_complete(user):
#         synced = sync_credit_signal_from_profile(user)
#         if synced is not None:
#             return synced

#     values = derive_signal_values_from_user(user)
#     try:
#         signal, created = UserCreditSignal.objects.get_or_create(user=user, defaults=values)
#         if not created and signal.source == "DUMMY_THIRD_PARTY":
#             for key, value in values.items():
#                 setattr(signal, key, value)
#             signal.save(update_fields=list(values.keys()) + ["updated_at"])
#     'financial_capacity': {
#         'weights': {'income_stability': 0.4, 'expense_buffer': 0.35, 'repayment_capacity': 0.25},
#         'scores': {
#             'STRONG':  {'income_stability': 95, 'expense_buffer': 90, 'repayment_capacity': 90},
#             'AVERAGE': {'income_stability': 75, 'expense_buffer': 70, 'repayment_capacity': 65},
#             'WEAK':    {'income_stability': 45, 'expense_buffer': 40, 'repayment_capacity': 35},
#         }
#     }

def get_or_create_credit_signal(user):
    """
    Build credit signals from profile data when available; otherwise use neutral defaults.
    Always re-syncs from the user record when the loan assessment is complete.
    """
    if profile_scoring_fields_complete(user):
        synced = sync_credit_signal_from_profile(user)
        if synced is not None:
            return synced

    values = derive_signal_values_from_user(user)
    try:
        signal, created = UserCreditSignal.objects.get_or_create(user=user, defaults=values)
        if not created and signal.source == "DUMMY_THIRD_PARTY":
            for key, value in values.items():
                setattr(signal, key, value)
            signal.save(update_fields=list(values.keys()) + ["updated_at"])
        return signal
    except (OperationalError, ProgrammingError):
        return SimpleNamespace(**values)


# Backwards-compatible alias
get_or_create_dummy_credit_signal = get_or_create_credit_signal

def get_or_create_dummy_credit_signal(user):
    """
    Simulate third-party enrichment.
    Creates one persistent dummy signal record per user when missing.
    Now uses more realistic values for new users (FAIR/MODERATE/AVERAGE)
    """
    defaults = {
        'payment_history': random.choice(['GOOD', 'FAIR', 'FAIR', 'POOR']),  # Weighted towards FAIR
        'energy_consumption': random.choice(['STABLE', 'MODERATE', 'MODERATE', 'ERRATIC']),  # Weighted towards MODERATE
        'financial_capacity': random.choice(['STRONG', 'AVERAGE', 'AVERAGE', 'WEAK']),  # Weighted towards AVERAGE
        'source': 'DUMMY_THIRD_PARTY',
    }
    
    try:
        signal, created = UserCreditSignal.objects.get_or_create(user=user, defaults=defaults)
        if created:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Created new credit signal for user {user.email}: {signal.payment_history}, {signal.energy_consumption}, {signal.financial_capacity}")
        return signal
    except (OperationalError, ProgrammingError):
        return SimpleNamespace(**values)


# Backwards-compatible alias
get_or_create_dummy_credit_signal = get_or_create_credit_signal


def _score_subfactors(choice_value, factor_key):
    """Compute the average score for a major factor using its sub-factors."""
    factor_cfg = FACTOR_SUBFACTORS[factor_key]
    sub_scores = factor_cfg["scores"].get(choice_value, {})
    weights = factor_cfg["weights"]

    weighted_sum = sum(sub_scores.get(sub, 0) * weight for sub, weight in weights.items())
    total_weight = sum(weights.values()) or 1
    return round(weighted_sum / total_weight)


def get_factor_breakdown(signal):
    """
    Return granular scores for each factor and its sub-factors.
    """
    factor_scores = {}
    subfactor_scores = {}

    for factor_key in FACTOR_SUBFACTORS.keys():
        choice_value = getattr(signal, factor_key, None)
        factor_cfg = FACTOR_SUBFACTORS[factor_key]

        sub_scores = factor_cfg["scores"].get(choice_value, {})
        subfactor_scores[factor_key] = sub_scores
        factor_scores[factor_key] = _score_subfactors(choice_value, factor_key)

    return {
        "factor_scores": factor_scores,
        "subfactor_scores": subfactor_scores,
    }


def calculate_weighted_credit_score(signal):
    """
    Return integer credit score (0-100) from weighted 3-factor model
    built from granular sub-factors.
    """
    breakdown = get_factor_breakdown(signal)
    factor_scores = breakdown["factor_scores"]

    weighted_total = sum(
        factor_scores.get(factor, 0) * weight for factor, weight in FACTOR_WEIGHTS.items()
    )
    total_weight = sum(FACTOR_WEIGHTS.values()) or 1
    score = round(weighted_total / total_weight)
    
    # Ensure score is between 0 and 100
    return max(0, min(100, score))