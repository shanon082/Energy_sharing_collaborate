from celery.utils.log import get_task_logger
from django.conf import settings
from celery import shared_task
from django.utils.encoding import force_str as force_text
from accounts.constants import ACCOUNT_VERIFICATION_SUBJECT, SECURITY_CODE
from accounts.utils import (
    b64encode_user,
    get_should_resend,
)
from accounts.models import User
from backend import celery_app as app
from utils.auth import token_generator
from utils.email import send_email
from utils.general import get_base_url
import random
import string



logger = get_task_logger(__name__)


@app.task()
def handle_send_email_verification(user_id):
    """
    Task that sends an email verification notification to a user
    """
    logger.info(f"[EMAIL VERIFICATION] Starting email verification for user {user_id}")
    
    try:
        user = User.objects.filter(pk=user_id).first()
        if not user:
            logger.error(f"[EMAIL VERIFICATION] User with ID {user_id} not found")
            return False
            
        logger.info(f"[EMAIL VERIFICATION] Found user: {user.email}")
        
        token = token_generator.make_token(user)
        user_hash = b64encode_user(force_text(user_id))
        
        # Use query parameters instead of path parameters to avoid encoding issues
        frontend_url = settings.FRONTEND_URL.rstrip('/')
        url = f"{frontend_url}/auth/verify-email?uid={user_hash}&token={token}"
        
        logger.info(f"[EMAIL VERIFICATION] Generated verification URL: {url}")
        
        message = (
            "You're almost there. Please click the link below to verify "
            f"your account\n\n{url}"
        )

        logger.info(
            f"[EMAIL VERIFICATION] About to send email to {user.email}"
        )
        
        sent, message = send_email(
            sender=settings.DEFAULT_EMAIL_SENDER,
            recipients=[user.email],
            subject=ACCOUNT_VERIFICATION_SUBJECT,
            message=message,
            reply_to=[settings.DEFAULT_EMAIL_SENDER],
        )
        
        if sent:
            logger.info(
                f"[EMAIL VERIFICATION] Email sent successfully to {user.email}"
            )
            return True
        else:
            logger.error(
                f"[EMAIL VERIFICATION] Failed to send email to {user.email}: {message}"
            )
            return False
            
    except Exception as e:
        logger.exception(f"[EMAIL VERIFICATION] Error in handle_send_email_verification: {str(e)}")
        return False


@app.task()
def handle_send_email_code(user_id, code):
    """
    Task that sends an email verification for settings change
    """
    logger.info("about to send settings change email")
    user = User.objects.filter(pk=user_id).first()

    message = (
        f"Security code: {code}"
    )

    logger.info(
        "[ACCOUNTS] About to send security code email "
        f"email to user {user_id}"
    )
    sent, message = send_email(
        sender=settings.DEFAULT_EMAIL_SENDER,
        recipients=[user.email],
        subject=SECURITY_CODE,
        message=message,
        reply_to=[settings.DEFAULT_EMAIL_SENDER],
    )
    if sent:
        logger.info(
            f"[ACCOUNTS] Security code. Sent: {sent}, message: {message},"
            f" user: {user_id}"
        )
    else:
        logger.info(
            f"[ACCOUNTS] Security code.  Not sent. message: {message}"
        )


# sample tasks
@app.task(name="add_task")
def add_task():
    logger.info("begin add task")
    logger.info("name--:")
    logger.info("done add task")


@app.task(bind=True)
def sum(self, x, y):
    logger.info("adding")
    sum = x + y
    logger.info(f"sum: {sum}")
    return sum


# Using a custom retry delay
@app.task(bind=True)
def retry(self):
    try:
        logger.info("executing")
        return 1 / 0
    except Exception as exc:
        logger.exception(f"error: {str(exc)}")
        raise self.retry(exc=exc, countdown=5, max_retries=3)


