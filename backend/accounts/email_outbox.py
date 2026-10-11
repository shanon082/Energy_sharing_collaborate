"""Account mail only. Durable queue; SMTP acceptance is not inbox delivery."""

import hashlib
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import AccountEmailDelivery, SettingsConfirmationEmailCode, User
from accounts.account_actions import account_email_link
from utils.email import send_email
from utils.hosting_tasks import BackgroundTaskUnavailable


def account_state(user):
    # No password hash, email address, token or code is copied into the queue.
    return hashlib.sha256(f"{user.password}:{user.email}:{user.is_active}".encode()).hexdigest()


def enqueue_account_email(user, kind, *, code_id=None):
    return AccountEmailDelivery.objects.create(
        user=user, kind=kind, account_state=account_state(user), code_id=code_id,
    )


def enqueue_email_task(task, *args, **kwargs):
    """Exact allowlist; arbitrary Celery tasks cannot be run through this adapter."""
    name = getattr(task, "name", "")
    if kwargs or name not in {"accounts.tasks.handle_send_email_verification", "accounts.tasks.handle_send_email_code"}:
        raise BackgroundTaskUnavailable()
    user = User.objects.get(pk=args[0])
    if name.endswith("handle_send_email_verification") and len(args) == 1:
        return enqueue_account_email(user, AccountEmailDelivery.VERIFICATION)
    if name.endswith("handle_send_email_code") and len(args) == 2:
        code = SettingsConfirmationEmailCode.objects.get(
            user=user, code=args[1], status=SettingsConfirmationEmailCode.ACTIVE,
        )
        return enqueue_account_email(user, AccountEmailDelivery.SETTINGS_CODE, code_id=code.pk)
    raise BackgroundTaskUnavailable()


def deliver_account_email(job):
    user = job.user
    if user is None or not user.is_active or account_state(user) != job.account_state:
        return AccountEmailDelivery.SKIPPED
    if job.created_at < timezone.now() - timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT):
        return AccountEmailDelivery.SKIPPED
    if job.kind == AccountEmailDelivery.VERIFICATION:
        if user.profile.email_verified:
            return AccountEmailDelivery.SKIPPED
        link = account_email_link(user)
        subject, body = "Verify your gPawa account", f"Verify your account: {link}"
    elif job.kind == AccountEmailDelivery.PASSWORD_RESET:
        link = account_email_link(user, reset=True)
        subject, body = "Reset your gPawa password", f"Reset your password: {link}\nIgnore this email if you did not request it."
    elif job.kind == AccountEmailDelivery.SETTINGS_CODE:
        code = SettingsConfirmationEmailCode.objects.filter(
            pk=job.code_id, user=user, status=SettingsConfirmationEmailCode.ACTIVE,
        ).first()
        if code is None or code.create_date < timezone.now() - timedelta(minutes=10):
            return AccountEmailDelivery.SKIPPED
        subject, body = "gPawa security code", f"Security code: {code.code}"
    else:
        return AccountEmailDelivery.SKIPPED
    sent, _ = send_email(settings.DEFAULT_EMAIL_SENDER, [user.email], subject, body, [settings.DEFAULT_EMAIL_SENDER])
    # SMTP can accept the message then disconnect before responding. Never retry
    # automatically when an attempted send did not return confirmed acceptance.
    return AccountEmailDelivery.SENT if sent else AccountEmailDelivery.OUTCOME_UNKNOWN


def drain_account_emails(limit):
    results = []
    for _ in range(limit):
        with transaction.atomic():
            job = AccountEmailDelivery.objects.select_for_update(skip_locked=True).filter(
                status=AccountEmailDelivery.QUEUED,
            ).order_by("pk").first()
            if job is None:
                break
            job.status = AccountEmailDelivery.SENDING
            job.attempted_at = timezone.now()
            job.save(update_fields=["status", "attempted_at"])
        # No DB lock/transaction held during SMTP. A crash leaves SENDING for
        # operator review; another command will not replay it.
        try:
            status = deliver_account_email(job)
        except Exception:
            status = AccountEmailDelivery.OUTCOME_UNKNOWN
        AccountEmailDelivery.objects.filter(pk=job.pk, status=AccountEmailDelivery.SENDING).update(
            status=status, finished_at=timezone.now(),
        )
        results.append((job.pk, status))
    return results
