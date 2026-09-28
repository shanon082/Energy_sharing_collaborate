from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from loan.models import CreditScoreFactors

User = get_user_model()

@receiver(post_save, sender=User)
def create_credit_factors(sender, instance, created, **kwargs):
    """Create CreditScoreFactors for every new user"""
    if created:
        CreditScoreFactors.objects.get_or_create(user=instance)

        