from backend.features import requires_feature
import random
import uuid
from decimal import Decimal, InvalidOperation
from django.forms import ValidationError
import requests
import logging
import traceback
from django.conf import settings
from django.http import JsonResponse
from meter.models import Meter, MeterToken
from meter.models import Transaction as MeterLedgerTransaction
from meter.services import (
    push_units_to_thingsboard,
    query_latest_units_from_thingsboard,
    record_balance_snapshot,
    _thingsboard_base_url,
)
from accounts.models import User
from mtn_momo.services import MTNMoMoService
from transactions.models import UnitTransaction, TransactionLog, TransactionType
from .serializers import SendUnitSerializer, TokenSerializer
from ..models import generate_random_string, generate_numeric_token
from rest_framework.generics import (
    CreateAPIView,
    GenericAPIView,
)
from loan.credit_score_service import CreditScoreService
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from utils.models import UnitReceiverResponse
from rest_framework import generics, permissions
from .serializers import MeterSerializer
from meter.models import Meter
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import time
import threading
from transactions.models import Transaction, UnitTransaction, TransactionType
from transactions.services import record_transaction_log
from accounts.models import Wallet as AccountWallet
from wallet.models import Wallet as MoneyWallet
from wallet.models import Wallet as UnitWallet
import time
import threading
from django.db import transaction as db_transaction
from loan.models import ElectricityTariff, LoanApplication, LoanRepayment
from utils.ami_gateway import apply_units_to_meter
# from transactions.api.generate_token import generate_numeric_token
import traceback
from wallet.models import UnitBalance 


