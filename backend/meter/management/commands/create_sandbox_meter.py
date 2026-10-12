from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from meter.models import Meter


class Command(BaseCommand):
    help = "Create only clean, unowned SANDBOX logical inventory; default dry-run. No physical device provisioning."

    def add_arguments(self, parser):
        parser.add_argument("--meter-no", required=True)
        parser.add_argument("--create", action="store_true")

    def handle(self, *args, **options):
        if getattr(settings, "CONSUMER_SANDBOX_ENABLED", False) is not True:
            raise CommandError("Use the reviewed sandbox deployment profile.")
        number = options["meter_no"]
        import re
        if not re.fullmatch(r"SANDBOX-[A-Z0-9-]{1,70}", number):
            raise CommandError("Use an explicitly synthetic SANDBOX- inventory number.")
        if Meter.all_objects.filter(meter_no=number).exists():
            raise CommandError("Existing inventory is never relabelled or reassigned by this command.")
        if not options["create"]:
            self.stdout.write("DRY_RUN: one new unowned logical TEST meter; no credentials, telemetry, energy or ownership.")
            return
        with transaction.atomic():
            # Bypass the legacy balance-mirroring post_save signal: metadata only.
            row = Meter.all_objects.bulk_create([Meter(meter_no=number, sandbox_inventory=True,
                architecture="AMI", label="SANDBOX logical test meter")])[0]
            from admin.models import AuditLog
            AuditLog.objects.create(action_type=AuditLog.ACTION_METER_REGISTER, target_type="system",
                target_id=str(row.pk), details={"environment": "MTN_SANDBOX", "inventory_only": True})
        self.stdout.write(f"Created test_inventory_id={row.pk}; staff authorization still required.")
