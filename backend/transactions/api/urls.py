from django.urls import path
from .views import BuyUnitsView, TransactionHistoryView, TransactionStatementEmailView





urlpatterns = [
    path('buy-units/', BuyUnitsView.as_view(), name="buy-units"),
    path('history/', TransactionHistoryView.as_view(), name="transaction-history"),
    path('statement/email/', TransactionStatementEmailView.as_view(), name="transaction-statement-email"),
]