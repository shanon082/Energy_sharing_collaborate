from django.urls import include, path

from backend.features import FeatureAvailabilityView

from meter.api.keypad_views import BenchRedeemView, BenchAcknowledgeView, BenchSessionView

from meter.api.prototype_views import (PrototypeSessionView, PrototypeRedeemView, PrototypeAckView,
    PrototypeTelemetryView, PrototypeMeasurementPrepareView, PrototypeMeasurementCommitView)

urlpatterns = [
    path("prototype-device/v1/session/", PrototypeSessionView.as_view()),
    path("prototype-device/v1/redeem/", PrototypeRedeemView.as_view()),
    path("prototype-device/v1/ack/", PrototypeAckView.as_view()),
    path("prototype-device/v1/telemetry/", PrototypeTelemetryView.as_view()),
    path("prototype-device/v1/measurement/prepare/", PrototypeMeasurementPrepareView.as_view()),
    path("prototype-device/v1/measurement/commit/", PrototypeMeasurementCommitView.as_view()),
    path("bench-device/v1/session/", BenchSessionView.as_view()),
    path("bench-device/v1/redeem/", BenchRedeemView.as_view()),
    path("bench-device/v1/ack/", BenchAcknowledgeView.as_view()),
    path("sandbox/", include("loan.sandbox_urls")),
    path("features/", FeatureAvailabilityView.as_view(), name="features"),
    path(
        "auth/",
        include(("accounts.api.urls", "auth"), namespace="auth"),
    ),
    path(
        "meter/",
        include(
            ("meter.api.urls", "meter"), namespace="meter"
        ),
    ),
    path(
        "transactions/",
        include(
            ("transactions.api.urls", "transactions"), namespace="transactions"
        ),
    ),
    path(
        "webhooks/",
        include(
            ("webhooks.api.urls", "webhooks"), namespace="webhooks"
        ),
    ),
    path(
        "loans/",
        include(
            ("loan.api.urls", "loan"), namespace="loan"
        ),
    ),
    path(
        "wallet/",
        include(
            ("wallet.urls", "wallet"), namespace="wallet" 
        ),
    ),
    path(
        "share/",
        include(
            ("share.urls", "share"), namespace="share"
        ),
    ),
    path(
        "ussd/",
        include(
            ("ussd.urls", "ussd"), namespace="ussd"
        ),
    ),
]
