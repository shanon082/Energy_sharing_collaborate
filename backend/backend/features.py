"""Guards for new optional activity. Settlement/history are deliberately ungated."""

from functools import wraps

from django.conf import settings
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.feature_config import FEATURE_ENV_VARS, RETIRED_FEATURES


def feature_enabled(feature):
    if feature in RETIRED_FEATURES:
        return False
    if feature not in FEATURE_ENV_VARS:
        raise ValueError(f"Unknown feature: {feature}")
    return getattr(settings, "FEATURE_FLAGS", {}).get(feature) is True


class FeatureDisabled(APIException):
    status_code = 403
    default_code = "FEATURE_DISABLED"

    def __init__(self, feature):
        super().__init__({
            "code": "FEATURE_DISABLED",
            "feature": feature,
            "message": "This feature is currently disabled. Existing records remain available.",
        })


def require_feature(feature):
    if not feature_enabled(feature):
        raise FeatureDisabled(feature)


def requires_feature(feature):
    """Place outside the handler body so its broad exception catches cannot hide 403."""
    def decorate(handler):
        @wraps(handler)
        def guarded(*args, **kwargs):
            require_feature(feature)
            return handler(*args, **kwargs)
        return guarded
    return decorate


class FeatureAvailabilityView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        from transactions.payment_settlement import PaymentSettlementError, require_real_ugx_provider
        provider_ready = False
        try:
            require_real_ugx_provider()
            provider_ready = True
        except PaymentSettlementError:
            pass
        from mtn_momo.sandbox import configured
        from backend.demo_config import test_domain, LOCAL_DEMO, new_mtn_payments_paused
        from backend.ugx_authorization import business_domain as authorization_enabled, enabled as authorization_active, missing_required_authorization
        from transactions.ugx_authorization import AUTHORIZATION
        mapped = authorization_enabled()
        currency, environment, provider = test_domain()
        sandbox_enabled = getattr(settings, "CONSUMER_SANDBOX_ENABLED", False) is True
        payments_paused = provider == "MTN_SANDBOX" and (new_mtn_payments_paused() or missing_required_authorization())
        test_payments = sandbox_enabled and not payments_paused and (provider == LOCAL_DEMO or configured())
        from loan.sandbox_service import policy, eur_pricing_available
        energy_pricing = mapped or provider == LOCAL_DEMO or eur_pricing_available(policy())
        loan_policy = provider == LOCAL_DEMO or getattr(settings, "SANDBOX_EUR_LOANS_ENABLED", False) is True
        from meter.prototype_device import enabled as lab_enabled, permitted_environment, DOMAIN_PROTOCOLS, require_mtn_purchase_tokens
        tokens_ready = True
        try:
            require_mtn_purchase_tokens()
        except PaymentSettlementError:
            tokens_ready = False
        from loan.prototype_lending import enabled as ugx_loans_enabled
        ugx_loans = ugx_loans_enabled()
        purchase_reason = (
            "Consumer sandbox is disabled." if not sandbox_enabled else
            "Sandbox payments unavailable: activate SANDBOX_UGX_AUTHORIZATION_ENABLED; legacy EUR charging is not a fallback." if missing_required_authorization() else
            "New MTN payment instructions are paused by server configuration; existing receipts and submitted references remain recoverable." if payments_paused else
            "Sandbox payments unavailable: MTN Sandbox credentials are not configured." if not test_payments else
            "EUR test pricing unavailable: configure the versioned EUR purchase policy." if not energy_pricing else
            "Sandbox token service unavailable: review the token service configuration." if not tokens_ready else ""
        )
        loan_reason = (
            "Sandbox token service unavailable: review the token service configuration." if ugx_loans and not tokens_ready else
            "" if ugx_loans or sandbox_enabled and energy_pricing and loan_policy else
            "UGX loan applications are disabled in this hosting profile. Legacy EUR loan origination remains disabled."
        )
        repayment_reason = (
            "Consumer sandbox is disabled." if not sandbox_enabled else
            "Sandbox payments unavailable: activate SANDBOX_UGX_AUTHORIZATION_ENABLED; legacy EUR charging is not a fallback." if missing_required_authorization() else
            "New MTN payment instructions are paused. EUR receipts cannot repay UGX debt except through the separately bound test-authorization instruction." if payments_paused else
            "Sandbox payments unavailable: MTN Sandbox credentials are not configured." if not test_payments else ""
        )
        response = Response({
            "sandbox": {"enabled": sandbox_enabled, "currency": currency, "environment": environment, "label": "UGX TEST / NO REAL MONEY" if mapped else "UGX DEMO / NO REAL MONEY" if provider == LOCAL_DEMO else "EUR TEST / MTN SANDBOX",
                        **({"authorization": {**AUTHORIZATION, "enabled": authorization_active(), "energy_environment": "SANDBOX"}} if mapped else {}),
                        "capability_version": "GPAWA-CONSUMER-v2",
                        "action_reasons": {"loan": loan_reason, "purchase": purchase_reason, "repayment": repayment_reason},
                        "ugx_payments": {"enabled": (mapped or provider == LOCAL_DEMO) and test_payments,
                                         "code": "UGX-MTN-TEST-AUTH-v1" if mapped else "TEST_AUTHORIZATION_MAPPING_REQUIRED" if provider != LOCAL_DEMO else "LOCAL_DEMO",
                                         "message": "Approved noncash test authorization; provider EUR evidence stays separate from UGX instructions." if mapped else "UGX business payments with MTN EUR test authorization require a separately approved mapping. No conversion is implemented." if provider != LOCAL_DEMO else "Local demo only; no real money."},
                        "loans": sandbox_enabled and energy_pricing and loan_policy and not mapped, "purchases": test_payments and energy_pricing and tokens_ready, "repayments": test_payments,
                        'lending': {'enabled': ugx_loans and tokens_ready, 'currency': 'UGX', 'environment': 'UGX_DEMO', 'energy_environment': 'SANDBOX',
                                    'policy': 'DEMO-UGX-ACLAB-v1', 'repayment_available': mapped and test_payments},
                        "new_payments_paused": payments_paused,
                        "payment_message": "New UGX test payment instructions are paused; existing receipts and submitted references remain recoverable." if mapped and payments_paused else "New payments paused: MTN Sandbox accepts EUR only. UGX loans remain available; no EUR payment can repay UGX debt. Existing receipts and pending recovery remain available." if payments_paused else "Sandbox payments unavailable" if not test_payments else "Sandbox token service unavailable" if not tokens_ready else "",
                        "ac_lab": {"enabled": lab_enabled(), "environment": permitted_environment(),
                                   "protocol": DOMAIN_PROTOCOLS.get(permitted_environment()), "physical_output": False},
                        "provider": provider, "physical_delivery": False,
                        "self_declared_meter_enrollment": sandbox_enabled},
            "features": {
                **{feature: False for feature in RETIRED_FEATURES},
                **{key: feature_enabled(key) for key in FEATURE_ENV_VARS},
            },
            "consumer_capabilities": {
                "meter_requests": True, "sandbox_self_enrollment": sandbox_enabled, "read_only_monitoring": True,
                "provisional_quotes": True,
                "purchase_history_scoring": getattr(settings, "PURCHASE_HISTORY_SCORING_ENABLED", False) is True,
                "background_processing_configured": getattr(settings, "BACKGROUND_TASKS_AVAILABLE", False) is True,
                "simulator_delivery_environment": bool(not getattr(settings, "ALWAYSDATA_TESTING", False)
                                        and getattr(settings, "SIMULATED_METER_ENABLED", False)
                                        and getattr(settings, "DEBUG", False)),
                "physical_meter": False,
            },
            "mobile_actions": {
                "purchase": bool(getattr(settings, "MOBILE_PAYMENT_ACTIONS_ENABLED", False) and provider_ready),
                "repayment": bool(getattr(settings, "MOBILE_PAYMENT_ACTIONS_ENABLED", False) and provider_ready),
                "loan_application": False,
            },
        })
        response["Cache-Control"] = "no-store"
        return response
