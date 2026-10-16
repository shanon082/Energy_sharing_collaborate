"""Explicit operator attestation for software-bench inventory only."""
import os
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from meter.bench_device import require_bench
from meter.models import BenchDevice, Meter
from meter.validators import validate_meter_no


class Command(BaseCommand):
    help = "Provision an isolated software device; never commissions a physical household meter."
    def add_arguments(self, parser):
        parser.add_argument("meter_id", type=int)
        parser.add_argument("--environment", required=True, choices=["CORE", "SANDBOX", "UGX_DEMO"])
        parser.add_argument("--confirm-software-bench", action="store_true")
    def handle(self, *args, **options):
        require_bench()
        credential = os.environ.get("BENCH_DEVICE_TOKEN", "")
        if not options["confirm_software_bench"] or len(credential) < 32:
            raise CommandError("Confirm software-bench isolation and set private BENCH_DEVICE_TOKEN (at least32 characters)")
        with transaction.atomic():
            meter = Meter.objects.select_for_update().filter(pk=options["meter_id"], status="ACTIVE", user__isnull=False).first()
            if (meter is None or not validate_meter_no(meter.meter_no)[0]
                    or meter.sandbox_inventory != (options["environment"] != "CORE")):
                raise CommandError("An active, assigned 11-digit meter in the matching isolated inventory is required")
            if BenchDevice.objects.filter(meter=meter).exists():
                raise CommandError("Existing or revoked binding requires reconciliation; automatic replacement is prohibited")
            device = BenchDevice.objects.create(meter=meter, owner_id=meter.user_id,
                environment=options["environment"], credential_hash=make_password(credential))
        self.stdout.write(f"SOFTWARE_BENCH provisioned device_id={device.pk}; no physical commissioning")
