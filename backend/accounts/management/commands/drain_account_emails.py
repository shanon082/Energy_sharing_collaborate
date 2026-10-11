"""Finite account-mail drain for alwaysdata Scheduled tasks; default read-only."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from accounts.models import AccountEmailDelivery


class Command(BaseCommand):
    help = "Report account mail status; --send drains only queued messages, without automatic retries."

    def add_arguments(self, parser):
        parser.add_argument("--send", action="store_true")
        parser.add_argument("--limit", type=int, default=5)

    def handle(self, *args, **options):
        if not getattr(settings, "ACCOUNT_EMAIL_OUTBOX_ENABLED", False):
            raise CommandError("Account mail outbox is not enabled in these settings")
        if not 1 <= options["limit"] <= 20:
            raise CommandError("--limit must be between 1 and 20")
        if not options["send"]:
            for row in AccountEmailDelivery.objects.values("status").annotate(total=Count("pk")).order_by("status"):
                self.stdout.write(f'{row["status"]}: {row["total"]}')
            for job in AccountEmailDelivery.objects.exclude(status=AccountEmailDelivery.SENT).order_by("pk")[:options["limit"]]:
                self.stdout.write(f"mail_job={job.pk} kind={job.kind} status={job.status} created={job.created_at.isoformat()}")
            return
        from accounts.email_outbox import drain_account_emails
        results = drain_account_emails(options["limit"])
        for pk, status in results:
            self.stdout.write(f"mail_job={pk} status={status}")
        if any(status == AccountEmailDelivery.OUTCOME_UNKNOWN for _, status in results):
            raise CommandError("Account mail outcome unknown; inspect SMTP history before requesting a new message")
