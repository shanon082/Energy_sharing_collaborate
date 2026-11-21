from django.urls import path
from loan.sandbox_api import (SandboxAssessmentView, SandboxQuoteView, SandboxLoanView, SandboxPaymentView,
    SandboxPaymentStatusView, SandboxStaffDecisionView, SandboxLoanRecoveryView, SandboxPaymentRecoveryView, ConsumerSummaryView, SandboxCheckoutRetryView)

urlpatterns = [
    path("summary/", ConsumerSummaryView.as_view()),
    path("assessment/", SandboxAssessmentView.as_view()),
    path("quotes/", SandboxQuoteView.as_view()),
    path("loans/", SandboxLoanView.as_view()),
    path("loan-recovery/<uuid:request_id>/", SandboxLoanRecoveryView.as_view()),
    path("payments/", SandboxPaymentView.as_view()),
    path("payments/<uuid:reference>/", SandboxPaymentStatusView.as_view()),
    path("payments/<uuid:reference>/retry/", SandboxCheckoutRetryView.as_view()),
    path("payment-recovery/<uuid:request_id>/", SandboxPaymentRecoveryView.as_view()),
    path("staff/decisions/", SandboxStaffDecisionView.as_view()),
]
