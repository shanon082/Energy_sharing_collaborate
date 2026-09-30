"""Generate local consumption against an enrolled development simulator."""

from django.core.management.base import BaseCommand, CommandError

from meter.models import SimulatedMeter
from meter.simulation import SimulationError, require_simulation, simulate_consumption


class Command(BaseCommand):
    help = "Record whole-Wh local consumption for a development-only simulated meter."

    def add_arguments(self, parser):
        parser.add_argument("meter_no")
        parser.add_argument("amount_wh", type=int)

    def handle(self, *args, **options):
        try:
            require_simulation()
        except SimulationError as exc:
            raise CommandError(str(exc)) from exc
        device = SimulatedMeter.objects.filter(meter__meter_no=options["meter_no"]).first()
        if device is None:
            raise CommandError("Simulator is not enrolled for that meter.")
        try:
            event, _ = simulate_consumption(device.device_id, options["amount_wh"])
        except SimulationError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Simulated telemetry event {event.event_id}: {event.classification}.")
