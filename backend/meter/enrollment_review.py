"""Metadata-only review: no provisioning, financial effect or device operation."""
from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.views.decorators.debug import sensitive_variables

from accounts.models import User
from admin.models import AuditLog
from meter.models import Meter, MeterEnrollmentRequest, MeterEnrollmentReview, DeletedMeterRecord
from wallet.models import MeterBalance


def require_reviewer(user):
    if not (user.is_authenticated and user.is_active and user.is_staff
            and user.user_role in {User.ADMIN, User.OPERATOR}
            and not user.is_suspended and not user.must_change_password
            and user.profile.email_verified):
        raise PermissionDenied("Active, verified operator/admin staff credentials are required.")


class ReviewForm(forms.Form):
    request_id = forms.UUIDField()
    decision = forms.ChoiceField(choices=[("APPROVED", "Approve"), ("REJECTED", "Reject")])
    evidence_type = forms.ChoiceField(required=False, choices=[("", "Select independently checked evidence"),
        ("SANDBOX_AUTHORIZATION", "Checked authorization for synthetic test inventory (not a household meter)"),
        ("UTILITY_ACCOUNT", "Utility-confirmed customer/meter assignment"),
        ("SITE_AUTHORIZATION", "Independently checked occupancy and owner's authorization")])
    evidence_reference = forms.CharField(required=False, max_length=160)
    ownership_verified = forms.BooleanField(required=False)
    consumer_reason = forms.CharField(max_length=240,
        help_text="Consumer-visible explanation. No private evidence or identity documents.")
    otp = forms.CharField(required=False, max_length=6, widget=forms.PasswordInput)

    def clean(self):
        data = super().clean()
        if data.get("decision") == "APPROVED" and not (
                data.get("ownership_verified") and data.get("evidence_type")
                and len(data.get("evidence_reference", "")) >= 8):
            raise forms.ValidationError("Approval requires independently verified ownership/usage authorization and a private evidence case reference; a meter number is insufficient.")
        return data


@sensitive_variables("data", "values", "form")
def review_enrollment(staff, data):
    require_reviewer(staff)
    # Preserve existing configured staff second-factor requirements even when
    # logging into Django's session-based admin rather than the JWT endpoint.
    if staff.totp_enabled:
        try:
            import pyotp
        except ImportError:
            raise PermissionDenied("Staff authenticator verification is unavailable; install the existing optional pyotp dependency before reviewing.") from None
        if not staff.totp_secret or not pyotp.TOTP(staff.totp_secret).verify(data.get("otp", ""), valid_window=1):
            raise PermissionDenied("A valid staff authenticator code is required.")
    form = ReviewForm(data)
    if not form.is_valid():
        raise ValidationError("Review fields are invalid. Supply the decision, consumer explanation and independently checked evidence for approval.")
    values = form.cleaned_data
    with transaction.atomic():
        row = MeterEnrollmentRequest.objects.select_for_update().get(request_id=values["request_id"])
        previous = MeterEnrollmentReview.objects.filter(request=row).first()
        if previous:
            if previous.decision != values["decision"]:
                raise ValidationError("Already reviewed; decisions cannot be overwritten through this workflow.")
            return previous
        if hasattr(row, "sandbox_transition"):
            raise ValidationError("This request was explicitly retried through prototype self-enrollment; it is not a staff verification decision.")
        meter = None
        if values["decision"] == "APPROVED":
            owner = User.objects.select_for_update().get(pk=row.owner_id)
            if not owner.is_active or owner.is_suspended or owner.user_role != User.CLIENT or not owner.profile.email_verified:
                raise ValidationError("The requesting consumer must be active and email verified.")
            meter = Meter.all_objects.select_for_update().filter(meter_no=row.meter_no).first()
            if not meter or meter.is_deleted or meter.status != Meter.STATUS_ACTIVE:
                raise ValidationError("An active, pre-provisioned meter is required; this workflow does not create devices.")
            if (values["evidence_type"] == "SANDBOX_AUTHORIZATION") != meter.sandbox_inventory:
                raise ValidationError("Test inventory needs checked sandbox authorization; it cannot substitute for household ownership proof.")
            if meter.user_id not in (None, row.owner_id):
                raise ValidationError("Already assigned elsewhere. Ownership transfers require separate tenancy/history reconciliation.")
            if meter.user_id is None:
                # Refuse any prior balances, telemetry, allocations or linked
                # historical records before giving a new owner read access.
                related_history = any(relation.related_model._base_manager.filter(
                    **{relation.field.name: meter.pk}).exists() for relation in Meter._meta.related_objects)
                if (related_history or meter.units or meter.pending_units or meter.deactivated_at
                        or meter.deleted_at or MeterBalance.objects.filter(meter_number=meter.meter_no).exists()
                        or DeletedMeterRecord.objects.filter(original_meter_no=meter.meter_no).exists()
                        or AuditLog.objects.filter(target_type="meter", target_id=str(meter.pk)).exists()):
                    raise ValidationError("Unassigned meter has historical evidence; reconcile tenancy and records before assignment.")
                # Avoid legacy post_save signals, which mirror balances/create
                # wallets. Only this owner metadata is changed, under a row lock.
                Meter.all_objects.filter(pk=meter.pk, user__isnull=True).update(user_id=row.owner_id)
        result = MeterEnrollmentReview.objects.create(request=row, decision=values["decision"], meter=meter,
            reviewed_by=staff, evidence_type=values.get("evidence_type", ""),
            evidence_reference=values.get("evidence_reference", ""), consumer_reason=values["consumer_reason"])
        # Audit failure rolls back both review and assignment. Private evidence
        # remains only in the protected review, never in consumer/API logs.
        AuditLog.objects.create(staff_member=staff,
            action_type=AuditLog.ACTION_KYC_VERIFY if meter else AuditLog.ACTION_KYC_REJECT,
            target_type=AuditLog.TARGET_METER if meter else AuditLog.TARGET_USER,
            target_id=str(meter.pk if meter else row.owner_id),
            details={"meter_enrollment_request_id": str(row.request_id), "review_id": result.pk,
                     "decision": result.decision, "consumer_id": row.owner_id, "meter_id": meter.pk if meter else None},
            notes="Meter enrollment evidence review; metadata only.")
        return result
