"""
gPawa Trust Ladder — starter access for every customer, growth through repayment.

New users can borrow up to STARTER_MAX_LOAN immediately. Each successfully repaid
loan unlocks a higher cap; late or missed payments pull the score and cap back down.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.utils import timezone

from loan.models import LoanApplication

# Everyone starts here (even with no profile / zero history).
STARTER_MAX_LOAN = 30_000
STARTER_CREDIT_SCORE = 76
TRUST_CAP_BONUS_ON_TIME = 15_000
TRUST_CAP_BONUS_LATE = 7_500
TRUST_SCORE_BONUS_ON_TIME = 4
TRUST_SCORE_BONUS_LATE = 1
TRUST_SCORE_PENALTY_DEFAULT = 12
TRUST_SCORE_PENALTY_OVERDUE = 5
DEFAULT_REHAB_CAP = 15_000
OVERDUE_CAP_CEILING = 20_000


@dataclass(frozen=True)
class TrustSnapshot:
    completed_loans: int
    on_time_completions: int
    late_completions: int
    defaulted_count: int
    active_overdue: bool
    score_delta: int
    trust_cap: int
    trust_level: str


def _loan_completed_on_time(loan: LoanApplication) -> bool:
    if loan.status != "COMPLETED":
        return False
    return not loan.repayments.filter(is_on_time=False).exists()


def compute_repayment_trust(user) -> TrustSnapshot:
    loans = LoanApplication.objects.filter(user=user).prefetch_related("repayments")
    completed = [loan for loan in loans if loan.status == "COMPLETED"]
    defaulted_count = loans.filter(status="DEFAULTED").count()

    on_time_completions = sum(1 for loan in completed if _loan_completed_on_time(loan))
    late_completions = len(completed) - on_time_completions

    active_overdue = False
    for loan in loans.filter(status="DISBURSED"):
        if loan.due_date and timezone.now() > loan.due_date:
            active_overdue = True
            break

    score_delta = (
        on_time_completions * TRUST_SCORE_BONUS_ON_TIME
        + late_completions * TRUST_SCORE_BONUS_LATE
        - defaulted_count * TRUST_SCORE_PENALTY_DEFAULT
    )
    if active_overdue:
        score_delta -= TRUST_SCORE_PENALTY_OVERDUE

    trust_cap = STARTER_MAX_LOAN + (
        on_time_completions * TRUST_CAP_BONUS_ON_TIME
        + late_completions * TRUST_CAP_BONUS_LATE
    )

    if defaulted_count > 0:
        trust_cap = min(trust_cap, DEFAULT_REHAB_CAP + on_time_completions * TRUST_CAP_BONUS_ON_TIME)
    if active_overdue:
        trust_cap = min(trust_cap, OVERDUE_CAP_CEILING)

    trust_level = _trust_level(
        completed_count=len(completed),
        on_time=on_time_completions,
        defaulted=defaulted_count,
        active_overdue=active_overdue,
    )

    return TrustSnapshot(
        completed_loans=len(completed),
        on_time_completions=on_time_completions,
        late_completions=late_completions,
        defaulted_count=defaulted_count,
        active_overdue=active_overdue,
        score_delta=score_delta,
        trust_cap=int(trust_cap),
        trust_level=trust_level,
    )


def _trust_level(*, completed_count: int, on_time: int, defaulted: int, active_overdue: bool) -> str:
    if active_overdue or defaulted > 0:
        return "at_risk"
    if completed_count == 0:
        return "starter"
    if on_time >= 3:
        return "trusted"
    return "building"


def apply_trust_to_score(profile_score: int, trust: TrustSnapshot) -> int:
    score = profile_score + trust.score_delta
    score = max(0, min(100, score))
    if trust.defaulted_count == 0 and not trust.active_overdue:
        score = max(score, STARTER_CREDIT_SCORE)
    return int(score)


def effective_max_loan(profile_tier_max: float, trust: TrustSnapshot, platform_max: int) -> int:
    min_amount = 5_000
    capped = min(int(trust.trust_cap), int(profile_tier_max), platform_max)
    if capped < min_amount:
        return 0
    return capped
