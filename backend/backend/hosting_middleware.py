"""Free testing host cannot run financial/device mutations or live GET probes."""

from django.http import JsonResponse
from django.conf import settings
from django.utils.cache import add_never_cache_headers


ACCOUNT_PAGE_PATHS = {"/account/verify-email/", "/account/reset-password/"}


class AccountPageSecurityMiddleware:
    """Protect responses including CSRF failures, errors and HTTPS redirects."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path in ACCOUNT_PAGE_PATHS:
            add_never_cache_headers(response)
            response["Referrer-Policy"] = "no-referrer"
            response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
            response["Content-Security-Policy"] = (
                "default-src 'none'; style-src 'self'; form-action 'self'; "
                "frame-ancestors 'none'; base-uri 'none'"
            )
        return response


class FreeTestingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        # A few legacy GET handlers poll providers or retry meter commands.
        unavailable_reads = (
            "/api/v1/meter/ami-status/", "/api/v1/meter/thingsboard-health/",
            "/api/v1/meter/check-units/", "/api/v1/meter/check-payment-status/",
            "/api/v1/loans/payment-status/", "/api/v1/transactions/statement/email/",
        )
        auth = path.startswith("/api/v1/auth/")
        account_page = (getattr(settings, "DJANGO_HOSTED_ACCOUNT_PAGES", False)
                        and path in ACCOUNT_PAGE_PATHS and request.method == "POST")
        local_metadata = path in {
            "/api/v1/meter/register/", "/api/v1/meter/mobile-notifications/",
            "/api/v1/meter/notifications/", "/admin-panel/login/", "/admin-panel/logout/",
        }
        if request.method != "OPTIONS" and (
                path.startswith(unavailable_reads)
                or (request.method not in {"GET", "HEAD"} and not (auth or account_page or local_metadata))):
            return JsonResponse({"code": "TESTING_OPERATION_UNAVAILABLE",
                                 "message": "Financial, delivery and worker-dependent operations are unavailable on this testing host."}, status=503)
        return self.get_response(request)
