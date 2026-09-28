import logging
import uuid
from django.db import transaction
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings  # Add this import

from loan.models import LoanApplication, LoanRepayment
from meter.models import Meter
from meter.services import push_units_to_thingsboard
from mtn_momo.services import MTNMoMoService
from transactions.models import TransactionLog, TransactionType

logger = logging.getLogger(__name__)

class MoMoPaymentView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, loan_id):
        try:
            loan = LoanApplication.objects.get(id=loan_id, user=request.user)
            
            if loan.status != 'DISBURSED':
                return Response(
                    {"error": "Loan is not disbursed or already completed"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            amount = float(request.data.get('amount', 0))
            phone_number = request.data.get('phone_number', '').strip()
            
            # Validate phone number
            if not phone_number:
                return Response(
                    {"error": "Phone number is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Format phone number
            if phone_number.startswith('0'):
                phone_number = '256' + phone_number[1:]
            elif not phone_number.startswith('256'):
                phone_number = '256' + phone_number
            
            # Remove any non-digit characters
            phone_number = ''.join(filter(str.isdigit, phone_number))
            
            if amount <= 0:
                return Response(
                    {"error": "Invalid amount"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if amount > loan.outstanding_balance:
                return Response(
                    {"error": f"Amount exceeds outstanding balance of {loan.outstanding_balance} UGX"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Generate unique references
            external_id = str(uuid.uuid4())
            payment_ref = f"LOAN{loan.loan_id}{uuid.uuid4().hex[:6].upper()}"
            
            # Use real MoMo when credentials are configured; otherwise simulate locally.
            from mtn_momo.config import should_simulate_payments

            if should_simulate_payments():
                return self.simulate_sandbox_payment(loan, amount, phone_number, external_id, payment_ref)
            return self.process_real_momo_payment(loan, amount, phone_number, external_id, payment_ref)
                
        except LoanApplication.DoesNotExist:
            return Response(
                {"error": "Loan not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"MoMo payment error: {str(e)}")
            return Response(
                {"error": f"Failed to process payment: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def simulate_sandbox_payment(self, loan, amount, phone_number, external_id, payment_ref):
        """Simulate successful payment in sandbox mode"""
        with transaction.atomic():
            repayment = LoanRepayment.objects.create(
                loan=loan,
                amount_paid=amount,
                units_paid=0,
                payment_reference=payment_ref,
                payment_method='MOBILE_MONEY',
                momo_external_id=external_id,
                momo_phone_number=phone_number,
                payment_status='PENDING',
                is_on_time=True
            )

        import threading
        threading.Thread(
            target=self._complete_sandbox_payment,
            args=(loan.id, amount, external_id, repayment.id),
            daemon=True
        ).start()

        return Response({
            "message": "Sandbox: Payment simulation started! Status will update in 5 seconds.",
            "payment_reference": payment_ref,
            "external_id": external_id,
            "status": "PENDING",
            "user_prompt": "Sandbox mode: No actual PIN prompt. Payment will auto-complete.",
            "note": "Check payment status in 5 seconds using the payment-status endpoint.",
            "poll_interval": 5000
        })

    def _complete_sandbox_payment(self, loan_id, amount, external_id, repayment_id):
        """Background task to complete sandbox payment after 5 seconds"""
        import time
        time.sleep(5)

        try:
            from loan.models import LoanApplication, LoanRepayment
            from django.db import transaction as db_transaction

            with db_transaction.atomic():
                repayment = LoanRepayment.objects.get(id=repayment_id)
                loan = LoanApplication.objects.get(id=loan_id)
                

                repayment.payment_status = 'SUCCESS'
                repayment.units_paid = 0
                repayment.momo_transaction_id = f"SANDBOX_{external_id}"
                repayment.save()

                TransactionLog.objects.create(
                    user=loan.user,
                    transaction_type=TransactionType.LOAN_REPAYMENT,
                    amount=amount,
                    units=0,
                    status='COMPLETED',
                    reference_id=loan.loan_id,
                    details={
                        'payment_reference': repayment.payment_reference,
                        'payment_source': 'PHONE',
                        'momo_external_id': external_id,
                        'sandbox': True,
                    }
                )

                logger.info(f"Sandbox: Loan payment completed. Loan: {loan.loan_id}, Amount: {amount}")
                
                # Check if loan is fully paid

                meter = Meter.objects.get(user=loan.user)
                meter.units += repayment.units_paid
                meter.save()
                push_ok, push_msg = push_units_to_thingsboard(
                    meter=meter,
                    units=repayment.units_paid,
                    reference_id=repayment.payment_reference,
                )
                if not push_ok:
                    logger.warning("ThingsBoard push failed for sandbox repayment %s: %s", repayment.payment_reference, push_msg)

                logger.info(f"Sandbox: Loan payment completed. Loan: {loan.loan_id}, Amount: {amount}, Units: {repayment.units_paid}")

                if loan.outstanding_balance <= 0:
                    loan.status = 'COMPLETED'
                    loan.save()
                    logger.info(f"Sandbox: Loan {loan.loan_id} marked as COMPLETED")

        except Exception as e:
            logger.error(f"Sandbox payment completion error: {str(e)}")

    def process_real_momo_payment(self, loan, amount, phone_number, external_id, payment_ref):
        """Process real MoMo payment via MTN request-to-pay."""
        momo_reference = str(uuid.uuid4())
        momo_service = MTNMoMoService()
        payment_result = momo_service.request_payment(
            amount=amount,
            phone_number=phone_number,
            reference_id=momo_reference,
            external_id=external_id,
            payer_message=f"Loan repayment - {payment_ref}",
        )

        if payment_result['status'] == 'PENDING':
            momo_reference = payment_result.get("reference_id", momo_reference)
            return self.create_pending_payment(
                loan, amount, phone_number, momo_reference, payment_ref, payment_result
            )
        return Response(
            {"error": f"Payment failed: {payment_result.get('message', 'Unknown error')}"},
            status=status.HTTP_400_BAD_REQUEST
        )

    def create_pending_payment(self, loan, amount, phone_number, external_id, payment_ref, payment_result):
        """Create pending payment record for later verification"""
        with transaction.atomic():
            LoanRepayment.objects.create(
                loan=loan,
                amount_paid=amount,
                units_paid=0,
                payment_reference=payment_ref,
                payment_method='MOBILE_MONEY',
                momo_external_id=external_id,
                momo_phone_number=phone_number,
                payment_status='PENDING',
                is_on_time=True
            )

        return Response({
            "message": "Payment initiated successfully! Please check your phone to complete the transaction.",
            "payment_reference": payment_ref,
            "external_id": external_id,
            "status": "PENDING",
            "user_prompt": payment_result.get('user_prompt', 'check your phone and enter the pin to complete the payment'),
            "note": "Payment is being processed. Check status in a few moments. Poll /payment-status/<external_id>/ endpoint.",
            "poll_interval": 5000
        })


class ActiveMoMoPaymentView(MoMoPaymentView):
    """Repay the account's active loan via MoMo without passing a loan ID."""

    def post(self, request):
        from loan.services import get_repayable_loan

        loan = get_repayable_loan(request.user)
        if not loan:
            return Response(
                {"error": "No active loan to repay."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().post(request, loan.id)


# class PaymentStatusView(APIView):
#     """Check payment status"""
#     authentication_classes = [JWTAuthentication]
#     permission_classes = [IsAuthenticated]
    
#     def get(self, request, external_id):
#         try:
#             repayment = LoanRepayment.objects.get(
#                 momo_external_id=external_id,
#                 loan__user=request.user
#             )

#             # If already successful, return immediately
#             if repayment.payment_status == 'SUCCESS':
#                 return self._build_success_response(repayment)

#             # FIXED: Check if we're in sandbox mode - use getattr with default
#             momo_config = getattr(settings, 'MTN_MOMO_CONFIG', {})
#             environment = momo_config.get('ENVIRONMENT', 'sandbox')
            
#             if environment == 'sandbox':
#                 # For sandbox, just return current status
#                 # The background thread will update it after 5 seconds
#                 return Response({
#                     "payment_status": repayment.payment_status,
#                     "amount": float(repayment.amount_paid),
#                     "units_added": repayment.units_paid,
#                     "transaction_id": repayment.momo_transaction_id,
#                     "note": "Sandbox mode: Status updates automatically after 5 seconds"
#                 })
#             else:
#                 # PRODUCTION: Check status from MoMo
#                 return self._check_real_payment_status(repayment, external_id)

#         except LoanRepayment.DoesNotExist:
#             logger.error(f"No repayment found for external_id {external_id} and user {request.user.id}")
#             return Response(
#                 {"error": "Payment not found"}, 
#                 status=status.HTTP_404_NOT_FOUND
#             )
#         except Exception as e:
#             logger.error(f"Error in PaymentStatusView for external_id {external_id}: {str(e)}")
#             return Response(
#                 {"error": f"Failed to check payment status: {str(e)}"},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
    
#     def _check_real_payment_status(self, repayment, external_id):
#         """Check real MoMo payment status"""
#         momo_service = MTNMoMoService()
#         status_result = momo_service.get_payment_status(external_id)
#         logger.info(f"MoMo status check for external_id {external_id}: {status_result}")

#         if status_result['status'] == 'SUCCESS':
#             with transaction.atomic():
#                 repayment.payment_status = 'SUCCESS'
#                 repayment.momo_transaction_id = status_result.get('transaction_id')

#                 # Calculate units
#                 if repayment.loan.tariff:
#                     units_equivalent = repayment.loan.calculate_units_from_amount(float(repayment.amount_paid))
#                 else:
#                     units_equivalent = float(repayment.amount_paid) / 500

#                 repayment.units_paid = round(units_equivalent, 2)
#                 repayment.save()

#                 # Add units to meter
#                 meter = Meter.objects.get(user=repayment.loan.user)
#                 meter.units += units_equivalent
#                 meter.save()

#                 # Check loan completion
#                 if repayment.loan.outstanding_balance <= 0:
#                     repayment.loan.status = 'COMPLETED'
#                     repayment.loan.save()

#         elif status_result['status'] in ['FAILED', 'CANCELLED']:
#             repayment.payment_status = status_result['status']
#             repayment.save()

#         return self._build_success_response(repayment)
    
#     def _build_success_response(self, repayment):
#         """Build standardized success response"""
#         return Response({
#             "payment_status": repayment.payment_status,
#             "amount": float(repayment.amount_paid),
#             "units_added": repayment.units_paid,
#             "transaction_id": repayment.momo_transaction_id,
#             "outstanding_balance": repayment.loan.outstanding_balance,
#             "loan_status": repayment.loan.status,
#             "user_prompt": "Enter PIN on phone if pending." if repayment.payment_status == 'PENDING' else None
#         })
        

class PaymentStatusView(APIView):
    """Check payment status"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, external_id):
        try:
            # FIXED: Use the correct field name for filtering
            repayment = LoanRepayment.objects.get(
                momo_external_id=external_id,
                loan__user=request.user  # Ensure user owns this payment
            )

            # If already successful, return immediately
            if repayment.payment_status == 'SUCCESS':
                return self._build_success_response(repayment)

            # Poll MoMo when not in simulated dev mode
            from mtn_momo.config import should_simulate_payments

            if should_simulate_payments():
                return Response({
                    "payment_status": repayment.payment_status,
                    "amount": float(repayment.amount_paid),
                    "transaction_id": repayment.momo_transaction_id,
                    "note": "Simulated mode: status updates automatically after a few seconds",
                })
            return self._check_real_payment_status(repayment, external_id)

        except LoanRepayment.DoesNotExist:
            logger.error(f"No repayment found for external_id {external_id} and user {request.user.id}")
            return Response(
                {"error": "Payment not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error in PaymentStatusView for external_id {external_id}: {str(e)}")
            return Response(
                {"error": f"Failed to check payment status: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _check_real_payment_status(self, repayment, external_id):
        """Check real MoMo payment status"""
        momo_service = MTNMoMoService()
        status_result = momo_service.get_payment_status(external_id)
        logger.info(f"MoMo status check for external_id {external_id}: {status_result}")

        if status_result['status'] == 'SUCCESS':
            with transaction.atomic():
                repayment.payment_status = 'SUCCESS'
                repayment.momo_transaction_id = status_result.get('transaction_id')

                repayment.units_paid = 0
                repayment.save()

                TransactionLog.objects.create(
                    user=repayment.loan.user,
                    transaction_type=TransactionType.LOAN_REPAYMENT,
                    amount=repayment.amount_paid,
                    units=0,
                    status='COMPLETED',
                    reference_id=repayment.loan.loan_id,
                    details={
                        'payment_reference': repayment.payment_reference,
                        'payment_source': 'PHONE',
                        'momo_external_id': external_id,
                    }
                )
                # Add units to meter
                meter = Meter.objects.get(user=repayment.loan.user)
                meter.units += units_equivalent
                meter.save()
                push_ok, push_msg = push_units_to_thingsboard(
                    meter=meter,
                    units=units_equivalent,
                    reference_id=repayment.payment_reference,
                )
                if not push_ok:
                    logger.warning("ThingsBoard push failed for repayment %s: %s", repayment.payment_reference, push_msg)

                # Check loan completion
                if repayment.loan.outstanding_balance <= 0:
                    repayment.loan.status = 'COMPLETED'
                    repayment.loan.save()

        elif status_result['status'] in ['FAILED', 'CANCELLED']:
            repayment.payment_status = status_result['status']
            repayment.save()

        return self._build_success_response(repayment)
    
    def _build_success_response(self, repayment):
        """Build standardized success response"""
        return Response({
            "payment_status": repayment.payment_status,
            "amount": float(repayment.amount_paid),
            "transaction_id": repayment.momo_transaction_id,
            "outstanding_balance": repayment.loan.outstanding_balance,
            "loan_status": repayment.loan.status,
            "user_prompt": "Enter PIN on phone if pending." if repayment.payment_status == 'PENDING' else None
        })        
        
        
        
        
