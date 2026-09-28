"""
Record server-side 5xx responses for the admin error log.
"""
from admin.system_errors import record_system_error


class SystemErrorLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code >= 500 and request.path.startswith("/api/"):
            user = getattr(request, "user", None)
            if user is not None and not getattr(user, "is_authenticated", False):
                user = None
            record_system_error(
                "API Gateway",
                f"{request.method} {request.path} returned HTTP {response.status_code}",
                user=user,
                details={"status_code": response.status_code, "path": request.path},
            )
        return response
