"""
Management command: seed_era_tariff

Seeds the ERA/UEDCL domestic tariff (Code 10.1, Q4 2025 / current rates) into
the ElectricityTariff and TariffBlock tables.

Run once after initial deployment or to add a new quarter's rates:
    python manage.py seed_era_tariff

Or use Admin → Tariffs → Import ERA defaults in the web console.
"""
from django.core.management.base import BaseCommand

from loan.tariff_utils import seed_era_domestic_tariff


class Command(BaseCommand):
    help = "Seed the ERA/UEDCL domestic tariff (Code 10.1) into the database"

    def handle(self, *args, **options):
        tariff, created = seed_era_domestic_tariff()
        action = "Created" if created else "Updated"
        self.stdout.write(f"{action} tariff: {tariff}")
        for block in tariff.blocks.order_by("block_order"):
            self.stdout.write(f"  Block: {block}")
        self.stdout.write(
            self.style.SUCCESS(
                "\nERA domestic tariff seeded and set as active.\n"
                "Service charge: UGX 3,360 | VAT: 18% (applied in billing engine)."
            )
        )
