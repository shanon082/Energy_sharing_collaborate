import logging
from rest_framework import serializers
from meter.models import Meter, MeterToken
from meter.validators import validate_meter_no


class MeterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meter
        fields = ["meter_no", "static_ip", "units", "architecture", "label", "iot_device_token"]
        extra_kwargs = {
            "units": {"read_only": True},
            "static_ip": {"required": False, "allow_null": True, "allow_blank": True},
            "label": {"required": False, "allow_blank": True},
            "iot_device_token": {"required": False, "allow_null": True, "allow_blank": True, "write_only": True},
        }

    def validate_meter_no(self, value):
        ok, result = validate_meter_no(value)
        if not ok:
            raise serializers.ValidationError(result)
        return result

    def validate(self, data):
        # Determine effective architecture (fall back to instance value on partial update)
        arch = data.get("architecture")
        if arch is None and self.instance:
            arch = self.instance.architecture
        arch = arch or Meter.ARCH_STS

        static_ip = data.get("static_ip")
        if static_ip is None and self.instance:
            static_ip = self.instance.static_ip
        static_ip = (static_ip or "").strip() or None

        token = data.get("iot_device_token")
        if token is None and self.instance:
            token = self.instance.iot_device_token
        token = (token or "").strip()

        if arch == Meter.ARCH_AMI and not token:
            raise serializers.ValidationError(
                {"iot_device_token": "ThingsBoard device access token is required for AMI meters."}
            )

        if arch == Meter.ARCH_AMI:
            data["iot_device_token"] = token
            if static_ip:
                data["static_ip"] = static_ip
            elif self.instance and self.instance.static_ip:
                data["static_ip"] = self.instance.static_ip
            else:
                data["static_ip"] = None
        else:
            # STS meters have no IP or device token
            data["static_ip"] = None
            data["iot_device_token"] = None
        return data



class SendUnitSerializer(serializers.ModelSerializer):

    receiver_meter_no = serializers.CharField(required=True)
    no_units = serializers.CharField(required=True)
    message = serializers.CharField(required=True)
    
    class Meta:
        model= Meter
        fields = [
            "receiver_meter_no",
            "no_units",
            "message"
        ]

class TokenSerializer(serializers.ModelSerializer):
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    loan_id = serializers.SerializerMethodField()

    class Meta:
        model = MeterToken
        fields = '__all__'

    def get_loan_id(self, obj):
        if obj.loan_application:
            return obj.loan_application.loan_id
        return None
