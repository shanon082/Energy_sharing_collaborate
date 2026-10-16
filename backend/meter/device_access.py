"""Contain legacy device paths until a source-bound physical adapter exists."""

from django.conf import settings
from rest_framework.exceptions import APIException


class DeviceOperationUnavailable(APIException):
    status_code = 503
    default_code = "DEVICE_PROTOCOL_UNAVAILABLE"

    def __init__(self):
        super().__init__({"code": self.default_code,
                         "message": "Use source-bound delivery and a reviewed device protocol; legacy physical operations are unavailable."})


def reject_legacy_delivery():
    # No switch can authorize this amount-only API: it has neither allocation
    # binding nor a durable command/application receipt. Keep pending history.
    raise DeviceOperationUnavailable()


def require_device_transport(meter, *, stub_only=False):
    """Never call ThingsBoard or synthesize evidence in a testing host/domain."""
    if (getattr(settings, "ALWAYSDATA_TESTING", False)
            or getattr(settings, "CONSUMER_SANDBOX_ENABLED", False)
            or meter.sandbox_inventory):
        raise DeviceOperationUnavailable()
    if (stub_only or (meter.iot_device_token or "").startswith("dev-")) and not (
        settings.DEBUG
        and getattr(settings, "AMI_GATEWAY", "") == "utils.ami_gateway.MockAMIGateway"
        and (meter.iot_device_token or "").startswith("dev-")
    ):
        raise DeviceOperationUnavailable()
