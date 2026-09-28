"""Tariff activation helpers — only one schedule may be active system-wide."""

from __future__ import annotations

from django.db import transaction

from loan.models import ElectricityTariff, TariffBlock


class TariffActivationError(Exception):
    pass


@transaction.atomic
def activate_tariff(tariff: ElectricityTariff) -> ElectricityTariff:
    """Set `tariff` as the sole active schedule; deactivate all others."""
    ElectricityTariff.objects.exclude(pk=tariff.pk).update(is_active=False)
    if not tariff.is_active:
        tariff.is_active = True
        tariff.save(update_fields=["is_active"])
    return tariff


def ensure_single_active_on_save(tariff: ElectricityTariff, *, activating: bool) -> None:
    """When saving with is_active=True, deactivate every other tariff."""
    if activating and tariff.is_active:
        ElectricityTariff.objects.exclude(pk=tariff.pk).update(is_active=False)


def validate_can_deactivate(tariff: ElectricityTariff) -> None:
    """Prevent turning off the only active tariff without replacing it."""
    if not tariff.is_active:
        return
    other_active = ElectricityTariff.objects.filter(is_active=True).exclude(pk=tariff.pk).exists()
    if not other_active:
        raise TariffActivationError(
            "At least one tariff must remain active. Activate another tariff first."
        )


def validate_can_delete(tariff: ElectricityTariff) -> None:
    if tariff.is_active:
        raise TariffActivationError(
            "Cannot delete the active tariff. Activate another tariff first, then delete this one."
        )


def seed_era_domestic_tariff() -> tuple[ElectricityTariff, bool]:
    """
    Seed ERA domestic Code 10.1 blocks (Q1 2026 rates).
    Returns (tariff, created).
    """
    import datetime

    defaults = {
        "tariff_name": "ERA Domestic Code 10.1 (Q1 2026)",
        "tariff_type": "DOMESTIC",
        "voltage_level": "Low Voltage Single Phase",
        "voltage_value": "240V",
        "service_charge": "3360.00",
        "is_active": True,
        "effective_from": datetime.date(2026, 1, 1),
        "effective_to": None,
    }
    tariff, created = ElectricityTariff.objects.update_or_create(
        tariff_code="DOM-10.1-2026Q1",
        defaults=defaults,
    )

    blocks = [
        {
            "block_name": "Lifeline (first 15 units)",
            "min_units": 0,
            "max_units": 15,
            "rate_per_unit": "250.00",
            "block_order": 1,
            "is_lifeline_block": True,
            "non_lifeline_rate": "756.20",
        },
        {
            "block_name": "Normal (16-80 units)",
            "min_units": 16,
            "max_units": 80,
            "rate_per_unit": "756.20",
            "block_order": 2,
            "is_lifeline_block": False,
            "non_lifeline_rate": None,
        },
        {
            "block_name": "Cooking tariff (81-150 units)",
            "min_units": 81,
            "max_units": 150,
            "rate_per_unit": "412.00",
            "block_order": 3,
            "is_lifeline_block": False,
            "non_lifeline_rate": None,
        },
        {
            "block_name": "Super normal (above 150 units)",
            "min_units": 151,
            "max_units": None,
            "rate_per_unit": "756.00",
            "block_order": 4,
            "is_lifeline_block": False,
            "non_lifeline_rate": None,
        },
    ]

    for block_data in blocks:
        TariffBlock.objects.update_or_create(
            tariff=tariff,
            block_order=block_data["block_order"],
            defaults=block_data,
        )

    ElectricityTariff.objects.filter(tariff_code="CODE10.1").update(is_active=False)
    activate_tariff(tariff)
    return tariff, created
