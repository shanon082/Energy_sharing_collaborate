from backend.features import requires_feature
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction as db_transaction
from django.utils import timezone
from decimal import Decimal
import uuid
from datetime import datetime, timedelta
import logging
from transactions.models import TransactionType, TransactionLog
from transactions.api.generate_token import generate_numeric_token
from meter.models import generate_numeric_token
from .serializers import ShareUnitSerializer, VerifyOTPSerializer, TransferUnitsSerializer

from .serializers import ConfirmShareSerializer, TransferUnitsSerializer, VerifyOTPSerializer
from .models import Share, ShareTransaction
from .flow import ShareFlowError, execute_share_units
from accounts.models import User, Wallet as AccountWallet
from wallet.models import Wallet, UnitBalance
from meter.models import Meter, MeterToken
from share.services import VerificationService, VerificationCode
from utils.general import format_currency
from wallet.models import Wallet
from meter.models import Meter
from share.services import VerificationCode
from utils.general import format_currency, dispatch_task
from accounts.tasks import (
    handle_send_transfer_verification,
    handle_send_wallet_update,
)

from meter.validators import normalize_meter_no, validate_meter_no

logger = logging.getLogger(__name__)

# class ShareUnitsView(APIView):
#     permission_classes = [IsAuthenticated]
    
#     def post(self, request):
#         verification_code = request.data.get('verification_code')
        
#         if not verification_code:
#             # Step 1: Initial share request
#             serializer = ShareUnitSerializer(data=request.data)
#             if not serializer.is_valid():
#                 return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
#             try:
#                 with db_transaction.atomic():
#                     # Get data
#                     receiver_meter_no = serializer.validated_data['meter_number']
#                     units_to_share = Decimal(str(serializer.validated_data['units']))
                    
#                     # Get sender (current user)
#                     sender = request.user
                    
#                     # Get sender's meters and handle multiple
#                     sender_meters = Meter.objects.filter(user=sender)
#                     if sender_meters.count() == 0:
#                         return Response(
#                             {"error": "No meter found for sender"},
#                             status=status.HTTP_400_BAD_REQUEST
#                         )
#                     if sender_meters.count() > 1:
#                         # For now, assume single; extend to accept 'sender_meter_no' in data if needed
#                         return Response(
#                             {"error": "Multiple meters found. Please specify which to send from."},
#                             status=status.HTTP_400_BAD_REQUEST
#                         )
#                     sender_meter = sender_meters.first()
                    
#                     # Check if sender's WALLET has sufficient units
#                     sender_wallet, _ = Wallet.objects.select_for_update().get_or_create(user=sender)
#                     if sender_wallet.balance < units_to_share:
#                         return Response({
#                             "error": f"Insufficient units in your wallet. Your balance: {format_currency(sender_wallet.balance)} units"
#                         }, status=status.HTTP_400_BAD_REQUEST)
                    
#                     # Validate receiver meter exists and is active
#                     try:
#                         receiver_meter = Meter.objects.select_for_update().get(
#                             meter_no=receiver_meter_no,
#                             # is_active=True  # Uncomment if Meter has is_active field
#                         )
#                     except Meter.DoesNotExist:
#                         return Response(
#                             {"error": "Receiver meter not found or inactive"},
#                             status=status.HTTP_400_BAD_REQUEST
#                         )
                    
#                     # Get receiver user
#                     receiver_user = receiver_meter.user
                    
#                     # Generate transaction ref
#                     transaction_ref = f"SHARE-{uuid.uuid4().hex[:8].upper()}"

#                     # Cancel older pending shares for this sender and persist the new pending share in DB.
#                     ShareTransaction.objects.filter(
#                         sender=sender,
#                         status='PENDING'
#                     ).update(
#                         status='CANCELLED',
#                         message='Cancelled due to a newer share request'
#                     )

#                     pending_share = ShareTransaction.objects.create(
#                         share_transaction_id=transaction_ref,
#                         sender=sender,
#                         receiver=receiver_user,
#                         units=units_to_share,
#                         meter_send=sender_meter,
#                         meter_receive=receiver_meter,
#                         direction='OUT',
#                         status='PENDING',
#                         message=f"Pending OTP verification for share to meter {receiver_meter_no}",
#                         ip_address=request.META.get('REMOTE_ADDR'),
#                         user_agent=request.META.get('HTTP_USER_AGENT', '')
#                     )
                    
