# meter/urls.py - Add the new endpoint

from django.urls import path
from meter.api.mobile_views import MobileConsumptionHistoryView, MobileDeliveryHistoryView
from .views import (
    BuyUnitsView, 
    CheckPaymentStatusView, 
    MeterRegisterView,
    LoadTokenToMeterView,
)

from .views import (
    ActivateReceivedUnitsView,
    AdminMeterPushTestView,
    BuyUnitsView,
    CheckPaymentStatusView,
    EstimateUnitsView,
    ApplyWalletToMeterView,
    GenerateTokenFromWalletView,
    MeterPushTestView,
    MeterRegisterView,
    ReceiveUnitsView,
    SendUnitsView,
    TokenView,
    update_meter,
    check_user_meter,
    delete_user_meter,
)

from meter.api import views
from transactions.api.payment_views import VerifiedPurchaseView, VerifiedPurchaseStatusView
from meter.api.delivery_views import (
    AllocationStatusView, DeliveryRequestView,
    SimulatorAcknowledgementView, SimulatorTelemetryView,
)


urlpatterns = [
    path('mobile-consumption/', MobileConsumptionHistoryView.as_view(), name='mobile-consumption'),
    path('mobile-deliveries/', MobileDeliveryHistoryView.as_view(), name='mobile-deliveries'),
    path('send-units/', SendUnitsView.as_view(), name="send-units"),
    path('receive-units/', ReceiveUnitsView.as_view(), name="receive-units"),
    path('token/', TokenView.as_view(), name="token"),
    path('buy-units/', VerifiedPurchaseView.as_view(), name="buy-units"),
    path('check-payment-status/', VerifiedPurchaseStatusView.as_view(), name="check-payment-status"),
    path('test-meter-push/', MeterPushTestView.as_view(), name="test-meter-push"),
    path('admin-test-meter-push/', AdminMeterPushTestView.as_view(), name="admin-test-meter-push"),
    path('register/', MeterRegisterView.as_view(), name='register-meter'),
    path('my-meter/', check_user_meter, name='check-user-meter'),
    path('ami-status/', views.ami_meter_status, name='ami-meter-status'),
    path('thingsboard-health/', views.thingsboard_health, name='thingsboard-health'),
    path('check-units/', views.check_meter_units, name='check-meter-units'),
    path('ledger-history/', views.meter_ledger_history, name='meter-ledger-history'),
    path('notifications/', views.meter_notifications, name='meter-notifications'),
    path('update/', update_meter, name='update-meter'),
    path('load-token/', LoadTokenToMeterView.as_view(), name='load-token'),  # New endpoint
    path('delete/', delete_user_meter, name='delete-meter'),
    # STS: generate token for pending (received/shared) units
    path('activate-received-units/', ActivateReceivedUnitsView.as_view(), name='activate-received-units'),
    # STS: generate token by drawing from wallet balance (for purchased units)
    path('generate-token/', GenerateTokenFromWalletView.as_view(), name='generate-token'),
    # AMI: apply wallet kWh to networked meter (no token)
    path('apply-wallet-units/', ApplyWalletToMeterView.as_view(), name='apply-wallet-units'),
    path('deliver/', DeliveryRequestView.as_view(), name='deliver-allocation'),
    path('allocation-status/', AllocationStatusView.as_view(), name='allocation-status'),
    path('simulator/ack/', SimulatorAcknowledgementView.as_view(), name='simulator-ack'),
    path('simulator/telemetry/', SimulatorTelemetryView.as_view(), name='simulator-telemetry'),
    path('power-usage/', views.power_usage, name='power-usage'),
    # Estimate kWh yield for a given UGX amount (no side effects)
    path('estimate-units/', EstimateUnitsView.as_view(), name='estimate-units'),
]
