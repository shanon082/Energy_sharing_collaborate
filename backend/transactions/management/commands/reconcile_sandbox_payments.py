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
        from transactions.checkouts import overdue_checkouts, expire_due_checkouts, SUBMISSION_PROOF
        def due_ids():
            now = timezone.now()
            rows = PaymentIntent.objects.filter(provider="MTN_SANDBOX", currency="EUR", status="PENDING", reconcile_after__lte=now).filter(
                Q(reconcile_lease_until__isnull=True) | Q(reconcile_lease_until__lte=now)).exclude(checkout__initiation_cancelled_at__isnull=False)
            if provider_mode() != "MTN_SANDBOX" or new_mtn_payments_paused():
                # Only provably unsubmitted NEW records are paused. Ambiguous
                # metadata still needs status recovery under its original provider.
                rows = rows.exclude(submission_state="NEW", reconcile_attempts=0,
                    reconcile_lease_id__isnull=True, reconcile_lease_until__isnull=True,
                    sandbox_context__has_key='checkout_submission_proof',
                    sandbox_context__checkout_submission_proof=SUBMISSION_PROOF)
            return list(rows.order_by("reconcile_after").values_list("pk", flat=True)[:options["limit"]])
        if not options["run"]:
            self.stdout.write(f'DRY_RUN overdue_checkout_ids={list(overdue_checkouts().values_list("pk", flat=True)[:20])}; no writes')
            self.stdout.write(f"DRY_RUN due_intent_ids={due_ids()}; no provider call")
            return
        started = time.monotonic()
        def deadline(signum, frame):
            raise CommandError("Sandbox reconciliation deadline reached; pending outcomes retained for subsequent review.")
        previous = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, deadline)
        signal.alarm(options["max_seconds"])
        try:
            expired = expire_due_checkouts(limit=20, stop_before=started+options['max_seconds']-25)
            self.stdout.write(f'local_checkout_expiry_ids={expired}; provider outcomes unchanged')
            ids = due_ids()
            if ids:
                MTNSandbox(recovery=True)  # existing references retain their original provider
            for pk in ids:
                if time.monotonic() - started > options["max_seconds"] - 25:
                    break
                try:
                    row, applied = reconcile_sandbox_payment(pk)
                except PermissionDenied:
                    self.stdout.write(f"intent_id={pk} BLOCKED_NEW_COLLECTION; retained")
                    continue
                self.stdout.write(f"intent_id={pk} status={row.status} submission={row.submission_state} effect={applied} error={row.reconciliation_error or 'none'}")
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)