#                     # Generate verification code
#                     verification = VerificationCode.create_code(
#                         user=sender,
#                         purpose='share_units',
#                         expiry_minutes=10
#                     )
                    
#                     # Prepare transaction details for email
#                     transaction_details = (
#                     f"You're sharing {units_to_share} units to meter {receiver_meter_no}."
#                     f"From your meter: {sender_meter.meter_no}."
#                     f"Transaction ID: {transaction_ref}."
#                     f"Code expires: {(datetime.now() + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')}."
#                     )
                    
#                     # Send verification email via Celery task
#                     handle_send_share_verification.delay(
#                         user_id=sender.id,
#                         code=verification.code,
#                         transaction_details=transaction_details
#                     )
                    
#                     logger.info(f"Generated OTP for {sender.email}: {verification.code}")
                    
#                     return Response({
#                         "success": True,
#                         "message": "Verification code sent to your email. Please check and verify.",
#                         "transaction_ref": pending_share.share_transaction_id,
#                         "requires_verification": True
#                     }, status=status.HTTP_200_OK)
                    
#             except Exception as e:
#                 logger.error(f"Error initiating share: {str(e)}", exc_info=True)
#                 return Response({
#                     "error": "An error occurred while initiating the share request"
#                 }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# share/views.py - Update ShareUnitsView to use UnitBalance


def _phone_for_api(phone) -> str:
    """Serialize phonenumber_field values for JSON API responses."""
    if not phone:
        return "Not on file"
    return str(phone)


