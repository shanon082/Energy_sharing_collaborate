"""Evidence provider boundary, independent of the existing scoring calculation."""
from typing import Protocol

SCENARIOS = {
    "APPROVAL_V1": {"payment_history": "GOOD", "energy_consumption": "MODERATE", "financial_capacity": "STRONG"},
    "REJECTION_V1": {"payment_history": "POOR", "energy_consumption": "ERRATIC", "financial_capacity": "WEAK"},
}
PROVIDER_ID = "SIMULATED_ACCOUNT_V1"
SCORING_VERSION = "DEMO-SCORE-v1"


class AccountDataUnavailable(Exception):
    pass


class AccountDataProvider(Protocol):
    def fetch(self, scenario: str) -> dict: ...


class SimulatedAccountDataProvider:
    """Fixed synthetic categories, no PII, random selection or external request."""
    def fetch(self, scenario):
        if scenario not in SCENARIOS:
            raise AccountDataUnavailable("No supported simulated profile")
        return {"provider": PROVIDER_ID, "provenance": "SIMULATED_ACCOUNT_INFORMATION",
                "scenario": scenario, "categories": dict(SCENARIOS[scenario]),
                "verified_external_records": False}


def account_data_provider() -> AccountDataProvider:
    # No utility/bank/telecom/CRB integration exists or is selected in this profile.
    return SimulatedAccountDataProvider()
