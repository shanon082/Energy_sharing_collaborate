"""Read-only staff decisions, usable without hosting Next.js."""
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from loan.sandbox_service import loan_record
from loan.models import SandboxLoan
from admin.models import AuditLog
from meter.enrollment_review import require_reviewer


@login_required(login_url="/admin-panel/login/")
@never_cache
@require_GET
def decisions(request):
    require_reviewer(request.user)
    if not getattr(settings, "CONSUMER_SANDBOX_ENABLED", False):
        raise PermissionDenied("Sandbox profile is disabled.")
    rows = SandboxLoan.objects.order_by("-created_at")[:100]
    audits = AuditLog.objects.filter(details__environment__in=["MTN_SANDBOX", "UGX_DEMO"]).order_by("-timestamp")[:100]
    return render(request, "loan/sandbox_decisions.html", {"loans": [loan_record(row) for row in rows], "audits": audits})
