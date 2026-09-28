from decimal import Decimal
import logging
from rest_framework import serializers
from .models import Share
from django.core.validators import MinValueValidator
from meter.validators import METER_NO_MAX_LEN, normalize_meter_no, validate_meter_no

logger = logging.getLogger(__name__)

class ShareUnitSerializer(serializers.ModelSerializer):
    meter_number = serializers.CharField(
        required=True,
        max_length=METER_NO_MAX_LEN,
        help_text="Receiver's meter number (any letters, numbers, or symbols)",
    )
    units = serializers.DecimalField(
        required=True,
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('2.00'),
        help_text="Minimum 2 units to share"
    )
    
    class Meta:
        model = Share
        fields = [
            "meter_number",
            "units",
        ]
    
    def validate_meter_number(self, value):
        ok, result = validate_meter_no(value)
        if not ok:
            raise serializers.ValidationError(result)
        return result
    
    def validate_units(self, value):
        if value < Decimal('2.00'):
            raise serializers.ValidationError("Minimum 2 units required to share")
        return value


class TransferUnitsSerializer(serializers.Serializer):
    meter_no_old = serializers.CharField(
        required=True,
        max_length=METER_NO_MAX_LEN,
        help_text="Your current meter number",
    )
    meter_no_new = serializers.CharField(
        required=True,
        max_length=METER_NO_MAX_LEN,
        help_text="New meter number",
    )
    
    def validate(self, data):
        if data['meter_no_old'] == data['meter_no_new']:
            raise serializers.ValidationError(
                "Old and new meter numbers must be different"
            )
        
        for field in ['meter_no_old', 'meter_no_new']:
            ok, result = validate_meter_no(data[field])
            if not ok:
                raise serializers.ValidationError({field: result})
            data[field] = result
        
        return data
    

class ConfirmShareSerializer(serializers.Serializer):
    meter_number = serializers.CharField(max_length=METER_NO_MAX_LEN)
    units = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("2.00"),
    )
    def validate_meter_number(self, value):
        ok, result = validate_meter_no(value)
        if not ok:
            raise serializers.ValidationError(result)
        return result


class VerifyOTPSerializer(serializers.Serializer):
    """Used by meter transfer flow only."""
    verification_code = serializers.CharField(
        required=True,
        min_length=6,
        max_length=6,
        help_text="6-digit OTP code",
    )

    def validate_verification_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("Verification code must contain only digits")
        return value