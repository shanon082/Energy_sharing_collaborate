from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from loan.models import CreditScoreFactors

User = get_user_model()

@receiver(post_save, sender=User)
def create_credit_factors(sender, instance, created, **kwargs):
    """Initialize automatic demo assessment or preserve existing core factors"""
    if created:
        from django.conf import settings
        from backend.demo_config import provider_mode
        from loan.prototype_lending import automatic_assessment_enabled
        if automatic_assessment_enabled() and instance.user_role == User.CLIENT and not instance.is_staff and not instance.is_superuser:
            from loan.demo_assessment import initialize_demo_assessment
            initialize_demo_assessment(instance)
        else:
            CreditScoreFactors.objects.get_or_create(user=instance)

        