from django.urls import path
from .views import ShareUnitsView, TransferUnitsView, ShareReceiverPreviewView

urlpatterns = [
    path('share-units/', ShareUnitsView.as_view(), name="share-units"),
    path('receiver-preview/', ShareReceiverPreviewView.as_view(), name="share-receiver-preview"),
    path('transfer-units/', TransferUnitsView.as_view(), name="transfer-units"),
]