@app.task()
def handle_send_share_verification(user_id, code, transaction_details):
    """
    Task that sends a share verification email with OTP
    """
    logger.info(f"[SHARE VERIFICATION] Sending share verification for user {user_id}")
    
    try:
        user = User.objects.filter(pk=user_id).first()
        if not user:
            logger.error(f"[SHARE VERIFICATION] User with ID {user_id} not found")
            return False
            
        logger.info(f"[SHARE VERIFICATION] Found user: {user.email}")
        
        subject = "Verify Your Energy Units Sharing"
        transaction_details_html = str(transaction_details).replace("\n", "<br/>")

        # Simple, clear HTML layout to highlight the OTP
        message = f"""
        <div style="font-family: Arial, sans-serif; max-width: 520px; margin: 0 auto; color: #1a1a1a;">
            <div style="border: 1px solid #e6e6e6; border-radius: 10px; padding: 24px;">
                <h2 style="margin: 0 0 12px 0; color: #0f172a;">Share Verification</h2>
                <p style="margin: 0 0 16px 0;">Hi {user.first_name or user.email},</p>
                <p style="margin: 0 0 12px 0;">You're about to share energy units. Use the code below to confirm:</p>

                <div style="background:#0f172a; color:#ffffff; text-align:center; padding:14px 18px; border-radius: 8px; letter-spacing: 6px; font-size: 28px; font-weight: 700; margin: 12px 0;">
                    {code}
                </div>

                <p style="margin: 0 0 10px 0; font-weight: 600;">Transaction Details</p>
                <div style="background:#f8fafc; padding:12px 14px; border-radius:8px; font-size:14px; line-height:1.5; border:1px solid #e2e8f0;">
                    {transaction_details_html}
                </div>

                <p style="margin: 14px 0 6px 0;">This code expires in <strong>10 minutes</strong>.</p>
                <p style="margin: 0 0 14px 0; color:#dc2626;">If you didn't initiate this transaction, contact support immediately.</p>

                <p style="margin: 0;">Best regards,<br/>gPawa Team</p>
            </div>
            <p style="font-size:12px; color:#6b7280; margin-top:12px;">Do not share this code with anyone.</p>
        </div>
        """
        logger.info(f"[SHARE VERIFICATION] About to send email to {user.email}")
        
        sent, email_message = send_email(
            sender=settings.DEFAULT_EMAIL_SENDER,
            recipients=[user.email],
            subject=subject,
            message=message,
            reply_to=[settings.DEFAULT_EMAIL_SENDER],
        )
        
        if sent:
            logger.info(f"[SHARE VERIFICATION] Email sent successfully to {user.email}")
            return True
        else:
            logger.error(f"[SHARE VERIFICATION] Failed to send email to {user.email}: {email_message}")
            return False
            
    except Exception as e:
        logger.exception(f"[SHARE VERIFICATION] Error in handle_send_share_verification: {str(e)}")
        return False

@app.task()
def handle_send_transfer_verification(user_id, code, transaction_details):
    """
    Task that sends a transfer verification email with OTP
    """
    logger.info(f"[TRANSFER VERIFICATION] Sending transfer verification for user {user_id}")
    
    try:
        user = User.objects.filter(pk=user_id).first()
        if not user:
            logger.error(f"[TRANSFER VERIFICATION] User with ID {user_id} not found")
            return False
            
        logger.info(f"[TRANSFER VERIFICATION] Found user: {user.email}")
        
        subject = "Verify Your Meter Transfer"
        
        message = f"""
        Hi {user.first_name},
        
        You are about to transfer all units to a new meter. Please use the verification code below:
        
        Verification Code: {code}
        
        Transaction Details:
        {transaction_details}
        
        WARNING: This will deactivate your old meter!
        
        This code will expire in 10 minutes.
        
        If you didn't initiate this transfer, please contact support immediately.
        
        Best regards,
        gPawa Team
        """
        
        logger.info(f"[TRANSFER VERIFICATION] About to send email to {user.email}")
        
        sent, email_message = send_email(
            sender=settings.DEFAULT_EMAIL_SENDER,
            recipients=[user.email],
            subject=subject,
            message=message,
            reply_to=[settings.DEFAULT_EMAIL_SENDER],
        )
        
        if sent:
            logger.info(f"[TRANSFER VERIFICATION] Email sent successfully to {user.email}")
            return True
        else:
            logger.error(f"[TRANSFER VERIFICATION] Failed to send email to {user.email}: {email_message}")
            return False
            
    except Exception as e:
        logger.exception(f"[TRANSFER VERIFICATION] Error in handle_send_transfer_verification: {str(e)}")
        return False

