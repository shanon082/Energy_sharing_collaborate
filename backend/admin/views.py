"""
EnergyWallet Admin & Operator API Views
Implements Sections 1–10 of the Admin & Operator Guide (Part 2).

Permission matrix (Section 2.2):
  CUSTOMER_SERVICE : view/edit users, transactions, active loans, flags
  OPERATOR         : all CS + meter register, reports, export
  ADMIN            : full access including suspend, deactivate, staff mgmt, system
"""

import logging
import secrets
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core import signing
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Profile, UserAccountDetails
from accounts.utils import create_admin_provisioned_user
from loan.models import LoanApplication
from meter.models import Meter, Transaction
from .models import (
    AdminActivityLog,
    AdminNotificationSettings,
    AdminSession,
    AuditLog,
    FlaggedAccount,
    ScheduledReport,
    StaffInvitation,
)
from .serializers import (
    AdminNotificationSettingsSerializer,
    AdminPasswordChangeSerializer,
    AdminProfileSerializer,
)
from loan.api.serializers import LoanTierSerializer, ElectricityTariffSerializer
from loan.models import LoanTier, ElectricityTariff

logger = logging.getLogger(__name__)
User = get_user_model()


# --------------------------------------------------------------------------- #
#  RBAC helpers                                                                #
# --------------------------------------------------------------------------- #

def _get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def _write_audit(
    request,
    action_type,
    target_type=None,
    target_id=None,
    target_repr=None,
    details=None,
    notes='',
):
    """Utility to write a spec-compliant AuditLog entry."""
    try:
        AuditLog.objects.create(
            staff_member=request.user if request else None,
            action_type=action_type,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            target_repr=target_repr or '',
            details=details or {},
            ip_address=_get_client_ip(request) if request else None,
            user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
            notes=notes,
        )
    except Exception as exc:
        logger.error(f"Failed to write audit log: {exc}")


def _safe_int(raw_value, default: int, *, minimum: int | None = None, maximum: int | None = None) -> int:
    """Parse integers from query params without raising 500s on bad input."""
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


