from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMessage
from backend import celery_app as app
from accounts.models import User
from transactions.statements import build_statement_pdf_bytes
from transactions.unified_history import filter_history, collect_unified_history, summarize_history


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
