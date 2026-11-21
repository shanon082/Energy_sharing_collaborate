"""No reconciliation, provider call, token generation or device operation."""
import json
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from accounts.models import User
from meter.device_audit import audit_credit


class Command(BaseCommand):
    help = 'Read-only sanitized purchase → token → device audit; no token/key/body output.'

    def add_arguments(self, parser):
        parser.add_argument('--operator-id', required=True, type=int)
        parser.add_argument('--owner-id', required=True, type=int)
        parser.add_argument('--meter-id', required=True, type=int)
        parser.add_argument('--purchase-reference')
        parser.add_argument('--limit', type=int, default=5)

    def handle(self, *args, **options):
        if not 1 <= options['limit'] <= 10:
            raise CommandError('Use limit1–10.')
        if not User.objects.filter(pk=options['operator_id'], is_active=True, is_staff=True,
                                   user_role__in=[User.ADMIN, User.OPERATOR], profile__email_verified=True).exists():
            raise CommandError('Verified active staff operator required.')
        with transaction.atomic():
            if connection.vendor == 'postgresql':
                with connection.cursor() as cursor:
                    cursor.execute('SET TRANSACTION READ ONLY')
            report = audit_credit(options['owner_id'], options['meter_id'], options['purchase_reference'], options['limit'])
        self.stdout.write(json.dumps(report, sort_keys=True))