class RBACMixin:
    """
    Provides role-checking helpers.
    All protected views should call one of:
      _require_role(request, *roles)  — returns (ok, error_response)
    """

    def _require_role(self, request, *roles):
        if not request.user.is_authenticated:
            return False, Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if getattr(request.user, "is_superuser", False):
            return True, None
        if request.user.user_role not in roles:
            return False, Response(
                {"error": "Insufficient permissions"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return True, None

    # Convenience wrappers
    def _require_admin(self, request):
        return self._require_role(request, User.ADMIN)

    def _require_operator_or_admin(self, request):
        return self._require_role(request, User.OPERATOR, User.ADMIN)

    def _require_cs_or_above(self, request):
        return self._require_role(
            request, User.CUSTOMER_SERVICE, User.OPERATOR, User.ADMIN
        )

    # Legacy alias (used by existing code)
    def check_admin_permission(self, request):
        return self._require_admin(request)

    def log_admin_activity(self, user, action, details=None, request=None):
        try:
            AdminActivityLog.objects.create(
                user=user,
                action=action,
                details=details or {},
                ip_address=_get_client_ip(request) if request else '',
                user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
            )
        except Exception as exc:
            logger.error(f"Failed to log admin activity: {exc}")


# Keep legacy alias
AdminPermissionMixin = RBACMixin


# --------------------------------------------------------------------------- #
#  Section 1 — Dashboard                                                       #
# --------------------------------------------------------------------------- #

class AdminDashboardView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ok, err = self._require_cs_or_above(request)
        if not ok:
            return err

        try:
            today = timezone.now().date()
            last_week = today - timedelta(days=7)
            last_month = today - timedelta(days=30)

            # --- Users ---
            total_users = User.objects.filter(user_role=User.CLIENT).count()
            total_admins = User.objects.filter(
                user_role__in=[User.ADMIN, User.CUSTOMER_SERVICE, User.OPERATOR]
            ).count()
            total_meters = Meter.objects.count()
            active_meters = Meter.objects.filter(status=Meter.STATUS_ACTIVE).count()
            new_users_today = User.objects.filter(
                user_role=User.CLIENT, create_date__date=today
            ).count()
            new_users_week = User.objects.filter(
                user_role=User.CLIENT, create_date__date__gte=last_week
            ).count()
            verified_users = Profile.objects.filter(email_verified=True).count()
            users_with_meters = (
                User.objects.filter(user_role=User.CLIENT, devices__isnull=False)
                .distinct()
                .count()
            )

            # Active users (transacted in last 30 days) — per spec Section 1.5
            active_users_30d = (
                User.objects.filter(
                    user_role=User.CLIENT,
                    transactions__create_date__date__gte=last_month,
                )
                .distinct()
                .count()
            )

            # --- Transactions ---
            transactions_today = Transaction.objects.filter(
                create_date__date=today
            ).count()
            failed_today = Transaction.objects.filter(
                create_date__date=today, status=Transaction.STATUS_FAILED
            ).count()
            total_today = max(transactions_today, 1)
            failed_pct = round(failed_today / total_today * 100, 1)

            # --- Loans ---
            active_loans = LoanApplication.objects.filter(
                status__in=['ACTIVE', 'APPROVED']
            ).count()
            # due_date is a Python property — compute overdue in Python
            try:
                active_loan_list = LoanApplication.objects.filter(
                    status='ACTIVE'
                ).select_related('disbursement')
                overdue_loans = sum(
                    1 for l in active_loan_list
                    if l.due_date and l.due_date.date() < today
                )
                loans_30d_overdue = sum(
                    1 for l in active_loan_list
                    if l.due_date and l.due_date.date() < today - timedelta(days=30)
                )
            except Exception:
                overdue_loans = 0
                loans_30d_overdue = 0

            # --- Flagged accounts ---
            flagged_accounts = FlaggedAccount.objects.filter(
                status=FlaggedAccount.STATUS_OPEN
            ).count()

            # --- System status (simplified — Green unless errors detected) ---
            system_status = "GREEN"

            # --- Recent users ---
            recent_users = (
                User.objects.filter(user_role=User.CLIENT)
                .select_related('profile')
                .order_by('-create_date')[:10]
            )
            recent_users_list = []
            for u in recent_users:
                recent_users_list.append({
                    "id": u.id,
                    "email": u.email,
                    "name": f"{u.first_name} {u.last_name}",
                    "phone": str(u.phone_number) if u.phone_number else '',
                    "email_verified": getattr(getattr(u, 'profile', None), 'email_verified', False),
                    "joined": u.create_date.strftime("%Y-%m-%d %H:%M"),
                    "has_meter": u.devices.exists(),
                })

            return Response({
                "success": True,
                # Users
                "total_users": total_users,
                "total_admins": total_admins,
                "total_meters": total_meters,
                "active_meters": active_meters,
                "verified_users": verified_users,
                "users_with_meters": users_with_meters,
                "new_users_today": new_users_today,
                "new_users_week": new_users_week,
                "active_users_30d": active_users_30d,
                # Transactions (Section 1.5 widgets)
                "transactions_today": transactions_today,
                "failed_transactions_today": failed_today,
                "failed_transaction_pct": failed_pct,
                # Loans
                "active_loans": active_loans,
                "overdue_loans": overdue_loans,
                "loans_30d_overdue": loans_30d_overdue,
                # Flags / status
                "flagged_accounts": flagged_accounts,
                "system_status": system_status,
                # Legacy compatibility
                "total_loans": active_loans,
                "pending_loans": LoanApplication.objects.filter(status='PENDING').count(),
                "outstanding_balance": 0,
                "recent_registrations": new_users_week,
                "verification_rate": round(
                    (verified_users / total_users * 100) if total_users > 0 else 0, 1
                ),
                "recent_users": recent_users_list,
                "timestamp": datetime.now().isoformat(),
            })

        except Exception as exc:
            logger.error(f"Admin dashboard error: {exc}")
            return Response(
                {"error": "Failed to fetch dashboard data"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# --------------------------------------------------------------------------- #
#  Section 2 — Staff Account Management (Admin only)                          #
# --------------------------------------------------------------------------- #

class StaffListView(APIView, RBACMixin):
    """GET all staff accounts; POST to create invitation."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ok, err = self._require_admin(request)
        if not ok:
            return err

        staff = User.objects.filter(
            user_role__in=[User.ADMIN, User.CUSTOMER_SERVICE, User.OPERATOR]
        ).select_related('profile').order_by('-create_date')

        staff_list = []
        for u in staff:
            staff_list.append({
                "id": u.id,
                "email": u.email,
                "full_name": f"{u.first_name} {u.last_name}",
                "phone_number": str(u.phone_number) if u.phone_number else '',
                "role": u.user_role,
                "account_active": u.account_is_active,
                "email_verified": getattr(getattr(u, 'profile', None), 'email_verified', False),
                "created_at": u.create_date.isoformat(),
                "last_login": u.last_login.isoformat() if u.last_login else None,
            })

        pending_invitations = StaffInvitation.objects.filter(
            status=StaffInvitation.PENDING
        ).values('id', 'email', 'full_name', 'role', 'created_at', 'expires_at')

        return Response({
            "success": True,
            "staff": staff_list,
            "pending_invitations": list(pending_invitations),
        })

    def post(self, request):
        """Create a new staff invitation (Admin only, Section 2.3)."""
        ok, err = self._require_admin(request)
        if not ok:
            return err

        email = request.data.get('email', '').strip()
        full_name = request.data.get('full_name', '').strip()
        phone_number = request.data.get('phone_number', '').strip()
        department = request.data.get('department', '').strip()
        role = request.data.get('role', '').strip()

        if not email or not full_name or not role:
            return Response(
                {"error": "email, full_name, and role are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        allowed_roles = [User.CUSTOMER_SERVICE, User.OPERATOR, User.ADMIN]
        if role not in allowed_roles:
            return Response(
                {"error": f"role must be one of {allowed_roles}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(email=email).exists():
            return Response(
                {"error": "A user with this email already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token = secrets.token_urlsafe(48)
        invitation = StaffInvitation.objects.create(
            email=email,
            full_name=full_name,
            phone_number=phone_number,
            department=department,
            role=role,
            token=token,
            invited_by=request.user,
            expires_at=timezone.now() + timedelta(days=7),
        )

        _write_audit(
            request,
            action_type=AuditLog.ACTION_STAFF_CREATE,
            target_type=AuditLog.TARGET_STAFF,
            target_id=invitation.id,
            target_repr=f"{full_name} <{email}> ({role})",
            details={"email": email, "role": role},
            notes=f"Invitation sent to {email}",
        )

        return Response({
            "success": True,
            "message": f"Invitation sent to {email}",
            "invitation_id": invitation.id,
            "token": token,  # In production, email this; expose here for testing
        }, status=status.HTTP_201_CREATED)


class StaffDetailView(APIView, RBACMixin):
    """GET/PUT/DELETE individual staff account."""
    permission_classes = [IsAuthenticated]

    def get(self, request, staff_id):
        ok, err = self._require_admin(request)
        if not ok:
            return err

        try:
            u = User.objects.get(
                id=staff_id,
                user_role__in=[User.ADMIN, User.CUSTOMER_SERVICE, User.OPERATOR],
            )
        except User.DoesNotExist:
            return Response({"error": "Staff member not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "success": True,
            "staff": {
                "id": u.id,
                "email": u.email,
                "full_name": f"{u.first_name} {u.last_name}",
                "phone_number": str(u.phone_number) if u.phone_number else '',
                "role": u.user_role,
                "account_active": u.account_is_active,
                "created_at": u.create_date.isoformat(),
                "last_login": u.last_login.isoformat() if u.last_login else None,
            },
        })

    def delete(self, request, staff_id):
        """Deactivate a staff account (Section 2.4)."""
        ok, err = self._require_admin(request)
        if not ok:
            return err

        if int(staff_id) == request.user.id:
            return Response(
                {"error": "Cannot deactivate your own account"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            u = User.objects.get(
                id=staff_id,
                user_role__in=[User.ADMIN, User.CUSTOMER_SERVICE, User.OPERATOR],
            )
        except User.DoesNotExist:
            return Response({"error": "Staff member not found"}, status=status.HTTP_404_NOT_FOUND)

        u.account_is_active = False
        u.save()

        _write_audit(
            request,
            action_type=AuditLog.ACTION_STAFF_DEACTIVATE,
            target_type=AuditLog.TARGET_STAFF,
            target_id=u.id,
            target_repr=f"{u.email} ({u.user_role})",
            details={"staff_email": u.email, "role": u.user_role},
            notes=request.data.get('notes', ''),
        )

        return Response({"success": True, "message": "Staff account deactivated"})


# --------------------------------------------------------------------------- #
#  Section 3 — User Management                                                 #
# --------------------------------------------------------------------------- #

class UserManagementView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ok, err = self._require_cs_or_above(request)
        if not ok:
            return err

        search = request.GET.get('search', '')
        status_filter = request.GET.get('status', 'all')
        page = _safe_int(request.GET.get('page', 1), 1, minimum=1)
        limit = _safe_int(request.GET.get('limit', 20), 20, minimum=1, maximum=100)
        offset = (page - 1) * limit

        users_query = User.objects.filter(user_role=User.CLIENT)

        if search:
            users_query = users_query.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(phone_number__icontains=search)
                | Q(national_id__icontains=search)
                | Q(devices__meter_no__icontains=search)
            ).distinct()

        if status_filter == 'active':
            users_query = users_query.filter(account_is_active=True, is_suspended=False)
        elif status_filter == 'inactive':
            users_query = users_query.filter(account_is_active=False)
        elif status_filter == 'suspended':
            users_query = users_query.filter(is_suspended=True)
        elif status_filter == 'verified':
            users_query = users_query.filter(profile__email_verified=True)
        elif status_filter == 'unverified':
            users_query = users_query.filter(profile__email_verified=False)
        elif status_filter == 'flagged':
            users_query = users_query.filter(fraud_flags__status=FlaggedAccount.STATUS_OPEN).distinct()

        total_count = users_query.count()
        users = users_query.select_related('profile').order_by('-create_date')[offset:offset + limit]

        user_list = []
        for u in users:
            meter = Meter.objects.filter(user=u).order_by("-create_date").first()
            if meter:
                meter_info = {"meter_no": meter.meter_no, "units": float(meter.units), "status": meter.status}
                has_meter = True
            else:
                has_meter = False
                meter_info = None

            account_details = UserAccountDetails.objects.filter(user=u).order_by("-create_date").first()
            if account_details:
                account_info = {
                    "account_number": account_details.account_number,
                    "address": account_details.address,
                }
            else:
                account_info = None

            user_list.append({
                "id": u.id,
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "phone_number": str(u.phone_number) if u.phone_number else '',
                "national_id": u.national_id,
                "email_verified": getattr(getattr(u, 'profile', None), 'email_verified', False),
                "account_active": u.account_is_active,
                "is_suspended": u.is_suspended,
                "suspension_reason": u.suspension_reason,
                "kyc_status": u.kyc_status,
                "has_meter": has_meter,
                "meter_info": meter_info,
                "account_info": account_info,
                "created_at": u.create_date.isoformat(),
                "last_login": u.last_login.isoformat() if u.last_login else None,
                "profile_complete": u.has_complete_profile,
            })

        return Response({
            "success": True,
            "users": user_list,
            "pagination": {
                "page": page, "limit": limit, "total": total_count,
                "pages": (total_count + limit - 1) // limit,
            },
            "filters": {"search": search, "status": status_filter},
        })


class UserDetailView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        ok, err = self._require_cs_or_above(request)
        if not ok:
            return err

        try:
            u = User.objects.select_related('profile').get(id=user_id, user_role=User.CLIENT)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            meter = Meter.objects.filter(user=u).order_by("-create_date").first()
            if not meter:
                raise Meter.DoesNotExist
            meter_info = {
                "id": meter.id, "meter_no": meter.meter_no,
                "static_ip": meter.static_ip, "units": float(meter.units),
                "label": meter.label, "status": meter.status,
                "created_at": meter.create_date.isoformat(),
                "updated_at": meter.modify_date.isoformat(),
            }
        except Meter.DoesNotExist:
            meter_info = None

        try:
            account_details = UserAccountDetails.objects.filter(user=u).order_by("-create_date").first()
            if not account_details:
                raise UserAccountDetails.DoesNotExist
            account_info = {
                "account_number": account_details.account_number,
                "address": account_details.address,
                "energy_preference": account_details.energy_preference,
                "payment_method": account_details.payment_method,
                "created_at": account_details.create_date.isoformat(),
            }
        except UserAccountDetails.DoesNotExist:
            account_info = None

        # Wallet summary
        wallet = getattr(u, 'wallet_set', None)
        wallet_balance = 0
        if wallet:
            w = wallet.first()
            if w:
                wallet_balance = float(w.balance)

        # Active loans
        active_loans_qs = LoanApplication.objects.filter(user=u, status__in=['ACTIVE', 'APPROVED'])
        active_loans = [{
            "id": l.id,
            "loan_id": l.loan_id,
            "amount_requested": float(l.amount_requested),
            "amount_approved": float(l.amount_approved) if l.amount_approved else None,
            "status": l.status,
            "due_date": l.due_date.isoformat() if l.due_date else None,
            "outstanding_balance": float(l.outstanding_balance),
        } for l in active_loans_qs[:5]]

        # Credit score (latest loan's credit_score)
        credit_score_val = None
        latest_loan = LoanApplication.objects.filter(user=u).order_by('-created_at').first()
        if latest_loan:
            credit_score_val = latest_loan.credit_score

        # Transaction history (last 20)
        txns = Transaction.objects.filter(user=u).order_by('-create_date')[:20]
        txn_list = [{
            "id": str(t.transaction_id),
            "type": t.transaction_type,
            "amount_kwh": float(t.amount_kwh),
            "amount_ugx": float(t.amount_ugx),
            "status": t.status,
            "channel": t.channel,
            "created_at": t.create_date.isoformat(),
        } for t in txns]

        # Flags & Notes
        flags = FlaggedAccount.objects.filter(user=u).order_by('-created_at')
        flags_list = [{
            "id": f.id,
            "flag_type": f.flag_type,
            "status": f.status,
            "trigger": f.trigger_description,
            "created_at": f.created_at.isoformat(),
        } for f in flags]

        # KYC
        profile = getattr(u, 'profile', None)

        return Response({
            "success": True,
            "user": {
                "id": u.id,
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "phone_number": str(u.phone_number) if u.phone_number else '',
                "national_id": u.national_id,
                "gender": u.gender,
                "email_verified": getattr(profile, 'email_verified', False),
                "account_active": u.account_is_active,
                "is_suspended": u.is_suspended,
                "suspension_reason": u.suspension_reason,
                "suspension_note": u.suspension_note,
                "suspended_at": u.suspended_at.isoformat() if u.suspended_at else None,
                "kyc_status": u.kyc_status,
                "created_at": u.create_date.isoformat(),
                "last_login": u.last_login.isoformat() if u.last_login else None,
                "profile_data": {
                    "monthly_expenditure": u.monthly_expenditure,
                    "purchase_frequency": u.purchase_frequency,
                    "payment_consistency": u.payment_consistency,
                    "disconnection_history": u.disconnection_history,
                    "meter_sharing": u.meter_sharing,
                    "monthly_income": u.monthly_income,
                    "income_stability": u.income_stability,
                    "consumption_level": u.consumption_level,
                    "profile_complete": u.has_complete_profile,
                },
                "wallet_summary": {
                    "balance": wallet_balance,
                    "total_transactions": Transaction.objects.filter(user=u).count(),
                },
                "meter": meter_info,
                "account_details": account_info,
                "active_loans": active_loans,
                "credit_score": credit_score_val,
                "credit_limit_override_kwh": float(u.credit_limit_override_kwh) if u.credit_limit_override_kwh else None,
                "transaction_history": txn_list,
                "flags": flags_list,
            },
        })

    def put(self, request, user_id):
        """Edit user profile (CS, Operator, Admin)."""
        ok, err = self._require_cs_or_above(request)
        if not ok:
            return err

        try:
            u = User.objects.get(id=user_id, user_role=User.CLIENT)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        editable = ['first_name', 'last_name', 'phone_number', 'national_id']
        before = {field: getattr(u, field, None) for field in editable}

        for field in editable:
            if field in request.data:
                setattr(u, field, request.data[field])
        u.save()

        after = {field: getattr(u, field, None) for field in editable}
        _write_audit(
            request,
            action_type=AuditLog.ACTION_USER_EDIT,
            target_type=AuditLog.TARGET_USER,
            target_id=u.id,
            target_repr=f"{u.email}",
            details={"before": before, "after": after},
            notes=request.data.get('notes', ''),
        )

        return Response({"success": True, "message": "User profile updated"})


class UserSuspendView(APIView, RBACMixin):
    """Suspend or reactivate a user account (Admin only — Section 3.4–3.5)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        ok, err = self._require_admin(request)
        if not ok:
            return err

        action = request.data.get('action')  # 'suspend' or 'reactivate'
        reason = request.data.get('reason', '')
        note = request.data.get('note', '')

        if action not in ('suspend', 'reactivate'):
            return Response(
                {"error": "action must be 'suspend' or 'reactivate'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            u = User.objects.get(id=user_id, user_role=User.CLIENT)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        if action == 'suspend':
            u.is_suspended = True
            u.account_is_active = False
            u.suspension_reason = reason
            u.suspension_note = note
            u.suspended_at = timezone.now()
            u.save()
            audit_action = AuditLog.ACTION_ACCOUNT_SUSPENSION
            msg = "Account suspended"
        else:
            u.is_suspended = False
            u.account_is_active = True
            u.suspension_reason = None
            u.suspension_note = None
            u.suspended_at = None
            u.save()
            audit_action = AuditLog.ACTION_ACCOUNT_REACTIVATION
            msg = "Account reactivated"

        _write_audit(
            request,
            action_type=audit_action,
            target_type=AuditLog.TARGET_USER,
            target_id=u.id,
            target_repr=u.email,
            details={"reason": reason},
            notes=note,
        )

        return Response({"success": True, "message": msg})


class UserPINResetView(APIView, RBACMixin):
    """Reset USSD PIN or send password reset SMS (CS, Operator, Admin — Section 3.3)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        ok, err = self._require_cs_or_above(request)
        if not ok:
            return err

        reset_type = request.data.get('type', 'pin')  # 'pin' or 'password'

        try:
            u = User.objects.get(id=user_id, user_role=User.CLIENT)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        _write_audit(
            request,
            action_type=AuditLog.ACTION_CREDENTIAL_RESET,
            target_type=AuditLog.TARGET_USER,
            target_id=u.id,
            target_repr=u.email,
            details={"reset_type": reset_type},
            notes=request.data.get('notes', ''),
        )

        return Response({
            "success": True,
            "message": f"{'PIN' if reset_type == 'pin' else 'Password reset SMS'} triggered for {u.email}",
        })


class UserKYCView(APIView, RBACMixin):
    """Verify or reject user KYC identity (CS, Operator, Admin — Section 3.7)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        ok, err = self._require_cs_or_above(request)
        if not ok:
            return err

        kyc_action = request.data.get('action')  # 'verify' or 'reject'
        reason = request.data.get('reason', '')

        if kyc_action not in ('verify', 'reject'):
            return Response(
                {"error": "action must be 'verify' or 'reject'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            u = User.objects.get(id=user_id, user_role=User.CLIENT)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        if kyc_action == 'verify':
            u.kyc_status = User.KYC_VERIFIED
            audit_action = AuditLog.ACTION_KYC_VERIFY
            msg = "Identity verified"
        else:
            u.kyc_status = User.KYC_UNVERIFIED
            audit_action = AuditLog.ACTION_KYC_REJECT
            msg = "Identity rejected"

        u.save()

        _write_audit(
            request,
            action_type=audit_action,
            target_type=AuditLog.TARGET_USER,
            target_id=u.id,
            target_repr=u.email,
            details={"kyc_action": kyc_action, "reason": reason},
            notes=reason,
        )

        return Response({"success": True, "message": msg})


# Legacy toggle (keep for existing frontend)
class ToggleUserStatusView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ok, err = self._require_admin(request)
        if not ok:
            return err

        user_id = request.data.get('user_id')
        if not user_id:
            return Response({"error": "user_id required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            u = User.objects.get(id=user_id, user_role=User.CLIENT)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        u.account_is_active = not u.account_is_active
        u.save()

        return Response({
            "success": True,
            "message": f"User {'activated' if u.account_is_active else 'deactivated'}",
            "user": {"id": u.id, "email": u.email, "account_active": u.account_is_active},
        })


# --------------------------------------------------------------------------- #
#  Section 4 — Meter Management                                                #
# --------------------------------------------------------------------------- #

class MeterManagementView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ok, err = self._require_cs_or_above(request)
        if not ok:
            return err

        search = request.GET.get('search', '')
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
        offset = (page - 1) * limit

        meters_query = Meter.objects.all()

        if search:
            meters_query = meters_query.filter(
                Q(meter_no__icontains=search)
                | Q(user__email__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
            )

        total_count = meters_query.count()
        meters = meters_query.select_related('user').order_by('-create_date')[offset:offset + limit]

        return Response({
            "success": True,
            "meters": [
                {
                    "meter_id": m.id,
                    "meter_no": m.meter_no,
                    "label": m.label,
                    "status": m.status,
                    "architecture": m.architecture,
                    "units": float(m.units),
                    "static_ip": m.static_ip or "",
                    "iot_device_token": m.iot_device_token or "",
                    "has_iot_token": bool((m.iot_device_token or "").strip()),
                    "user": {
                        "id": m.user.id,
                        "email": m.user.email,
                        "name": f"{m.user.first_name} {m.user.last_name}",
                        "phone": str(m.user.phone_number) if m.user.phone_number else '',
                    },
                    "created_at": m.create_date.isoformat(),
                    "last_updated": m.modify_date.isoformat(),
                }
                for m in meters
            ],
            "pagination": {
                "page": page, "limit": limit, "total": total_count,
                "pages": (total_count + limit - 1) // limit,
            },
        })

    def post(self, request):
        """Register a new meter (Operator, Admin — Section 4.2)."""
        ok, err = self._require_operator_or_admin(request)
        if not ok:
            return err

        meter_no = request.data.get('meter_no', '').strip()
        label = request.data.get('label', 'Home').strip()
        architecture = request.data.get('architecture', Meter.ARCH_STS).strip().upper()
        static_ip = request.data.get('static_ip', '').strip() or None
        iot_device_token = (request.data.get('iot_device_token') or '').strip() or None

        owner_name = (request.data.get('owner_name') or '').strip()
        owner_email = (request.data.get('owner_email') or '').strip()
        owner_phone = (request.data.get('owner_phone') or '').strip()

        if not meter_no:
            return Response(
                {"error": "meter_no is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not owner_name or not owner_email or not owner_phone:
            return Response(
                {"error": "owner_name, owner_email, and owner_phone are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if architecture not in (Meter.ARCH_STS, Meter.ARCH_AMI):
            return Response(
                {"error": "architecture must be STS or AMI"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if architecture == Meter.ARCH_AMI and not iot_device_token:
            return Response(
                {"error": "iot_device_token is required for AMI meters"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if Meter.objects.filter(meter_no=meter_no).exists():
            return Response(
                {"error": "Meter number already registered"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            owner = create_admin_provisioned_user(
                owner_name=owner_name,
                email=owner_email,
                phone_number=owner_phone,
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        meter = Meter.objects.create(
            meter_no=meter_no,
            user=owner,
            label=label,
            architecture=architecture,
            static_ip=static_ip or '0.0.0.0',
            iot_device_token=iot_device_token if architecture == Meter.ARCH_AMI else None,
            status=Meter.STATUS_ACTIVE,
        )

        _write_audit(
            request,
            action_type=AuditLog.ACTION_METER_REGISTER,
            target_type=AuditLog.TARGET_METER,
            target_id=meter.id,
            target_repr=f"{meter_no} → {owner.email}",
            details={
                "meter_no": meter_no,
                "owner_email": owner_email,
                "label": label,
                "architecture": architecture,
                "provisioned_user": True,
            },
        )

        return Response({
            "success": True,
            "message": "Meter and owner account created. They can sign in with their email and temporary password 1234.",
            "meter_id": meter.id,
            "user_id": owner.id,
            "owner_email": owner.email,
        }, status=status.HTTP_201_CREATED)


class MeterDetailView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request, meter_id):
        ok, err = self._require_cs_or_above(request)
        if not ok:
            return err

        try:
            m = Meter.objects.select_related('user').get(id=meter_id)
        except Meter.DoesNotExist:
            return Response({"error": "Meter not found"}, status=status.HTTP_404_NOT_FOUND)

        tokens = m.tokens.all().order_by('-create_date')
        last_token = tokens.first()
        total_tokens = tokens.count()
        total_kwh_issued = tokens.aggregate(total=Sum('units'))['total'] or 0

        transfers_received = Transaction.objects.filter(
            meter=m, transaction_type=Transaction.TYPE_TRANSFER_IN
        ).aggregate(total=Sum('amount_kwh'))['total'] or 0

        return Response({
            "success": True,
            "meter": {
                "id": m.id,
                "meter_no": m.meter_no,
                "label": m.label,
                "status": m.status,
                "architecture": m.architecture,
                "units": float(m.units),
                "static_ip": m.static_ip or "",
                "iot_device_token": m.iot_device_token or "",
                "has_iot_token": bool((m.iot_device_token or "").strip()),
                "linked_user": {
                    "id": m.user.id,
                    "name": f"{m.user.first_name} {m.user.last_name}",
                    "phone": str(m.user.phone_number) if m.user.phone_number else '',
                    "email": m.user.email,
                },
                "registration_date": m.create_date.isoformat(),
                "last_token_loaded": last_token.create_date.isoformat() if last_token else None,
                "last_token_units": float(last_token.units) if last_token else None,
                "total_tokens_issued": total_tokens,
                "total_kwh_issued": float(total_kwh_issued),
                "transfers_received_kwh": float(transfers_received),
                "deactivation_reason": m.deactivation_reason,
                "deactivated_at": m.deactivated_at.isoformat() if m.deactivated_at else None,
            },
        })

    def patch(self, request, meter_id):
        """Update meter fields (Operator/Admin). AMI meters may set iot_device_token."""
        ok, err = self._require_operator_or_admin(request)
        if not ok:
            return err

        try:
            m = Meter.objects.get(id=meter_id)
        except Meter.DoesNotExist:
            return Response({"error": "Meter not found"}, status=status.HTTP_404_NOT_FOUND)

        label = request.data.get('label')
        architecture = request.data.get('architecture')
        static_ip = request.data.get('static_ip')
        iot_device_token = request.data.get('iot_device_token')

        if label is not None:
            m.label = str(label).strip() or m.label

        if architecture is not None:
            arch = str(architecture).strip().upper()
            if arch not in (Meter.ARCH_STS, Meter.ARCH_AMI):
                return Response(
                    {"error": "architecture must be STS or AMI"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            m.architecture = arch
            if arch == Meter.ARCH_STS:
                m.iot_device_token = None

        if static_ip is not None:
            m.static_ip = str(static_ip).strip() or m.static_ip

        if iot_device_token is not None:
            token = str(iot_device_token).strip()
            if m.architecture == Meter.ARCH_AMI and not token:
                return Response(
                    {"error": "iot_device_token cannot be empty for AMI meters"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            m.iot_device_token = token or None

        if m.architecture == Meter.ARCH_AMI and not (m.iot_device_token or "").strip():
            return Response(
                {"error": "iot_device_token is required for AMI meters"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        m.save()

        _write_audit(
            request,
            action_type=AuditLog.ACTION_METER_REGISTER,
            target_type=AuditLog.TARGET_METER,
            target_id=m.id,
            target_repr=m.meter_no,
            details={
                "event": "meter_updated",
                "architecture": m.architecture,
                "has_iot_token": bool((m.iot_device_token or "").strip()),
            },
        )

        return Response({
            "success": True,
            "message": "Meter updated",
            "meter": {
                "id": m.id,
                "meter_no": m.meter_no,
                "architecture": m.architecture,
                "iot_device_token": m.iot_device_token or "",
                "has_iot_token": bool((m.iot_device_token or "").strip()),
            },
        })


class MeterDeactivateView(APIView, RBACMixin):
    """Deactivate a meter (Admin only — Section 4.4)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, meter_id):
        ok, err = self._require_admin(request)
        if not ok:
            return err

        try:
            m = Meter.objects.get(id=meter_id)
        except Meter.DoesNotExist:
            return Response({"error": "Meter not found"}, status=status.HTTP_404_NOT_FOUND)

        reason = request.data.get('reason', 'Other')
        note = request.data.get('note', '')

        m.status = Meter.STATUS_INACTIVE
        m.deactivation_reason = reason
        m.deactivation_note = note
        m.deactivated_at = timezone.now()
        m.deactivated_by = request.user
        m.save()

        _write_audit(
            request,
            action_type=AuditLog.ACTION_METER_DEACTIVATE,
            target_type=AuditLog.TARGET_METER,
            target_id=m.id,
            target_repr=m.meter_no,
            details={"reason": reason},
            notes=note,
        )

        return Response({"success": True, "message": "Meter deactivated"})


class MeterDeleteView(APIView, RBACMixin):
    """Permanently remove a meter from a user account (Admin — soft delete + audit)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, meter_id):
        ok, err = self._require_admin(request)
        if not ok:
            return err

        from meter.lifecycle import MeterDeleteError, release_meter_from_account
        from meter.models import DeletedMeterRecord

        try:
            m = Meter.objects.select_related("user").get(id=meter_id)
        except Meter.DoesNotExist:
            return Response({"error": "Meter not found"}, status=status.HTTP_404_NOT_FOUND)

        reason = request.data.get("reason", "") or request.data.get("note", "")

        try:
            record = release_meter_from_account(
                m,
                deleted_by=request.user,
                deleted_by_role=DeletedMeterRecord.ROLE_ADMIN,
                reason=str(reason),
                metadata={"channel": "ADMIN"},
            )
        except MeterDeleteError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        _write_audit(
            request,
            action_type=AuditLog.ACTION_METER_DELETE,
            target_type=AuditLog.TARGET_METER,
            target_id=m.id,
            target_repr=record.original_meter_no,
            details={"deletion_record_id": record.id},
            notes=str(reason),
        )

        return Response(
            {
                "success": True,
                "message": f"Meter {record.original_meter_no} removed from account.",
                "deletion_record_id": record.id,
            }
        )


class DeletedMeterRecordsView(APIView, RBACMixin):
    """List archived deleted-meter records for admin audit."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        ok, err = self._require_cs_or_above(request)
        if not ok:
            return err

        from meter.models import DeletedMeterRecord

        search = request.GET.get("search", "").strip()
        page = int(request.GET.get("page", 1))
        limit = min(int(request.GET.get("limit", 20)), 100)
        offset = (page - 1) * limit

        qs = DeletedMeterRecord.objects.all().select_related("deleted_by")
        if search:
            qs = qs.filter(
                Q(original_meter_no__icontains=search)
                | Q(former_user_email__icontains=search)
                | Q(former_user_phone__icontains=search)
            )

        total = qs.count()
        rows = qs.order_by("-deleted_at")[offset : offset + limit]

        return Response(
            {
                "success": True,
                "total": total,
                "page": page,
                "records": [
                    {
                        "id": r.id,
                        "original_meter_no": r.original_meter_no,
                        "architecture": r.architecture,
                        "label": r.label,
                        "former_user_id": r.former_user_id,
                        "former_user_email": r.former_user_email,
                        "units_at_deletion": float(r.units_at_deletion),
                        "deleted_at": r.deleted_at.isoformat(),
                        "deleted_by_role": r.deleted_by_role,
                        "deleted_by_email": r.deleted_by.email if r.deleted_by else None,
                        "reason": r.reason,
                    }
                    for r in rows
                ],
            }
        )


class MeterTransferOwnershipView(APIView, RBACMixin):
    """Transfer meter to a new owner (Admin only — Section 4.5)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, meter_id):
        ok, err = self._require_admin(request)
        if not ok:
            return err

        new_user_id = request.data.get('new_user_id')
        note = request.data.get('note', '')

        if not new_user_id:
            return Response({"error": "new_user_id required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            m = Meter.objects.select_related('user').get(id=meter_id)
        except Meter.DoesNotExist:
            return Response({"error": "Meter not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            new_owner = User.objects.get(id=new_user_id, user_role=User.CLIENT)
        except User.DoesNotExist:
            return Response({"error": "New owner not found"}, status=status.HTTP_404_NOT_FOUND)

        old_owner = m.user
        m.user = new_owner
        m.save()

        _write_audit(
            request,
            action_type=AuditLog.ACTION_METER_TRANSFER,
            target_type=AuditLog.TARGET_METER,
            target_id=m.id,
            target_repr=m.meter_no,
            details={
                "old_owner": old_owner.email,
                "new_owner": new_owner.email,
            },
            notes=note,
        )

        return Response({"success": True, "message": "Meter ownership transferred"})


# --------------------------------------------------------------------------- #
#  Section 5 — Credit & Loan Oversight                                         #
# --------------------------------------------------------------------------- #

class CreditLoansDashboardView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ok, err = self._require_cs_or_above(request)
        if not ok:
            return err

        today = timezone.now().date()
        week_from_now = today + timedelta(days=7)
        grace_cutoff = today - timedelta(days=2)

        total_active = LoanApplication.objects.filter(status__in=['ACTIVE', 'APPROVED']).count()

        # due_date is a Python property — evaluate in Python
        try:
            active_loans_qs = list(
                LoanApplication.objects.filter(status='ACTIVE').select_related('disbursement')
            )
            due_this_week = sum(
                1 for l in active_loans_qs
                if l.due_date and today <= l.due_date.date() <= week_from_now
            )
            overdue = sum(
                1 for l in active_loans_qs
                if l.due_date and l.due_date.date() < grace_cutoff
            )
            overdue_30d = sum(
                1 for l in active_loans_qs
                if l.due_date and l.due_date.date() < today - timedelta(days=30)
            )
        except Exception:
            due_this_week = overdue = overdue_30d = 0

        repaid_30d = LoanApplication.objects.filter(
            status='REPAID',
            updated_at__date__gte=today - timedelta(days=30),
        ).count()
        total_closed_30d = max(
            LoanApplication.objects.filter(
                created_at__date__gte=today - timedelta(days=30),
                status__in=['REPAID', 'ACTIVE'],
            ).count(),
            1,
        )
        repayment_rate = round(repaid_30d / total_closed_30d * 100, 1)

        return Response({
            "success": True,
            "total_active_loans": total_active,
            "loans_due_this_week": due_this_week,
            "overdue_loans": overdue,
            "overdue_loans_30d": overdue_30d,
            "repayment_rate_30d": repayment_rate,
        })


class LoanManagementView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ok, err = self._require_cs_or_above(request)
        if not ok:
            return err

        search = request.GET.get('search', '')
        status_filter = request.GET.get('status', '')
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
        offset = (page - 1) * limit

        loans_query = LoanApplication.objects.all()

        if search:
            loans_query = loans_query.filter(
                Q(loan_id__icontains=search)
                | Q(user__email__icontains=search)
                | Q(user__first_name__icontains=search)
            )

        if status_filter:
            loans_query = loans_query.filter(status=status_filter)

        total_count = loans_query.count()
        loans = loans_query.select_related('user').order_by('-created_at')[offset:offset + limit]

        return Response({
            "success": True,
            "loans": [
                {
                    "id": l.id,
                    "loan_id": l.loan_id,
                    "loan_ref": l.loan_id,
                    "status": l.status,
                    "amount_requested": float(l.amount_requested),
                    "amount_approved": float(l.amount_approved) if l.amount_approved else None,
                    "outstanding_balance": float(l.outstanding_balance),
                    "due_date": l.due_date.isoformat() if l.due_date else None,
                    "credit_score": l.credit_score,
                    "loan_tier": l.loan_tier,
                    "user": {
                        "id": l.user.id,
                        "email": l.user.email,
                        "name": f"{l.user.first_name} {l.user.last_name}",
                        "phone": str(l.user.phone_number) if l.user.phone_number else '',
                    },
                    "created_at": l.created_at.isoformat(),
                }
                for l in loans
            ],
            "pagination": {
                "page": page, "limit": limit, "total": total_count,
                "pages": (total_count + limit - 1) // limit,
            },
        })


class LoanDetailView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request, loan_id):
        ok, err = self._require_cs_or_above(request)
        if not ok:
            return err

        try:
            loan = LoanApplication.objects.select_related('user', 'tariff').get(id=loan_id)
        except LoanApplication.DoesNotExist:
            return Response({"error": "Loan not found"}, status=status.HTTP_404_NOT_FOUND)

        repayments = loan.repayments.all().order_by('-payment_date')
        disbursement = getattr(loan, 'disbursement', None)

        loan_data = {
            "id": loan.id,
            "loan_id": loan.loan_id,
            "user": {
                "id": loan.user.id,
                "email": loan.user.email,
                "first_name": loan.user.first_name,
                "last_name": loan.user.last_name,
                "phone_number": str(loan.user.phone_number) if loan.user.phone_number else '',
            },
            "purpose": loan.purpose,
            "amount_requested": float(loan.amount_requested),
            "amount_approved": float(loan.amount_approved) if loan.amount_approved else None,
            "tenure_months": loan.tenure_months,
            "interest_rate": float(loan.interest_rate),
            "status": loan.status,
            "credit_score": loan.credit_score,
            "loan_tier": loan.loan_tier,
            "due_date": loan.due_date.isoformat() if loan.due_date else None,
            "total_amount_due": float(loan.total_amount_due),
            "amount_paid": float(loan.amount_paid),
            "outstanding_balance": float(loan.outstanding_balance),
            "created_at": loan.created_at.isoformat(),
            "repayments": [
                {
                    "id": r.id,
                    "amount_paid": float(r.amount_paid),
                    "payment_date": r.payment_date.isoformat(),
                    "units_paid": float(r.units_paid),
                    "is_on_time": r.is_on_time,
                    "payment_reference": r.payment_reference,
                }
                for r in repayments
            ],
        }

        if disbursement:
            loan_data["disbursement"] = {
                "id": disbursement.id,
                "token": disbursement.token,
                "units_disbursed": float(disbursement.units_disbursed),
                "disbursement_date": disbursement.disbursement_date.isoformat(),
                "meter": {"id": disbursement.meter.id, "meter_no": disbursement.meter.meter_no},
            }

        return Response({"success": True, "loan": loan_data})


class LoanPenaltyWaiverView(APIView, RBACMixin):
    """Waive a late penalty (Admin only — Section 5.3)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, loan_id):
        ok, err = self._require_admin(request)
        if not ok:
            return err

        reason = request.data.get('reason', '').strip()
        if not reason:
            return Response(
                {"error": "reason is required for penalty waivers"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            loan = LoanApplication.objects.get(id=loan_id)
        except LoanApplication.DoesNotExist:
            return Response({"error": "Loan not found"}, status=status.HTTP_404_NOT_FOUND)

        _write_audit(
            request,
            action_type=AuditLog.ACTION_PENALTY_WAIVER,
            target_type=AuditLog.TARGET_LOAN,
            target_id=loan.id,
            target_repr=f"Loan {loan.loan_id} — {loan.user.email}",
            details={"loan_id": loan.loan_id},
            notes=reason,
        )

        return Response({"success": True, "message": "Late penalty waived"})


class LoanDisburseView(APIView, RBACMixin):
    """Disburse an approved loan to the borrower's unit wallet (operator/admin)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, loan_id):
        ok, err = self._require_operator_or_admin(request)
        if not ok:
            return err

        try:
            loan = LoanApplication.objects.select_related("user").get(id=loan_id)
        except LoanApplication.DoesNotExist:
            return Response({"error": "Loan not found"}, status=status.HTTP_404_NOT_FOUND)

        from loan.services import LoanOperationError, disburse_loan

        try:
            result = disburse_loan(loan.user, loan.id, channel="ADMIN")
        except LoanOperationError as exc:
            return Response({"error": exc.message}, status=status.HTTP_400_BAD_REQUEST)

        self.log_admin_activity(
            request.user,
            "loan_disburse",
            details={
                "loan_id": loan.loan_id,
                "loan_pk": loan.id,
                "user_email": loan.user.email,
                "units_disbursed": result.get("units_disbursed"),
            },
            request=request,
        )

        return Response(
            {
                "success": True,
                "message": "Loan disbursed successfully",
                "loan_id": loan.loan_id,
                "units_disbursed": result.get("units_disbursed"),
                "meter_push_ok": result.get("meter_push_ok"),
            }
        )


class CreditLimitOverrideView(APIView, RBACMixin):
    """Override a user's credit limit (Admin only, hard cap 20 kWh — Section 5.4)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        ok, err = self._require_admin(request)
        if not ok:
            return err

        try:
            u = User.objects.get(id=user_id, user_role=User.CLIENT)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        new_limit = request.data.get('credit_limit_kwh')
        reason = request.data.get('reason', '').strip()

        if new_limit is None or not reason:
            return Response(
                {"error": "credit_limit_kwh and reason are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_limit_decimal = float(new_limit)
        if new_limit_decimal > 20:
            return Response(
                {"error": "Credit limit cannot exceed 20 kWh (system hard cap)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_limit = float(u.credit_limit_override_kwh) if u.credit_limit_override_kwh else None
        u.credit_limit_override_kwh = new_limit_decimal
        u.credit_limit_override_reason = reason
        u.save()

        _write_audit(
            request,
            action_type=AuditLog.ACTION_CREDIT_LIMIT_OVERRIDE,
            target_type=AuditLog.TARGET_USER,
            target_id=u.id,
            target_repr=u.email,
            details={"old_limit": old_limit, "new_limit": new_limit_decimal},
            notes=reason,
        )

        return Response({"success": True, "message": "Credit limit updated"})


# --------------------------------------------------------------------------- #
#  Section 6 — Transaction Monitoring                                          #
# --------------------------------------------------------------------------- #

class TransactionLogView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ok, err = self._require_cs_or_above(request)
        if not ok:
            return err

        # Filters
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        txn_type = request.GET.get('type', '')
        user_search = request.GET.get('user', '')
        meter_no = request.GET.get('meter', '')
        txn_status = request.GET.get('status', '')
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
        offset = (page - 1) * limit

        qs = Transaction.objects.select_related('user', 'meter')

        if date_from:
            qs = qs.filter(create_date__date__gte=date_from)
        if date_to:
            qs = qs.filter(create_date__date__lte=date_to)
        if txn_type:
            qs = qs.filter(transaction_type=txn_type)
        if user_search:
            qs = qs.filter(
                Q(user__email__icontains=user_search)
                | Q(user__first_name__icontains=user_search)
                | Q(user__phone_number__icontains=user_search)
            )
        if meter_no:
            qs = qs.filter(meter__meter_no__icontains=meter_no)
        if txn_status:
            qs = qs.filter(status=txn_status)

        total = qs.count()
        transactions = qs.order_by('-create_date')[offset:offset + limit]

        return Response({
            "success": True,
            "transactions": [
                {
                    "id": str(t.transaction_id),
                    "type": t.transaction_type,
                    "user": {
                        "id": t.user.id,
                        "name": f"{t.user.first_name} {t.user.last_name}",
                        "phone": str(t.user.phone_number) if t.user.phone_number else '',
                    },
                    "amount_kwh": float(t.amount_kwh),
                    "amount_ugx": float(t.amount_ugx),
                    "source": t.source,
                    "destination": t.destination,
                    "meter_no": t.meter.meter_no if t.meter else None,
                    "sts_token": t.sts_token,
                    "payment_reference": t.payment_reference,
                    "status": t.status,
                    "channel": t.channel,
                    "failure_reason": t.failure_reason,
                    "is_flagged": t.is_flagged,
                    "created_at": t.create_date.isoformat(),
                }
                for t in transactions
            ],
            "pagination": {
                "page": page, "limit": limit, "total": total,
                "pages": (total + limit - 1) // limit,
            },
        })


class TransactionDetailView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request, transaction_id):
        ok, err = self._require_cs_or_above(request)
        if not ok:
            return err

        try:
            t = Transaction.objects.select_related('user', 'meter').get(
                transaction_id=transaction_id
            )
        except Transaction.DoesNotExist:
            return Response({"error": "Transaction not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "success": True,
            "transaction": {
                "id": str(t.transaction_id),
                "type": t.transaction_type,
                "user": {
                    "id": t.user.id,
                    "email": t.user.email,
                    "name": f"{t.user.first_name} {t.user.last_name}",
                    "phone": str(t.user.phone_number) if t.user.phone_number else '',
                },
                "amount_kwh": float(t.amount_kwh),
                "amount_ugx": float(t.amount_ugx),
                "source": t.source,
                "destination": t.destination,
                "meter": {"meter_no": t.meter.meter_no, "label": t.meter.label} if t.meter else None,
                "sts_token": t.sts_token,
                "payment_reference": t.payment_reference,
                "status": t.status,
                "channel": t.channel,
                "failure_reason": t.failure_reason,
                "is_flagged": t.is_flagged,
                "flag_reason": t.flag_reason,
                "refunded_at": t.refunded_at.isoformat() if t.refunded_at else None,
                "refund_reason": t.refund_reason,
                "created_at": t.create_date.isoformat(),
            },
        })


class TransactionRefundView(APIView, RBACMixin):
    """Issue a refund for a failed transaction (Admin only — Section 6.5)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, transaction_id):
        ok, err = self._require_admin(request)
        if not ok:
            return err

        reason = request.data.get('reason', '').strip()
        refund_method = request.data.get('refund_method', 'mobile_money')

        if not reason:
            return Response({"error": "reason is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            t = Transaction.objects.get(transaction_id=transaction_id)
        except Transaction.DoesNotExist:
            return Response({"error": "Transaction not found"}, status=status.HTTP_404_NOT_FOUND)

        if t.status not in (Transaction.STATUS_FAILED,):
            return Response(
                {"error": "Only FAILED transactions can be refunded"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        t.status = Transaction.STATUS_REVERSED
        t.refunded_by = request.user
        t.refund_reason = reason
        t.refunded_at = timezone.now()
        t.save()

        _write_audit(
            request,
            action_type=AuditLog.ACTION_REFUND,
            target_type=AuditLog.TARGET_TRANSACTION,
            target_id=str(t.transaction_id),
            target_repr=f"Txn {t.transaction_id} — {t.user.email}",
            details={"refund_method": refund_method, "amount_ugx": float(t.amount_ugx)},
            notes=reason,
        )

        return Response({"success": True, "message": "Refund initiated"})


class TokenRedeliveryView(APIView, RBACMixin):
    """Re-send STS token for a completed transaction (CS+ — Section 10.3)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, transaction_id):
        ok, err = self._require_cs_or_above(request)
        if not ok:
            return err

        try:
            t = Transaction.objects.get(
                transaction_id=transaction_id,
                status=Transaction.STATUS_COMPLETED,
            )
        except Transaction.DoesNotExist:
            return Response(
                {"error": "Completed transaction not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not t.sts_token:
            return Response({"error": "No token associated with this transaction"}, status=400)

        _write_audit(
            request,
            action_type=AuditLog.ACTION_TOKEN_REDELIVERY,
            target_type=AuditLog.TARGET_TRANSACTION,
            target_id=str(t.transaction_id),
            target_repr=f"Txn {t.transaction_id} — {t.user.email}",
            details={"token": t.sts_token},
            notes=request.data.get('notes', ''),
        )

        return Response({"success": True, "message": "Token re-sent to user's registered phone"})


class FlaggedTransactionsView(APIView, RBACMixin):
    """List all fraud-flagged transactions (CS+ — Section 6.6)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ok, err = self._require_cs_or_above(request)
        if not ok:
            return err

        flagged = Transaction.objects.filter(is_flagged=True).select_related('user').order_by('-create_date')[:50]

        return Response({
            "success": True,
            "flagged_transactions": [
                {
                    "id": str(t.transaction_id),
                    "type": t.transaction_type,
                    "user": {"id": t.user.id, "email": t.user.email, "name": f"{t.user.first_name} {t.user.last_name}"},
                    "amount_kwh": float(t.amount_kwh),
                    "flag_reason": t.flag_reason,
                    "status": t.status,
                    "created_at": t.create_date.isoformat(),
                }
                for t in flagged
            ],
        })

    def post(self, request):
        """Review a flagged transaction: clear, escalate, or suspend account."""
        ok, err = self._require_cs_or_above(request)
        if not ok:
            return err

        transaction_id = request.data.get('transaction_id')
        decision = request.data.get('decision')  # 'clear', 'escalate', 'suspend'
        note = request.data.get('note', '')

        if decision not in ('clear', 'escalate', 'suspend'):
            return Response({"error": "decision must be clear, escalate, or suspend"}, status=400)

        # 'suspend' is Admin-only
        if decision == 'suspend':
            ok2, err2 = self._require_admin(request)
            if not ok2:
                return err2

        try:
            t = Transaction.objects.select_related('user').get(transaction_id=transaction_id)
        except Transaction.DoesNotExist:
            return Response({"error": "Transaction not found"}, status=404)

        if decision == 'clear':
            t.is_flagged = False
            t.save()
            action = AuditLog.ACTION_FRAUD_CLEAR
        elif decision == 'escalate':
            action = AuditLog.ACTION_FRAUD_FLAG
        else:  # suspend
            t.user.is_suspended = True
            t.user.account_is_active = False
            t.user.suspension_reason = "Fraud Suspicion"
            t.user.suspended_at = timezone.now()
            t.user.save()
            action = AuditLog.ACTION_ACCOUNT_SUSPENSION

        _write_audit(
            request,
            action_type=action,
            target_type=AuditLog.TARGET_TRANSACTION,
            target_id=str(t.transaction_id),
            target_repr=f"Txn {t.transaction_id} — {t.user.email}",
            details={"decision": decision},
            notes=note,
        )

        return Response({"success": True, "message": f"Decision '{decision}' applied"})


# --------------------------------------------------------------------------- #
#  Section 7 — System Health (Admin only)                                      #
# --------------------------------------------------------------------------- #

class SystemHealthView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ok, err = self._require_admin(request)
        if not ok:
            return err

        from admin.health_checks import run_all_health_checks

        payload = run_all_health_checks()
        return Response({
            "success": True,
            "overall_status": payload["overall_status"],
            "components": payload["components"],
            "timestamp": timezone.now().isoformat(),
        })


class SystemErrorLogView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ok, err = self._require_admin(request)
        if not ok:
            return err

        from admin.system_errors import collect_recent_errors

        limit = _safe_int(request.GET.get("limit", 50), 50, minimum=1, maximum=100)
        errors = collect_recent_errors(limit=limit)
        return Response({"success": True, "errors": errors})


# --------------------------------------------------------------------------- #
#  Section 8 — Reports & Analytics                                             #
# --------------------------------------------------------------------------- #

class ReportsView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Generate a report (Operator, Admin)."""
        ok, err = self._require_operator_or_admin(request)
        if not ok:
            return err

        report_type = request.GET.get('type', 'daily_transaction_summary')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')

        today = timezone.now().date()
        start = datetime.strptime(date_from, '%Y-%m-%d').date() if date_from else today - timedelta(days=30)
        end = datetime.strptime(date_to, '%Y-%m-%d').date() if date_to else today

        data = {}

        if report_type == 'daily_transaction_summary':
            txn_counts = (
                Transaction.objects.filter(create_date__date__gte=start, create_date__date__lte=end)
                .values('transaction_type', 'status')
                .annotate(count=Count('id'), total_kwh=Sum('amount_kwh'), total_ugx=Sum('amount_ugx'))
            )
            data = {
                "transactions": list(txn_counts),
                "total": Transaction.objects.filter(create_date__date__gte=start, create_date__date__lte=end).count(),
                "failed": Transaction.objects.filter(create_date__date__gte=start, create_date__date__lte=end, status='FAILED').count(),
            }

        elif report_type == 'user_adoption':
            new_users = User.objects.filter(user_role=User.CLIENT, create_date__date__gte=start, create_date__date__lte=end).count()
            active_users = (
                User.objects.filter(
                    user_role=User.CLIENT,
                    transactions__create_date__date__gte=start,
                    transactions__create_date__date__lte=end,
                ).distinct().count()
            )
            data = {"new_registrations": new_users, "active_users": active_users}

        elif report_type == 'credit_loan':
            loans = LoanApplication.objects.filter(created_at__date__gte=start, created_at__date__lte=end)
            data = {
                "disbursed": loans.filter(status__in=['ACTIVE', 'REPAID']).count(),
                "repaid": loans.filter(status='REPAID').count(),
                "overdue": loans.filter(status='ACTIVE', due_date__lt=today).count(),
            }

        elif report_type == 'meter_registration':
            data = {
                "new_meters": Meter.objects.filter(create_date__date__gte=start, create_date__date__lte=end).count(),
                "total_active": Meter.objects.filter(status=Meter.STATUS_ACTIVE).count(),
                "total_inactive": Meter.objects.filter(status=Meter.STATUS_INACTIVE).count(),
            }

        elif report_type == 'fraud_flags':
            data = {
                "total_flagged": FlaggedAccount.objects.filter(created_at__date__gte=start, created_at__date__lte=end).count(),
                "cleared": FlaggedAccount.objects.filter(status=FlaggedAccount.STATUS_CLEARED, reviewed_at__date__gte=start).count(),
                "suspended": User.objects.filter(is_suspended=True, suspended_at__date__gte=start).count(),
            }

        return Response({
            "success": True,
            "report_type": report_type,
            "period": {"from": str(start), "to": str(end)},
            "data": data,
            "generated_at": timezone.now().isoformat(),
        })


class ScheduledReportsView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ok, err = self._require_admin(request)
        if not ok:
            return err
        schedules = ScheduledReport.objects.filter(is_active=True).values(
            'id', 'report_type', 'frequency', 'recipients', 'last_run', 'created_at'
        )
        return Response({"success": True, "schedules": list(schedules)})

    def post(self, request):
        ok, err = self._require_admin(request)
        if not ok:
            return err

        sr = ScheduledReport.objects.create(
            report_type=request.data.get('report_type'),
            frequency=request.data.get('frequency'),
            recipients=request.data.get('recipients', []),
            created_by=request.user,
        )
        return Response({"success": True, "id": sr.id}, status=status.HTTP_201_CREATED)


class AdminStatsView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ok, err = self._require_operator_or_admin(request)
        if not ok:
            return err

        today = timezone.now().date()
        last_week = today - timedelta(days=7)
        last_month = today - timedelta(days=30)

        daily_registrations = []
        for i in range(7):
            date = today - timedelta(days=i)
            count = User.objects.filter(user_role=User.CLIENT, create_date__date=date).count()
            daily_registrations.append({"date": date.isoformat(), "count": count})
        daily_registrations.reverse()

        meter_daily = []
        for i in range(7):
            date = today - timedelta(days=i)
            count = Meter.objects.filter(create_date__date=date).count()
            meter_daily.append({"date": date.isoformat(), "count": count})
        meter_daily.reverse()

        total_meters = Meter.objects.count()
        with_units = Meter.objects.filter(units__gt=0).count()
        without_units = max(0, total_meters - with_units)
        active_ratio = round((with_units / total_meters) * 100, 1) if total_meters else 0

        return Response({
            "success": True,
            "stats": {
                "user_registrations": {
                    "daily": daily_registrations,
                    "weekly_total": User.objects.filter(user_role=User.CLIENT, create_date__date__gte=last_week).count(),
                    "monthly_total": User.objects.filter(user_role=User.CLIENT, create_date__date__gte=last_month).count(),
                },
                "meter_registrations": {
                    "daily": meter_daily,
                    "total": total_meters,
                },
                "user_status": {
                    "active": User.objects.filter(account_is_active=True, user_role=User.CLIENT).count(),
                    "inactive": User.objects.filter(account_is_active=False, user_role=User.CLIENT).count(),
                    "verified": Profile.objects.filter(email_verified=True).count(),
                    "unverified": Profile.objects.filter(email_verified=False).count(),
                },
                "meter_status": {
                    "with_units": with_units,
                    "without_units": without_units,
                    "active_ratio": active_ratio,
                },
            },
        })


# --------------------------------------------------------------------------- #
#  Section 9 — Audit Log (Admin only)                                          #
# --------------------------------------------------------------------------- #

class AuditLogView(APIView, RBACMixin):
    """Read-only audit log — append-only, no edit/delete per spec Section 9.1."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ok, err = self._require_admin(request)
        if not ok:
            return err

        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        staff_id = request.GET.get('staff_id')
        action_type = request.GET.get('action_type')
        target_id = request.GET.get('target_id')
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 50))
        offset = (page - 1) * limit

        qs = AuditLog.objects.select_related('staff_member')

        if date_from:
            qs = qs.filter(timestamp__date__gte=date_from)
        if date_to:
            qs = qs.filter(timestamp__date__lte=date_to)
        if staff_id:
            qs = qs.filter(staff_member_id=staff_id)
        if action_type:
            qs = qs.filter(action_type=action_type)
        if target_id:
            qs = qs.filter(target_id=target_id)

        total = qs.count()
        entries = qs.order_by('-timestamp')[offset:offset + limit]

        return Response({
            "success": True,
            "entries": [
                {
                    "id": e.id,
                    "timestamp": e.timestamp.isoformat(),
                    "staff_member": {
                        "id": e.staff_member.id if e.staff_member else None,
                        "email": e.staff_member.email if e.staff_member else "Unknown",
                        "name": f"{e.staff_member.first_name} {e.staff_member.last_name}" if e.staff_member else "Unknown",
                    },
                    "action_type": e.action_type,
                    "target_type": e.target_type,
                    "target_id": e.target_id,
                    "target_repr": e.target_repr,
                    "details": e.details,
                    "ip_address": e.ip_address,
                    "notes": e.notes,
                }
                for e in entries
            ],
            "action_types": [c[0] for c in AuditLog.ACTION_TYPE_CHOICES],
            "pagination": {
                "page": page, "limit": limit, "total": total,
                "pages": (total + limit - 1) // limit,
            },
        })


# --------------------------------------------------------------------------- #
#  Remaining legacy / existing views                                           #
# --------------------------------------------------------------------------- #

class AdminAccountView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        ok, err = self._require_admin(request)
        if not ok:
            return err

        user = request.user
        profile = getattr(user, 'profile', None)
        notification_settings = getattr(user, 'notification_settings', None)
        active_sessions = AdminSession.objects.filter(user=user, is_active=True, expires_at__gt=timezone.now()).order_by('-login_time')
        recent_activities = AdminActivityLog.objects.filter(user=user).order_by('-created_at')[:10]

        return Response({
            "success": True,
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone_number": str(user.phone_number) if user.phone_number else None,
                "gender": user.gender,
                "role": user.user_role,
                "account_active": user.account_is_active,
                "is_superuser": user.is_superuser,
                "email_verified": getattr(profile, 'email_verified', False),
                "created_at": user.create_date.isoformat() if user.create_date else None,
                "last_login": user.last_login.isoformat() if user.last_login else None,
            },
            "notification_settings": {
                "email_notifications": getattr(notification_settings, 'email_notifications', True),
                "sms_notifications": getattr(notification_settings, 'sms_notifications', False),
                "loan_approvals": getattr(notification_settings, 'loan_approvals', True),
                "user_registrations": getattr(notification_settings, 'user_registrations', True),
                "system_alerts": getattr(notification_settings, 'system_alerts', True),
                "weekly_reports": getattr(notification_settings, 'weekly_reports', False),
                "report_schedule": getattr(notification_settings, 'report_schedule', 'weekly'),
            },
            "sessions": [
                {
                    "id": s.id,
                    "ip_address": s.ip_address,
                    "user_agent": s.user_agent[:100],
                    "login_time": s.login_time.isoformat(),
                    "expires_at": s.expires_at.isoformat(),
                }
                for s in active_sessions
            ],
            "recent_activities": [
                {"action": a.action, "details": a.details, "created_at": a.created_at.isoformat()}
                for a in recent_activities
            ],
        })

    def put(self, request):
        ok, err = self._require_admin(request)
        if not ok:
            return err

        user = request.user
        serializer = AdminProfileSerializer(user, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response({"error": "Validation failed", "details": serializer.errors}, status=400)

        with transaction.atomic():
            serializer.save()

        self.log_admin_activity(user, "Updated profile", {"updated_fields": list(request.data.keys())}, request)
        return Response({"success": True, "message": "Profile updated", "user": serializer.data})


class AdminPasswordChangeView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ok, err = self._require_admin(request)
        if not ok:
            return err

        serializer = AdminPasswordChangeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"error": "Validation failed", "details": serializer.errors}, status=400)

        data = serializer.validated_data
        user = request.user

        if not check_password(data['current_password'], user.password):
            return Response({"error": "Current password is incorrect"}, status=400)

        if check_password(data['new_password'], user.password):
            return Response({"error": "New password must differ from current"}, status=400)

        user.password = make_password(data['new_password'])
        user.save()
        self.log_admin_activity(user, "Changed password", request=request)
        return Response({"success": True, "message": "Password changed"})


class AdminNotificationSettingsView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ok, err = self._require_admin(request)
        if not ok:
            return err

        settings_obj, _ = AdminNotificationSettings.objects.get_or_create(user=request.user)
        serializer = AdminNotificationSettingsSerializer(settings_obj)
        return Response({"success": True, "settings": serializer.data})

    def put(self, request):
        ok, err = self._require_admin(request)
        if not ok:
            return err

        settings_obj, _ = AdminNotificationSettings.objects.get_or_create(user=request.user)
        serializer = AdminNotificationSettingsSerializer(settings_obj, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response({"error": "Validation failed", "details": serializer.errors}, status=400)
        serializer.save()
        return Response({"success": True, "message": "Settings updated", "settings": serializer.data})


class AdminSessionManagementView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ok, err = self._require_admin(request)
        if not ok:
            return err

        sessions = AdminSession.objects.filter(user=request.user).order_by('-login_time')
        session_list = [{
            "id": s.id,
            "ip_address": s.ip_address,
            "is_active": s.is_active and s.expires_at > timezone.now(),
            "login_time": s.login_time.isoformat(),
            "expires_at": s.expires_at.isoformat(),
        } for s in sessions]

        return Response({
            "success": True,
            "sessions": session_list,
            "total_sessions": len(session_list),
            "active_sessions": sum(1 for s in session_list if s['is_active']),
        })

    def post(self, request):
        ok, err = self._require_admin(request)
        if not ok:
            return err

        session_id = request.data.get('session_id')
        if not session_id:
            return Response({"error": "session_id required"}, status=400)

        try:
            s = AdminSession.objects.get(id=session_id, user=request.user)
        except AdminSession.DoesNotExist:
            return Response({"error": "Session not found"}, status=404)

        s.is_active = False
        s.logout_time = timezone.now()
        s.save()
        return Response({"success": True, "message": "Session terminated"})

    def delete(self, request):
        ok, err = self._require_admin(request)
        if not ok:
            return err

        terminated = AdminSession.objects.filter(user=request.user, is_active=True).update(
            is_active=False, logout_time=timezone.now()
        )
        return Response({"success": True, "terminated_count": terminated})


class AdminActivityLogView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ok, err = self._require_admin(request)
        if not ok:
            return err

        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 50))
        offset = (page - 1) * limit

        activities = AdminActivityLog.objects.filter(user=request.user).order_by('-created_at')
        total_count = activities.count()
        activities = activities[offset:offset + limit]

        return Response({
            "success": True,
            "activities": [{
                "id": a.id,
                "action": a.action,
                "details": a.details,
                "ip_address": a.ip_address,
                "created_at": a.created_at.isoformat(),
            } for a in activities],
            "pagination": {
                "page": page, "limit": limit, "total": total_count,
                "pages": (total_count + limit - 1) // limit,
            },
        })


# --- Loan tier / tariff views (unchanged) ---

class LoanTierDetailView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        ok, err = self._require_admin(request)
        if not ok:
            return err
        try:
            tier = LoanTier.objects.get(pk=pk)
        except LoanTier.DoesNotExist:
            return Response({"error": "Loan tier not found"}, status=404)
        return Response(LoanTierSerializer(tier).data)

    def put(self, request, pk):
        ok, err = self._require_admin(request)
        if not ok:
            return err
        try:
            tier = LoanTier.objects.get(pk=pk)
        except LoanTier.DoesNotExist:
            return Response({"error": "Loan tier not found"}, status=404)
        serializer = LoanTierSerializer(tier, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, pk):
        ok, err = self._require_admin(request)
        if not ok:
            return err
        try:
            LoanTier.objects.get(pk=pk).delete()
        except LoanTier.DoesNotExist:
            return Response({"error": "Not found"}, status=404)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TariffsView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ok, err = self._require_cs_or_above(request)
        if not ok:
            return err
        tariffs = ElectricityTariff.objects.prefetch_related("blocks").order_by(
            "-is_active", "-effective_from", "-effective_date"
        )
        return Response(ElectricityTariffSerializer(tariffs, many=True).data)

    def post(self, request):
        ok, err = self._require_admin(request)
        if not ok:
            return err
        serializer = ElectricityTariffSerializer(data=request.data)
        if serializer.is_valid():
            tariff = serializer.save()
            return Response(ElectricityTariffSerializer(tariff).data, status=201)
        return Response(serializer.errors, status=400)


class TariffSeedEraView(APIView, RBACMixin):
    """Import ERA domestic Code 10.1 default blocks into the database."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ok, err = self._require_admin(request)
        if not ok:
            return err
        from loan.tariff_utils import seed_era_domestic_tariff

        tariff, created = seed_era_domestic_tariff()
        return Response(
            {
                "success": True,
                "created": created,
                "tariff": ElectricityTariffSerializer(tariff).data,
                "message": (
                    "ERA domestic tariff imported and set as active."
                    if created
                    else "ERA domestic tariff updated and set as active."
                ),
            },
            status=201 if created else 200,
        )


class TariffActivateView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        ok, err = self._require_admin(request)
        if not ok:
            return err
        try:
            tariff = ElectricityTariff.objects.get(pk=pk)
        except ElectricityTariff.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        from loan.tariff_utils import activate_tariff

        activate_tariff(tariff)
        return Response(
            {
                "success": True,
                "message": f"{tariff.tariff_code} is now the active system-wide tariff.",
                "tariff": ElectricityTariffSerializer(tariff).data,
            }
        )


class TariffDetailView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        ok, err = self._require_cs_or_above(request)
        if not ok:
            return err
        try:
            tariff = ElectricityTariff.objects.get(pk=pk)
        except ElectricityTariff.DoesNotExist:
            return Response({"error": "Not found"}, status=404)
        return Response(ElectricityTariffSerializer(tariff).data)

    def put(self, request, pk):
        ok, err = self._require_admin(request)
        if not ok:
            return err
        try:
            tariff = ElectricityTariff.objects.get(pk=pk)
        except ElectricityTariff.DoesNotExist:
            return Response({"error": "Not found"}, status=404)
        serializer = ElectricityTariffSerializer(tariff, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, pk):
        ok, err = self._require_admin(request)
        if not ok:
            return err
        try:
            tariff = ElectricityTariff.objects.get(pk=pk)
        except ElectricityTariff.DoesNotExist:
            return Response({"error": "Not found"}, status=404)
        from loan.tariff_utils import TariffActivationError, validate_can_delete

        try:
            validate_can_delete(tariff)
        except TariffActivationError as exc:
            return Response({"error": str(exc)}, status=400)
        tariff.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class LoanTiersView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ok, err = self._require_cs_or_above(request)
        if not ok:
            return err
        tiers = LoanTier.objects.filter(is_active=True).order_by('min_score')
        return Response(LoanTierSerializer(tiers, many=True).data)

    def post(self, request):
        ok, err = self._require_admin(request)
        if not ok:
            return err
        serializer = LoanTierSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class FlaggedAccountsView(APIView, RBACMixin):
    """List open flagged accounts (CS+ — Section 6.6 / dashboard)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ok, err = self._require_cs_or_above(request)
        if not ok:
            return err

        flags = FlaggedAccount.objects.filter(
            status=FlaggedAccount.STATUS_OPEN
        ).select_related('user').order_by('-created_at')

        return Response({
            "success": True,
            "flagged_accounts": [
                {
                    "id": f.id,
                    "user": {"id": f.user.id, "email": f.user.email, "name": f"{f.user.first_name} {f.user.last_name}"},
                    "flag_type": f.flag_type,
                    "trigger": f.trigger_description,
                    "status": f.status,
                    "created_at": f.created_at.isoformat(),
                }
                for f in flags
            ],
        })


# --------------------------------------------------------------------------- #
#  Section 1.3 — 2FA (TOTP / Google Authenticator)                            #
# --------------------------------------------------------------------------- #

def _get_totp():
    """Lazy-import pyotp so startup doesn't fail if not yet installed."""
    try:
        import pyotp
        return pyotp
    except ImportError:
        raise ImportError(
            "pyotp is required for 2FA. Install it: pip install pyotp>=2.9.0"
        )


class TOTP2FASetupView(APIView, RBACMixin):
    """
    GET  — generate a new TOTP secret and return the otpauth:// URI for QR code.
    POST — verify the TOTP code from the authenticator app and enable 2FA.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ok, err = self._require_cs_or_above(request)
        if not ok:
            return err

        pyotp = _get_totp()
        secret = pyotp.random_base32()

        # Store the pending secret on the user (overwrite any previous pending secret).
        request.user.totp_secret = secret
        request.user.totp_enabled = False
        request.user.save(update_fields=['totp_secret', 'totp_enabled'])

        from django.conf import settings
        issuer = getattr(settings, 'TOTP_ISSUER_NAME', 'Gpawa Admin')
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(name=request.user.email, issuer_name=issuer)

        return Response({
            "success": True,
            "secret": secret,
            "qr_uri": uri,
            "instructions": (
                "Scan the QR code (or enter the secret) in Google Authenticator. "
                "Then POST the 6-digit code to this endpoint to confirm setup."
            ),
        })

    def post(self, request):
        ok, err = self._require_cs_or_above(request)
        if not ok:
            return err

        code = request.data.get('code', '').strip()
        if not code:
            return Response(
                {"error": "code is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.totp_secret:
            return Response(
                {"error": "No 2FA setup in progress. GET this endpoint first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pyotp = _get_totp()
        totp = pyotp.TOTP(request.user.totp_secret)
        if not totp.verify(code, valid_window=1):
            return Response(
                {"error": "Invalid TOTP code. Check your authenticator app and try again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.user.totp_enabled = True
        request.user.save(update_fields=['totp_enabled'])

        _write_audit(
            request,
            action_type=AuditLog.ACTION_LOGIN,
            target_type=AuditLog.TARGET_USER,
            target_id=request.user.id,
            target_repr=request.user.email,
            details={"event": "2fa_enabled"},
            notes="Staff member enabled 2FA",
        )

        return Response({"success": True, "message": "2FA enabled successfully."})


class TOTP2FAStatusView(APIView, RBACMixin):
    """GET — return current 2FA status for the authenticated staff member."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ok, err = self._require_cs_or_above(request)
        if not ok:
            return err
        return Response({
            "totp_enabled": request.user.totp_enabled,
            "email": request.user.email,
        })


class TOTP2FADisableView(APIView, RBACMixin):
    """POST — Admin can disable 2FA for another staff member. Requires TOTP code."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ok, err = self._require_admin(request)
        if not ok:
            return err

        target_id = request.data.get('user_id')
        code = request.data.get('code', '').strip()

        if not target_id or not code:
            return Response(
                {"error": "user_id and code are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify *admin's own* TOTP code before performing a sensitive action
        if request.user.totp_enabled:
            pyotp = _get_totp()
            totp = pyotp.TOTP(request.user.totp_secret)
            if not totp.verify(code, valid_window=1):
                return Response(
                    {"error": "Invalid TOTP code"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            target = User.objects.get(pk=target_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        target.totp_enabled = False
        target.totp_secret = None
        target.save(update_fields=['totp_enabled', 'totp_secret'])

        _write_audit(
            request,
            action_type=AuditLog.ACTION_LOGIN,
            target_type=AuditLog.TARGET_USER,
            target_id=target.id,
            target_repr=target.email,
            details={"event": "2fa_disabled_by_admin"},
            notes=f"2FA disabled by admin {request.user.email}",
        )

        return Response({"success": True, "message": f"2FA disabled for {target.email}"})


class TOTP2FALoginVerifyView(APIView):
    """
    POST — Second factor during login.

    Accepts:
      - challenge_token: signed token returned by LoginAPIView when requires_2fa=true
      - code: 6-digit TOTP code

    Returns full JWT tokens on success.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        challenge_token = request.data.get('challenge_token', '')
        code = request.data.get('code', '').strip()

        if not challenge_token or not code:
            return Response(
                {"error": "challenge_token and code are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.conf import settings
        max_age = getattr(settings, 'TOTP_CHALLENGE_MAX_AGE_SECONDS', 300)

        try:
            payload = signing.loads(
                challenge_token,
                salt='2fa_login_challenge',
                max_age=max_age,
            )
            user_id = payload['user_id']
        except signing.SignatureExpired:
            return Response(
                {"error": "Challenge token expired. Please log in again."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except (signing.BadSignature, KeyError):
            return Response(
                {"error": "Invalid challenge token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        if not user.totp_enabled or not user.totp_secret:
            return Response(
                {"error": "2FA is not enabled on this account"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pyotp = _get_totp()
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(code, valid_window=1):
            return Response(
                {"error": "Invalid TOTP code. Check your authenticator app."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Issue full JWT tokens
        remember_me = bool(payload.get('remember_me'))
        refresh = RefreshToken.for_user(user)
        if remember_me:
            from datetime import timedelta
            from django.conf import settings
            days = getattr(settings, "REMEMBER_ME_REFRESH_DAYS", 30)
            refresh.set_exp(lifetime=timedelta(days=days))
        access = refresh.access_token

        _write_audit(
            None,
            action_type=AuditLog.ACTION_LOGIN,
            target_type=AuditLog.TARGET_USER,
            target_id=user.id,
            target_repr=user.email,
            details={"event": "2fa_login_success"},
        )

        redirect = '/admin/dashboard' if (user.is_staff_member or user.is_superuser) else '/dashboard'

        return Response({
            "success": True,
            "access": str(access),
            "refresh": str(refresh),
            "remember_me": remember_me,
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "user_role": user.user_role,
                "is_admin": user.user_role == User.ADMIN or user.is_superuser,
                "is_staff_member": user.is_staff_member or user.is_superuser,
                "is_superuser": user.is_superuser,
                "totp_enabled": user.totp_enabled,
                "redirect_to": redirect,
            },
        })
