from django.db.models.signals import pre_save
from django.dispatch import receiver

from transactions.models import UnitTransaction
from accounts.models import generate_random_string


@receiver(pre_save, sender=UnitTransaction)
def generate_transaction_id(sender, instance, *args, **kwargs):
    if not instance.pk:
        instance.transaction_id = generate_random_string(16)
