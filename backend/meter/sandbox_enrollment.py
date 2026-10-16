"""Immediate prototype enrollment; no physical provisioning or legacy signals."""
from django.db import IntegrityError, transaction
from django.db.models.functions import Trim
from rest_framework.exceptions import APIException, ValidationError

from accounts.models import User
from meter.models import (Meter, MeterEnrollmentRequest, MeterEnrollmentReview,
                          SandboxMeterEnrollment, DeletedMeterRecord)
from meter.validators import validate_meter_no

OWNERSHIP_NOTICE = "Meter linked for prototype testing. Ownership and live readings are not verified with the electricity provider."


class MeterUnavailable(APIException):
    status_code = 409
    default_code = "METER_UNAVAILABLE"
    default_detail = {"code": "METER_UNAVAILABLE", "message": "This meter number is unavailable for prototype enrollment."}


def normalized_number(raw):
    # CharField serializers coerce integers, which would lose leading zeros.
    if not isinstance(raw, str):
        raise ValidationError({"meter_no": "Meter number must be text."})
    valid, value = validate_meter_no(raw)
    if not valid or any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in value):
        raise ValidationError({"meter_no": "Enter your 11-digit meter number."})
    return value


def sandbox_meter_authorized(meter, owner):
    if meter.user_id != owner.pk or not meter.sandbox_inventory or meter.is_deleted or meter.status != Meter.STATUS_ACTIVE:
        return False
    return (SandboxMeterEnrollment.objects.filter(meter=meter, owner=owner, provenance="SELF_DECLARED").exists()
        or MeterEnrollmentReview.objects.filter(meter=meter, request__owner=owner, decision="APPROVED").exists())


def enroll_sandbox_meter(owner, raw_number):
    from loan.sandbox_service import require_sandbox, verified_consumer
    require_sandbox()
    number = normalized_number(raw_number)
    with transaction.atomic():
        owner = User.objects.select_for_update().get(pk=owner.pk)
        verified_consumer(owner)
        prior = MeterEnrollmentRequest.objects.select_for_update().filter(owner=owner, meter_no=number).first()
        review = MeterEnrollmentReview.objects.filter(request=prior).first() if prior else None
        if review and review.decision == "REJECTED":
            raise ValidationError({"code": "PRIOR_ENROLLMENT_REJECTED",
                "message": "A previous request for this number was declined. Contact support before retrying."})
        existing = Meter.all_objects.annotate(normalized_number=Trim("meter_no")).filter(normalized_number=number).first()
        if existing:
            if sandbox_meter_authorized(existing, owner):
                _complete_assessment(owner, existing)
                return existing, False
            raise MeterUnavailable()
        # Old renamed/deleted records and string-keyed core balances are not
        # clean inventory, even when no active Meter currently has that number.
        from wallet.models import MeterBalance
        if (DeletedMeterRecord.objects.filter(original_meter_no=number).exists()
                or MeterBalance.objects.filter(meter_number=number).exists() or review):
            raise MeterUnavailable()
        try:
            with transaction.atomic():
                # bulk_create skips the legacy post_save wallet/financial mirror.
                # Registry meter_no unique constraint is the cross-owner arbiter.
                meter = Meter(user=owner, meter_no=number, sandbox_inventory=True,
                    architecture=Meter.ARCH_AMI, label="Prototype meter", status=Meter.STATUS_ACTIVE)
                Meter.all_objects.bulk_create([meter])
                SandboxMeterEnrollment.objects.create(meter=meter, owner=owner, prior_request=prior)
        except IntegrityError:
            raise MeterUnavailable() from None
        _complete_assessment(owner, meter)
        return meter, True


def _complete_assessment(owner, meter):
    from backend.demo_config import provider_mode
    if provider_mode() == "LOCAL_DEMO":
        from loan.demo_assessment import complete_demo_assessment
        complete_demo_assessment(owner, meter)
