"""
URL configuration for backend project.
"""

from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from webhooks.api.views import ThingsBoardLowUnitsWebhookView, ThingsBoardDailyUsageWebhookView

def home(request):
    return HttpResponse("Welcome to the Metering API! Visit /api/v1/ for API endpoints or /admin/ for the admin interface.")

urlpatterns = [
    path('', home, name='home'),
    path('admin-panel/', admin.site.urls), 
    path('api/v1/', include(("backend.api1", "api1"), namespace="api1")),
    path('api/v1/admin/', include('admin.urls')),
    path('api/v1/wallet/', include('wallet.urls')),
    path(
        'webhooks/thingsboard/low-units',
        ThingsBoardLowUnitsWebhookView.as_view(),
        name='thingsboard-low-units-webhook',
    ),
    path(
        'webhooks/thingsboard/daily-usage',
        ThingsBoardDailyUsageWebhookView.as_view(),
        name='thingsboard-daily-usage-webhook',
    ),
]

urlpatterns += static(
    settings.STATIC_URL, document_root=settings.STATIC_ROOT
)

urlpatterns += static(
    settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
)

admin.site.site_header = "Metering System"
admin.site.site_title = "Metering Admin Portal"
admin.site.index_title = "Welcome to Metering Portal"