@app.task()
def handle_send_wallet_update(user_id, transaction_details):
    """
    Task that sends wallet update notification
    """
    logger.info(f"[WALLET UPDATE] Sending wallet update for user {user_id}")
    
    try:
        user = User.objects.filter(pk=user_id).first()
        if not user:
            logger.error(f"[WALLET UPDATE] User with ID {user_id} not found")
            return False

        details_str = str(transaction_details)
        if "You received a unit share" in details_str or "Units applied:" in details_str:
            subject = "Units received on your meter — gPAWA"
            heading = "Units Received"
            intro = "Another gPAWA customer shared electricity units to your meter. Details:"
        elif "Share completed successfully" in details_str:
            subject = "Share confirmation — gPAWA"
            heading = "Share Completed"
            intro = "Your unit share was completed successfully. Details:"
        else:
            subject = "Wallet Transaction Update"
            heading = "Wallet Update"
            intro = "Your wallet was updated. Here are the details:"

        transaction_details_html = details_str.replace("\n", "<br/>")
        
        message = f"""
        <div style="font-family: Arial, sans-serif; max-width: 520px; margin: 0 auto; color: #1a1a1a;">
            <div style="border: 1px solid #e6e6e6; border-radius: 10px; padding: 24px;">
                <h2 style="margin: 0 0 12px 0; color: #0f172a;">{heading}</h2>
                <p style="margin: 0 0 12px 0;">Hi {user.first_name or user.email},</p>
                <p style="margin: 0 0 10px 0;">{intro}</p>

                <div style="background:#f8fafc; padding:12px 14px; border-radius:8px; font-size:14px; line-height:1.5; border:1px solid #e2e8f0;">
                    {transaction_details_html}
                </div>

                <p style="margin: 14px 0 6px 0; color:#dc2626;">If you didn't authorize this transaction, contact support immediately.</p>
                <p style="margin: 0;">Best regards,<br/>gPawa Team</p>
            </div>
            <p style="font-size:12px; color:#6b7280; margin-top:12px;">Do not share sensitive information from this email.</p>
        </div>
        """
        
        sent, email_message = send_email(
            sender=settings.DEFAULT_EMAIL_SENDER,
            recipients=[user.email],
            subject=subject,
            message=message,
            reply_to=[settings.DEFAULT_EMAIL_SENDER],
        )
        
        if sent:
            logger.info(f"[WALLET UPDATE] Email sent successfully to {user.email}")
            return True
        else:
            logger.error(f"[WALLET UPDATE] Failed to send email to {user.email}: {email_message}")
        return False
            
    except Exception as e:
        logger.exception(f"[WALLET UPDATE] Error in handle_send_wallet_update: {str(e)}")
        return False


@app.task()
def handle_send_share_token(user_id, token, units, meter_number, sender_meter=None, sender_email=None, sender_name=None):
    """
    Task that sends a share token to the receiver's email
    """
    logger.info(f"[SHARE TOKEN] Sending share token to user {user_id}")
    
    try:
        user = User.objects.filter(pk=user_id).first()
        if not user:
            logger.error(f"[SHARE TOKEN] User with ID {user_id} not found")
            return False
            
        subject = "Your Shared Energy Units Token"
        
        sender_lines = []
        if sender_name:
            sender_lines.append(f"<strong>Name:</strong> {sender_name}")
        if sender_email:
            sender_lines.append(f"<strong>Email:</strong> {sender_email}")
        if sender_meter:
            sender_lines.append(f"<strong>Meter:</strong> {sender_meter}")
        sender_block = ""
        if sender_lines:
            sender_block = (
                "<p style=\"margin: 0 0 10px 0; color:#475569;\"><strong>Shared by</strong><br/>"
                + "<br/>".join(sender_lines)
                + "</p>"
            )

        message = f"""
        <div style="font-family: Arial, sans-serif; max-width: 520px; margin: 0 auto; color: #1a1a1a;">
            <div style="border: 1px solid #e6e6e6; border-radius: 10px; padding: 24px;">
                <h2 style="margin: 0 0 12px 0; color: #0f172a;">Shared Units Token</h2>
                <p style="margin: 0 0 12px 0;">Hi {user.first_name or user.email},</p>
                <p style="margin: 0 0 10px 0;">You have received <strong>{units}</strong> energy units for meter <strong>{meter_number}</strong>.</p>
                {sender_block}

                <div style="background:#0f172a; color:#ffffff; text-align:center; padding:14px 18px; border-radius: 8px; letter-spacing: 4px; font-size: 24px; font-weight: 700; margin: 12px 0;">
                    {token}
                </div>

                <p style="margin: 0 0 12px 0;">Use this token to load the units onto your meter.</p>
                <p style="margin: 0 0 14px 0; color:#dc2626;">If you did not expect this token, contact support immediately.</p>

                <p style="margin: 0;">Best regards,<br/>gPawa Team</p>
            </div>
            <p style="font-size:12px; color:#6b7280; margin-top:12px;">Do not share this token with anyone else.</p>
        </div>
        """
        
        sent, email_message = send_email(
            sender=settings.DEFAULT_EMAIL_SENDER,
            recipients=[user.email],
            subject=subject,
            message=message,
            reply_to=[settings.DEFAULT_EMAIL_SENDER],
        )
        
        if sent:
            logger.info(f"[SHARE TOKEN] Email sent successfully to {user.email}")
            return True
        else:
            logger.error(f"[SHARE TOKEN] Failed to send email to {user.email}: {email_message}")
            return False
            
    except Exception as e:
        logger.exception(f"[SHARE TOKEN] Error in handle_send_share_token: {str(e)}")
        return False


