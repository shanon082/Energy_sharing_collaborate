from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from django.http import JsonResponse
from django.conf import settings
import time

class ShareSecurityMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Only apply to share/transfer endpoints
        if request.path in ['share/share-units/', 'transfer/transfer-units/']:
            if request.method == 'POST':
                user_id = request.user.id if request.user.is_authenticated else None
                ip_address = self.get_client_ip(request)
                
                if user_id:
                    # Rate limiting per user
                    user_key = f"share_rate_limit_user_{user_id}"
                    user_count = cache.get(user_key, 0)
                    
                    if user_count >= getattr(settings, 'SHARE_RATE_LIMIT', 5):
                        return JsonResponse(
                            {"error": "Too many requests. Please try again later."},
                            status=429
                        )
                    
                    # IP-based rate limiting
                    ip_key = f"share_rate_limit_ip_{ip_address}"
                    ip_count = cache.get(ip_key, 0)
                    
                    if ip_count >= getattr(settings, 'IP_SHARE_RATE_LIMIT', 10):
                        return JsonResponse(
                            {"error": "Too many requests from your IP address."},
                            status=429
                        )
    
    def process_response(self, request, response):
        if request.path in ['share/share-units/', 'transfer/transfer-units/']:
            if request.method == 'POST' and response.status_code == 200:
                user_id = request.user.id if request.user.is_authenticated else None
                ip_address = self.get_client_ip(request)
                
                if user_id:
                    # Increment counters with expiry
                    user_key = f"share_rate_limit_user_{user_id}"
                    cache.set(user_key, cache.get(user_key, 0) + 1, 3600)  # 1 hour
                    
                    ip_key = f"share_rate_limit_ip_{ip_address}"
                    cache.set(ip_key, cache.get(ip_key, 0) + 1, 3600)
        
        return response
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip