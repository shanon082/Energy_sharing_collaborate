from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from meter.bench_device import require_bench
from meter.models import BenchDevice

class Command(BaseCommand):
    help = "Disable an isolated bench credential; preserves all pending commands and paid entitlement."
    def add_arguments(self, parser):
        parser.add_argument("device_id")
        parser.add_argument("--confirm", action="store_true")
    def handle(self, *args, **options):
        require_bench()
        if not options["confirm"]:
            self.stdout.write("DRY_RUN: no credentials changed; use --confirm after review")
            return
        with transaction.atomic():
            device = BenchDevice.objects.select_for_update().get(pk=options["device_id"])
            device.active = False
            device.revoked_at = timezone.now()
            device.save(update_fields=["active", "revoked_at"])
        self.stdout.write("SOFTWARE_BENCH credential revoked; obligations retained for reconciliation")
