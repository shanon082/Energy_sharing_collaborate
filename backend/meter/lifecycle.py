"""Meter registration lifecycle — soft delete with audit archive."""

from __future__ import annotations

from django.db import transaction as db_transaction
from django.utils import timezone

from meter.models import DeletedMeterRecord, Meter


class MeterDeleteError(Exception):
    pass


@db_transaction.atomic
def release_meter_from_account(
    meter: Meter,
    *,
    deleted_by,
    deleted_by_role: str,
    reason: str = "",
    metadata: dict | None = None,
) -> DeletedMeterRecord:
    """
    Remove a meter from its owner's account while preserving history.

    - Writes DeletedMeterRecord snapshot
    - Soft-deletes Meter (renames meter_no to free the number for re-registration)
    - Clears user link; historical FKs (tokens, shares) remain on the ghost row
    """
    meter = Meter.all_objects.select_for_update().get(pk=meter.pk)

    if meter.is_deleted:
        raise MeterDeleteError("This meter has already been removed.")

    if not meter.user_id and deleted_by_role == DeletedMeterRecord.ROLE_USER:
        raise MeterDeleteError("Meter is not linked to your account.")

    original_no = meter.meter_no
    former_user = meter.user

    record = DeletedMeterRecord.objects.create(
        original_meter_no=original_no,
        meter=meter,
        former_user_id=former_user.id if former_user else None,
        former_user_email=getattr(former_user, "email", "") or "",
        former_user_phone=str(getattr(former_user, "phone_number", "") or ""),
        architecture=meter.architecture,
        label=meter.label or "",
        static_ip=meter.static_ip,
        units_at_deletion=meter.units,
        pending_units_at_deletion=meter.pending_units,
        had_iot_token=bool((meter.iot_device_token or "").strip()),
        status_at_deletion=meter.status,
        deleted_at=timezone.now(),
        deleted_by=deleted_by,
        deleted_by_role=deleted_by_role,
        reason=(reason or "").strip(),
        metadata=metadata or {},
    )

    meter.is_deleted = True
    meter.deleted_at = record.deleted_at
    meter.deleted_by = deleted_by
    meter.deleted_reason = record.reason
    meter.user = None
    meter.status = Meter.STATUS_INACTIVE
    meter.meter_no = f"{original_no}__del_{meter.pk}"
    meter.save(
        update_fields=[
            "is_deleted",
            "deleted_at",
            "deleted_by",
            "deleted_reason",
            "user",
            "status",
            "meter_no",
            "modify_date",
        ]
    )

    return record
