"""Finite scheduled provider reconciliation, never a Celery/eager shortcut."""
import time
import signal
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Q
from transactions.models import PaymentIntent
from transactions.sandbox_payments import reconcile_sandbox_payment
from loan.sandbox_service import require_sandbox
from backend.demo_config import require_mtn_sandbox, provider_mode, new_mtn_payments_paused
from mtn_momo.sandbox import MTNSandbox
from rest_framework.exceptions import PermissionDenied


class Command(BaseCommand):
    help = "Dry-run due MTN sandbox intents; --run performs bounded trusted reconciliation."

    def add_arguments(self, parser):
        parser.add_argument("--run", action="store_true")
        parser.add_argument("--limit", type=int, default=2)
        parser.add_argument("--max-seconds", type=int, default=50)

    def handle(self, *args, **options):
        require_sandbox()
        require_mtn_sandbox(recovery=True)
        if not 1 <= options["limit"] <= 10 or not 25 <= options["max_seconds"] <= 120:
            raise CommandError("Use limit 1–10 and max-seconds 25–120.")
        now = timezone.now()
        rows = PaymentIntent.objects.filter(provider="MTN_SANDBOX", currency="EUR", status="PENDING", reconcile_after__lte=now).filter(
            Q(reconcile_lease_until__isnull=True) | Q(reconcile_lease_until__lte=now))
        if provider_mode() != "MTN_SANDBOX" or new_mtn_payments_paused():
            # Filter before LIMIT: paused NEW records cannot fill every batch
            # and starve recovery of already-submitted collections.
            rows = rows.exclude(submission_state="NEW")
        ids = list(rows.order_by("reconcile_after").values_list("pk", flat=True)[:options["limit"]])
        if not options["run"]:
            self.stdout.write(f"DRY_RUN due_intent_ids={ids}; no provider call")
            return
        MTNSandbox(recovery=True)  # existing references remain recoverable after a mode switch
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
                try:
                    row, applied = reconcile_sandbox_payment(pk)
                except PermissionDenied:
                    # A never-submitted intent must not initiate a collection
                    # while NEW MTN activity is paused, nor block older recovery.
                    self.stdout.write(f"intent_id={pk} BLOCKED_NEW_COLLECTION; retained")
                    continue
                self.stdout.write(f"intent_id={pk} status={row.status} submission={row.submission_state} effect={applied} error={row.reconciliation_error or 'none'}")
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)
