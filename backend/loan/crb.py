"""
Credit Reference Bureau (CRB) integration seam.

Uganda's licensed CRBs (as of 2025):
  - gnuGrid CRB Limited (gnugrid.co.ug)
  - Metropol CRB Uganda (metropol.co.ug)
  - Creditinfo CRB Uganda
  - Armada Credit Bureau

The platform's internal credit scoring (UserCreditSignal + purchase-history-based
scoring) is a complement to CRB reports, not a replacement. CRB data can enrich the
score in the future; for the pilot, the NoOpCreditBureauProvider is used.

To integrate a real CRB:
  1. Subclass CreditBureauProvider.
  2. Implement fetch_report() to call the CRB's API and map the response to CreditReport.
  3. Point CRB_PROVIDER in settings to your class path, e.g.
       CRB_PROVIDER = 'loan.crb.MetropolCRBProvider'
  4. Wire it into the credit-scoring flow in loan/api/views.py where UserCreditSignal is used.
"""
from backend.features import feature_enabled, requires_feature

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CreditReport:
    """Normalised CRB report returned by any provider."""
    crb_name: str
    reference_id: str
    score: Optional[int] = None                 # CRB-native score if provided
    has_active_default: bool = False            # True if the bureau reports a current default
    num_active_credit_facilities: int = 0
    total_outstanding_ugx: float = 0.0
    raw: dict = field(default_factory=dict)     # Full raw response for auditing


class CreditBureauProvider:
    """
    Abstract base. Every real CRB integration must subclass this and
    implement fetch_report().
    """

    def fetch_report(self, national_id: str, user=None) -> Optional[CreditReport]:
        """
        Fetch a CRB report for the given national ID.
        Returns None if the bureau cannot find the individual or the call fails.
        Implementations should log errors rather than raising, so a CRB outage
        never blocks a legitimate loan application at the platform level.
        """
        raise NotImplementedError


class NoOpCreditBureauProvider(CreditBureauProvider):
    """
    Default provider for the pilot — returns None (no CRB data).
    The internal credit score is used as-is.
    """

    def fetch_report(self, national_id: str, user=None) -> Optional[CreditReport]:
        logger.debug("NoOpCreditBureauProvider: CRB lookup skipped for pilot")
        return None


# ---------------------------------------------------------------------------
# Stubs for future integrations (do not delete; switch via settings.CRB_PROVIDER)
# ---------------------------------------------------------------------------

class MetropolCRBProvider(CreditBureauProvider):
    """
    STUB — Metropol CRB Uganda integration.
    Ask the developer for: API endpoint, client ID, secret, certificate.
    """

    @requires_feature("external_crb")
    def fetch_report(self, national_id: str, user=None) -> Optional[CreditReport]:
        raise NotImplementedError("MetropolCRBProvider is a stub. Implement with Metropol API credentials.")


class GnuGridCRBProvider(CreditBureauProvider):
    """
    STUB — gnuGrid CRB Limited integration.
    Ask the developer for: Consumer Portal API credentials.
    """

    @requires_feature("external_crb")
    def fetch_report(self, national_id: str, user=None) -> Optional[CreditReport]:
        raise NotImplementedError("GnuGridCRBProvider is a stub. Implement with gnuGrid API credentials.")


def get_crb_provider() -> CreditBureauProvider:
    """Return the active CRB provider based on settings.CRB_PROVIDER (default: NoOp)."""
    from django.conf import settings
    import importlib

    if not feature_enabled("external_crb"):
        return NoOpCreditBureauProvider()

    provider_path = getattr(settings, 'CRB_PROVIDER', 'loan.crb.NoOpCreditBureauProvider')
    module_path, class_name = provider_path.rsplit('.', 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls()
