"""Account browser pages exist only in the app-first testing profile."""

from django.urls import path

from accounts.account_pages import reset_password, verify_email
from backend.urls import urlpatterns as api_patterns
from meter.review_pages import meter_requests
from loan.sandbox_staff import decisions

urlpatterns = [
    path("admin-panel/sandbox-decisions/", decisions, name="staff-sandbox-decisions"),
    path("admin-panel/meter-link-requests/", meter_requests, name="staff-meter-requests"),
    path("account/verify-email/", verify_email, name="account-verify-email"),
    path("account/reset-password/", reset_password, name="account-reset-password"),
    *api_patterns,
]
