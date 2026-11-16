from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from accounts.models import User
from meter.models import PrototypeDevice
from meter.prototype_device import require_lab


class Command(BaseCommand):
    help = 'Revoke AC_LAB credentials without releasing reservations or modifying receipts.'
    def add_arguments(self, parser):
        parser.add_argument('device_id')
        parser.add_argument('--operator-id', required=True, type=int)
    def handle(self, *args, **options):
        require_lab()
        operator = User.objects.filter(pk=options['operator_id'], is_active=True, is_staff=True,
            user_role__in=[User.ADMIN, User.OPERATOR], profile__email_verified=True).first()
        if not operator:
            raise CommandError('Verified staff operator required.')
        with transaction.atomic():
            device = PrototypeDevice.objects.select_for_update().get(pk=options['device_id'])
            device.active = False; device.revoked_at = timezone.now(); device.revoked_by = operator
            device.save(update_fields=['active', 'revoked_at', 'revoked_by'])
        self.stdout.write(f'Revoked {device.pk}; reservations and receipts retained; operator_id={operator.pk}.')
