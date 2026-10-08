"""Server-side access boundary for consumer mobile endpoints."""

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from accounts.models import Profile, User


class ConsumerAccountPermission(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if not user.is_active:
            raise PermissionDenied({"code": "ACCOUNT_INACTIVE", "detail": "The account is inactive."})
        if user.user_role != User.CLIENT or user.is_staff or user.is_superuser:
            raise PermissionDenied({"code": "CONSUMER_ONLY", "detail": "Use the web app for staff accounts."})
        try:
            verified = user.profile.email_verified
        except Profile.DoesNotExist:
            verified = False
        if not verified and not getattr(view, "allow_unverified_account", False):
            raise PermissionDenied({"code": "UNVERIFIED", "detail": "Verify your email before accessing your account."})
        if user.must_change_password and not getattr(view, "allow_required_password_change", False):
            raise PermissionDenied({"code": "PASSWORD_CHANGE_REQUIRED", "detail": "Change your password before continuing."})
        return True