@app.task()
def handle_send_low_units_alert_email(user_id, meter_no, units_kwh, notification_id):
    """Email alert when ThingsBoard reports low remaining units on an AMI meter."""
    try:
        user = User.objects.filter(pk=user_id).first()
        if not user or not user.email:
            logger.warning("[LOW UNITS] No user/email for notification %s", notification_id)
            return False

        frontend_url = settings.FRONTEND_URL.rstrip("/")
        meter_path = f"{frontend_url}/dashboard/tokens"
        subject = f"gPawa: Low units on meter {meter_no}"
        message = (
            f"<p>Hello {user.first_name or 'there'},</p>"
            f"<p>Your AMI meter <strong>{meter_no}</strong> is running low: "
            f"<strong>{units_kwh:.2f} kWh</strong> remaining.</p>"
            f"<p><a href=\"{meter_path}\">Open your meter dashboard</a> to check units or top up.</p>"
            f"<p>— gPawa Energy Wallet</p>"
        )

        sent, email_message = send_email(
            sender=settings.DEFAULT_EMAIL_SENDER,
            recipients=[user.email],
            subject=subject,
            message=message,
            reply_to=[settings.DEFAULT_EMAIL_SENDER],
        )
        if not sent:
            logger.error("[LOW UNITS] Failed to email user %s: %s", user.email, email_message)
        return sent
    except Exception as exc:
        logger.exception("[LOW UNITS] Email task error: %s", exc)
        return False


@app.task()
def handle_send_payment_receipt_email(
    user_id,
    amount_ugx,
    units_purchased,
    transaction_id,
    transaction_reference="",
):
    """Email receipt after a successful buy-units payment."""
    try:
        user = User.objects.filter(pk=user_id).first()
        if not user or not user.email:
            logger.warning("[PAYMENT RECEIPT] No user/email for transaction %s", transaction_id)
            return False

        frontend_url = settings.FRONTEND_URL.rstrip("/")
        subject = f"gPawa: Payment receipt #{transaction_id}"
        message = (
            f"<p>Hello {user.first_name or 'there'},</p>"
            "<p>Your payment was completed successfully.</p>"
            "<ul>"
            f"<li><strong>Amount paid:</strong> UGX {float(amount_ugx):,.2f}</li>"
            f"<li><strong>Units purchased:</strong> {float(units_purchased):.2f} kWh</li>"
            f"<li><strong>Transaction ID:</strong> {transaction_id}</li>"
            f"<li><strong>Reference:</strong> {transaction_reference or 'N/A'}</li>"
            "</ul>"
            f"<p><a href=\"{frontend_url}/dashboard/transactions\">View transaction history</a></p>"
            "<p>— gPawa Energy Wallet</p>"
        )

        sent, email_message = send_email(
            sender=settings.DEFAULT_EMAIL_SENDER,
            recipients=[user.email],
            subject=subject,
            message=message,
            reply_to=[settings.DEFAULT_EMAIL_SENDER],
        )
        if not sent:
            logger.error("[PAYMENT RECEIPT] Failed to email user %s: %s", user.email, email_message)
        return sent
    except Exception as exc:
        logger.exception("[PAYMENT RECEIPT] Email task error: %s", exc)
        return False


