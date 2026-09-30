"""Enrol an AMI meter in the isolated database-backed simulator."""

import os

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError

from meter.models import Meter, SimulatedMeter
from meter.simulation import SimulationError, require_simulation


class Command(BaseCommand):
    help = "Enrol a development AMI meter; SIMULATOR_DEVICE_TOKEN must be provided in the environment."

    def add_arguments(self, parser):
        parser.add_argument("meter_no")

    def handle(self, *args, **options):
        try:
            require_simulation()
        except SimulationError as exc:
            raise CommandError(str(exc)) from exc
        raw_token = os.environ.get("SIMULATOR_DEVICE_TOKEN", "")
        if len(raw_token) < 32:
            raise CommandError("Set a simulator-only device token of at least 32 characters.")
        meter = Meter.objects.filter(
            meter_no=options["meter_no"], status=Meter.STATUS_ACTIVE,
            architecture=Meter.ARCH_AMI, user__isnull=False,
        ).first()
        if meter is None:
            raise CommandError("An active, assigned AMI meter is required.")
        if SimulatedMeter.objects.filter(meter=meter).exists():
            raise CommandError("Simulator already enrolled; credential rotation requires a separate reviewed action.")
        device = SimulatedMeter.objects.create(
            meter=meter, credential_hash=make_password(raw_token),
        )
        self.stdout.write(f"Simulator enrolled with device ID {device.device_id}.")
