"""Account browser pages exist only in the app-first testing profile."""

from django.urls import path

from accounts.account_pages import reset_password, verify_email
from backend.urls import urlpatterns as api_patterns

urlpatterns = [
    path("account/verify-email/", verify_email, name="account-verify-email"),
    path("account/reset-password/", reset_password, name="account-reset-password"),
    *api_patterns,
]
