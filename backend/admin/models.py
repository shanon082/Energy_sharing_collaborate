from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class AdminNotificationSettings(models.Model):
    """Notification settings for admin users"""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='notification_settings'
    )
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    loan_approvals = models.BooleanField(default=True)
    user_registrations = models.BooleanField(default=True)
    system_alerts = models.BooleanField(default=True)
    weekly_reports = models.BooleanField(default=False)
    report_schedule = models.CharField(
        max_length=20,
        choices=[
            ('weekly', 'Weekly'),
            ('daily', 'Daily'),
            ('monthly', 'Monthly'),
            ('never', 'Never')
        ],
        default='weekly'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Notification settings for {self.user.email}"

    class Meta:
        app_label = 'portal_admin'
        verbose_name = "Admin Notification Settings"
        verbose_name_plural = "Admin Notification Settings"


class AdminSession(models.Model):
    """Track admin sessions"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sessions'
    )
    session_key = models.CharField(max_length=40)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    is_active = models.BooleanField(default=True)
    login_time = models.DateTimeField(auto_now_add=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()

    class Meta:
        app_label = 'portal_admin'
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['expires_at']),
        ]
        ordering = ['-login_time']

    def __str__(self):
        return f"Session {self.session_key} for {self.user.email}"


# --------------------------------------------------------------------------- #
#  Full spec-compliant Audit Log — Section 9.1                                #
# --------------------------------------------------------------------------- #
class AuditLog(models.Model):
    """
    Append-only log of every state-changing action taken by any staff member.
    Fields match exactly the spec table in Section 9.1.
    """

    # Action type categories (Section 9.1)
    ACTION_USER_EDIT = "User Edit"
    ACTION_ACCOUNT_SUSPENSION = "Account Suspension"
    ACTION_ACCOUNT_REACTIVATION = "Account Reactivation"
    ACTION_CREDENTIAL_RESET = "Credential Reset"
    ACTION_KYC_VERIFY = "KYC Verify"
    ACTION_KYC_REJECT = "KYC Reject"
    ACTION_METER_REGISTER = "Meter Register"
    ACTION_METER_DEACTIVATE = "Meter Deactivate"
    ACTION_METER_DELETE = "Meter Delete"
    ACTION_METER_TRANSFER = "Meter Transfer"
    ACTION_REFUND = "Refund"
    ACTION_PENALTY_WAIVER = "Penalty Waiver"
    ACTION_CREDIT_LIMIT_OVERRIDE = "Credit Limit Override"
    ACTION_TRANSACTION_REVERSE = "Transaction Reverse"
    ACTION_FRAUD_FLAG = "Fraud Flag"
    ACTION_FRAUD_CLEAR = "Fraud Clear"
    ACTION_STAFF_CREATE = "Staff Create"
    ACTION_STAFF_DEACTIVATE = "Staff Deactivate"
    ACTION_SETTINGS_CHANGE = "Settings Change"
    ACTION_TOKEN_REDELIVERY = "Token Redelivery"
    ACTION_LOAN_APPROVE = "Loan Approve"
    ACTION_LOAN_REJECT = "Loan Reject"

    ACTION_TYPE_CHOICES = [
        (ACTION_USER_EDIT, "User Edit"),
        (ACTION_ACCOUNT_SUSPENSION, "Account Suspension"),
        (ACTION_ACCOUNT_REACTIVATION, "Account Reactivation"),
        (ACTION_CREDENTIAL_RESET, "Credential Reset"),
        (ACTION_KYC_VERIFY, "KYC Verify"),
        (ACTION_KYC_REJECT, "KYC Reject"),
        (ACTION_METER_REGISTER, "Meter Register"),
        (ACTION_METER_DEACTIVATE, "Meter Deactivate"),
        (ACTION_METER_DELETE, "Meter Delete"),
        (ACTION_METER_TRANSFER, "Meter Transfer"),
        (ACTION_REFUND, "Refund"),
        (ACTION_PENALTY_WAIVER, "Penalty Waiver"),
        (ACTION_CREDIT_LIMIT_OVERRIDE, "Credit Limit Override"),
        (ACTION_TRANSACTION_REVERSE, "Transaction Reverse"),
        (ACTION_FRAUD_FLAG, "Fraud Flag"),
        (ACTION_FRAUD_CLEAR, "Fraud Clear"),
        (ACTION_STAFF_CREATE, "Staff Create"),
        (ACTION_STAFF_DEACTIVATE, "Staff Deactivate"),
        (ACTION_SETTINGS_CHANGE, "Settings Change"),
        (ACTION_TOKEN_REDELIVERY, "Token Redelivery"),
        (ACTION_LOAN_APPROVE, "Loan Approve"),
        (ACTION_LOAN_REJECT, "Loan Reject"),
    ]

    # Target types
    TARGET_USER = "user"
    TARGET_METER = "meter"
    TARGET_TRANSACTION = "transaction"
    TARGET_LOAN = "loan"
    TARGET_STAFF = "staff"
    TARGET_SYSTEM = "system"

    TARGET_TYPE_CHOICES = [
        (TARGET_USER, "User"),
        (TARGET_METER, "Meter"),
        (TARGET_TRANSACTION, "Transaction"),
        (TARGET_LOAN, "Loan"),
        (TARGET_STAFF, "Staff"),
        (TARGET_SYSTEM, "System"),
    ]

    # Core fields
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    staff_member = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_entries'
    )
    action_type = models.CharField(max_length=30, choices=ACTION_TYPE_CHOICES, db_index=True)
    target_type = models.CharField(max_length=20, choices=TARGET_TYPE_CHOICES, null=True, blank=True)
    target_id = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    target_repr = models.CharField(max_length=200, null=True, blank=True)  # human-readable target desc
    details = models.JSONField(default=dict)  # before/after values
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    notes = models.TextField(blank=True, default='')  # reason entered by staff

    class Meta:
        app_label = 'portal_admin'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['staff_member', 'timestamp']),
            models.Index(fields=['action_type', 'timestamp']),
            models.Index(fields=['target_type', 'target_id']),
        ]

    def __str__(self):
        staff = self.staff_member.email if self.staff_member else 'Unknown'
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {self.action_type} by {staff}"


# --------------------------------------------------------------------------- #
#  Legacy activity log (kept for compatibility with existing admin views)      #
# --------------------------------------------------------------------------- #
class AdminActivityLog(models.Model):
    """Legacy log — new code should write to AuditLog instead."""
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='activities'
    )
    action = models.CharField(max_length=100)
    details = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(default='', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'portal_admin'
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} by {self.user.email if self.user else 'Unknown'}"


# --------------------------------------------------------------------------- #
#  Staff Invitation — Section 2.3                                             #
# --------------------------------------------------------------------------- #
class StaffInvitation(models.Model):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    EXPIRED = "EXPIRED"

    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (ACCEPTED, "Accepted"),
        (EXPIRED, "Expired"),
    ]

    email = models.EmailField(unique=False)
    full_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20, blank=True, default='')
    department = models.CharField(max_length=100, blank=True, default='')
    role = models.CharField(max_length=20)  # CUSTOMER_SERVICE, OPERATOR, ADMIN
    token = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='staff_invitations_sent'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    # The staff User account created when invitation is accepted
    staff_user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_invitation'
    )

    class Meta:
        app_label = 'portal_admin'
        ordering = ['-created_at']

    def __str__(self):
        return f"Invitation for {self.email} ({self.role}) — {self.status}"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at and self.status == self.PENDING


# --------------------------------------------------------------------------- #
#  Fraud / Flagged Account tracking — Section 6.6                             #
# --------------------------------------------------------------------------- #
class FlaggedAccount(models.Model):
    FLAG_VOLUME_SPIKE = "Volume Spike"
    FLAG_RAPID_TRANSFERS = "Rapid Transfers"
    FLAG_NEW_METER_TRANSFER = "New Meter Transfer"
    FLAG_HIGH_CREDIT_USAGE = "High Credit Usage"
    FLAG_GEOGRAPHIC_ANOMALY = "Geographic Anomaly"
    FLAG_MANUAL = "Manual Flag"

    FLAG_TYPE_CHOICES = [
        (FLAG_VOLUME_SPIKE, "Volume Spike"),
        (FLAG_RAPID_TRANSFERS, "Rapid Transfers"),
        (FLAG_NEW_METER_TRANSFER, "New Meter Transfer"),
        (FLAG_HIGH_CREDIT_USAGE, "High Credit Usage"),
        (FLAG_GEOGRAPHIC_ANOMALY, "Geographic Anomaly"),
        (FLAG_MANUAL, "Manual Flag"),
    ]

    STATUS_OPEN = "OPEN"
    STATUS_CLEARED = "CLEARED"
    STATUS_ESCALATED = "ESCALATED"

    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_CLEARED, "Cleared"),
        (STATUS_ESCALATED, "Escalated"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fraud_flags')
    flag_type = models.CharField(max_length=30, choices=FLAG_TYPE_CHOICES)
    trigger_description = models.TextField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_OPEN)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_flags'
    )
    review_note = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'portal_admin'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.flag_type} — {self.user.email} ({self.status})"


# --------------------------------------------------------------------------- #
#  Scheduled Reports configuration — Section 8.4                              #
# --------------------------------------------------------------------------- #
class ScheduledReport(models.Model):
    REPORT_TYPES = [
        ('daily_transaction_summary', 'Daily Transaction Summary'),
        ('user_adoption', 'User Adoption Report'),
        ('credit_loan', 'Credit & Loan Report'),
        ('transfer_activity', 'Transfer Activity Report'),
        ('revenue_summary', 'Revenue Summary'),
        ('meter_registration', 'Meter Registration Report'),
        ('fraud_flags', 'Fraud & Flags Report'),
        ('system_performance', 'System Performance Report'),
        ('social_impact', 'Social Impact Report'),
    ]

    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    report_type = models.CharField(max_length=50, choices=REPORT_TYPES)
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES)
    recipients = models.JSONField(default=list)  # list of email addresses
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    is_active = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'portal_admin'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.report_type} ({self.frequency})"


# --------------------------------------------------------------------------- #
#  System error events — admin health error log                               #
# --------------------------------------------------------------------------- #
class SystemErrorEvent(models.Model):
    component = models.CharField(max_length=80, db_index=True)
    message = models.TextField()
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="system_error_events",
    )
    reference_id = models.CharField(max_length=100, blank=True, default="")
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "portal_admin"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["component", "created_at"]),
        ]

    def __str__(self):
        return f"[{self.component}] {self.message[:60]}"
