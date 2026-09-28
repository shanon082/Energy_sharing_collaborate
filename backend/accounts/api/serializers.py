import logging
from datetime import timedelta

from django.conf import settings
from rest_framework import serializers
from cities_light.models import Country
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.validators import UniqueValidator
from accounts.models import (
    Profile,
    SettingsConfirmationEmailCode,
    User,
    UserAccountDetails,
    generate_random_string, 
)
from django.db.models import Q
import re
from wallet.models import Wallet as MoneyWallet

from utils.validations import validate_password

logger = logging.getLogger(__name__)


# class CreateUserSerializer(serializers.ModelSerializer):

#     first_name = serializers.CharField(required=True,
#         error_messages={
#             'required': 'First name is required',
#             'blank': 'First name cannot be blank'
#         })
#     last_name = serializers.CharField(required=True,
#         error_messages={
#             'required': 'Last name is required',
#             'blank': 'Last name cannot be blank'
#         })
#     email = serializers.EmailField(
#         required=True,
#         validators=[
#             UniqueValidator(
#                 queryset=User.objects.all(), message="This email is already registered. Please use a different email or try logging in."
#             )
#         ],
#         error_messages={
#             'required': 'Email address is required',
#             'invalid': 'Please enter a valid email address'
#         }
#     )
#     phone_number = serializers.CharField(
#         required=True,
#         validators=[
#             UniqueValidator(
#                 queryset=User.objects.all(), message="Phone number already in use!"
#             )
#         ],
#         error_messages={
#             'required': 'Phone number is required',
#             'blank': 'Phone number cannot be blank'
#         }
#     )
   
#     gender = serializers.CharField(required=True)
#     password = serializers.CharField(
#         validators=[validate_password], required=True
#     )
#     confirm_password = serializers.CharField(required=True)

#     class Meta:
#         model = User
#         fields = [
#             "first_name",
#             "last_name",
#             "email",
#             "phone_number",
#             "password",
#             "confirm_password",
#             "gender"
            
#         ]

#     def validate_phone_number(self, value):
#         """Validate phone number format"""
#         phone_pattern = r'^\+?1?\d{9,14}$'
#         if not re.match(phone_pattern, value):
#             raise serializers.ValidationError(
#                 "Please enter a valid phone number (9-15 digits, optional + prefix)"
#             )
#         return value

#     def create(self, validated_data):
#         """
#         Create and return a new User instance
#         """
       
#         validated_data.pop("confirm_password", None)

#         validated_data.pop('profile', None)

#         user = User.objects.create_user(**validated_data)
#         # Profile.objects.create(
#         #     user=user
#         # )
#         if not hasattr(user, 'profile'):
#             Profile.objects.create(user=user)

#         logger.info(
#             f"[ACCOUNTS] Successfully created user account for user {user.id}"
#         )

#         return user

#     def validate(self, data):
#         """
#         Method to validate request data
#         """
#         password = data.get("password") 
#         confirm_password = data.pop("confirm_password")
#         if data.get("password") != confirm_password:
#             raise serializers.ValidationError({"password": "Passwords mismatch"})

#         if len(data.get("password")) < 8:
#             raise serializers.ValidationError({"password": "Password should be atleast 8 characters long"})
#         elif not any(char.isdigit() for char in password):
#             errors["password"] = "Password must contain at least one number."
#         elif not any(char.isalpha() for char in password):
#             errors["password"] = "Password must contain at least one letter."
        
#         if data.get("country"):
#             country = Country.objects.filter(code=data.get("country")).first()
#             if not country:
#             # error_message = f"Country {country} does not exist!"
#                 raise serializers.ValidationError({"country": f"Country {data.get('country')} does not exist"})
#         return data


# class SettingsSerializer(serializers.ModelSerializer):

#     first_name = serializers.CharField(required=True)
#     last_name = serializers.CharField(required=True)
#     phone_number = serializers.CharField(required=True)
#     country = serializers.CharField(required=True)
#     gender = serializers.CharField(required=True)
#     current_password = serializers.CharField(required=True)
#     phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
#     confirm_password = serializers.CharField(required=False, allow_blank=True, allow_null=True)
#     password = serializers.CharField(required=False, allow_blank=True, allow_null=True)
#     code = serializers.CharField(required=False, allow_blank=True, allow_null=True)