@app.task()
def handle_send_loan_application_email(user_id, loan_id, status_value, amount_requested, amount_approved=0):
    """Email user after loan application decision (approved/rejected)."""
    try:
        user = User.objects.filter(pk=user_id).first()
        if not user or not user.email:
            logger.warning("[LOAN APPLICATION] No user/email for loan %s", loan_id)
            return False

        approved = str(status_value).upper() == "APPROVED"
        subject = "gPawa: Loan application update"
        if approved:
            body = (
                f"<p>Hello {user.first_name or 'there'},</p>"
                "<p>Your electricity loan application has been <strong>approved</strong>.</p>"
                "<ul>"
                f"<li><strong>Loan ID:</strong> {loan_id}</li>"
                f"<li><strong>Amount requested:</strong> UGX {float(amount_requested):,.2f}</li>"
                f"<li><strong>Amount approved:</strong> UGX {float(amount_approved):,.2f}</li>"
                "</ul>"
                "<p>Your electricity units are being credited to your wallet automatically — "
                "you'll receive a follow-up email once disbursement completes.</p>"
                "<p>— gPawa Energy Wallet</p>"
            )
        else:
            body = (
                f"<p>Hello {user.first_name or 'there'},</p>"
                "<p>Your electricity loan application has been reviewed and was "
                "<strong>not approved</strong> at this time.</p>"
                "<ul>"
                f"<li><strong>Loan ID:</strong> {loan_id}</li>"
                f"<li><strong>Amount requested:</strong> UGX {float(amount_requested):,.2f}</li>"
                "</ul>"
                "<p>You can continue buying units directly from your dashboard.</p>"
                "<p>— gPawa Energy Wallet</p>"
            )

        sent, msg = send_email(
            sender=settings.DEFAULT_EMAIL_SENDER,
            recipients=[user.email],
            subject=subject,
            message=body,
            reply_to=[settings.DEFAULT_EMAIL_SENDER],
        )
        if not sent:
            logger.error("[LOAN APPLICATION] Failed to email user %s: %s", user.email, msg)
        return sent
    except Exception as exc:
        logger.exception("[LOAN APPLICATION] Email task error: %s", exc)
        return False


@app.task()
def handle_send_loan_disbursed_email(user_id, loan_id, amount_approved, units_disbursed):
    """Email user after loan disbursement."""
    try:
        user = User.objects.filter(pk=user_id).first()
        if not user or not user.email:
            logger.warning("[LOAN DISBURSEMENT] No user/email for loan %s", loan_id)
            return False

        subject = "gPawa: Loan disbursed to your wallet"
        body = (
            f"<p>Hello {user.first_name or 'there'},</p>"
            "<p>Your approved electricity loan has been <strong>disbursed</strong>.</p>"
            "<ul>"
            f"<li><strong>Loan ID:</strong> {loan_id}</li>"
            f"<li><strong>Amount disbursed:</strong> UGX {float(amount_approved):,.2f}</li>"
            f"<li><strong>Units credited:</strong> {float(units_disbursed):.2f} kWh</li>"
            "</ul>"
            "<p>Check your dashboard wallet and meter pages for details.</p>"
            "<p>— gPawa Energy Wallet</p>"
        )

        sent, msg = send_email(
            sender=settings.DEFAULT_EMAIL_SENDER,
            recipients=[user.email],
            subject=subject,
            message=body,
            reply_to=[settings.DEFAULT_EMAIL_SENDER],
        )
        if not sent:
            logger.error("[LOAN DISBURSEMENT] Failed to email user %s: %s", user.email, msg)
        return sent
    except Exception as exc:
        logger.exception("[LOAN DISBURSEMENT] Email task error: %s", exc)
        return False


