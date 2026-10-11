import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.db import transaction
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
        user_id = instance.user_id
        if getattr(settings, "ACCOUNT_EMAIL_OUTBOX_ENABLED", False):
            # Insert with the account transaction: rollback loses both, never just
            # the email. Rendering does not claim SMTP acceptance.
            from accounts.email_outbox import enqueue_account_email
            from accounts.models import AccountEmailDelivery
            enqueue_account_email(instance.user, AccountEmailDelivery.VERIFICATION)
        else:
            transaction.on_commit(lambda: dispatch_task(handle_send_email_verification, user_id))