class ShareReceiverPreviewView(APIView):
    """
    GET /api/v1/share/receiver-preview/?meter_number=

    Returns recipient details for the share confirmation step (no side effects).
    """
    permission_classes = [IsAuthenticated]

    @requires_feature("peer_sharing")
    def get(self, request):
        meter_number = normalize_meter_no(request.query_params.get("meter_number") or "")
        if not meter_number:
            return Response(
                {"error": "meter_number is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ok, msg = validate_meter_no(meter_number)
        if not ok:
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

        try:
            meter = Meter.objects.select_related("user").get(meter_no=meter_number)
        except Meter.DoesNotExist:
            return Response(
                {"error": "Receiver meter not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if meter.user_id == request.user.id:
            return Response(
                {
                    "error": (
                        "This is your own meter. Use Load Units to top up your AMI meter "
                        "from your wallet."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if meter.status != Meter.STATUS_ACTIVE:
            return Response(
                {"error": "Receiver meter is not active."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        owner = meter.user
        display_name = f"{owner.first_name or ''} {owner.last_name or ''}".strip()
        if not display_name:
            display_name = owner.email or "Unknown"

        is_ami = meter.architecture == Meter.ARCH_AMI
        return Response(
            {
                "success": True,
                "recipient": {
                    "name": display_name,
                    "meter_number": meter.meter_no,
                    "meter_type": meter.architecture,
                    "meter_type_label": "AMI (networked)" if is_ami else "STS (token keypad)",
                    "phone_number": _phone_for_api(owner.phone_number),
                },
                "delivery_method": (
                    "Units will be sent directly to the AMI meter device token (ThingsBoard)."
                    if is_ami
                    else "An STS keypad token will be generated and sent to the recipient."
                ),
            },
            status=status.HTTP_200_OK,
        )


class ShareUnitsView(APIView):
    permission_classes = [IsAuthenticated]
    
    @requires_feature("peer_sharing")
    def post(self, request):
        verification_code = request.data.get('verification_code')
        
        if not verification_code:
            # Initial share request - check UNIT balance, not money wallet
            serializer = ShareUnitSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                with db_transaction.atomic():
                    receiver_meter_no = serializer.validated_data['meter_number']
                    units_to_share = Decimal(str(serializer.validated_data['units']))
                    sender = request.user
                    
                    # Get sender's unit balance (NOT money wallet)
                    sender_units, _ = UnitBalance.objects.select_for_update().get_or_create(user=sender)
                    
                    # Check if sender has enough UNITS
                    if sender_units.balance < units_to_share:
                        return Response({
                            "error": f"Insufficient units. Your balance: {sender_units.balance} units"
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Validate receiver meter exists
                    try:
                        receiver_meter = Meter.objects.select_for_update().get(
                            meter_no=receiver_meter_no,
                        )
                    except Meter.DoesNotExist:
                        return Response(
                            {"error": "Receiver meter not found"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                    # Create pending share transaction
                    transaction_ref = f"SHARE-{uuid.uuid4().hex[:8].upper()}"
                    
                    # Cancel older pending shares
                    ShareTransaction.objects.filter(
                        sender=sender,
                        status='PENDING'
                    ).update(status='CANCELLED')
                    
                    pending_share = ShareTransaction.objects.create(
                        share_transaction_id=transaction_ref,
                        sender=sender,
                        receiver=receiver_meter.user,
                        units=units_to_share,
                        meter_send=sender_meter,
                        meter_receive=receiver_meter,
                        direction='OUT',
                        status='PENDING',
                        message=f"Pending OTP verification for share to meter {receiver_meter_no}",
                        ip_address=request.META.get('REMOTE_ADDR'),
                        user_agent=request.META.get('HTTP_USER_AGENT', '')
                    )
                    
                    # Generate and send OTP
                    verification = VerificationCode.create_code(
                        user=sender,
                        purpose='share_units',
                        expiry_minutes=10
                    )
                    
                    transaction_details = f"Sharing {units_to_share} units to meter {receiver_meter_no}"
                    handle_send_share_verification.delay(
                        user_id=sender.id,
                        code=verification.code,
                        transaction_details=transaction_details
                    )
                    
                    return Response({
                        "success": True,
                        "message": "Verification code sent to your email",
                        "transaction_ref": transaction_ref,
                        "requires_verification": True
                    }, status=status.HTTP_200_OK)
                    
            except Exception as e:
                logger.error(f"Error initiating share: {str(e)}", exc_info=True)
                return Response({
                    "error": "An error occurred while initiating the share request"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        else:
            # Step 2: OTP verification and complete share
            otp_serializer = VerifyOTPSerializer(data=request.data)
            if not otp_serializer.is_valid():
                return Response(otp_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            verification_code = otp_serializer.validated_data['verification_code']
            transaction_ref = request.data.get('transaction_ref')
            
            # Fetch pending share from DB (session-less, works with API/server-action calls)
            pending_share_qs = ShareTransaction.objects.select_for_update().filter(
                sender=request.user,
                status='PENDING'
            )
            if transaction_ref:
                pending_share_qs = pending_share_qs.filter(share_transaction_id=transaction_ref)
            pending_share = pending_share_qs.order_by('-create_date').first()

            if not pending_share:
                return Response({"error": "No pending share found. Please start over."}, status=status.HTTP_400_BAD_REQUEST)
            
            user = request.user
            if not VerificationCode.verify_code(user, verification_code, 'share_units'):
                return Response({"error": "Invalid or expired verification code"}, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                with db_transaction.atomic():
                    # Retrieve pending data
                    receiver_meter_no = pending_share.meter_receive.meter_no
                    units_to_share = pending_share.units
                    transaction_ref = pending_share.share_transaction_id
                    
                    # Reload objects with lock
                    sender_meter = Meter.objects.select_for_update().get(id=pending_share.meter_send_id)
                    receiver_meter = Meter.objects.select_for_update().get(meter_no=receiver_meter_no)
                    
                    # Double-check wallet units
                    sender_wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)
                    if sender_wallet.balance < units_to_share:
                        return Response({"error": "Insufficient units. Transaction cancelled."}, status=status.HTTP_400_BAD_REQUEST)

                    # Deduct from sender wallet
                    sender_wallet.balance -= units_to_share
                    sender_wallet.save()

                    is_self_share = sender_meter.meter_no == receiver_meter_no
                    share_token = None

                    if is_self_share:
                        # Self-share: issue numeric token to load units to sender's meter
                        share_token = generate_numeric_token(10)  # Use numeric token
                        while MeterToken.objects.filter(token=share_token).exists():
                            share_token = generate_numeric_token(10)
                    
                        MeterToken.objects.create(
                            token=share_token,
                            units=units_to_share,
                            meter=receiver_meter,
                            user=receiver_meter.user,
                            is_used=False,
                            source='SHARE',
                            share_transaction_id=transaction_ref,
                            share_sender=user
                        )
                    else:
                        # Share to another meter: credit receiver wallet directly (no token)
                        receiver_wallet, _ = Wallet.objects.select_for_update().get_or_create(user=receiver_meter.user)
                        receiver_wallet.add(
                            units_to_share,
                            description=f"Units received from {sender_meter.meter_no}",
                            transaction_ref=transaction_ref
                        )
                        
                        # Update credit score for sharing (positive behavior)
                        CreditScoreService.update_credit_score(
                            user=user,
                            event_type='SHARE_UNITS',
                            reference_id=transaction_ref,
                            extra_data={'units': float(units_to_share)}
                        )
                    
                    # Create share record using legacy accounts wallet relation used by Share model
                    sender_account_wallet = AccountWallet.objects.filter(user=user).order_by('-create_date').first()
                    if sender_account_wallet is None:
                        sender_account_wallet = AccountWallet.objects.create(
                            user=user,
                            currency='USD',
                            balance=Decimal('0.00')
                        )
                    Share.objects.create(
                        share_transaction_id=transaction_ref,
                        wallet=sender_account_wallet,
                        units=units_to_share,
                        status="COMPLETED",
                        meter_number=receiver_meter,
                        share_transaction_reference=transaction_ref
                    )
                    
                    # Mark pending share transaction as completed
                    pending_share.status = "COMPLETED"
                    pending_share.verified_at = timezone.now()
                    pending_share.message = (
                        f"Shared {units_to_share} units from {sender_meter.meter_no} to {receiver_meter_no}"
                        + (" (token issued)" if is_self_share else " (wallet credited)")
                    )
                    pending_share.save(update_fields=['status', 'verified_at', 'message', 'modify_date'])

                    TransactionLog.objects.create(
                        user=user,
                        transaction_type=TransactionType.UNIT_SHARE,
                        units=units_to_share,
                        status='COMPLETED',
                        reference_id=transaction_ref,
                        details={'receiver_meter': receiver_meter_no, 'sender_meter': sender_meter.meter_no}
                    )
                    
                    # Send update email to sender (wallet deducted)
                    update_details = VerificationService.format_transaction_details(
                        'wallet_update',
                        amount=units_to_share,
                        transaction_id=transaction_ref,
                        new_balance=sender_wallet.balance,
                        date=timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                    )
                    handle_send_wallet_update.delay(user.id, update_details)

                    if is_self_share and share_token:
                        # Send token to sender (same meter)
                        handle_send_share_token.delay(
                            user.id,
                            share_token,
                            str(units_to_share),
                            receiver_meter_no,
                            sender_meter=sender_meter.meter_no,
                            sender_email=user.email
                        )
                    else:
                        # Notify receiver wallet credit (no token)
                        receiver_update = (
                            f"Wallet balance increased by {units_to_share} units\n"
                            f"Transaction ID: {transaction_ref}\n"
                            f"New Balance: {receiver_wallet.balance} units\n"
                            f"Date: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                        handle_send_wallet_update.delay(receiver_meter.user.id, receiver_update)
                    
                    logger.info(f"Share completed: {units_to_share} units from wallet to {receiver_meter_no}")
                    
                    return Response({
                        "success": True,
                        "message": "Units shared successfully.",
                        "transaction_id": transaction_ref,
                        "units_shared": str(units_to_share),
                        "new_sender_wallet_balance": str(sender_wallet.balance),
                        "token_sent": True if is_self_share else False,
                        "receiver_wallet_credited": False if is_self_share else True,
                        "timestamp": timezone.now().isoformat()
                    }, status=status.HTTP_200_OK)
                    
            except Exception as e:
                logger.error(f"Error completing share: {str(e)}", exc_info=True)
                return Response({
                    "error": "An error occurred while completing the share"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TransferUnitsView(APIView):
    permission_classes = [IsAuthenticated]

    @requires_feature("meter_transfers")
    def post(self, request):
        verification_code = request.data.get("verification_code")

        if not verification_code:
            serializer = TransferUnitsSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            try:
                with db_transaction.atomic():
                    old_meter_no = serializer.validated_data["meter_no_old"]
                    new_meter_no = serializer.validated_data["meter_no_new"]

                    user = request.user
                    user_wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)

                    if user_wallet.balance <= 0:
                        return Response({"error": "No units to transfer"}, status=status.HTTP_400_BAD_REQUEST)

                    try:
                        old_meter = Meter.objects.select_for_update().get(
                            meter_no=old_meter_no,
                            user=user,
                            is_active=True,
                        )
                    except Meter.DoesNotExist:
                        return Response(
                            {"error": "Old meter not found or inactive"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    try:
                        new_meter = Meter.objects.select_for_update().get(
                            meter_no=new_meter_no,
                            is_active=True,
                        )
                    except Meter.DoesNotExist:
                        return Response(
                            {"error": "New meter not found or inactive"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    if old_meter == new_meter:
                        return Response(
                            {"error": "Old and new meters must be different"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    transaction_ref = f"TRANSFER-{uuid.uuid4().hex[:8].upper()}"

                    request.session["pending_transfer"] = {
                        "old_meter_no": old_meter_no,
                        "new_meter_no": new_meter_no,
                        "units_to_transfer": str(user_wallet.balance),
                        "transaction_ref": transaction_ref,
                        "old_meter_id": old_meter.id,
                        "new_meter_id": new_meter.id,
                    }
                    request.session.modified = True

                    verification = VerificationCode.create_code(
                        user=user,
                        purpose="transfer_units",
                        expiry_minutes=10,
                    )

                    transaction_details = f"""
                    You're transferring all units ({user_wallet.balance}) from meter {old_meter_no} to {new_meter_no}.
                    WARNING: Your old meter will be deactivated!
                    Transaction ID: {transaction_ref}.
                    Code expires: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.
                    """

                    dispatch_task(
                        handle_send_transfer_verification,
                        user.id,
                        verification.code,
                        transaction_details,
                    )

                    return Response(
                        {
                            "success": True,
                            "message": "Verification code sent to your email. Please check and enter the 6-digit code.",
                            "step": "verification",
                            "warning": "This will deactivate your old meter!",
                        },
                        status=status.HTTP_200_OK,
                    )

            except Exception as e:
                logger.error("Error initiating transfer: %s", e, exc_info=True)
                return Response(
                    {"error": "An error occurred while initiating the transfer request"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        otp_serializer = VerifyOTPSerializer(data=request.data)
        if not otp_serializer.is_valid():
            return Response(otp_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        verification_code = otp_serializer.validated_data["verification_code"]
        pending_transfer = request.session.get("pending_transfer")
        if not pending_transfer:
            return Response(
                {"error": "No pending transfer found. Please start over."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        if not VerificationCode.verify_code(user, verification_code, "transfer_units"):
            return Response(
                {"error": "Invalid or expired verification code"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with db_transaction.atomic():
                old_meter_no = pending_transfer["old_meter_no"]
                new_meter_no = pending_transfer["new_meter_no"]
                units_to_transfer = Decimal(pending_transfer["units_to_transfer"])
                transaction_ref = pending_transfer["transaction_ref"]

                user_wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)
                old_meter = Meter.objects.select_for_update().get(meter_no=old_meter_no)
                new_meter = Meter.objects.select_for_update().get(meter_no=new_meter_no)

                if user_wallet.balance < units_to_transfer:
                    return Response(
                        {"error": "Insufficient units. Transaction cancelled."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                user_wallet.deduct(
                    units_to_transfer,
                    description=f"Transferred to new meter {new_meter_no}",
                    transaction_ref=transaction_ref,
                )

                old_meter.balance = Decimal("0.00")
                old_meter.is_active = False
                old_meter.save()

                new_meter.balance += units_to_transfer
                new_meter.save()

                ShareTransaction.objects.create(
                    share_transaction_id=transaction_ref,
                    sender=user,
                    receiver=new_meter.user if new_meter.user != user else user,
                    units=units_to_transfer,
                    meter_send=old_meter,
                    meter_receive=new_meter,
                    status="COMPLETED",
                    message=f"Meter transfer from {old_meter_no} to {new_meter_no} (old deactivated)",
                )

                update_details = f"""
                Transfer Completed Successfully:
                - Old Meter: {old_meter_no} (Now deactivated)
                - New Meter: {new_meter_no}
                - Units Transferred: {units_to_transfer}
                - New Balance on {new_meter_no}: {new_meter.balance} units
                - Transaction ID: {transaction_ref}
                - Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """

                dispatch_task(handle_send_wallet_update, user.id, update_details)

                if "pending_transfer" in request.session:
                    del request.session["pending_transfer"]
                request.session.modified = True

                return Response(
                    {
                        "success": True,
                        "message": "Transfer completed successfully",
                        "transaction_id": transaction_ref,
                        "units_transferred": str(units_to_transfer),
                        "new_balance": str(new_meter.balance),
                        "old_meter_deactivated": old_meter_no,
                        "timestamp": timezone.now().isoformat(),
                    },
                    status=status.HTTP_200_OK,
                )

        except Exception as e:
            logger.error("Error completing transfer: %s", e, exc_info=True)
            return Response(
                {"error": "An error occurred while completing the transfer"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
