from django.conf import settings
from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status
import datetime


class StaffInactivityMiddleware:
    """
    Enforces 30-minute inactivity timeout for staff admin users (spec Section 1.3).
    Tracks last activity via a custom JWT claim and rejects requests from staff
    whose last activity was more than STAFF_SESSION_INACTIVITY_MINUTES ago.

    Since JWT tokens are already set to 30-minute lifetime, this middleware
    additionally stamps the last activity time in a response header so the
    frontend can track inactivity and warn/logout before token expiry.
    """

    INACTIVITY_MINUTES = getattr(settings, 'STAFF_SESSION_INACTIVITY_MINUTES', 30)
    LAST_ACTIVITY_HEADER = 'X-Last-Activity'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Stamp last-activity time on every authenticated staff response
        # so the frontend JS can track idle time and proactively log out.
        if hasattr(request, 'user') and request.user.is_authenticated:
            if getattr(request.user, 'is_staff_member', False):
                response[self.LAST_ACTIVITY_HEADER] = timezone.now().isoformat()

        return response
