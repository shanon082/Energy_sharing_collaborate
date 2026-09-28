from django.urls import path
from .views import (
    # Dashboard
    AdminDashboardView,
    AdminStatsView,
    # Staff management (Section 2)
    StaffListView,
    StaffDetailView,
    # User management (Section 3)
    UserManagementView,
    UserDetailView,
    UserSuspendView,
    UserPINResetView,
    UserKYCView,
    ToggleUserStatusView,
    CreditLimitOverrideView,
    # Meter management (Section 4)
    MeterManagementView,
    MeterDetailView,
    MeterDeactivateView,
    MeterDeleteView,
    DeletedMeterRecordsView,
    MeterTransferOwnershipView,
    # Credit & Loans (Section 5)
    CreditLoansDashboardView,
    LoanManagementView,
    LoanDetailView,
    LoanPenaltyWaiverView,
    LoanDisburseView,
    # Transaction monitoring (Section 6)
    TransactionLogView,
    TransactionDetailView,
    TransactionRefundView,
    TokenRedeliveryView,
    FlaggedTransactionsView,
    FlaggedAccountsView,
    # System health (Section 7)
    SystemHealthView,
    SystemErrorLogView,
    # Reports (Section 8)
    ReportsView,
    ScheduledReportsView,
    # Audit log (Section 9)
    AuditLogView,
    # Account settings
    AdminAccountView,
    AdminPasswordChangeView,
    AdminNotificationSettingsView,
    AdminSessionManagementView,
    AdminActivityLogView,
    # Configuration
    LoanTiersView,
    LoanTierDetailView,
    TariffsView,
    TariffDetailView,
    TariffSeedEraView,
    TariffActivateView,
    # 2FA (Section 1.3)
    TOTP2FASetupView,
    TOTP2FAStatusView,
    TOTP2FADisableView,
    TOTP2FALoginVerifyView,
)

urlpatterns = [
    # --- Dashboard ---
    path('dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),
    path('stats/', AdminStatsView.as_view(), name='admin-stats'),

    # --- Staff management (Admin only) ---
    path('staff/', StaffListView.as_view(), name='admin-staff-list'),
    path('staff/<int:staff_id>/', StaffDetailView.as_view(), name='admin-staff-detail'),

    # --- User management ---
    path('users/', UserManagementView.as_view(), name='admin-users'),
    path('users/<int:user_id>/', UserDetailView.as_view(), name='user-detail'),
    path('users/<int:user_id>/suspend/', UserSuspendView.as_view(), name='user-suspend'),
    path('users/<int:user_id>/reset-pin/', UserPINResetView.as_view(), name='user-reset-pin'),
    path('users/<int:user_id>/kyc/', UserKYCView.as_view(), name='user-kyc'),
    path('users/<int:user_id>/credit-limit/', CreditLimitOverrideView.as_view(), name='user-credit-limit'),
    path('toggle-user-status/', ToggleUserStatusView.as_view(), name='toggle-user-status'),

    # --- Meter management ---
    path('meters/', MeterManagementView.as_view(), name='admin-meters'),
    path('meters/<int:meter_id>/', MeterDetailView.as_view(), name='admin-meter-detail'),
    path('meters/<int:meter_id>/deactivate/', MeterDeactivateView.as_view(), name='meter-deactivate'),
    path('meters/<int:meter_id>/delete/', MeterDeleteView.as_view(), name='meter-delete'),
    path('meters/<int:meter_id>/transfer/', MeterTransferOwnershipView.as_view(), name='meter-transfer'),
    path('deleted-meters/', DeletedMeterRecordsView.as_view(), name='admin-deleted-meters'),

    # --- Credit & Loans ---
    path('loans/dashboard/', CreditLoansDashboardView.as_view(), name='loans-dashboard'),
    path('loans/', LoanManagementView.as_view(), name='admin-loans'),
    path('loans/<int:loan_id>/', LoanDetailView.as_view(), name='admin-loan-detail'),
    path('loans/<int:loan_id>/waive-penalty/', LoanPenaltyWaiverView.as_view(), name='loan-waive-penalty'),
    path('loans/<int:loan_id>/disburse/', LoanDisburseView.as_view(), name='loan-disburse'),

    # --- Transaction monitoring ---
    path('transactions/', TransactionLogView.as_view(), name='admin-transactions'),
    path('transactions/flagged/', FlaggedTransactionsView.as_view(), name='admin-flagged-transactions'),
    path('transactions/<uuid:transaction_id>/', TransactionDetailView.as_view(), name='admin-transaction-detail'),
    path('transactions/<uuid:transaction_id>/refund/', TransactionRefundView.as_view(), name='transaction-refund'),
    path('transactions/<uuid:transaction_id>/redeliver/', TokenRedeliveryView.as_view(), name='token-redeliver'),

    # --- Flagged accounts ---
    path('flagged-accounts/', FlaggedAccountsView.as_view(), name='admin-flagged-accounts'),

    # --- System health ---
    path('system-health/', SystemHealthView.as_view(), name='system-health'),
    path('system-health/errors/', SystemErrorLogView.as_view(), name='system-error-log'),

    # --- Reports ---
    path('reports/', ReportsView.as_view(), name='admin-reports'),
    path('reports/scheduled/', ScheduledReportsView.as_view(), name='admin-scheduled-reports'),

    # --- Audit log (read-only, append-only) ---
    path('audit-log/', AuditLogView.as_view(), name='admin-audit-log'),

    # --- Account settings ---
    path('account/', AdminAccountView.as_view(), name='admin-account'),
    path('account/password-change/', AdminPasswordChangeView.as_view(), name='admin-password-change'),
    path('account/notifications/', AdminNotificationSettingsView.as_view(), name='admin-notifications'),
    path('account/sessions/', AdminSessionManagementView.as_view(), name='admin-sessions'),
    path('account/activities/', AdminActivityLogView.as_view(), name='admin-activities'),

    # --- Configuration ---
    path('loan-tiers/', LoanTiersView.as_view(), name='admin-loan-tiers'),
    path('loan-tiers/<int:pk>/', LoanTierDetailView.as_view(), name='admin-loan-tier-detail'),
    path('tariffs/', TariffsView.as_view(), name='admin-tariffs'),
    path('tariffs/seed-era/', TariffSeedEraView.as_view(), name='admin-tariffs-seed-era'),
    path('tariffs/<int:pk>/activate/', TariffActivateView.as_view(), name='admin-tariff-activate'),
    path('tariffs/<int:pk>/', TariffDetailView.as_view(), name='admin-tariff-detail'),

    # --- 2FA (Section 1.3) ---
    path('2fa/setup/', TOTP2FASetupView.as_view(), name='2fa-setup'),
    path('2fa/status/', TOTP2FAStatusView.as_view(), name='2fa-status'),
    path('2fa/disable/', TOTP2FADisableView.as_view(), name='2fa-disable'),
    path('2fa/login-verify/', TOTP2FALoginVerifyView.as_view(), name='2fa-login-verify'),
]
