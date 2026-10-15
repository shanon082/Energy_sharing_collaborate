"""Finite scheduled provider reconciliation, never a Celery/eager shortcut."""
import time
import signal
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Q
from transactions.models import PaymentIntent
from transactions.sandbox_payments import reconcile_sandbox_payment
from loan.sandbox_service import require_sandbox
from backend.demo_config import require_mtn_sandbox
from mtn_momo.sandbox import MTNSandbox


class Command(BaseCommand):
    help = "Dry-run due MTN sandbox intents; --run performs bounded trusted reconciliation."

    def add_arguments(self, parser):
        parser.add_argument("--run", action="store_true")
        parser.add_argument("--limit", type=int, default=2)
        parser.add_argument("--max-seconds", type=int, default=50)

    def handle(self, *args, **options):
        require_sandbox()
        require_mtn_sandbox()
        if not 1 <= options["limit"] <= 10 or not 25 <= options["max_seconds"] <= 120:
            raise CommandError("Use limit 1–10 and max-seconds 25–120.")
        now = timezone.now()
        ids = list(PaymentIntent.objects.filter(provider="MTN_SANDBOX", currency="EUR", status="PENDING", reconcile_after__lte=now)
            .filter(Q(reconcile_lease_until__isnull=True) | Q(reconcile_lease_until__lte=now))
            .order_by("reconcile_after").values_list("pk", flat=True)[:options["limit"]])
        if not options["run"]:
            self.stdout.write(f"DRY_RUN due_intent_ids={ids}; no provider call")
            return
        MTNSandbox()  # fail truthfully rather than silently discarding queued work
        started = time.monotonic()
        def deadline(signum, frame):
            raise CommandError("Sandbox reconciliation deadline reached; pending outcomes retained for subsequent review.")
        previous = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, deadline)
        signal.alarm(options["max_seconds"])
        try:
            for pk in ids:
                if time.monotonic() - started > options["max_seconds"] - 25:
                    break
                row, applied = reconcile_sandbox_payment(pk)
                self.stdout.write(f"intent_id={pk} status={row.status} submission={row.submission_state} effect={applied} error={row.reconciliation_error or 'none'}")
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)
