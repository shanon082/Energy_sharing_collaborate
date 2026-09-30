from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMessage
from backend import celery_app as app
from accounts.models import User
from transactions.statements import build_statement_pdf_bytes
from transactions.unified_history import filter_history, collect_unified_history, summarize_history
import logging
from datetime import timedelta
from django.utils import timezone
from transactions.models import PaymentIntent
from transactions.payment_settlement import PaymentSettlementError, reconcile_payment

logger = logging.getLogger(__name__)


@app.task()
def reconcile_pending_payments():
    """Poll trusted provider status independently of any browser session."""
    cutoff = timezone.now() - timedelta(minutes=1)
    ids = list(PaymentIntent.objects.filter(
        status=PaymentIntent.PENDING,
        provider="MTN_PRODUCTION",
        initiated_at__lte=cutoff,
    ).order_by("initiated_at").values_list("pk", flat=True)[:100])
    for intent_id in ids:
        try:
            reconcile_payment(intent_id)
        except PaymentSettlementError as exc:
            logger.warning("Payment intent %s requires review: %s", intent_id, exc)
        except Exception:
            logger.exception("Payment intent %s reconciliation failed", intent_id)
    return len(ids)


@app.task()
def handle_send_transaction_statement_email(user_id, start_date, end_date):
    user = User.objects.filter(pk=user_id).first()
    if not user or not user.email:
        return False

    entries = collect_unified_history(user)
    entries = filter_history(entries, start_date=start_date, end_date=end_date)
    summary = summarize_history(entries)
    pdf_bytes = build_statement_pdf_bytes(
        user_email=user.email,
        start_date=start_date,
        end_date=end_date,
        summary=summary,
        entries=entries,
    )

    subject = f"gPawa transaction statement ({start_date} to {end_date})"
    body = (
        f"Hi {user.first_name or user.email},<br/><br/>"
        f"Attached is your transaction statement for <b>{start_date}</b> to <b>{end_date}</b>.<br/>"
        "You can also view details in Transaction History on the app.<br/><br/>"
        "Regards,<br/>gPawa"
    )
    msg = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_EMAIL_SENDER,
        to=[user.email],
        reply_to=[settings.DEFAULT_EMAIL_SENDER],
    )
    msg.content_subtype = "html"
    msg.attach(
        f"gpawa-statement-{start_date}-to-{end_date}.pdf",
        pdf_bytes,
        "application/pdf",
    )
    msg.send()
    return True
