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
        count = 0
        for owner in users.order_by("pk").iterator():
            meters = Meter.objects.filter(user=owner, sandbox_inventory=True).order_by("pk")
            if options["meter_id"]:
                meters = meters.filter(pk=options["meter_id"])
                if not meters.exists():
                    raise CommandError("Selected meter is not an active owned prototype meter.")
            for meter in meters:
                if count >= options["limit"]:
                    return
                if not sandbox_meter_authorized(meter, owner):
                    if options["meter_id"]:
                        raise CommandError("Selected meter is not an active owned prototype meter.")
                    continue
                row = DemoCreditAssessment.objects.filter(owner=owner, meter=meter, environment="UGX_DEMO", scope="METER").first()
                if row and row.status == "READY" and not options["user_id"] and not options["refresh_purchases"]:
                    continue
                count += 1
                state = row.status if row else "MISSING"
                self.stdout.write(f"{'APPLY' if options['apply'] else 'PREVIEW'} owner_id={owner.pk} meter_id={meter.pk} assessment={state}; legacy=preserved")
                if not options["apply"]:
                    continue
                if options["scenario"] and row is not None:
                    raise CommandError("An existing demo scenario is immutable; no assessment/history overwrite.")
                if not Profile.objects.filter(user=owner, email_verified=True).exists():
                    self.stdout.write(f"owner_id={owner.pk} meter_id={meter.pk} retained=PENDING waiting=email-verification")
                    continue
                if options["scenario"]:
                    initialize_demo_assessment(owner, meter=meter, scenario=options["scenario"])
                row = complete_demo_assessment(owner, meter)
                if options["refresh_purchases"] and row.status == "READY":
                    refresh_demo_purchase_contribution(owner, meter)
                self.stdout.write(f"owner_id={owner.pk} meter_id={meter.pk} status={row.status}; core records unchanged")
