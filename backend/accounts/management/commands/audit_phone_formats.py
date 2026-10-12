"""Read-only format/collision audit. Prints IDs/counts, never phone values."""
from collections import defaultdict
from django.core.management.base import BaseCommand
from accounts.models import User
from accounts.phones import normalize_ugandan_phone


class Command(BaseCommand):
    help = "Dry-run phone-format audit; no records are changed."

    def handle(self, **options):
        groups = defaultdict(list)
        invalid, empty = [], 0
        # Raw values avoid PhoneNumberField's presentation normalizing the audit input.
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute('SELECT id, phone_number FROM accounts_user ORDER BY id')
            for pk, value in cursor:
                if not value:
                    empty += 1
                    continue
                try:
                    groups[normalize_ugandan_phone(value)].append(pk)
                except ValueError:
                    invalid.append(pk)
        collisions = [ids for ids in groups.values() if len(ids) > 1]
        self.stdout.write(f"DRY_RUN empty={empty} invalid={len(invalid)} collision_groups={len(collisions)}")
        for pk in invalid:
            self.stdout.write(f"INVALID user_id={pk}")
        for ids in collisions:
            self.stdout.write(f"COLLISION user_ids={','.join(map(str, ids))}")
