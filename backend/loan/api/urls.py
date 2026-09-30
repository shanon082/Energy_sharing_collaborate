from django.urls import path

from .views import (
    ActiveLoanRepaymentView,
    LoanApplicationView,
    LoanDetailView,
    LoanDisbursementView,
    LoanLookupByPhoneView,
    LoanNotificationView,
    LoanRepaymentView,
    LoanStatsView,
    PayForSomeoneView,
    RepayableLoanView,
    TariffListView,
    UserLoansView,
    CreditScoreView,
)
from transactions.api.payment_views import VerifiedLoanRepaymentView, VerifiedLoanPaymentStatusView
from webhooks.api.views import LoanTokenVerificationView

urlpatterns = [
    path('apply/', LoanApplicationView.as_view(), name='loan-apply'),
    path('my-loans/', UserLoansView.as_view(), name='user-loans'),
    path('stats/', LoanStatsView.as_view(), name='loan-stats'),
    path('repayable/', RepayableLoanView.as_view(), name='loan-repayable'),
    path('repay/active/', ActiveLoanRepaymentView.as_view(), name='loan-repay-active'),
    path('loan/<int:pk>/', LoanDetailView.as_view(), name='loan-detail'),
    path('repay/<int:loan_id>/', LoanRepaymentView.as_view(), name='loan-repay'),
    path('disburse/<int:loan_id>/', LoanDisbursementView.as_view(), name='loan-disburse'),
    path('notify/<int:loan_id>/', LoanNotificationView.as_view(), name='loan-notify'),
    path('verify-token/', LoanTokenVerificationView.as_view(), name='verify-token'),
    path('repay/momo/<int:loan_id>/', VerifiedLoanRepaymentView.as_view(), name='loan-repay-momo'),
    path('repay/momo/active/', VerifiedLoanRepaymentView.as_view(), name='loan-repay-momo-active'),
    path('payment-status/<str:external_id>/', VerifiedLoanPaymentStatusView.as_view(), name='payment-status'),
    # path('momo-callback/', MoMoPaymentCallbackView.as_view(), name='momo-callback'),
    path('tariffs/', TariffListView.as_view(), name='tariff-list'),
    path('credit-score/', CreditScoreView.as_view(), name='credit-score'),
    path('lookup-by-phone/', LoanLookupByPhoneView.as_view(), name='loan-lookup-by-phone'),
    path('pay-for-someone/', PayForSomeoneView.as_view(), name='loan-pay-for-someone'),
]
