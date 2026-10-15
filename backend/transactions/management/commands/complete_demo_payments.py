"""Finite alwaysdata scheduled simulator; never consumes MTN/core intents."""
import signal
import time
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from rest_framework.exceptions import APIException
from backend.demo_config import require_demo, LOCAL_DEMO
from transactions.models import PaymentIntent
from transactions.demo_payments import complete_demo_payment
from transactions.payment_settlement import PaymentSettlementError


class Command(BaseCommand):
    help = "Dry-run eligible local demo payments; --run settles a bounded batch without external calls."

    def add_arguments(self, parser):
        parser.add_argument("--run", action="store_true")
        parser.add_argument("--limit", type=int, default=20)
        parser.add_argument("--max-seconds", type=int, default=50)

    def handle(self, *args, **options):
        require_demo()
        if not 1 <= options["limit"] <= 100 or not 1 <= options["max_seconds"] <= 55:
            raise CommandError("Use limit 1–100 and max-seconds 1–55.")
        ids = list(PaymentIntent.objects.filter(provider=LOCAL_DEMO, currency="UGX", status="PENDING",
            demo_eligible_at__lte=timezone.now()).order_by("demo_eligible_at").values_list("pk", flat=True)[:options["limit"]])
        if not options["run"]:
            self.stdout.write(f"DRY_RUN eligible_intent_ids={ids}; no settlement")
            return
        def deadline(signum, frame):
            raise CommandError("Demo batch deadline reached; unfinished records remain pending.")
        previous = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, deadline)
        signal.alarm(options["max_seconds"])
        started = time.monotonic()
        failed = False
        try:
            for pk in ids:
                if time.monotonic() - started >= options["max_seconds"] - 1:
                    break
                try:
                    row, effect = complete_demo_payment(pk)
                    self.stdout.write(f"intent_id={pk} status={row.status} effect={effect}")
                except (PaymentSettlementError, APIException):
                    failed = True
                    self.stderr.write(f"intent_id={pk} BLOCKED; retained for reconciliation")
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)
        if failed:
            raise CommandError("Some demo payments could not settle; inspect source bindings/account state. No automatic cancellation.")
