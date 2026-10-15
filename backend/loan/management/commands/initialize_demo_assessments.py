"""Preview-first, bounded prototype assessment repair; never changes real scores."""
from django.core.management.base import BaseCommand, CommandError
from accounts.models import Profile, User
from backend.demo_config import require_demo
from loan.models import DemoCreditAssessment
from loan.demo_assessment import initialize_demo_assessment, complete_demo_assessment, refresh_demo_purchase_contribution
from loan.account_data import SCENARIOS
from meter.sandbox_enrollment import sandbox_meter_authorized
from meter.models import Meter


class Command(BaseCommand):
    help = "Preview missing/pending demo assessments; --apply creates or retries only test evidence."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument("--user-id", type=int)
        parser.add_argument("--meter-id", type=int)
        parser.add_argument("--scenario", choices=list(SCENARIOS))
        parser.add_argument("--refresh-purchases", action="store_true")

    def handle(self, *args, **options):
        require_demo()
        if not 1 <= options["limit"] <= 100:
            raise CommandError("Use limit 1–100.")
        if (options["scenario"] or options["meter_id"]) and not options["user_id"]:
            raise CommandError("Scenario/meter selection requires explicit --user-id; no bulk assignment.")
        users = User.objects.filter(user_role=User.CLIENT, is_staff=False, is_superuser=False, is_active=True, is_suspended=False)
        if options["user_id"]:
            users = users.filter(pk=options["user_id"])
        elif not options["refresh_purchases"]:
            users = users.exclude(demo_assessments__environment="UGX_DEMO", demo_assessments__status="READY")
        for owner in users.order_by("pk")[:options["limit"]]:
            row = DemoCreditAssessment.objects.filter(owner=owner, environment="UGX_DEMO").first()
            state = row.status if row else "MISSING"
            self.stdout.write(f"{'APPLY' if options['apply'] else 'PREVIEW'} owner_id={owner.pk} assessment={state}")
            if not options["apply"]:
                continue
            if options["scenario"] and row is not None:
                raise CommandError("An existing demo scenario is immutable; no assessment/history overwrite.")
            row, _ = initialize_demo_assessment(owner, scenario=options["scenario"])
            if row.status == "READY":
                if options["refresh_purchases"]:
                    refresh_demo_purchase_contribution(owner)
                continue
            if not Profile.objects.filter(user=owner, email_verified=True).exists():
                self.stdout.write(f"owner_id={owner.pk} retained=PENDING waiting=email-verification")
                continue
            if options["meter_id"]:
                meter = Meter.objects.filter(pk=options["meter_id"], user=owner).first()
                if not meter or not sandbox_meter_authorized(meter, owner):
                    raise CommandError("Selected meter is not an active owned prototype meter.")
            else:
                # Do not silently choose the first of multiple meters.
                meters = [m for m in Meter.objects.filter(user=owner, sandbox_inventory=True)
                          if sandbox_meter_authorized(m, owner)]
                meter = meters[0] if len(meters) == 1 else None
            if meter:
                row = complete_demo_assessment(owner, meter)
            self.stdout.write(f"owner_id={owner.pk} status={row.status}; core records unchanged")