base_url = settings.BASE_URL

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ami_meter_status(request):
    """
    GET /api/v1/meter/ami-status/?meter_no=...

    Returns connectivity and balance sync status for an AMI meter owned by the user.
    """
    meter_no = request.query_params.get("meter_no")
    if not meter_no:
        return Response({"error": "meter_no is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        meter = Meter.objects.get(user=request.user, meter_no=meter_no)
    except Meter.DoesNotExist:
        return Response(
            {"error": "Meter not found or not owned by you."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if meter.architecture != Meter.ARCH_AMI:
        return Response(
            {"error": "This endpoint is only for AMI meters."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from utils.ami_gateway import get_ami_gateway

    gateway_status = get_ami_gateway().get_status(meter)
    unit_wallet = UnitWallet.objects.filter(user=request.user).first()
    wallet_balance = float(unit_wallet.balance) if unit_wallet else 0.0

    if gateway_status is None:
        return Response(
            {
                "success": False,
                "is_online": False,
                "meter_no": meter.meter_no,
                "current_balance_kwh": float(meter.units),
                "wallet_balance": wallet_balance,
                "message": "Meter unreachable.",
            },
            status=status.HTTP_200_OK,
        )

    return Response(
        {
            "success": True,
            "is_online": gateway_status.is_online,
            "last_seen": gateway_status.last_seen,
            "meter_no": gateway_status.meter_no,
            "current_balance_kwh": gateway_status.current_balance_kwh,
            "wallet_balance": wallet_balance,
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def meter_ledger_history(request):
    """
    GET /api/v1/meter/ledger-history/?meter_no=...

    Credits that contribute to the meter ledger balance (``meter.units``).
    """
    meter_no = request.query_params.get("meter_no")
    if not meter_no:
        return Response({"error": "meter_no is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        meter = Meter.objects.get(user=request.user, meter_no=meter_no)
    except Meter.DoesNotExist:
        return Response(
            {"error": "Meter not found or not owned by you."},
            status=status.HTTP_404_NOT_FOUND,
        )

    from meter.ledger import get_meter_ledger_history

    payload = get_meter_ledger_history(meter)
    return Response({"success": True, **payload}, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def thingsboard_health(request):
    """
    GET /api/v1/meter/thingsboard-health/

    Diagnostic: which ThingsBoard URL Django uses and whether it can connect.
    """
    from meter.services import (
        _thingsboard_base_url,
        _thingsboard_public_base_url,
        _thingsboard_request_kwargs,
    )

    base = _thingsboard_base_url()
    public = _thingsboard_public_base_url()
    internal = (getattr(settings, "THINGSBOARD_INTERNAL_BASE_URL", "") or "").strip()

    try:
        response = requests.get(f"{base}/", **_thingsboard_request_kwargs())
        return Response(
            {
                "success": True,
                "thingsboard_url_in_use": base,
                "thingsboard_base_url": public,
                "thingsboard_internal_base_url": internal or None,
                "http_status": response.status_code,
            },
            status=status.HTTP_200_OK,
        )
    except requests.RequestException as exc:
        return Response(
            {
                "success": False,
                "thingsboard_url_in_use": base,
                "thingsboard_base_url": public,
                "thingsboard_internal_base_url": internal or None,
                "error": f"{exc.__class__.__name__}: {exc}",
                "hint": (
                    "Set THINGSBOARD_BASE_URL=http://127.0.0.1:9090 (or THINGSBOARD_INTERNAL_BASE_URL) "
                    "in backend/.env and restart gunicorn."
                ),
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_meter_units(request):
    """
    GET /api/v1/meter/check-units/?meter_no=...

    On-demand read of live remaining kWh from ThingsBoard (shared attribute remaining_units).
    """
    meter_no = request.query_params.get("meter_no")
    if not meter_no:
        return Response({"error": "meter_no is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        meter = Meter.objects.get(user=request.user, meter_no=meter_no)
    except Meter.DoesNotExist:
        return Response(
            {"error": "Meter not found or not owned by you."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if meter.architecture != Meter.ARCH_AMI:
        return Response(
            {"error": "Check units is only available for AMI meters."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from meter.ami_delivery import retry_pending_for_meter

    retry_result = retry_pending_for_meter(meter)
    meter.refresh_from_db(fields=["units", "pending_units"])

    ok, msg, data = query_latest_units_from_thingsboard(meter)
    if not ok and meter.units > 0 and meter.pending_units <= 0:
        from meter.services import set_shared_remaining_units

        bootstrap_ok, _bootstrap_msg = set_shared_remaining_units(meter, meter.units)
        if bootstrap_ok:
            ok, msg, data = query_latest_units_from_thingsboard(meter)
    if not ok or not data:
        return Response(
            {
                "success": False,
                "meter_no": meter.meter_no,
                "message": msg,
                "units_balance_kwh": float(meter.units),
                "thingsboard_host": _thingsboard_base_url(),
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )

    record_balance_snapshot(
        meter,
        data["units_kwh"],
        source=data.get("source", "thingsboard"),
    )

    return Response(
        {
            "success": True,
            "meter_no": meter.meter_no,
            "units_kwh": data["units_kwh"],
            "queried_at": data["queried_at"],
            "units_balance_kwh": float(meter.units),
            "pending_delivery_kwh": float(meter.pending_units),
            "pending_retry": retry_result,
            "source": data.get("source", "thingsboard"),
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def meter_notifications(request):
    """
    GET  /api/v1/meter/notifications/ — list meter alerts (e.g. low-units from ThingsBoard).
    PATCH /api/v1/meter/notifications/ — mark notifications read: {"ids": [1,2]} or {"all": true}
    """
    from meter.models import MeterNotification

    if request.method == "GET":
        unread_only = request.query_params.get("unread", "").lower() in ("1", "true", "yes")
        qs = MeterNotification.objects.filter(user=request.user)
        if unread_only:
            qs = qs.filter(is_read=False)
        qs = qs.select_related("meter")[:50]
        items = [
            {
                "id": n.id,
                "notification_type": n.notification_type,
                "units_kwh": float(n.units_kwh),
                "occurred_at": n.occurred_at.isoformat(),
                "is_read": n.is_read,
                "message": n.message,
                "meter_no": n.meter.meter_no if n.meter else None,
                "meter_label": n.meter.label if n.meter else None,
            }
            for n in qs
        ]
        unread_count = MeterNotification.objects.filter(user=request.user, is_read=False).count()
        return Response(
            {"success": True, "notifications": items, "unread_count": unread_count},
            status=status.HTTP_200_OK,
        )

    ids = request.data.get("ids")
    mark_all = request.data.get("all") is True
    qs = MeterNotification.objects.filter(user=request.user, is_read=False)
    if mark_all:
        updated = qs.update(is_read=True)
    elif ids:
        updated = qs.filter(id__in=ids).update(is_read=True)
    else:
        return Response(
            {"error": "Provide 'ids' list or {'all': true}."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response({"success": True, "marked_read": updated}, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def power_usage(request):
    """
    GET /api/v1/meter/power-usage/

    AMI-only energy consumption reports (daily series + summary).
    Query params: meter_no, period=week|month|year, year, month
    """
    from meter.usage_service import get_power_usage_report

    period = request.query_params.get("period", "week")
    meter_no = request.query_params.get("meter_no")
    year_raw = request.query_params.get("year")
    month_raw = request.query_params.get("month")

    year = int(year_raw) if year_raw and year_raw.isdigit() else None
    month = int(month_raw) if month_raw and month_raw.isdigit() else None

    report = get_power_usage_report(
        request.user,
        meter_no=meter_no,
        period=period,
        year=year,
        month=month,
    )
    status_code = status.HTTP_200_OK if report.get("eligible", True) else status.HTTP_200_OK
    return Response({"success": True, "data": report}, status=status_code)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_user_meter(request):
    try:
        meters = Meter.objects.filter(user=request.user).order_by('create_date')
        if not meters.exists():
            return Response({
                'success': True,
                'data': {
                    'has_meter': False,
                    'message': 'No meter registered for this account'
                }
            }, status=status.HTTP_200_OK)

        meters_list = [
            {
                'meter_number': m.meter_no,
                'static_ip': m.static_ip,
                'units': float(m.units),
                'architecture': m.architecture,
                'pending_units': float(m.pending_units),
                'status': m.status,
                'label': m.label,
                'has_iot_token': bool((m.iot_device_token or '').strip()),
            }
            for m in meters
        ]
        primary = meters_list[0]
        return Response({
            'success': True,
            'data': {
                'has_meter': True,
                'meters': meters_list,
                # backward-compat single-meter fields (first registered meter)
                'meter_number': primary['meter_number'],
                'static_ip': primary['static_ip'],
                'units': primary['units'],
                'architecture': primary['architecture'],
                'pending_units': primary['pending_units'],
            }
        })
    except Exception as e:
        logger.error(f"Error checking user meter: {str(e)}")
        return Response({
            'success': False,
            'error': 'Server Error',
            'message': 'Failed to check meter status'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_meter(request):
    """
    Update existing meter information
    """
    try:
        user = request.user
        data = request.data
        
        # Identify which meter to update (supports multiple meters per account)
        current_meter_no = data.get('current_meter_no') or data.get('original_meter_no')
        user_meters = Meter.objects.filter(user=user)

        if current_meter_no:
            try:
                meter = user_meters.get(meter_no=current_meter_no)
            except Meter.DoesNotExist:
                return Response(
                    {"error": "Meter not found on your account"},
                    status=status.HTTP_404_NOT_FOUND
                )
        elif user_meters.count() == 1:
            meter = user_meters.first()
        else:
            return Response(
                {
                    "success": False,
                    "error": "Meter Required",
                    "message": "Specify which meter to update using current_meter_no.",
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate meter number uniqueness (excluding current meter)
        new_meter_no = data.get('meter_no')
        if new_meter_no and new_meter_no != meter.meter_no:
            if Meter.objects.filter(meter_no=new_meter_no).exclude(id=meter.id).exists():
                return Response({
                    "success": False,
                    "error": "Duplicate Meter Number",
                    "message": "This meter number is already registered to another account."
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update fields
        serializer = MeterSerializer(meter, data=data, partial=True)
        if serializer.is_valid():
            updated_meter = serializer.save()
            
            logger.info(f"Meter updated for user {user.id}: {updated_meter.meter_no}")
            
            return Response({
                "success": True,
                "message": "Meter updated successfully",
                "data": MeterSerializer(updated_meter).data
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                "success": False,
                "error": "Validation Error",
                "message": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Meter update error: {str(e)}")
        return Response({
            "success": False,
            "error": "Update Failed",
            "message": "Failed to update meter. Please try again."
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def delete_user_meter(request):
    """
    POST/DELETE /api/v1/meter/delete/

    Remove a meter from the authenticated user's account. Writes DeletedMeterRecord
    and soft-deletes the meter so the number can be registered again later.
    """
    from meter.lifecycle import MeterDeleteError, release_meter_from_account
    from meter.models import DeletedMeterRecord

    meter_no = request.data.get("meter_no") or request.query_params.get("meter_no")
    reason = (request.data.get("reason") or "").strip()

    if not meter_no:
        return Response(
            {"error": "meter_no is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        meter = Meter.objects.get(user=request.user, meter_no=meter_no)
    except Meter.DoesNotExist:
        return Response(
            {"error": "Meter not found on your account."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        record = release_meter_from_account(
            meter,
            deleted_by=request.user,
            deleted_by_role=DeletedMeterRecord.ROLE_USER,
            reason=reason,
            metadata={"channel": "WEB_PORTAL"},
        )
    except MeterDeleteError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        logger.error("delete_user_meter error: %s", exc, exc_info=True)
        return Response(
            {"error": "Failed to remove meter."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(
        {
            "success": True,
            "message": (
                f"Meter {record.original_meter_no} removed from your account. "
                "You can register it again later if needed."
            ),
            "deleted_meter_no": record.original_meter_no,
            "deletion_record_id": record.id,
        },
        status=status.HTTP_200_OK,
    )


class MeterRegisterView(generics.CreateAPIView):
    serializer_class = MeterSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Check if meter number already exists
            meter_no = request.data.get('meter_no')
            if Meter.objects.filter(meter_no=meter_no).exists():
                return Response({
                    "success": False,
                    "error": "Duplicate Meter Number",
                    "message": "This meter number is already registered to another account."
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Save with user
            meter = serializer.save(user=request.user)
            
            return Response({
                "success": True,
                "message": "Meter registered successfully",
                "data": MeterSerializer(meter).data
            }, status=status.HTTP_201_CREATED)
            
        except ValidationError as e:
            return Response({
                "success": False,
                "error": "Validation Error",
                "message": str(e),
                "details": e.message_dict if hasattr(e, 'message_dict') else None
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Meter registration error: {str(e)}\n{traceback.format_exc()}")
            return Response(
                {
                    "success": False,
                    "error": "Registration Failed",
                    "message": "Failed to register meter. Please try again or contact support."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _validate_ip_address(self, ip):
        """Validate IP address format"""
        import socket
        try:
            socket.inet_aton(ip)
            return True
        except socket.error:
            return False


class SendUnitsView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = SendUnitSerializer

    @requires_feature("peer_sharing")
    def post(self, request, *args, **kwargs):
        try:
            serializer = self.serializer_class(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            receiver_meter_no = request.data.get("receiver_meter_no")
            user = request.user
            units_to_send = request.data.get('no_units')
            user_message = request.data.get('message', '')

            # Validate units
            try:
                units_to_send = int(units_to_send)
                if units_to_send <= 0:
                    return Response({
                        "success": False,
                        "error": "Invalid Units",
                        "message": "Number of units must be greater than 0"
                    }, status=status.HTTP_400_BAD_REQUEST)
            except (ValueError, TypeError):
                return Response({
                    "success": False,
                    "error": "Invalid Units",
                    "message": "Please enter a valid number of units"
                }, status=status.HTTP_400_BAD_REQUEST)

            # Get meters
            try:
                sender_meter = Meter.objects.get(user=user)
                receiver_meter = Meter.objects.get(meter_no=receiver_meter_no)
                
                # Prevent sending to own meter
                if sender_meter.id == receiver_meter.id:
                    return Response({
                        "success": False,
                        "error": "Invalid Operation",
                        "message": "Cannot send units to your own meter"
                    }, status=status.HTTP_400_BAD_REQUEST)
                
            except Meter.DoesNotExist:
                return Response({
                    "success": False,
                    "error": "Meter Not Found",
                    "message": "One or both meters were not found. Please check the meter numbers."
                }, status=status.HTTP_404_NOT_FOUND)

            # Check sender has enough units
            if sender_meter.units < units_to_send:
                return Response({
                    "success": False,
                    "error": "Insufficient Units",
                    "message": f"You only have {sender_meter.units} units available",
                    "available_units": sender_meter.units,
                    "requested_units": units_to_send
                }, status=status.HTTP_400_BAD_REQUEST)

            # Create transaction record
            sender_transaction = UnitTransaction.objects.create(
                sender=user,
                transaction_id=generate_random_string(16),
                receiver=receiver_meter.user,
                units=units_to_send,
                direction="Out",
                meter=receiver_meter,
                message=user_message,
                status="PENDING"
            )

            try:
                # Send request to ESP32 meter
                payload = {"units": units_to_send}
                url = f"http://{receiver_meter.static_ip}/process"
                
                response = requests.post(url, json=payload, timeout=10)
                response.raise_for_status()  # Raise exception for bad status codes
                
                # Update database if ESP32 responds successfully
                with db_transaction.atomic():
                    sender_meter.units -= units_to_send
                    sender_meter.save()
                    
                    receiver_meter.units += units_to_send
                    receiver_meter.save()
                    
                    sender_transaction.status = "COMPLETED"
                    sender_transaction.save()

                return Response({
                    "success": True,
                    "message": f"Successfully sent {units_to_send} units to {receiver_meter_no}",
                    "data": {
                        "transaction_id": sender_transaction.transaction_id,
                        "units_sent": units_to_send,
                        "receiver_meter": receiver_meter_no,
                        "remaining_units": sender_meter.units,
                        "timestamp": sender_transaction.created_at.isoformat()
                    }
                }, status=status.HTTP_200_OK)
                
            except requests.exceptions.Timeout:
                sender_transaction.status = "TIMEOUT"
                sender_transaction.save()
                
                return Response({
                    "success": False,
                    "error": "Connection Timeout",
                    "message": "The meter is not responding. Please try again later.",
                    "transaction_id": sender_transaction.transaction_id
                }, status=status.HTTP_408_REQUEST_TIMEOUT)
                
            except requests.exceptions.ConnectionError:
                sender_transaction.status = "CONNECTION_ERROR"
                sender_transaction.save()
                
                return Response({
                    "success": False,
                    "error": "Connection Failed",
                    "message": "Unable to connect to the meter. Please check the meter's network connection.",
                    "transaction_id": sender_transaction.transaction_id
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
                
            except requests.exceptions.RequestException as e:
                sender_transaction.status = "FAILED"
                sender_transaction.save()
                
                logger.error(f"ESP32 request failed: {str(e)}")
                return Response({
                    "success": False,
                    "error": "Transfer Failed",
                    "message": "Failed to send units to the meter. Please try again.",
                    "transaction_id": sender_transaction.transaction_id
                }, status=status.HTTP_502_BAD_GATEWAY)
                
        except Exception as e:
            logger.error(f"Send units error: {str(e)}\n{traceback.format_exc()}")
            return Response({
                "success": False,
                "error": "Server Error",
                "message": "An unexpected error occurred. Please try again."
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            

class ReceiveUnitsView(APIView):


    @requires_feature("peer_sharing")
    def post(self, request, *args, **kwargs):
        meter_info = request.data
        logger.info(
            f"Receiver function called"
        )

        data = UnitReceiverResponse(**meter_info)
        receiver_meter_no = data.receiver_meter_no
        sender_meter_no = data.sender_meter_no
        no_units = data.units
        user_message = "from emorut"

        print(f"{receiver_meter_no}")
        print(f"{sender_meter_no}")
        print(f"{no_units}")

        try:
            receiver_meter = Meter.objects.get(meter_no=receiver_meter_no)
            sender_meter = Meter.objects.get(meter_no=sender_meter_no)
            
            if receiver_meter and sender_meter:
                units_to_send = no_units # Units to add

                if units_to_send == 0:
                    message = (
                        "Unit can not be 0"
                    )
                    response_data = {
                        "message": message,
                    }
                    return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

                if not units_to_send:
                    message = (
                        "Invalid units value"
                    )
                    response_data = {
                        "message": message,
                    }
                    return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                
                units_to_receive = int(units_to_send)
                
                # Ensure there are enough units in the system
                if sender_meter.units < units_to_receive:
                    message = (
                        "You don't have enough units"
                    )
                    response_data = {
                        "error": message,
                    }
                    return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
                
                sender_transaction = UnitTransaction.objects.create(
                    sender=sender_meter.user,
                    transaction_id=generate_random_string(16),
                    receiver=receiver_meter.user,
                    units=units_to_send,
                    direction="In",
                    meter=receiver_meter,
                    message=user_message

                )


                # # Prepare data to send to the ESP32 meter
                payload = {"units": units_to_send}
                url = f"http://{receiver_meter.static_ip}/process"
                # Send HTTP request to the ESP32
                response = requests.post(url, json=payload, timeout=5) 

                if response.status_code == 200:
                    # Update the units in the database
                    sender_meter.units -= units_to_send
                    sender_meter.save()
                    receiver_meter.units += units_to_send
                    receiver_meter.save()
                    print("subtracted units")
                    sender_transaction.status = "COMPLETED"
                    sender_transaction.save()

                    message = (
                        "success"
                    )
                    response_data = {
                        "status": message,
                    }
                    return Response(response_data, status=status.HTTP_200_OK)
                else:
                    sender_transaction.status = "FAILED"
                    sender_transaction.save()
                    message = (
                        "Failed to send units"
                    )
                    response_data = {
                        "error": message,
                    }
                    return Response(response_data, status=status.HTTP_400_BAD_REQUEST) 
                
            else:
                message = (
                        "Either sender meter or receiver meter does not exist"
                )
                response_data = {
                        "error": message,
                }
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)  
        except Meter.DoesNotExist:
            message = (
                "Meter not found"
            )
            response_data = {
                "error": message,
            }
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
        

class TokenView(GenericAPIView):

    permission_classes = (IsAuthenticated,)
    serializer_class = TokenSerializer
    def get(self, request, *args, **kwargs):
        user = request.user
        meter_no = request.query_params.get("meter_no")

        try:
            if meter_no:
                user_meters = Meter.objects.filter(user=user, meter_no=meter_no)
            else:
                user_meters = Meter.objects.filter(user=user)

            if not user_meters.exists():
                return Response({"data": []}, status=status.HTTP_200_OK)

            token_data = MeterToken.objects.filter(meter__in=user_meters).order_by('-id')[:20]
            serializer = self.serializer_class(token_data, many=True)
            
            response_data = {
            "data": serializer.data
            
            }
            return Response(response_data, status=status.HTTP_200_OK)
        except Meter.DoesNotExist:
            return Response({
                "data": {
                    "data": []
                }
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching tokens: {str(e)}")
            return Response({
                "error": "Failed to fetch tokens"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
   

   
class ActivateReceivedUnitsView(APIView):
    """
    POST /api/v1/meter/activate-received-units/

    For STS meters: converts pending_units into a MeterToken the user can enter
    on the physical keypad to load the units. Clears pending_units on success.

    For AMI meters: units are already applied — returns 409 with a clear message.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response({
            "code": "DEVICE_PROTOCOL_UNAVAILABLE",
            "message": "STS token provisioning is paused until an authenticated meter protocol is validated.",
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        user = request.user
        meter_no = request.data.get("meter_no")

        if meter_no:
            try:
                meter = Meter.objects.get(user=user, meter_no=meter_no)
            except Meter.DoesNotExist:
                return Response({"error": "Meter not found or not owned by you."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            user_meters = Meter.objects.filter(user=user, architecture=Meter.ARCH_STS)
            if not user_meters.exists():
                return Response({"error": "No STS meter registered."}, status=status.HTTP_400_BAD_REQUEST)
            if user_meters.count() > 1:
                return Response(
                    {"error": "You have multiple STS meters. Please specify meter_no."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            meter = user_meters.first()

        if meter.architecture == Meter.ARCH_AMI:
            return Response(
                {"error": "AMI meter — units are applied automatically; no token needed."},
                status=status.HTTP_409_CONFLICT,
            )

        if meter.pending_units <= 0:
            return Response(
                {"error": "No pending units to activate. Buy or receive units first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with db_transaction.atomic():
                units = meter.pending_units
                # Lock the row to prevent double-activation
                locked_meter = Meter.objects.select_for_update().get(pk=meter.pk)
                if locked_meter.pending_units <= 0:
                    return Response(
                        {"error": "Pending units already activated."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                token_value = generate_numeric_token(10)
                MeterToken.objects.create(
                    user=user,
                    token=token_value,
                    units=units,
                    meter=locked_meter,
                    source='SHARE',
                )
                locked_meter.pending_units = 0
                locked_meter.save(update_fields=['pending_units'])

            return Response(
                {
                    "success": True,
                    "token": token_value,
                    "units": float(units),
                    "message": f"Enter this token on your meter keypad to load {float(units):.2f} kWh.",
                },
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            logger.error("ActivateReceivedUnitsView error: %s", exc, exc_info=True)
            return Response({"error": "Failed to generate token."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# class GenerateTokenFromWalletView(APIView):
#     """
#     POST /api/v1/meter/generate-token/

#     STS meters: draws `amount` kWh from the user's unit wallet and returns
#     a 10-digit token the user enters on the physical meter keypad.
#     AMI meters receive balance updates over the network — no token needed.
#     """
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         user = request.user
#         meter_no = request.data.get("meter_no")

#         if meter_no:
#             try:
#                 meter = Meter.objects.get(user=user, meter_no=meter_no)
#             except Meter.DoesNotExist:
#                 return Response({"error": "Meter not found or not owned by you."}, status=status.HTTP_400_BAD_REQUEST)
#         else:
#             sts_meters = Meter.objects.filter(user=user, architecture=Meter.ARCH_STS)
#             if not sts_meters.exists():
#                 if Meter.objects.filter(user=user, architecture=Meter.ARCH_AMI).exists():
#                     return Response(
#                         {
#                             "error": (
#                                 "AMI meter — units are applied automatically over the network. "
#                                 "No token needed."
#                             )
#                         },
#                         status=status.HTTP_409_CONFLICT,
#                     )
#                 return Response({"error": "No meter registered."}, status=status.HTTP_400_BAD_REQUEST)
#             if sts_meters.count() > 1:
#                 return Response(
#                     {"error": "You have multiple STS meters. Please specify meter_no."},
#                     status=status.HTTP_400_BAD_REQUEST,
#                 )
#             meter = sts_meters.first()

#         if meter.architecture == Meter.ARCH_AMI:
#             return Response(
#                 {"error": "AMI meter — units are applied automatically over the network. No token needed."},
#                 status=status.HTTP_409_CONFLICT,
#             )

#         raw = request.data.get("amount")
#         try:
#             amount = Decimal(str(raw))
#             if amount <= 0:
#                 raise ValueError
#         except (InvalidOperation, ValueError, TypeError):
#             return Response(
#                 {"error": "Provide a positive numeric kWh amount."},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         unit_wallet = UnitWallet.objects.filter(user=user).first()
#         if not unit_wallet:
#             return Response(
#                 {"error": "No unit wallet found. Buy units first."},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         if unit_wallet.balance < amount:
#             return Response(
#                 {
#                     "error": f"Insufficient wallet balance. Available: {float(unit_wallet.balance):.2f} kWh.",
#                     "available": float(unit_wallet.balance),
#                 },
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         try:
#             with db_transaction.atomic():
#                 locked_wallet = UnitWallet.objects.select_for_update().get(user=user)
#                 if locked_wallet.balance < amount:
#                     return Response(
#                         {"error": "Insufficient wallet balance."},
#                         status=status.HTTP_400_BAD_REQUEST,
#                     )
#                 locked_wallet.balance -= amount
#                 locked_wallet.save(update_fields=["balance"])

#                 token_value = generate_numeric_token(10)
#                 MeterToken.objects.create(
#                     user=user,
#                     token=token_value,
#                     units=amount,
#                     meter=meter,
#                     source="PURCHASE",
#                 )
#                 MeterLedgerTransaction.objects.create(
#                     user=user,
#                     meter=meter,
#                     transaction_type=MeterLedgerTransaction.TYPE_GENERATE_TOKEN,
#                     amount_kwh=amount,
#                     status=MeterLedgerTransaction.STATUS_COMPLETED,
#                     channel=MeterLedgerTransaction.CHANNEL_WEB,
#                     sts_token=token_value,
#                     source="wallet",
#                     destination=meter.meter_no,
#                     payment_reference=f"TOKEN-{token_value}",
#                 )
#                 record_transaction_log(
#                     user,
#                     TransactionType.TOKEN_GENERATE,
#                     units=amount,
#                     status="COMPLETED",
#                     reference_id=f"TOKEN-{token_value}",
#                     details={
#                         "channel": MeterLedgerTransaction.CHANNEL_WEB,
#                         "meter_no": meter.meter_no,
#                         "token": token_value,
#                     },
#                 )

#             return Response(
#                 {
#                     "success": True,
#                     "token": token_value,
#                     "units": float(amount),
#                     "remaining_balance": float(locked_wallet.balance),
#                     "message": (
#                         f"Enter this token on your meter keypad to load {float(amount):.2f} kWh."
#                     ),
#                 },
#                 status=status.HTTP_200_OK,
#             )
#         except Exception as exc:
#             logger.error("GenerateTokenFromWalletView error: %s", exc, exc_info=True)
#             return Response(
#                 {"error": "Failed to generate token."},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             )


class GenerateTokenFromWalletView(APIView):
    """
    POST /api/v1/meter/generate-token/

    STS meters: draws `amount` kWh from the user's unit balance and returns
    a 10-digit token the user enters on the physical meter keypad.
    AMI meters receive balance updates over the network — no token needed.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response({
            "code": "DEVICE_PROTOCOL_UNAVAILABLE",
            "message": "STS token provisioning is paused until an authenticated meter protocol is validated.",
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        user = request.user
        meter_no = request.data.get("meter_no")

        if meter_no:
            try:
                meter = Meter.objects.get(user=user, meter_no=meter_no)
            except Meter.DoesNotExist:
                return Response({"error": "Meter not found or not owned by you."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            sts_meters = Meter.objects.filter(user=user, architecture=Meter.ARCH_STS)
            if not sts_meters.exists():
                if Meter.objects.filter(user=user, architecture=Meter.ARCH_AMI).exists():
                    return Response(
                        {
                            "error": (
                                "AMI meter — units are applied automatically over the network. "
                                "No token needed."
                            )
                        },
                        status=status.HTTP_409_CONFLICT,
                    )
                return Response({"error": "No meter registered."}, status=status.HTTP_400_BAD_REQUEST)
            if sts_meters.count() > 1:
                return Response(
                    {"error": "You have multiple STS meters. Please specify meter_no."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            meter = sts_meters.first()

        if meter.architecture == Meter.ARCH_AMI:
            return Response(
                {"error": "AMI meter — units are applied automatically over the network. No token needed."},
                status=status.HTTP_409_CONFLICT,
            )

        raw = request.data.get("amount")
        try:
            amount = Decimal(str(raw))
            if not amount.is_finite() or amount <= 0:
                raise ValueError
        except (InvalidOperation, ValueError, TypeError):
            return Response(
                {"error": "Provide a positive numeric kWh amount."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # FIX: Use UnitBalance instead of UnitWallet
        unit_balance = UnitBalance.objects.filter(user=user).first()
        if not unit_balance:
            return Response(
                {"error": "No unit balance found. Buy units first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if unit_balance.balance < amount:
            return Response(
                {
                    "error": f"Insufficient unit balance. Available: {float(unit_balance.balance):.2f} kWh.",
                    "available": float(unit_balance.balance),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with db_transaction.atomic():
                # FIX: Lock UnitBalance instead of UnitWallet
                locked_balance = UnitBalance.objects.select_for_update().get(user=user)
                if locked_balance.balance < amount:
                    return Response(
                        {"error": "Insufficient unit balance."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                locked_balance.balance -= amount
                locked_balance.save(update_fields=["balance"])

                token_value = generate_numeric_token(10)
                MeterToken.objects.create(
                    user=user,
                    token=token_value,
                    units=amount,
                    meter=meter,
                    source="PURCHASE",
                )
                MeterLedgerTransaction.objects.create(
                    user=user,
                    meter=meter,
                    transaction_type=MeterLedgerTransaction.TYPE_GENERATE_TOKEN,
                    amount_kwh=amount,
                    status=MeterLedgerTransaction.STATUS_COMPLETED,
                    channel=MeterLedgerTransaction.CHANNEL_WEB,
                    sts_token=token_value,
                    source="wallet",
                    destination=meter.meter_no,
                    payment_reference=f"TOKEN-{token_value}",
                )
                record_transaction_log(
                    user,
                    TransactionType.TOKEN_GENERATE,
                    units=amount,
                    status="COMPLETED",
                    reference_id=f"TOKEN-{token_value}",
                    details={
                        "channel": MeterLedgerTransaction.CHANNEL_WEB,
                        "meter_no": meter.meter_no,
                        "token": token_value,
                    },
                )

            return Response(
                {
                    "success": True,
                    "token": token_value,
                    "units": float(amount),
                    "remaining_balance": float(locked_balance.balance),
                    "message": (
                        f"Enter this token on your meter keypad to load {float(amount):.2f} kWh."
                    ),
                },
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            logger.error("GenerateTokenFromWalletView error: %s", exc, exc_info=True)
            return Response(
                {"error": "Failed to generate token."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# class ApplyWalletToMeterView(APIView):
#     """
#     POST /api/v1/meter/apply-wallet-units/

#     AMI meters: debit the user's unit wallet and push kWh to the meter over the network.
#     STS meters: use /meter/generate-token/ to obtain a keypad token instead.
#     """
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         user = request.user
#         meter_no = request.data.get("meter_no")

#         if meter_no:
#             try:
#                 meter = Meter.objects.get(user=user, meter_no=meter_no)
#             except Meter.DoesNotExist:
#                 return Response(
#                     {"error": "Meter not found or not owned by you."},
#                     status=status.HTTP_400_BAD_REQUEST,
#                 )
#         else:
#             ami_meters = Meter.objects.filter(user=user, architecture=Meter.ARCH_AMI)
#             if not ami_meters.exists():
#                 return Response(
#                     {
#                         "error": (
#                             "No AMI meter found. STS meters require a token — "
#                             "use Generate STS Token on the dashboard."
#                         )
#                     },
#                     status=status.HTTP_400_BAD_REQUEST,
#                 )
#             if ami_meters.count() > 1:
#                 return Response(
#                     {"error": "You have multiple AMI meters. Please specify meter_no."},
#                     status=status.HTTP_400_BAD_REQUEST,
#                 )
#             meter = ami_meters.first()

#         if meter.architecture != Meter.ARCH_AMI:
#             return Response(
#                 {
#                     "error": (
#                         "This action is for AMI meters only. "
#                         "STS meters need a token — use Generate STS Token."
#                     ),
#                     "architecture": meter.architecture,
#                 },
#                 status=status.HTTP_409_CONFLICT,
#             )

#         raw = request.data.get("amount")
#         try:
#             amount = Decimal(str(raw))
#             if amount <= 0:
#                 raise ValueError
#         except (InvalidOperation, ValueError, TypeError):
#             return Response(
#                 {"error": "Provide a positive numeric kWh amount."},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         unit_wallet = UnitWallet.objects.filter(user=user).first()
#         if not unit_wallet or unit_wallet.balance < amount:
#             available = float(unit_wallet.balance) if unit_wallet else 0.0
#             return Response(
#                 {
#                     "error": f"Insufficient wallet balance. Available: {available:.2f} kWh.",
#                     "available": available,
#                 },
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         try:
#             with db_transaction.atomic():
#                 locked_wallet = UnitWallet.objects.select_for_update().get(user=user)
#                 if locked_wallet.balance < amount:
#                     return Response(
#                         {"error": "Insufficient wallet balance."},
#                         status=status.HTTP_400_BAD_REQUEST,
#                     )
#                 locked_wallet.balance -= amount
#                 locked_wallet.save(update_fields=["balance"])

#                 if not apply_units_to_meter(meter, amount):
#                     raise ValueError("AMI gateway could not apply units to the meter.")

#                 meter.refresh_from_db(fields=["units", "pending_units"])

#                 ref = generate_random_string(12)
#                 record_transaction_log(
#                     user,
#                     TransactionType.WALLET_LOAD_AMI,
#                     units=amount,
#                     status="COMPLETED",
#                     reference_id=ref,
#                     details={
#                         "channel": MeterLedgerTransaction.CHANNEL_WEB,
#                         "meter_no": meter.meter_no,
#                     },
#                 )

#             delivered = meter.pending_units <= 0
#             live_units_kwh = None
#             live_queried_at = None
#             live_read_message = None
#             ok, live_msg, live_data = query_latest_units_from_thingsboard(meter)
#             if ok and live_data:
#                 live_units_kwh = float(live_data["units_kwh"])
#                 live_queried_at = live_data.get("queried_at")
#                 record_balance_snapshot(
#                     meter,
#                     live_data["units_kwh"],
#                     source=live_data.get("source", "thingsboard"),
#                 )
#             else:
#                 live_read_message = live_msg

#             wallet_remaining = float(locked_wallet.balance)
#             meter_ledger = float(meter.units)
#             units_applied = float(amount)
#             pending_kwh = float(meter.pending_units)

#             if not delivered:
#                 load_message = (
#                     f"{units_applied:.2f} kWh queued for delivery to your meter. "
#                     f"Wallet remaining: {wallet_remaining:.2f} kWh. "
#                     "Units will be sent automatically when the meter is reachable."
#                 )
#             elif live_units_kwh is not None:
#                 load_message = (
#                     f"Successfully loaded {units_applied:.2f} kWh to your AMI meter. "
#                     f"Live meter reading: {live_units_kwh:.2f} kWh. "
#                     f"Meter ledger: {meter_ledger:.2f} kWh. "
#                     f"Wallet remaining: {wallet_remaining:.2f} kWh."
#                 )
#             else:
#                 load_message = (
#                     f"Successfully loaded {units_applied:.2f} kWh to your AMI meter. "
#                     f"Meter ledger: {meter_ledger:.2f} kWh. "
#                     f"Wallet remaining: {wallet_remaining:.2f} kWh."
#                 )
#                 if live_read_message:
#                     load_message += f" Live reading unavailable: {live_read_message}"

#             return Response(
#                 {
#                     "success": True,
#                     "units_applied": units_applied,
#                     "meter_balance": meter_ledger,
#                     "pending_delivery_kwh": pending_kwh,
#                     "remaining_wallet_balance": wallet_remaining,
#                     "live_units_kwh": live_units_kwh,
#                     "live_queried_at": live_queried_at,
#                     "delivery_status": "delivered" if delivered else "pending",
#                     "message": load_message,
#                 },
#                 status=status.HTTP_200_OK,
#             )
#         except ValueError as exc:
#             return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
#         except Exception as exc:
#             logger.error("ApplyWalletToMeterView error: %s", exc, exc_info=True)
#             return Response(
#                 {"error": "Failed to apply units to meter."},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             )

class ApplyWalletToMeterView(APIView):
    """
    POST /api/v1/meter/apply-wallet-units/

    Compatibility route for new, source-bound simulator reservations. It no
    longer spends the ambiguous legacy UnitBalance or calls a physical gateway.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from meter.api.delivery_views import reserve_delivery_response
        return reserve_delivery_response(request)

        user = request.user
        meter_no = request.data.get("meter_no")

        if meter_no:
            try:
                meter = Meter.objects.get(user=user, meter_no=meter_no)
            except Meter.DoesNotExist:
                return Response(
                    {"error": "Meter not found or not owned by you."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            ami_meters = Meter.objects.filter(user=user, architecture=Meter.ARCH_AMI)
            if not ami_meters.exists():
                return Response(
                    {
                        "error": (
                            "No AMI meter found. STS meters require a token — "
                            "use Generate STS Token on the dashboard."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if ami_meters.count() > 1:
                return Response(
                    {"error": "You have multiple AMI meters. Please specify meter_no."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            meter = ami_meters.first()

        if meter.architecture != Meter.ARCH_AMI:
            return Response(
                {
                    "error": (
                        "This action is for AMI meters only. "
                        "STS meters need a token — use Generate STS Token."
                    ),
                    "architecture": meter.architecture,
                },
                status=status.HTTP_409_CONFLICT,
            )

        raw = request.data.get("amount")
        try:
            amount = Decimal(str(raw))
            if amount <= 0:
                raise ValueError
        except (InvalidOperation, ValueError, TypeError):
            return Response(
                {"error": "Provide a positive numeric kWh amount."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # FIX: Use UnitBalance instead of UnitWallet
        unit_balance = UnitBalance.objects.filter(user=user).first()
        if not unit_balance or unit_balance.balance < amount:
            available = float(unit_balance.balance) if unit_balance else 0.0
            return Response(
                {
                    "error": f"Insufficient unit balance. Available: {available:.2f} kWh.",
                    "available": available,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with db_transaction.atomic():
                # FIX: Lock UnitBalance instead of UnitWallet
                locked_balance = UnitBalance.objects.select_for_update().get(user=user)
                if locked_balance.balance < amount:
                    return Response(
                        {"error": "Insufficient unit balance."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                locked_balance.balance -= amount
                locked_balance.save(update_fields=["balance"])

                if not apply_units_to_meter(meter, amount):
                    raise ValueError("AMI gateway could not apply units to the meter.")

                meter.refresh_from_db(fields=["units", "pending_units"])

                ref = generate_random_string(12)
                record_transaction_log(
                    user,
                    TransactionType.WALLET_LOAD_AMI,
                    units=amount,
                    status="COMPLETED",
                    reference_id=ref,
                    details={
                        "channel": MeterLedgerTransaction.CHANNEL_WEB,
                        "meter_no": meter.meter_no,
                    },
                )

            delivered = meter.pending_units <= 0
            live_units_kwh = None
            live_queried_at = None
            live_read_message = None
            ok, live_msg, live_data = query_latest_units_from_thingsboard(meter)
            if ok and live_data:
                live_units_kwh = float(live_data["units_kwh"])
                live_queried_at = live_data.get("queried_at")
                record_balance_snapshot(
                    meter,
                    live_data["units_kwh"],
                    source=live_data.get("source", "thingsboard"),
                )
            else:
                live_read_message = live_msg

            wallet_remaining = float(locked_balance.balance)
            meter_ledger = float(meter.units)
            units_applied = float(amount)
            pending_kwh = float(meter.pending_units)

            if not delivered:
                load_message = (
                    f"{units_applied:.2f} kWh queued for delivery to your meter. "
                    f"Unit balance remaining: {wallet_remaining:.2f} kWh. "
                    "Units will be sent automatically when the meter is reachable."
                )
            elif live_units_kwh is not None:
                load_message = (
                    f"Successfully loaded {units_applied:.2f} kWh to your AMI meter. "
                    f"Live meter reading: {live_units_kwh:.2f} kWh. "
                    f"Meter ledger: {meter_ledger:.2f} kWh. "
                    f"Unit balance remaining: {wallet_remaining:.2f} kWh."
                )
            else:
                load_message = (
                    f"Successfully loaded {units_applied:.2f} kWh to your AMI meter. "
                    f"Meter ledger: {meter_ledger:.2f} kWh. "
                    f"Unit balance remaining: {wallet_remaining:.2f} kWh."
                )
                if live_read_message:
                    load_message += f" Live reading unavailable: {live_read_message}"

            return Response(
                {
                    "success": True,
                    "units_applied": units_applied,
                    "meter_balance": meter_ledger,
                    "pending_delivery_kwh": pending_kwh,
                    "remaining_wallet_balance": wallet_remaining,
                    "live_units_kwh": live_units_kwh,
                    "live_queried_at": live_queried_at,
                    "delivery_status": "delivered" if delivered else "pending",
                    "message": load_message,
                },
                status=status.HTTP_200_OK,
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception as exc:
            logger.error("ApplyWalletToMeterView error: %s", exc, exc_info=True)
            return Response(
                {"error": "Failed to apply units to meter."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class BuyUnitsView(GenericAPIView):
    permission_classes = (IsAuthenticated,)

    def _get_active_tariff(self):
        from utils.billing import get_active_domestic_tariff
        return get_active_domestic_tariff()


    def _create_purchase_and_update_balances(self, user, meter, units_purchased, reference_id):
        """
        When user buys units:
        1. Add to UnitBalance (available to share)
        2. Create token (optional loading to meter)
        3. Update credit score
        """
        
        # 1. Add to UnitBalance - units available for sharing
        unit_balance, _ = UnitBalance.objects.get_or_create(user=user)
        unit_balance.add_units(
            units_purchased,
            description=f"Purchased {units_purchased} units via {reference_id}",
            reference=reference_id
        )
        
        # 2. Create token for meter loading
        token_value = generate_numeric_token(10)
        while MeterToken.objects.filter(token=token_value).exists():
            token_value = generate_numeric_token(10)
        
        token = MeterToken.objects.create(
            user=user,
            token=token_value,
            units=units_purchased,
            meter=meter,
            source='PURCHASE',
            is_used=False
        )
        
        # 3. Update credit score for purchase
        CreditScoreService.update_credit_score(
            user=user,
            event_type='UNIT_PURCHASE',
            reference_id=reference_id,
            extra_data={
                'units': float(units_purchased),
                'amount': float(units_purchased * 500),  # Approximate amount
                'payment_source': 'WALLET'
            }
        )
        
        logger.info(
            f"Purchase complete for user {user.email}: "
            f"Added {units_purchased} units to UnitBalance (new balance: {unit_balance.balance}), "
            f"Token {token.token} created"
        )
        
        return token, unit_balance.balance
        
        logger.info(
            f"Purchase complete for user {user.email}: "
            f"Added {units_purchased} units to UnitBalance (new balance: {unit_balance.balance}), "
            f"Token {token.token} created"
        )
        
        return token, unit_balance.balance
    


#   def _calculate_units_from_tariff(self, amount, user=None):
#         """
#         Calculate purchasable kWh from a UGX payment using ERA domestic billing
#         (tiered blocks + service charge + 18% VAT).
#         """
#         from utils.billing import calculate_units_from_payment, get_active_domestic_tariff

#         if user is None:
#             fallback_rate = Decimal("756.2")
#             return (Decimal(str(amount)) / fallback_rate).quantize(Decimal("0.01")), None

#         tariff = get_active_domestic_tariff()
#         units, breakdown = calculate_units_from_payment(
#             Decimal(str(amount)),
#             user,
#             tariff=tariff,
#             apply_deductions=False,
#         )
#         return units, tariff  

    def _calculate_units_from_tariff(self, amount):
        """
        Calculate purchasable units from amount using tariff blocks.
        Falls back to legacy flat rate (500 UGX/unit) if no active tariff exists.
        """
        tariff = self._get_active_tariff()
        fallback_rate = Decimal("500")

        if not tariff:
            return (amount / fallback_rate).quantize(Decimal("0.01")), None

        blocks = tariff.blocks.all().order_by('block_order')
        if not blocks.exists():
            return (amount / fallback_rate).quantize(Decimal("0.01")), tariff

        remaining_amount = Decimal(str(amount))
        total_units = Decimal("0")

        for block in blocks:
            if remaining_amount <= 0:
                break

            rate = Decimal(str(block.rate_per_unit))
            if rate <= 0:
                continue

            if block.max_units is None:
                total_units += remaining_amount / rate
                remaining_amount = Decimal("0")
                break

            block_units_available = Decimal(block.max_units - block.min_units + 1)
            block_cost = block_units_available * rate

            if remaining_amount >= block_cost:
                total_units += block_units_available
                remaining_amount -= block_cost
            else:
                total_units += remaining_amount / rate
                remaining_amount = Decimal("0")
                break

        return total_units.quantize(Decimal("0.01")), tariff


    def _get_active_loan_balances(self, user):
        from loan.services import get_disbursed_loan_balances

        return get_disbursed_loan_balances(user)

    def _apply_auto_loan_repayment(self, user, payment_amount):
        """
        Use incoming purchase payment to clear disbursed loan balances first.
        Returns (remaining_amount_for_units, total_repaid).
        """
        remaining = Decimal(str(payment_amount))
        total_repaid = Decimal("0")
        loans_with_balance, _ = self._get_active_loan_balances(user)

        for loan, outstanding in loans_with_balance:
            if remaining <= 0:
                break

            paid = min(remaining, outstanding)
            LoanRepayment.objects.create(
                loan=loan,
                amount_paid=paid,
                units_paid=0,
                payment_reference=generate_random_string(12),
                is_on_time=True,
                payment_method='MOBILE_MONEY',
                payment_status='SUCCESS'
            )
            remaining -= paid
            total_repaid += paid

            loan.refresh_from_db()
            if loan.outstanding_balance <= 0:
                loan.status = 'COMPLETED'
                loan.save()

        return remaining, total_repaid

    def _create_purchase_token(self, user, meter, units_purchased):
        token_value = generate_random_string(10)
        while MeterToken.objects.filter(token=token_value).exists():
            token_value = generate_random_string(10)

        return MeterToken.objects.create(
            user=user,
            token=token_value,
            units=units_purchased,
            meter=meter,
            source='PURCHASE',
        )

    def _record_purchase_history(self, user, amount, units_purchased, token, meter, payment_source, reference_id):
        TransactionLog.objects.create(
            user=user,
            transaction_type=TransactionType.UNIT_PURCHASE,
            amount=amount,
            units=units_purchased,
            status='COMPLETED',
            reference_id=reference_id,
            details={
                'meter_no': meter.meter_no,
                'token': token.token,
                'payment_source': payment_source,
            },
        )

        UnitTransaction.objects.create(
            sender=user,
            receiver=user,
            units=float(units_purchased),
            meter=meter,
            direction="IN",
            status="COMPLETED",
            message=f"Purchased {units_purchased} units. Token {token.token} issued.",
        )
    
    def post(self, request, *args, **kwargs):
        amount = request.data.get("amount")
        phone_number = request.data.get("phone_number", "")
        payment_source = str(request.data.get("payment_source", "PHONE")).upper()
        
        if not amount:
            phone_number = request.data.get("phone_number")

        if not amount or not phone_number:
            return Response({
                "error": "Amount is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        if payment_source not in {"WALLET", "PHONE", "MOBILE_MONEY"}:
            return Response({
                "error": "Payment source must be WALLET or PHONE"
            }, status=status.HTTP_400_BAD_REQUEST)

        if payment_source in {"PHONE", "MOBILE_MONEY"} and not phone_number:
            return Response({
                "error": "Phone number is required for phone payments"
            }, status=status.HTTP_400_BAD_REQUEST)
        
               
        try:
            user = request.user

            # Block purchases when there is any pending or incomplete loan (same as loans/stats)
            from loan.services import user_can_purchase_units

            can_buy, purchase_message = user_can_purchase_units(user)
            if not can_buy:
                return Response({
                    "error": "Loan in progress",
                    "message": purchase_message,
                }, status=status.HTTP_400_BAD_REQUEST)
            try:
                amount = Decimal(str(amount))
            except (InvalidOperation, TypeError, ValueError):
                return Response({
                    "error": "Amount must be a valid number"
                }, status=status.HTTP_400_BAD_REQUEST)

            if amount <= 0:
                return Response({
                    "error": "Amount must be greater than 0"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                meter = Meter.objects.filter(user=user).order_by("create_date").first()
                if not meter:
                    raise Meter.DoesNotExist
            except Meter.DoesNotExist:
                return Response({
                    "error": "No meter found. Please register your meter before purchasing units."
                }, status=status.HTTP_400_BAD_REQUEST)

            account_wallet = AccountWallet.objects.filter(user=user).order_by('-create_date').first()
            if account_wallet is None:
                account_wallet = AccountWallet.objects.create(user=user)

            estimated_units, tariff = self._calculate_units_from_tariff(amount)

            if payment_source == "WALLET":
                with db_transaction.atomic():
                    # Deduct from money wallet
                    money_wallet, _ = MoneyWallet.objects.select_for_update().get_or_create(user=user)
                    if money_wallet.balance < amount:
                        return Response({
                            "error": "Insufficient wallet balance",
                            "wallet_balance": str(money_wallet.balance),
                        }, status=status.HTTP_400_BAD_REQUEST)

                    reference_id = f"PUR-{uuid.uuid4().hex[:8].upper()}"
                    money_wallet.deduct(
                        amount,
                        description=f"Purchased {estimated_units} electricity units",
                        transaction_ref=reference_id,
                    )
                
                    # Create token AND add to UnitBalance
                    token, new_unit_balance = self._create_purchase_and_update_balances(
                        user, meter, estimated_units, reference_id
                    )

                    self._record_purchase_history(
                        user,
                        amount,
                        estimated_units,
                        token,
                        meter,
                        "WALLET",
                        reference_id,
                    )

                    return Response({
                        "status": "SUCCESS",
                        "message": "Units purchased successfully!",
                        "token": token.token,
                        "units_purchased": "{:.2f}".format(estimated_units),
                        "units_available_to_share": "{:.2f}".format(new_unit_balance),
                        "wallet_balance": str(money_wallet.balance),
                        "tariff_applied": tariff.tariff_code if tariff else "DEFAULT_500",
                    }, status=status.HTTP_200_OK)
            
            if settings.MTN_MOMO_CONFIG.get('ENVIRONMENT', 'sandbox') == 'sandbox':
                # Generate external ID for tracking
                external_id = str(uuid.uuid4())
                
                # Create pending transaction
                try:
                    transaction = Transaction.objects.create(
                        wallet=account_wallet,
                        amount=amount,
                        phone_number=phone_number,
                        status='PENDING',
                        transaction_reference=external_id,
                        message=f"Buy units - {amount} UGX"
                    )
                except Exception:
                    return Response({
                        "error": "Invalid phone number. Use full format e.g. +2567XXXXXXXX."
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Return pending response immediately
                response_data = {
                    "status": "PENDING",
                    "message": "Simulating sandbox payment - Please wait...",
                    "external_id": external_id,
                    "transaction_id": transaction.id,
                    "user_prompt": "Sandbox mode: Payment will auto-complete in 2 seconds",
                    "estimated_units": float(estimated_units),
                    "tariff_applied": tariff.tariff_code if tariff else "DEFAULT_500",
                }
                
            _, total_outstanding = self._get_active_loan_balances(user)
            estimated_buy_amount = max(Decimal("0"), amount - total_outstanding)
            estimated_units, tariff = self._calculate_units_from_tariff(estimated_buy_amount)

            momo_reference = str(uuid.uuid4())
            from mtn_momo.config import should_simulate_payments

            use_simulated = should_simulate_payments()

            try:
                transaction = Transaction.objects.create(
                    wallet=account_wallet,
                    amount=amount,
                    phone_number=phone_number,
                    status='PENDING',
                    transaction_reference=momo_reference,
                    message=f"Buy units - {amount} UGX"
                )
            except Exception:
                return Response({
                    "error": "Invalid phone number. Use full format e.g. +2567XXXXXXXX."
                }, status=status.HTTP_400_BAD_REQUEST)

            response_data = {
                "status": "PENDING",
                "transaction_id": transaction.id,
                "estimated_units": float(estimated_units),
                "tariff_applied": tariff.tariff_code if tariff else "DEFAULT_500",
                "loan_outstanding_deduction": float(total_outstanding) if total_outstanding > 0 else 0,
                "payment_mode": "simulated" if use_simulated else "momo",
            }

            if use_simulated:
                response_data.update({
                    "message": "Simulating sandbox payment - Please wait...",
                    "external_id": momo_reference,
                    "user_prompt": "Dev mode: payment will auto-complete in 2 seconds (no PIN required).",
                })
                threading.Thread(
                    target=self._simulate_sandbox_payment,
                    args=(user.id, str(amount), transaction.id, meter.id),
                    daemon=True
                ).start()
                return Response(response_data, status=status.HTTP_200_OK)

            momo_service = MTNMoMoService()
            payment_result = momo_service.request_payment(
                amount=amount,
                phone_number=phone_number,
                reference_id=momo_reference,
                external_id=str(transaction.id),
                payer_message=f"gPAWA wallet top-up {amount} UGX",
            )

            if payment_result.get("status") != "PENDING":
                transaction.status = "FAILED"
                transaction.message = payment_result.get("message", "MoMo request failed")
                transaction.save(update_fields=["status", "message"])
                return Response({
                    "error": payment_result.get("message", "Failed to initiate mobile money payment"),
                }, status=status.HTTP_400_BAD_REQUEST)

            response_data.update({
                "message": payment_result.get("message", "Payment request sent to your phone."),
                "external_id": payment_result.get("reference_id", momo_reference),
                "user_prompt": payment_result.get(
                    "user_prompt",
                    "Check your phone and enter your Mobile Money PIN to approve the payment.",
                ),
            })
            return Response(response_data, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.exception(f"Buy units error: {str(e)}")
            return Response({
                "error": "Failed to process buy units request"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _simulate_sandbox_payment(self, user_id, amount, transaction_id, meter_id):
        """Simulate successful payment in dev mode after 2 seconds."""
        # Old process-local threads must never create purchased credit.
        return
        logger.info(f"Sandbox: Starting payment simulation for user {user_id}")
        time.sleep(2)
        time.sleep(2)

        try:
            user = User.objects.get(id=user_id)
        
            meter = Meter.objects.get(id=meter_id)

            with db_transaction.atomic():
                amount_decimal = Decimal(str(amount))
                units_purchased, tariff = self._calculate_units_from_tariff(amount_decimal)

                # Update transaction status
                transaction = Transaction.objects.get(id=transaction_id)
                transaction.status = 'COMPLETED'
                transaction.message = (
                    f"Buy units - {amount_decimal} UGX | Token issued for {units_purchased} units | "
                    f"Tariff: {tariff.tariff_code if tariff else 'DEFAULT_500'}"
                )
                transaction.save()

                if units_purchased > 0:
                    token, new_unit_balance = self._create_purchase_and_update_balances(
                        user, meter, units_purchased, transaction.transaction_reference
                    )
                    
                    self._record_purchase_history(
                        user,
                        amount_decimal,
                        units_purchased,
                        token,
                        meter,
                        "PHONE",
                        transaction.transaction_reference,
                    )

            logger.info(
                f"Sandbox: Payment complete for user {user_id}. "
                f"token_units={units_purchased}"
            )

        except Meter.DoesNotExist:
            logger.error(f"No meter found with ID {meter_id} for user {user_id}")
            from meter.buy_units_payment import complete_buy_units_payment

            user = User.objects.get(id=user_id)
            ok, units_purchased, err = complete_buy_units_payment(
                user, Decimal(str(amount)), transaction_id, meter_id
            )
            if ok:
                logger.info(
                    f"Sandbox: Payment complete for user {user_id}. units_to_wallet={units_purchased}"
                )
            else:
                logger.error(f"Sandbox payment simulation error: {err}")
        except User.DoesNotExist:
            logger.error(f"User {user_id} not found during sandbox simulation")
            try:
                transaction = Transaction.objects.get(id=transaction_id)
                transaction.status = 'FAILED'
                transaction.save()
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Sandbox payment simulation error: {str(e)}")
            try:
                transaction = Transaction.objects.get(id=transaction_id)
                transaction.status = 'FAILED'
                transaction.save()
            except Exception:
                pass
    
    
    
class CheckPaymentStatusView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    
    def post(self, request, *args, **kwargs):
        transaction_id = request.data.get("transaction_id")
        
        if not transaction_id:
            return Response({
                "error": "Transaction ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            transaction = Transaction.objects.get(
                id=transaction_id,
                wallet__user=request.user
            )
            
            if transaction.status == 'COMPLETED':
                purchase_log = TransactionLog.objects.filter(
                    user=request.user,
                    transaction_type=TransactionType.UNIT_PURCHASE,
                    reference_id=transaction.transaction_reference,
                    status="COMPLETED",
                ).order_by('-created_at').first()

                details = purchase_log.details if purchase_log and purchase_log.details else {}
                units_purchased = float(purchase_log.units) if purchase_log and purchase_log.units else 0
                token = details.get("token")

                return Response({
                    "status": "SUCCESS",
                    "message": "Payment completed successfully",
                    "units_purchased": units_purchased,
                    "token": token,
                    "wallet_balance": float(
                        UnitWallet.objects.filter(user=request.user)
                        .values_list("balance", flat=True)
                        .first()
                        or 0
                    ),
                    "token": None,
                    "transaction": {
                        "id": transaction.id,
                        "amount": float(transaction.amount),
                        "units": units_purchased,
                        "token": token,
                        "timestamp": transaction.create_date.isoformat()
                    }
                }, status=status.HTTP_200_OK)
                
            elif transaction.status == 'FAILED':
                return Response({
                    "status": "FAILED",
                    "message": "Payment failed"
                }, status=status.HTTP_400_BAD_REQUEST)

            else:
                from mtn_momo.config import should_simulate_payments
                from meter.buy_units_payment import complete_buy_units_payment

                if not should_simulate_payments() and transaction.transaction_reference:
                    momo_service = MTNMoMoService()
                    momo_status = momo_service.get_payment_status(transaction.transaction_reference)

                    if momo_status.get("status") == "SUCCESS":
                        meter = Meter.objects.filter(user=request.user).order_by("create_date").first()
                        if meter:
                            complete_buy_units_payment(
                                request.user,
                                transaction.amount,
                                transaction.id,
                                meter.id,
                            )
                        transaction.refresh_from_db()
                    elif momo_status.get("status") == "FAILED":
                        # Only mark as definitively failed when MoMo itself says so,
                        # not when we couldn't reach the API (UNKNOWN).
                        transaction.status = "FAILED"
                        transaction.message = momo_status.get("message", "Payment failed")
                        transaction.save(update_fields=["status", "message"])
                        return Response({
                            "status": "FAILED",
                            "message": momo_status.get("message", "Payment failed"),
                        }, status=status.HTTP_400_BAD_REQUEST)
                    # UNKNOWN means we couldn't reach MoMo — fall through so the
                    # client keeps polling rather than seeing a false failure.

                if transaction.status == 'COMPLETED':
                    unit_tx = UnitTransaction.objects.filter(
                        sender=request.user,
                        receiver=request.user,
                        direction="IN",
                        status="COMPLETED",
                        create_date__gte=transaction.create_date
                    ).order_by('-create_date').first()

                    units_purchased = float(unit_tx.units) if unit_tx else 0

                    return Response({
                        "status": "SUCCESS",
                        "message": "Payment completed successfully",
                        "units_purchased": units_purchased,
                        "wallet_balance": float(
                            UnitWallet.objects.filter(user=request.user)
                            .values_list("balance", flat=True)
                            .first()
                            or 0
                        ),
                        "token": None,
                        "transaction": {
                            "id": transaction.id,
                            "amount": float(transaction.amount),
                            "units": units_purchased,
                            "timestamp": transaction.create_date.isoformat()
                        }
                    }, status=status.HTTP_200_OK)

                return Response({
                    "status": "PENDING",
                    "message": "Payment still processing. Approve the MoMo prompt on your phone if you have not yet.",
                }, status=status.HTTP_200_OK)
                
        except Transaction.DoesNotExist:
            return Response({
                "error": "Transaction not found"
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Check payment status error: {str(e)}")
            return Response({
                "error": "Failed to check payment status"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            


class LoadTokenToMeterView(APIView):
    """
    User loads a token to add units to their physical meter
    Units REMAIN in UnitBalance - user can still share them
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        return Response({
            "code": "LEGACY_TOKEN_LOAD_DISABLED",
            "message": "This route could duplicate meter credit without debiting its source allocation.",
        }, status=status.HTTP_410_GONE)
        token_code = request.data.get('token')
        
        if not token_code:
            return Response({
                "error": "Token is required"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Ensure token is numeric only
        if not token_code.isdigit():
            return Response({
                "error": "Invalid token format. Token must contain only numbers."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            token = MeterToken.objects.get(
                token=token_code,
                user=request.user,
                is_used=False
            )
        except MeterToken.DoesNotExist:
            return Response({
                "error": "Invalid or already used token"
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get user's meter
        try:
            meter = Meter.objects.get(user=request.user)
        except Meter.DoesNotExist:
            return Response({
                "error": "No meter found. Please register your meter first."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Ensure token belongs to this meter
        if token.meter.id != meter.id:
            return Response({
                "error": "This token is for a different meter"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        with db_transaction.atomic():
            # Add units to physical meter
            meter.units += token.units
            meter.save()
            
            # IMPORTANT: Units REMAIN in UnitBalance
            # User can still share these units with others
            # The physical meter reading is just for consumption tracking
            
            # Mark token as used
            token.is_used = True
            token.save()
            
            # Record the meter loading transaction
            try:
                meter_balance = MeterBalance.objects.get(meter=meter)
                MeterTransaction.objects.create(
                    meter=meter_balance,
                    amount=token.units,
                    operation='ADD',
                    balance_after=meter.units,
                    description=f"Loaded token {token.token} from {token.source}",
                    reference=token.token
                )
            except MeterBalance.DoesNotExist:
                # Create meter balance if doesn't exist
                meter_balance = MeterBalance.objects.create(
                    user=request.user,
                    meter=meter,
                    meter_number=meter.meter_no,
                    balance=meter.units
                )
            
            # Get current unit balance
            unit_balance, _ = UnitBalance.objects.get_or_create(user=request.user)
            
            logger.info(
                f"Token allocation loaded for user {request.user.id}: "
                f"Added {token.units} units to meter {meter.meter_no}. "
                f"UnitBalance unchanged at {unit_balance.balance} units"
            )
            
            return Response({
                "success": True,
                "message": f"Successfully loaded {token.units} units to your meter",
                "meter_units": float(meter.units),
                "units_available_to_share": float(unit_balance.balance),
                "token_used": token.token,
                "source": token.source
            }, status=status.HTTP_200_OK)


class MeterPushTestView(APIView):
    """
    Manual utility endpoint to test ThingsBoard unit push.
    This does not change wallet balances; it only pushes telemetry.
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        if not settings.DEBUG or settings.AMI_GATEWAY != "utils.ami_gateway.MockAMIGateway":
            return Response({"code": "SIMULATION_ONLY", "message": "Test pushes are available only with the mock gateway in development."}, status=403)
        amount_raw = request.data.get("amount")
        reference_id = str(request.data.get("reference_id", "")).strip() or f"TEST-{uuid.uuid4().hex[:8].upper()}"

        try:
            amount = Decimal(str(amount_raw))
        except (InvalidOperation, TypeError, ValueError):
            return Response({"error": "Invalid amount. Provide a numeric value."}, status=status.HTTP_400_BAD_REQUEST)

        if amount <= 0:
            return Response({"error": "Amount must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            meter = Meter.objects.get(user=request.user)
        except Meter.DoesNotExist:
            return Response({"error": "No meter found for this user."}, status=status.HTTP_404_NOT_FOUND)

        if not (meter.iot_device_token or "").startswith("dev-"):
            return Response({"code": "SIMULATION_ONLY", "message": "A simulation meter is required."}, status=403)

        ok, msg = push_units_to_thingsboard(meter=meter, units=amount, reference_id=reference_id)
        status_code = status.HTTP_200_OK if ok else status.HTTP_400_BAD_REQUEST

        return Response(
            {
                "success": ok,
                "meter_no": meter.meter_no,
                "amount": float(amount),
                "reference_id": reference_id,
                "message": msg,
            },
            status=status_code,
        )


class AdminMeterPushTestView(APIView):
    """
    Admin-only ThingsBoard push utility that targets any meter by meter_no.
    This does not change wallet balances; it only sends telemetry.
    """
    permission_classes = (permissions.IsAdminUser,)

    def post(self, request, *args, **kwargs):
        if not settings.DEBUG or settings.AMI_GATEWAY != "utils.ami_gateway.MockAMIGateway":
            return Response({"code": "SIMULATION_ONLY", "message": "Test pushes are available only with the mock gateway in development."}, status=403)
        meter_no = str(request.data.get("meter_no", "")).strip()
        amount_raw = request.data.get("amount")
        reference_id = str(request.data.get("reference_id", "")).strip() or f"ADMIN-TEST-{uuid.uuid4().hex[:8].upper()}"

        if not meter_no:
            return Response({"error": "meter_no is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = Decimal(str(amount_raw))
        except (InvalidOperation, TypeError, ValueError):
            return Response({"error": "Invalid amount. Provide a numeric value."}, status=status.HTTP_400_BAD_REQUEST)

        if amount <= 0:
            return Response({"error": "Amount must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            meter = Meter.objects.get(meter_no=meter_no)
        except Meter.DoesNotExist:
            return Response({"error": "Meter not found."}, status=status.HTTP_404_NOT_FOUND)

        if not (meter.iot_device_token or "").startswith("dev-"):
            return Response({"code": "SIMULATION_ONLY", "message": "A simulation meter is required."}, status=403)

        ok, msg = push_units_to_thingsboard(meter=meter, units=amount, reference_id=reference_id)
        status_code = status.HTTP_200_OK if ok else status.HTTP_400_BAD_REQUEST

        return Response(
            {
                "success": ok,
                "meter_no": meter.meter_no,
                "amount": float(amount),
                "reference_id": reference_id,
                "message": msg,
            },
            status=status_code,
        )


class EstimateUnitsView(APIView):
    """
    GET /api/v1/meter/estimate-units/?amount=5000

    Returns estimated kWh for a UGX payment using ERA domestic billing
    (tiered blocks + service charge + 18% VAT). No side effects.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        raw = request.query_params.get("amount", "")
        try:
            amount = Decimal(str(raw))
            if not amount.is_finite() or amount <= 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            return Response({"error": "Provide a positive numeric amount."}, status=status.HTTP_400_BAD_REQUEST)

        from utils.billing import (
            calculate_units_from_payment,
            get_active_domestic_tariff,
            get_minimum_payment_for_units,
            get_monthly_tier_context,
            get_monthly_units_consumed,
        )

        # This endpoint previews an electricity purchase. Loan repayment is a
        # separate, verified payment purpose and cannot be inferred here.
        net_amount = amount
        tariff = get_active_domestic_tariff()
        units, breakdown = calculate_units_from_payment(
            amount,
            request.user,
            tariff=tariff,
            outstanding_bills=Decimal("0"),
            apply_deductions=False,
        )
        minimum_payment = get_minimum_payment_for_units(request.user, tariff)
        service_included = get_monthly_units_consumed(request.user) <= 0
        tier_ctx = get_monthly_tier_context(request.user)

        return Response({
            "estimated_units": float(units),
            "tariff": tariff.tariff_code if tariff else None,
            "gross_amount": float(amount),
            "deductions": 0,
            "net_amount": float(net_amount),
            "service_charge": float(breakdown.service_charge),
            "vat": float(breakdown.vat),
            "energy_cost": float(breakdown.energy_cost),
            "total_bill": float(breakdown.total),
            "insufficient_amount": float(units) <= 0 and float(net_amount) > 0,
            "minimum_payment": float(minimum_payment),
            "service_charge_included": service_included,
            "monthly_units_consumed": float(tier_ctx["monthly_units_consumed"]),
            "lifeline_remaining_kwh": float(tier_ctx["lifeline_remaining_kwh"]),
            "current_tier_band": tier_ctx["current_tier_band"],
        })
