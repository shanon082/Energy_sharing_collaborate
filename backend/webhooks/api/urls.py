from django.urls import path
from .views import TokenDecryptionView





urlpatterns = [
    path('token/', TokenDecryptionView.as_view(), name="token")
]