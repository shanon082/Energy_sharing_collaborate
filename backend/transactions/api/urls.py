from django.urls import path
from transactions.api.mobile_views import MobilePaymentReceiptsView
from .views import BuyUnitsView, TransactionHistoryView, TransactionStatementEmailView





urlpatterns = [
    path('mobile-receipts/', MobilePaymentReceiptsView.as_view(), name='mobile-payment-receipts'),
    path('buy-units/', BuyUnitsView.as_view(), name="buy-units"),
    path('history/', TransactionHistoryView.as_view(), name="transaction-history"),
    path('statement/email/', TransactionStatementEmailView.as_view(), name="transaction-statement-email"),
]