#     class Meta:
#         model = User
#         fields = [
#             "first_name",
#             "last_name",
#             "phone_number",
#             "password",
#             "confirm_password",
#             "country",
#             "gender",
#             "current_password",
#             "code",
#         ]

#     def create(self, validated_data):
#         """
#         Save and return  User instance
#         """
#         country_code = validated_data.pop('country', None)
#         first_name = validated_data.get("first_name")
#         last_name = validated_data.get("last_name")
#         phone_number = validated_data.get("phone_number")
#         password = validated_data.get("password")
#         code = validated_data.get("code")
#         gender = validated_data.get("gender")

#         user = self.context.user
#         user.first_name = first_name
#         user.last_name = last_name
#         user.gender = gender
#         print(f"Received code: {code}")
#         if code:
#             print(f"Changing phone number  to {phone_number}")
#             user.phone_number = phone_number
#         else:
#             print(f"Not Changing phone number  to {phone_number}")

#         if password:
#             user.set_password(password)

#         country = Country.objects.get(code=country_code)
#         user.country = country
#         user.save()

#         return user

#     def validate(self, data):
#         """
#         Method to validate request data
#         """
#         user = self.context.user
#         phone_exists = User.objects.filter(Q(~Q(id=user.id) & Q(phone_number=data.get("phone_number")))).last()
#         if phone_exists:
#             raise serializers.ValidationError({"phone_number": "Phone number is already registered"})
#         if "password" in data and data.get("password"):
#             confirm_password = data.pop("confirm_password")
#             if data.get("password") != confirm_password:
#                 raise serializers.ValidationError({"password": "Passwords mismatch"})

#             elif len(data.get("password")) < 8:
#                 raise serializers.ValidationError({"password": "Password should be atleast 8 characters long"})
#         country_code = data.get("country")
#         country = Country.objects.filter(code=country_code).first()

#         if not country:
#             error_message = f"Country {country} does not exist!"
#             raise serializers.ValidationError({"country": error_message})

#         if "code" in data and data.get("code"):
#             # check and validate code
#             code = data.get("code")
#             active_code = SettingsConfirmationEmailCode.objects.filter(code=code).first()
#             if not active_code:
#                 error_message = "Confirmation code is invalid"
#                 raise serializers.ValidationError({"code": error_message})

#             active_code.delete()

#         if not user.check_password(data.get("current_password")):
#             error_message = "Password is invalid"
#             raise serializers.ValidationError({"current_password": error_message})

#         return data


# class EmailTokenObtainSerializer(TokenObtainPairSerializer):
#     username_field = User.EMAIL_FIELD


# class LoginSerializer(EmailTokenObtainSerializer):
#     tokens = serializers.CharField(read_only=True)
#     email = serializers.EmailField(required=True,
#         error_messages={
#             'required': 'Email address is required',
#             'invalid': 'Please enter a valid email address'
#         })
#     password = serializers.CharField(
#         required=True,
#         write_only=True,
#         error_messages={
#             'required': 'Password is required',
#             'blank': 'Password cannot be blank'
#         }
#     )
    
#     default_error_messages = {
#         'no_active_account': 'The account is inactive or the credentials are invalid.',
#         'invalid_credentials': 'Invalid email or password. Please try again.',
#     }

#     @classmethod
#     def get_token(cls, user):
#         return RefreshToken.for_user(user)

#     def validate(self, attrs):
#         try:
#             data = super().validate(attrs)
#             # tokens = super().validate(attrs)
#             user = self.user
#             if not user.profile.email_verified:
#                 error_msg = "Please verify your email address"
#                 raise serializers.ValidationError({"email": error_msg})

#             # Add user info to response
#             data['user'] = {
#                 'id': user.id,
#                 'email': user.email,
#                 'first_name': user.first_name,
#                 'last_name': user.last_name,
#                 'user_role': user.user_role,
#                 'is_admin': user.user_role == User.ADMIN,
#                 'redirect_to': '/admin/dashboard' if user.user_role == User.ADMIN else '/dashboard'
#             }
#             return data
            
#         except Exception as e:
#             logger.error(f"Login error: {str(e)}")
#             # Generic error for security (don't reveal specifics)
#             raise serializers.ValidationError({
#                 'non_field_errors': ['Invalid credentials or server error. Please try again.']
#             })

# class LoginResponseSerializer(serializers.Serializer):
#     access_token = serializers.CharField(read_only=True)
#     refresh_token = serializers.EmailField(read_only=True)


