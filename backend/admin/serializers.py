from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import AdminNotificationSettings

User = get_user_model()

class AdminProfileSerializer(serializers.ModelSerializer):
    """Serializer for admin profile updates"""
    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = User
        fields = [
            'first_name', 
            'last_name', 
            'email', 
            'phone_number',
            'gender'
        ]
    
    def validate_email(self, value):
        """Ensure email is unique"""
        user = self.instance
        if User.objects.filter(email=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("This email is already registered")
        return value
    
    def validate_phone_number(self, value):
        """Validate phone number"""
        if value and User.objects.filter(phone_number=value).exclude(id=self.instance.id).exists():
            raise serializers.ValidationError("This phone number is already registered")
        return value


class AdminPasswordChangeSerializer(serializers.Serializer):
    """Serializer for password change"""
    current_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True)
    confirm_password = serializers.CharField(write_only=True, required=True)
    
    def validate(self, data):
        # Check if new passwords match
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match"
            })
        
        # Validate new password strength
        try:
            validate_password(data['new_password'])
        except DjangoValidationError as e:
            raise serializers.ValidationError({
                "new_password": list(e.messages)
            })
        
        return data


class AdminNotificationSettingsSerializer(serializers.ModelSerializer):
    """Serializer for notification settings"""
    
    class Meta:
        model = AdminNotificationSettings
        fields = [
            'email_notifications',
            'sms_notifications',
            'loan_approvals',
            'user_registrations',
            'system_alerts',
            'weekly_reports',
            'report_schedule'
        ]