from django.urls import path
from .views import (
    WalletBalanceView,
    TransactionHistoryView,
    CreateWalletView,
    WalletDepositView,
    WalletWithdrawView,
)

urlpatterns = [
    path('balance/', WalletBalanceView.as_view(), name='wallet-balance'),
    path('transactions/', TransactionHistoryView.as_view(), name='transaction-history'),
    path('create/', CreateWalletView.as_view(), name='create-wallet'),
    path('deposit/', WalletDepositView.as_view(), name='wallet-deposit'),
    path('withdraw/', WalletWithdrawView.as_view(), name='wallet-withdraw'),
]
