from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal
from django.db import transaction
from .models import Meter
from wallet.models import Wallet, MeterBalance

@receiver(post_save, sender=Meter)
def sync_meter_to_balance(sender, instance, **kwargs):
    """
    Keep MeterBalance in sync with Meter.units without mutating the user's
    wallet balance. The wallet balance represents money and is managed by
    deposit, withdrawal, purchase, and repayment transactions.
    Overwriting it here with the sum of meter balances caused double
    deductions when units were shared to a meter.
    """
    if instance.pk:  # Skip on create if no units yet
        with transaction.atomic():
            user = instance.user
            Wallet.objects.select_for_update().get_or_create(user=user)

            # Update/create MeterBalance
            meter_balance, _ = MeterBalance.objects.get_or_create(
                user=user,
                meter_number=instance.meter_no,
                defaults={'balance': Decimal(str(instance.units)), 'is_active': True}
            )
            if meter_balance.balance != Decimal(str(instance.units)):
                meter_balance.balance = Decimal(str(instance.units))
                meter_balance.save()
