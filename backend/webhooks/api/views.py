from django.utils import timezone
from django.utils.dateparse import parse_datetime
from datetime import date
from decimal import Decimal, InvalidOperation
import logging
from utils.models import TokenValidator
from rest_framework.response import Response
from rest_framework import status, permissions
from django.shortcuts import get_object_or_404, render
from rest_framework.views import APIView
from meter.models import MeterToken, Meter
from loan.models import LoanDisbursement
from django.db import transaction
from django.conf import settings

logger = logging.getLogger(__name__)


class TokenDecryptionView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        """Docs for browsable API"""
        return Response({
            "message": "This endpoint accepts POST requests for token decryption.",
            "required_fields": {
                "token": "The token to decrypt",
                "meterNo": "The meter number"
            },
            "example_payload": {
                "token": "example_token_123",
                "meterNo": "METER123"
            }
        })

    def post(self, request, *args, **kwargs):
        token_info = request.data
        logger.info(f"Token Decryption function called")

        data = TokenValidator(**token_info)
        token = data.token
        meter_no = data.meterNo

        try:
            token_obj = MeterToken.objects.get(token=token)
            meter = Meter.objects.get(meter_no=meter_no)
            if token_obj and meter and not token_obj.is_used:
                meter.units += token_obj.units
                meter.save()
                token_obj.is_used = True
                token_obj.save()
                response_data = {
                    "success": True,
                    "units": float(token_obj.units),
                    "message": "Token decrypted and units added",
                    "status": status.HTTP_200_OK
                }
                return Response(response_data, status=status.HTTP_200_OK)
            else:
                response_data = {
                    "success": False,
                    "message": "Either meter or token not found or token already used",
                }
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
        except MeterToken.DoesNotExist:
            message = "Token not found"
            response_data = {
                "success": False,
                "error": message,
            }
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Token decryption error: {str(e)}")
            return Response({
                "success": False,
                "message": "Internal server error"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LoanTokenVerificationView(APIView):
    """
    API endpoint for ESP32 to verify loan tokens and transfer units
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        """Docs for browsable API"""
        return Response({
            "message": "This endpoint accepts POST requests for loan token verification (for ESP32).",
            "required_fields": {
                "token": "The loan token to verify",
                "meter_number": "The meter number"
            },
            "example_payload": {
                "token": "example_loan_token_123",
                "meter_number": "METER123"
            },
            "response_format": {
                "success": True,
                "units_transferred": 50.5,  # Example
                "message": "Token verified successfully"
            }
        })

    def post(self, request, *args, **kwargs):
        token = request.data.get('token')
        meter_number = request.data.get('meter_number')
        
        logger.info(f"Token verification request - Token: {token}, Meter: {meter_number}")
        
        if not token or not meter_number:
            return Response({
                "success": False,
                "message": "Token and meter number are required"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Check if token exists in LoanDisbursement
            disbursement = get_object_or_404(
                LoanDisbursement, 
                token=token,
                token_expiry__gte=timezone.now() 
            )
            
            # Verify meter exists (Fixed: Use model's 'meter_no' field)
            meter = get_object_or_404(Meter, meter_no=meter_number)  # Changed: meter_no instead of meter_number
            
            # Check if token is already used
            if MeterToken.objects.filter(token=token, is_used=True).exists():
                return Response({
                    "success": False,
                    "message": "Token has already been used"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Transfer units to meter
            with transaction.atomic():
                # Update meter units
                meter.units += disbursement.units_disbursed
                meter.save()
                
                # Create MeterToken record to mark as used
                meter_token, created = MeterToken.objects.get_or_create(
                    token=token,
                    defaults={
                        'units': disbursement.units_disbursed,
                        'meter': meter,
                        'user': disbursement.loan_application.user,
                        'is_used': True,
                        'source': 'LOAN',
                        'loan_application': disbursement.loan_application
                    }
                )
                
                if not created:
                    meter_token.is_used = True
                    meter_token.save()
            
            logger.info(f"Token verified successfully. Units transferred: {disbursement.units_disbursed}")
            
            return Response({
                "success": True,
                "message": "Token verified successfully",
                "units_transferred": float(disbursement.units_disbursed),
                "loan_id": disbursement.loan_application.loan_id,
                "meter_number": meter_number,
                "token_expiry": disbursement.token_expiry.isoformat()
            }, status=status.HTTP_200_OK)
            
        except LoanDisbursement.DoesNotExist:
            return Response({
                "success": False,
                "message": "Invalid token or token expired"
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Meter.DoesNotExist:
            return Response({
                "success": False,
                "message": "Meter not found"
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"Token verification error: {str(e)}")
            return Response({
                "success": False,
                "message": "Internal server error"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ThingsBoardLowUnitsWebhookView(APIView):
    """
    POST /webhooks/thingsboard/low-units

    Inbound webhook from ThingsBoard when an AMI meter's remaining_units <= threshold.
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        configured_secret = (getattr(settings, "THINGSBOARD_WEBHOOK_SECRET", "") or "").strip()
        if configured_secret:
            header_secret = (request.headers.get("X-ThingsBoard-Webhook-Secret") or "").strip()
            if header_secret != configured_secret:
                return Response(
                    {"success": False, "message": "Invalid webhook secret."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

        device_token = str(request.data.get("device_token", "")).strip()
        units_raw = request.data.get("units_kwh")
        occurred_raw = request.data.get("occurred_at")

        if not device_token or units_raw is None or not occurred_raw:
            return Response(
                {"success": False, "message": "device_token, units_kwh, and occurred_at are required."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        try:
            units_kwh = Decimal(str(units_raw))
        except (InvalidOperation, TypeError, ValueError):
            return Response(
                {"success": False, "message": "units_kwh must be a number."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        occurred_at = parse_datetime(str(occurred_raw))
        if occurred_at is None:
            return Response(
                {"success": False, "message": "occurred_at must be a valid ISO-8601 datetime."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        if timezone.is_naive(occurred_at):
            occurred_at = timezone.make_aware(occurred_at, timezone.get_current_timezone())

        meter = (
            Meter.objects.filter(
                iot_device_token=device_token,
                architecture=Meter.ARCH_AMI,
                status=Meter.STATUS_ACTIVE,
            )
            .select_related("user")
            .first()
        )
        if not meter:
            return Response(
                {"success": False, "message": "No active AMI meter found for this device token."},
                status=status.HTTP_404_NOT_FOUND,
            )

        from meter.low_units_alerts import (
            create_low_units_notification,
            low_units_threshold_kwh,
            should_send_low_units_alert,
        )
        from meter.models import MeterBalanceSnapshot
        from meter.services import record_balance_snapshot

        previous_snap = (
            MeterBalanceSnapshot.objects.filter(meter=meter)
            .order_by("-recorded_at")
            .first()
        )
        previous = (
            Decimal(str(previous_snap.remaining_kwh)) if previous_snap is not None else None
        )

        record_balance_snapshot(meter, units_kwh, source="thingsboard_webhook")

        if units_kwh > low_units_threshold_kwh():
            return Response(
                {
                    "success": True,
                    "skipped": "above_threshold",
                    "units_kwh": float(units_kwh),
                },
                status=status.HTTP_200_OK,
            )

        if not should_send_low_units_alert(meter, units_kwh, previous):
            return Response(
                {
                    "success": True,
                    "skipped": "cooldown",
                    "units_kwh": float(units_kwh),
                },
                status=status.HTTP_200_OK,
            )

        user = meter.user
        owner_name = user.first_name or user.email
        notification = create_low_units_notification(
            meter,
            units_kwh,
            source="webhook",
            occurred_at=occurred_at,
        )
        if not notification:
            return Response(
                {"success": False, "message": "Meter has no assigned user."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        email_queued = bool(user.email)

        logger.info(
            "ThingsBoard low-units webhook: user=%s meter=%s units=%s notification=%s",
            user.id,
            meter.meter_no,
            units_kwh,
            notification.id,
        )

        return Response(
            {
                "success": True,
                "notification_id": notification.id,
                "user_id": user.id,
                "owner_name": owner_name,
                "email_queued": email_queued,
            },
            status=status.HTTP_201_CREATED,
        )


class ThingsBoardDailyUsageWebhookView(APIView):
    """
    POST /webhooks/thingsboard/daily-usage

    Inbound webhook from ThingsBoard rule chain with daily kWh consumption.
    Body: { device_token, usage_date (YYYY-MM-DD), kwh_used }
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        from meter.models import MeterUsageDaily
        from meter.usage_service import upsert_daily_usage

        configured_secret = (getattr(settings, "THINGSBOARD_WEBHOOK_SECRET", "") or "").strip()
        if configured_secret:
            header_secret = (request.headers.get("X-ThingsBoard-Webhook-Secret") or "").strip()
            if header_secret != configured_secret:
                return Response(
                    {"success": False, "message": "Invalid webhook secret."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

        device_token = str(request.data.get("device_token", "")).strip()
        usage_date_raw = request.data.get("usage_date")
        kwh_raw = request.data.get("kwh_used")

        if not device_token or not usage_date_raw or kwh_raw is None:
            return Response(
                {
                    "success": False,
                    "message": "device_token, usage_date, and kwh_used are required.",
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        try:
            usage_date = date.fromisoformat(str(usage_date_raw)[:10])
            kwh_used = Decimal(str(kwh_raw))
            if kwh_used < 0:
                raise ValueError
        except (InvalidOperation, TypeError, ValueError):
            return Response(
                {"success": False, "message": "Invalid usage_date or kwh_used."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        meter = (
            Meter.objects.filter(
                iot_device_token=device_token,
                architecture=Meter.ARCH_AMI,
                status=Meter.STATUS_ACTIVE,
            )
            .first()
        )
        if not meter:
            return Response(
                {"success": False, "message": "No active AMI meter found for this device token."},
                status=status.HTTP_404_NOT_FOUND,
            )

        row = upsert_daily_usage(
            meter,
            usage_date,
            kwh_used,
            MeterUsageDaily.SOURCE_WEBHOOK,
        )

        logger.info(
            "ThingsBoard daily-usage webhook: meter=%s date=%s kwh=%s",
            meter.meter_no,
            usage_date,
            kwh_used,
        )

        return Response(
            {
                "success": True,
                "meter_no": meter.meter_no,
                "usage_date": usage_date.isoformat(),
                "kwh_used": float(row.kwh_used),
            },
            status=status.HTTP_201_CREATED,
        )
