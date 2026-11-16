"""Private one-time commissioning, no device I/O and no token/backfill operations."""
import hashlib
import json
import os
from pathlib import Path
import secrets
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from accounts.models import User
from meter.models import BenchDevice, Meter, PrototypeDevice
from meter.prototype_device import require_lab, identity
from meter.validators import validate_meter_no


class Command(BaseCommand):
    help = 'Provision one AC_LAB binding with physical output DISABLED. Writes private configuration, never stdout secrets.'

    def add_arguments(self, parser):
        parser.add_argument('meter_id', type=int)
        parser.add_argument('--owner-id', type=int, required=True)
        parser.add_argument('--operator-id', type=int, required=True)
        parser.add_argument('--private-config', required=True)
        parser.add_argument('--confirm-output-disabled', action='store_true')

    def handle(self, *args, **options):
        require_lab()
        if not options['confirm_output_disabled']:
            raise CommandError('Confirm relay output is disabled in firmware and physically disconnected.')
        operator = User.objects.filter(pk=options['operator_id'], is_active=True, is_staff=True,
                                       user_role__in=[User.ADMIN, User.OPERATOR]).first()
        if not operator or not getattr(getattr(operator, 'profile', None), 'email_verified', False):
            raise CommandError('A verified active staff ADMIN/OPERATOR must authorize commissioning.')
        target = Path(options['private_config']).expanduser()
        backend = Path(__file__).resolve().parents[3]
        if not target.is_absolute() or target.resolve().is_relative_to(backend):
            raise CommandError('Use an absolute private output path outside the uploaded backend.')
        created = False
        try:
            # Exclusive creation refuses overwriting an existing credential file.
            with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as output:
                created = True
                with transaction.atomic():
                    meter = Meter.objects.select_for_update().filter(pk=options['meter_id'], user_id=options['owner_id'],
                        status='ACTIVE', sandbox_inventory=True, user__is_active=True, user__is_staff=False, user__is_superuser=False, user__profile__email_verified=True).first()
                    if (not meter or not validate_meter_no(meter.meter_no)[0] or meter.meter_no == "0" * 11 or meter.user.user_role != User.CLIENT
                            or PrototypeDevice.objects.filter(meter=meter).exists() or BenchDevice.objects.filter(meter=meter).exists()):
                        raise CommandError('Need an owned active 11-digit test meter without a previous device binding; reconcile existing bindings first.')
                    secret = secrets.token_urlsafe(48)
                    device = PrototypeDevice.objects.create(meter=meter, owner_id=meter.user_id, provisioned_by=operator,
                        credential_hash=make_password(secret), credential_fingerprint=hashlib.sha256(secret.encode()).hexdigest())
                    json.dump({**identity(device), 'device_secret': secret, 'output_enabled': False}, output)
                    output.flush(); os.fsync(output.fileno())
        except Exception:
            if created:
                target.unlink(missing_ok=True)
            raise
        self.stdout.write(f'AC_LAB provisioned device_id={device.pk}; output disabled; configuration written privately.')
