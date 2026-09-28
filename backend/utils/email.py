import logging
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from six import text_type
logger = logging.getLogger(__name__)
User = get_user_model()


def send_email(
    sender: str, recipients: list, subject: str, message: str, reply_to: list
) -> tuple:
    """
    :param sender: Email address of the sender
    :param recipients: List of recipient email addresses
    :param subject: Email subject
    :param message: Body of the email either as html or plain text
    :param reply_to: List of email to which a response can be sent


    :returns: Tuple containing success boolean and a message string
    :rtype: Tuple
    """
    try:
        msg = EmailMessage(
            subject,
            body=message,
            from_email=sender,
            to=recipients,
            reply_to=reply_to,
        )
        msg.content_subtype = "html"
        success = msg.send()
    except Exception as e:
        logger.exception(
            f"[EMAILS] SMTP error sending email with subject '{subject}' "
            f"to {recipients}: {str(e)}"
        )
        return (False, f"SMTP error: {str(e)}")

    if not success:
        users = User.objects.filter(email__in=recipients)
        failed_ids = [text_type(user.id) for user in users]
        failed_ids_str = ",".join(failed_ids)
        logger.info(
            f"[EMAILS] Error while sending email with subject {subject} to"
            f" users: {failed_ids_str}"
        )
        return (False, "Email not sent")

    return (True, "Email sent successfully!")
