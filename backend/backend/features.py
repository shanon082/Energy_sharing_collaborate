"""Guards for new optional activity. Settlement/history are deliberately ungated."""

from functools import wraps

from django.conf import settings
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.feature_config import FEATURE_ENV_VARS


def feature_enabled(feature):
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
        response = Response({
            "features": {key: feature_enabled(key) for key in FEATURE_ENV_VARS},
            "mobile_actions": {
                "purchase": bool(getattr(settings, "MOBILE_PAYMENT_ACTIONS_ENABLED", False) and provider_ready),
                "repayment": bool(getattr(settings, "MOBILE_PAYMENT_ACTIONS_ENABLED", False) and provider_ready),
                "loan_application": False,
            },
        })
        response["Cache-Control"] = "no-store"
        return response
