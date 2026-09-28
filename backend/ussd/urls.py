from django.urls import path

from .views import ussd_entry, ussd_phone_numbers, ussd_receiver_meters


urlpatterns = [
    path("entry/", ussd_entry, name="ussd-entry"),
    path("phones/", ussd_phone_numbers, name="ussd-phone-numbers"),
    path("meters/", ussd_receiver_meters, name="ussd-receiver-meters"),
]