# class ProfileSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Profile
#         fields = ['email_verified']  # Add other profile fields as necessary


# class UserAccountDetailsSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = UserAccountDetails
#         fields = ['account_number', 'address', 'energy_preference', 'payment_method']

# class UserConfigSerializer(serializers.ModelSerializer):
#     profile = ProfileSerializer(read_only=True)
#     account_details = UserAccountDetailsSerializer(read_only=True)
    
#     is_admin = serializers.SerializerMethodField()
#     is_staff = serializers.SerializerMethodField()
#     is_superuser = serializers.SerializerMethodField()

#     def get_is_admin(self, obj):
#         return obj.user_role == User.ADMIN
    
#     def get_is_staff(self, obj):
#         return hasattr(obj, 'is_staff') and obj.is_staff
    
#     def get_is_superuser(self, obj):
#         return hasattr(obj, 'is_superuser') and obj.is_superuser

#     class Meta:
#         model = User
#         fields = [
#             'id', 'email', 'first_name', 'last_name', 
#             'phone_number', 'profile', 'account_is_active',
#             'account_details', 'is_admin', 'is_staff', 'is_superuser',
#             'user_role'  
#         ]

#     def to_representation(self, instance):
#         """
#         Ensure account_details is always a dict, even if None
#         """
#         representation = super().to_representation(instance)
        
#         # Ensure account_details is a dict
#         if representation.get('account_details') is None:
#             representation['account_details'] = {}
        
#         return representation

# class ForgotPasswordSerializer(serializers.Serializer):
#     email = serializers.EmailField(
#         required=True,
#         error_messages={
#             'required': 'Email address is required',
#             'invalid': 'Please enter a valid email address'
#         }
#     )
    
#     def validate_email(self, value):
#         """Check if email exists in the system"""
#         if not User.objects.filter(email=value).exists():
#             pass
#         return value


# class ResetPasswordConfirmSerializer(serializers.Serializer):
#     password = serializers.CharField(
#         validators=[validate_password],
#         max_length=128,
#         min_length=8,
#         required=True,
#     )
#     confirm_password = serializers.CharField(
#         max_length=128, min_length=8, required=True
#     )

#     def validate(self, data):
#         password = data.get("password")
#         confirm_password = data.pop("confirm_password")
#         if password != confirm_password:
#             raise serializers.ValidationError("Passwords mismatch!")
#         return data


# class UpdateAccountDetailsSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = UserAccountDetails
#         fields = ['address', 'energy_preference', 'payment_method']
    
#     def update(self, instance, validated_data):
#         validated_data.pop('account_number', None)
        
#         for attr, value in validated_data.items():
#             setattr(instance, attr, value)
#         instance.save()
#         return instance



class CreateUserSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(required=True,
        error_messages={
            'required': 'First name is required',
            'blank': 'First name cannot be blank'
        })
    last_name = serializers.CharField(required=True,
        error_messages={
            'required': 'Last name is required',
            'blank': 'Last name cannot be blank'
        })
    email = serializers.EmailField(
        required=True,
        validators=[
            UniqueValidator(
                queryset=User.objects.all(), message="This email is already registered. Please use a different email or try logging in."
            )
        ],
        error_messages={
            'required': 'Email address is required',
            'invalid': 'Please enter a valid email address'
        }
    )
    phone_number = serializers.CharField(
        required=True,
        validators=[
            UniqueValidator(
                queryset=User.objects.all(), message="Phone number already in use!"
            )
        ],
        error_messages={
            'required': 'Phone number is required',
            'blank': 'Phone number cannot be blank'
        }
    )
    gender = serializers.CharField(required=True)
    password = serializers.CharField(
        validators=[validate_password], required=True
    )
    confirm_password = serializers.CharField(required=True)

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "password",
            "confirm_password",
            "gender"
        ]

    def validate_phone_number(self, value):
        """Validate phone number format"""
        phone_pattern = r'^\+?1?\d{9,14}$'
        if not re.match(phone_pattern, value):
            raise serializers.ValidationError(
                "Please enter a valid phone number (9-15 digits, optional + prefix)"
            )
        return value

    def create(self, validated_data):
        """
        Create and return a new User instance
        """
        validated_data.pop("confirm_password", None)
        validated_data.pop('profile', None)

        user = User.objects.create_user(**validated_data)
        if not hasattr(user, 'profile'):
            Profile.objects.create(user=user)

        logger.info(
            f"[ACCOUNTS] Successfully created user account for user {user.id}"
        )

        return user

    def validate(self, data):
        """
        Method to validate request data
        """
        password = data.get("password") 
        confirm_password = data.pop("confirm_password")
        if data.get("password") != confirm_password:
            raise serializers.ValidationError({"password": "Passwords mismatch"})

        if len(data.get("password")) < 8:
            raise serializers.ValidationError({"password": "Password should be atleast 8 characters long"})
        
        # Check password complexity
        if not any(char.isdigit() for char in password):
            raise serializers.ValidationError({"password": "Password must contain at least one number."})
        elif not any(char.isalpha() for char in password):
            raise serializers.ValidationError({"password": "Password must contain at least one letter."})
        
        if data.get("country"):
            country = Country.objects.filter(code=data.get("country")).first()
            if not country:
                raise serializers.ValidationError({"country": f"Country {data.get('country')} does not exist"})
        return data


class SettingsSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    phone_number = serializers.CharField(required=True)
    country = serializers.CharField(required=True)
    gender = serializers.CharField(required=True)
    current_password = serializers.CharField(required=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    confirm_password = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    password = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    code = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "phone_number",
            "password",
            "confirm_password",
            "country",
            "gender",
            "current_password",
            "code",
        ]

    def create(self, validated_data):
        """
        Save and return  User instance
        """
        country_code = validated_data.pop('country', None)
        first_name = validated_data.get("first_name")
        last_name = validated_data.get("last_name")
        phone_number = validated_data.get("phone_number")
        password = validated_data.get("password")
        code = validated_data.get("code")
        gender = validated_data.get("gender")

        user = self.context.user
        user.first_name = first_name
        user.last_name = last_name
        user.gender = gender
        
        if code:
            user.phone_number = phone_number

        if password:
            user.set_password(password)

        country = Country.objects.get(code=country_code)
        user.country = country
        user.save()

        return user

    def validate(self, data):
        """
        Method to validate request data
        """
        user = self.context.user
        phone_exists = User.objects.filter(Q(~Q(id=user.id) & Q(phone_number=data.get("phone_number")))).last()
        if phone_exists:
            raise serializers.ValidationError({"phone_number": "Phone number is already registered"})
        
        if "password" in data and data.get("password"):
            confirm_password = data.pop("confirm_password")
            if data.get("password") != confirm_password:
                raise serializers.ValidationError({"password": "Passwords mismatch"})
            elif len(data.get("password")) < 8:
                raise serializers.ValidationError({"password": "Password should be atleast 8 characters long"})
        
        country_code = data.get("country")
        country = Country.objects.filter(code=country_code).first()
        if not country:
            error_message = f"Country {country} does not exist!"
            raise serializers.ValidationError({"country": error_message})

        if "code" in data and data.get("code"):
            # check and validate code
            code = data.get("code")
            active_code = SettingsConfirmationEmailCode.objects.filter(code=code).first()
            if not active_code:
                error_message = "Confirmation code is invalid"
                raise serializers.ValidationError({"code": error_message})
            active_code.delete()

        if not user.check_password(data.get("current_password")):
            error_message = "Password is invalid"
            raise serializers.ValidationError({"current_password": error_message})

        return data


class EmailTokenObtainSerializer(TokenObtainPairSerializer):
    username_field = User.EMAIL_FIELD


class LoginSerializer(EmailTokenObtainSerializer):
    tokens = serializers.CharField(read_only=True)
    remember_me = serializers.BooleanField(required=False, default=False, write_only=True)
    email = serializers.EmailField(required=True,
        error_messages={
            'required': 'Email address is required',
            'invalid': 'Please enter a valid email address'
        })
    password = serializers.CharField(
        required=True,
        write_only=True,
        error_messages={
            'required': 'Password is required',
            'blank': 'Password cannot be blank'
        }
    )
    
    default_error_messages = {
        'no_active_account': 'The account is inactive or the credentials are invalid.',
        'invalid_credentials': 'Invalid email or password. Please try again.',
    }

    @classmethod
    def get_token(cls, user, *, remember_me=False):
        refresh = RefreshToken.for_user(user)
        if remember_me:
            days = getattr(settings, "REMEMBER_ME_REFRESH_DAYS", 30)
            refresh.set_exp(lifetime=timedelta(days=days))
        return refresh

    def validate(self, attrs):
        remember_me = bool(attrs.pop("remember_me", False))
        try:
            data = super().validate(attrs)
        except serializers.ValidationError:
            raise
        except Exception as e:
            logger.error(f"Login authentication error: {str(e)}")
            raise serializers.ValidationError({
                'non_field_errors': ['Invalid email or password. Please try again.']
            })

        if remember_me:
            refresh = self.get_token(self.user, remember_me=True)
            data["refresh"] = str(refresh)
            data["access"] = str(refresh.access_token)

        user = self.user
        if not user.profile.email_verified:
            raise serializers.ValidationError({
                "email": ["Please verify your email address before logging in."]
            })

        data['user'] = {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'user_role': user.user_role,
            'is_admin': user.user_role == User.ADMIN,
            'redirect_to': '/admin/dashboard' if user.user_role == User.ADMIN else '/dashboard'
        }
        return data


class LoginResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField(read_only=True)
    refresh_token = serializers.EmailField(read_only=True)


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['email_verified']


class UserAccountDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAccountDetails
        fields = ['account_number', 'address', 'energy_preference', 'payment_method']


class UserConfigSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)
    account_details = UserAccountDetailsSerializer(read_only=True)
    
    is_admin = serializers.SerializerMethodField()
    is_staff_member = serializers.SerializerMethodField()
    is_staff = serializers.SerializerMethodField()
    is_superuser = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()  # Convert PhoneNumber to string
    wallet = serializers.SerializerMethodField()

    def get_is_admin(self, obj):
        return obj.user_role == User.ADMIN or getattr(obj, "is_superuser", False)

    def get_is_staff_member(self, obj):
        return obj.is_staff_member or getattr(obj, "is_superuser", False)
    
    def get_is_staff(self, obj):
        return hasattr(obj, 'is_staff') and obj.is_staff
    
    def get_is_superuser(self, obj):
        return hasattr(obj, 'is_superuser') and obj.is_superuser
    
    def get_phone_number(self, obj):
        # Convert PhoneNumber object to string
        return str(obj.phone_number) if obj.phone_number else None

    def get_wallet(self, obj):
        wallet, _ = MoneyWallet.objects.get_or_create(user=obj)
        return {
            "wallet_id": str(wallet.id),
            "balance": str(wallet.balance),
            "currency": "UGX",
        }

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 
            'phone_number', 'profile', 'account_is_active',
            'account_details', 'is_admin', 'is_staff', 'is_superuser',
            'user_role', 'wallet', 'is_staff_member', 'must_change_password'
        ]

    def to_representation(self, instance):
        """
        Ensure account_details is always a dict, even if None
        """
        representation = super().to_representation(instance)
        
        # Ensure account_details is a dict
        if representation.get('account_details') is None:
            representation['account_details'] = {}
        
        return representation


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile data"""
    phone_number = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'monthly_expenditure',
            'purchase_frequency',
            'payment_consistency',
            'disconnection_history',
            'meter_sharing',
            'monthly_income',
            'income_stability',
            'consumption_level',
            'phone_number',
            'email',
            'first_name',
            'last_name',
        ]
    
    def get_phone_number(self, obj):
        return str(obj.phone_number) if obj.phone_number else None


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(
        required=True,
        error_messages={
            'required': 'Email address is required',
            'invalid': 'Please enter a valid email address'
        }
    )
    
    def validate_email(self, value):
        """Check if email exists in the system"""
        if not User.objects.filter(email=value).exists():
            pass
        return value


class ResetPasswordConfirmSerializer(serializers.Serializer):
    password = serializers.CharField(
        validators=[validate_password],
        max_length=128,
        min_length=8,
        required=True,
    )
    confirm_password = serializers.CharField(
        max_length=128, min_length=8, required=True
    )

    def validate(self, data):
        password = data.get("password")
        confirm_password = data.pop("confirm_password")
        if password != confirm_password:
            raise serializers.ValidationError("Passwords mismatch!")
        return data


class UpdateAccountDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAccountDetails
        fields = ['address', 'energy_preference', 'payment_method']
    
    def update(self, instance, validated_data):
        validated_data.pop('account_number', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class UpdateUserProfileSerializer(serializers.Serializer):
    """Serializer for updating user profile assessment data"""
    monthly_expenditure = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    purchase_frequency = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    payment_consistency = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    disconnection_history = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    meter_sharing = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    monthly_income = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    income_stability = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    consumption_level = serializers.CharField(required=False, allow_blank=True, allow_null=True)
