from django.urls import path
from transactions.api.mobile_views import MobilePaymentReceiptsView, MobilePaymentRecoveryView
from transactions.api.mobile_views import MobilePaymentReceiptView, MobileTransactionHistoryView
from .views import BuyUnitsView, TransactionHistoryView, TransactionStatementEmailView





urlpatterns = [
    path("mobile-payment-recovery/", MobilePaymentRecoveryView.as_view(), name="mobile-payment-recovery"),
    path('mobile-history/', MobileTransactionHistoryView.as_view(), name='mobile-transaction-history'),
    path('mobile-receipts/<uuid:reference>/', MobilePaymentReceiptView.as_view(), name='mobile-payment-receipt'),
    path('mobile-receipts/', MobilePaymentReceiptsView.as_view(), name='mobile-payment-receipts'),
    path('buy-units/', BuyUnitsView.as_view(), name="buy-units"),
    path('history/', TransactionHistoryView.as_view(), name="transaction-history"),
    path('statement/email/', TransactionStatementEmailView.as_view(), name="transaction-statement-email"),
]
