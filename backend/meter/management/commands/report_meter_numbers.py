"""Read-only compatibility report. No personal fields, tokens or secret values."""
from django.core.management.base import BaseCommand
from meter.models import Meter
from meter.validators import validate_meter_no

class Command(BaseCommand):
    help = "Dry-run report of legacy nonconforming meter IDs; no renaming, padding, deletion or reassignment."
    def handle(self, *args, **options):
        count = 0
        for meter in Meter.all_objects.all().only("pk", "meter_no", "is_deleted").iterator():
            if not validate_meter_no(meter.meter_no)[0] or meter.meter_no != meter.meter_no.strip():
                count += 1
                self.stdout.write(f"meter_id={meter.pk} length={len(meter.meter_no)} deleted={meter.is_deleted} needs_review=True")
        self.stdout.write(f"DRY_RUN nonconforming={count}; records unchanged")
