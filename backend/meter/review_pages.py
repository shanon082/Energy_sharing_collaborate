"""Django-hosted staff review; works without a hosted Next.js application."""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from meter.enrollment_review import ReviewForm, require_reviewer, review_enrollment
from meter.models import MeterEnrollmentRequest


@login_required(login_url="/admin-panel/login/")
@never_cache
@sensitive_post_parameters()
@require_http_methods(["GET", "POST"])
def meter_requests(request):
    require_reviewer(request.user)
    error = None
    if request.method == "POST":
        try:
            review_enrollment(request.user, request.POST)
        except MeterEnrollmentRequest.DoesNotExist:
            error = "Request no longer available."
        except ValidationError as exc:
            error = " ".join(exc.messages)
        else:
            return redirect("staff-meter-requests")
    pending = MeterEnrollmentRequest.objects.filter(review__isnull=True, sandbox_transition__isnull=True).order_by("created_at")[:50]
    return render(request, "meter/review_requests.html", {"pending": pending, "form": ReviewForm(), "error": error})