@app.task()
def handle_send_loan_repayment_email(user_id, loan_id, amount_paid, outstanding_balance, is_fully_repaid):
    """Email user after a loan repayment (partial or full)."""
    try:
        user = User.objects.filter(pk=user_id).first()
        if not user or not user.email:
            logger.warning("[LOAN REPAYMENT] No user/email for loan %s", loan_id)
            return False

        if is_fully_repaid:
            subject = "gPawa: Loan fully repaid"
            body = (
                f"<p>Hello {user.first_name or 'there'},</p>"
                "<p>Your electricity loan has been <strong>fully repaid</strong>. Thank you!</p>"
                "<ul>"
                f"<li><strong>Loan ID:</strong> {loan_id}</li>"
                f"<li><strong>Final payment:</strong> UGX {float(amount_paid):,.2f}</li>"
                f"<li><strong>Outstanding balance:</strong> UGX 0.00</li>"
                "</ul>"
                "<p>Your loan account is now clear. You can apply for a new loan anytime.</p>"
                "<p>— gPawa Energy Wallet</p>"
            )
        else:
            subject = "gPawa: Loan repayment received"
            body = (
                f"<p>Hello {user.first_name or 'there'},</p>"
                "<p>We have received your loan repayment.</p>"
                "<ul>"
                f"<li><strong>Loan ID:</strong> {loan_id}</li>"
                f"<li><strong>Amount paid:</strong> UGX {float(amount_paid):,.2f}</li>"
                f"<li><strong>Remaining balance:</strong> UGX {float(outstanding_balance):,.2f}</li>"
                "</ul>"
                "<p>Keep making payments to clear your loan and improve your credit score.</p>"
                "<p>— gPawa Energy Wallet</p>"
            )

        sent, msg = send_email(
            sender=settings.DEFAULT_EMAIL_SENDER,
            recipients=[user.email],
            subject=subject,
            message=body,
            reply_to=[settings.DEFAULT_EMAIL_SENDER],
        )
        if not sent:
            logger.error("[LOAN REPAYMENT] Failed to email user %s: %s", user.email, msg)
        return sent
    except Exception as exc:
        logger.exception("[LOAN REPAYMENT] Email task error: %s", exc)
        return False


@app.task()
def handle_send_third_party_loan_payment_to_owner(owner_id, loan_id, amount_paid, payer_display_name, is_fully_repaid):
    """Email the loan owner when someone else pays their loan."""
    try:
        owner = User.objects.filter(pk=owner_id).first()
        if not owner or not owner.email:
            return False
        verb = "fully repaid" if is_fully_repaid else "partially paid"
        subject = f"gPawa: Your loan has been {verb}"
        body = (
            f"<p>Hello {owner.first_name or 'there'},</p>"
            f"<p>Your electricity loan <strong>{loan_id}</strong> has been <strong>{verb}</strong> by "
            f"<strong>{payer_display_name}</strong>.</p>"
            f"<ul>"
            f"<li><strong>Amount paid:</strong> UGX {float(amount_paid):,.2f}</li>"
            f"<li><strong>Loan status:</strong> {'Fully cleared' if is_fully_repaid else 'Partially repaid'}</li>"
            f"</ul>"
            f"<p>Check your dashboard for the updated balance.</p>"
            f"<p>— gPawa Energy Wallet</p>"
        )
        sent, msg = send_email(
            sender=settings.DEFAULT_EMAIL_SENDER,
            recipients=[owner.email],
            subject=subject,
            message=body,
            reply_to=[settings.DEFAULT_EMAIL_SENDER],
        )
        if not sent:
            logger.error("[THIRD PARTY PAYMENT OWNER] Failed to email %s: %s", owner.email, msg)
        return sent
    except Exception as exc:
        logger.exception("[THIRD PARTY PAYMENT OWNER] Email task error: %s", exc)
        return False


@app.task()
def handle_send_third_party_loan_payment_to_payer(payer_id, owner_name, loan_id, amount_paid, is_fully_repaid):
    """Email the payer confirming they cleared someone else's loan."""
    try:
        payer = User.objects.filter(pk=payer_id).first()
        if not payer or not payer.email:
            return False
        verb = "fully repaid" if is_fully_repaid else "partially paid"
        subject = f"gPawa: You {verb} a loan on behalf of {owner_name}"
        body = (
            f"<p>Hello {payer.first_name or 'there'},</p>"
            f"<p>You have successfully {verb} the electricity loan belonging to "
            f"<strong>{owner_name}</strong>.</p>"
            f"<ul>"
            f"<li><strong>Loan ID:</strong> {loan_id}</li>"
            f"<li><strong>Amount paid:</strong> UGX {float(amount_paid):,.2f}</li>"
            f"<li><strong>Status:</strong> {'Loan fully cleared' if is_fully_repaid else 'Partial payment applied'}</li>"
            f"</ul>"
            f"<p>Thank you for your generosity.</p>"
            f"<p>— gPawa Energy Wallet</p>"
        )
        sent, msg = send_email(
            sender=settings.DEFAULT_EMAIL_SENDER,
            recipients=[payer.email],
            subject=subject,
            message=body,
            reply_to=[settings.DEFAULT_EMAIL_SENDER],
        )
        if not sent:
            logger.error("[THIRD PARTY PAYMENT PAYER] Failed to email %s: %s", payer.email, msg)
        return sent
    except Exception as exc:
        logger.exception("[THIRD PARTY PAYMENT PAYER] Email task error: %s", exc)
        return False
