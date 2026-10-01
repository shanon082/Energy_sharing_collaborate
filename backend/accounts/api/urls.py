from accounts.api.views import (
    AccountDetailsAPIView,
    CreateUserAPIView,
    ResendVerificationEmailAPIView,
    ResetPasswordAPIView,
    SettingsAPIView,
    UpdateAccountDetailsAPIView,
    VerifyEmailAPIView,
    LoginAPIView,
    ForgotPasswordAPIView,
    UserConfigAPIView,
    RequiredPasswordChangeAPIView,
    # user_profile_view,
    UserProfileAPIView,
    # RawUserProfileAPIView,
    # UpdateUserProfileAPIView,
)
from django.urls import path, include

from rest_framework_simplejwt.views import (
    TokenRefreshView,
)
from accounts.api.mobile_views import MobileAccountView, MobileLogoutView, MobileProfileView, MobilePasswordView

urlpatterns = [
    path("mobile-account/", MobileAccountView.as_view(), name="mobile-account"),
    path("mobile-logout/", MobileLogoutView.as_view(), name="mobile-logout"),
    path("mobile-profile/", MobileProfileView.as_view(), name="mobile-profile"),
    path("mobile-password/", MobilePasswordView.as_view(), name="mobile-password"),
    path("register/", CreateUserAPIView.as_view(), name="register"),
    path(
        "verify-email/",
        view=VerifyEmailAPIView.as_view(),
        name="verify_email",
    ),
    path("login/", LoginAPIView.as_view(), name="login"),
    path("refresh/token/", TokenRefreshView.as_view(), name="refresh_token"),
    path(
        "get-user-config/",
        view=UserConfigAPIView.as_view(),
        name="get_user_config",
    ),
    path(
        "change-required-password/",
        view=RequiredPasswordChangeAPIView.as_view(),
        name="change_required_password",
    ),

   
    path(
        "forgot-password/",
        view=ForgotPasswordAPIView.as_view(),
        name="forgot_password",
    ),
    path(
        "reset-password/",
        view=ResetPasswordAPIView.as_view(),
        name="reset_password",
    ),
    path(
        "resend-email-link/",
        view=ResendVerificationEmailAPIView.as_view(),
        name="resend-email-link",
    ),
    path(
        "security-code/",
        view=SettingsAPIView.as_view(),
        name="security-code",
    ),
    path(
        "account-details/",
        view=AccountDetailsAPIView.as_view(),
        name="account_details",
    ),
    path(
        "update-account-details/",
        view=UpdateAccountDetailsAPIView.as_view(),
        name="update_account_details",
    ),
    path(
    "user-profile/",
    view=UserProfileAPIView.as_view(),
    name="user_profile",
    ),
]
