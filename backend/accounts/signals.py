import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from accounts.models import Profile, UserAccountDetails
from accounts.tasks import handle_send_email_verification
from utils.general import dispatch_task

logger = logging.getLogger(__name__)



@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(
            user=instance,
            email_verified=instance.is_superuser  # auto-verify superusers only
        )



@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_account_details(sender, instance, created, **kwargs):
    if created:
        UserAccountDetails.objects.create(user=instance)



@receiver(post_save, sender=Profile)
def send_email_verification(sender, instance, created, **kwargs):
    if created and not instance.email_verified:
        dispatch_task(handle_send_email_verification, instance.user.pk)