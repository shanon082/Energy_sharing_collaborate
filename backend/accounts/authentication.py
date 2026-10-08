"""Account state checks for JWT requests, including shared web/mobile routes."""

from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication

from accounts.models import User


class AccountJWTAuthentication(JWTAuthentication):
    # Identity and password-change bootstrap must remain reachable for the
    # existing Next.js and Android required-password-change screens.
    PASSWORD_CHANGE_PATHS = frozenset({
        "/api/v1/auth/mobile-account/", "/api/v1/auth/mobile-password/",
        "/api/v1/auth/mobile-logout/", "/api/v1/auth/get-user-config/",
        "/api/v1/auth/change-required-password/",
    })

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, _token = result
        if user.user_role == User.CLIENT and not user.is_staff and not user.is_superuser:
            if request.path != "/api/v1/auth/mobile-logout/":
                profile = getattr(user, "profile", None)
                if profile is None or not profile.email_verified:
                    raise PermissionDenied({"code": "UNVERIFIED", "detail": "Verify your email before continuing."})
            if user.must_change_password and request.path not in self.PASSWORD_CHANGE_PATHS:
                raise PermissionDenied({"code": "PASSWORD_CHANGE_REQUIRED", "detail": "Change your password before continuing."})
        return result
