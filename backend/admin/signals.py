from django.db.models.signals import post_save
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import AdminSession

User = get_user_model()

@receiver(user_logged_in)
def create_admin_session(sender, request, user, **kwargs):
    """Create admin session record when admin logs in"""
    if user.user_role == User.ADMIN:
        # Create session record
        session = AdminSession.objects.create(
            user=user,
            session_key=request.session.session_key,
            ip_address=request.META.get('REMOTE_ADDR', ''),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            expires_at=request.session.get_expiry_date()
        )
        
        # Log activity (this would be in your activity log system)
        print(f"Admin {user.email} logged in from {session.ip_address}")


@receiver(user_logged_out)
def update_admin_session(sender, request, user, **kwargs):
    """Update admin session record when admin logs out"""
    if user and user.user_role == User.ADMIN:
        try:
            session = AdminSession.objects.get(
                session_key=request.session.session_key,
                user=user
            )
            session.is_active = False
            session.logout_time = timezone.now()
            session.save()
        except AdminSession.DoesNotExist:
            pass