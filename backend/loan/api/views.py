import logging
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from accounts.models import generate_random_string
from wallet.models import UnitBalance
from meter.models import generate_numeric_token
from meter.models import Meter, MeterToken
from meter.services import push_units_to_thingsboard
from meter.api.serializers import MeterSerializer
from loan.models import ElectricityTariff, LoanApplication, LoanDisbursement, LoanRepayment
from transactions.models import UnitTransaction, TransactionLog, TransactionType
from loan.api.serializers import ElectricityTariffSerializer, LoanApplicationCreateSerializer, LoanApplicationSerializer
from loan.models import get_tier_by_score
from meter.models import MeterNotification
from meter.notifications import create_system_notification
from loan.scoring import (
    calculate_weighted_credit_score,
    get_or_create_credit_signal,
    get_factor_breakdown,
    FACTOR_WEIGHTS,
)
from wallet.models import Wallet as MoneyWallet
from loan.credit_score_service import CreditScoreService
from datetime import datetime
from loan.models import CreditScoreHistory, CreditScoreFactors
from loan.scoring import calculate_weighted_credit_score, get_or_create_dummy_credit_signal

from wallet.models import Wallet as UnitWallet
from utils.general import dispatch_task
from accounts.tasks import handle_send_loan_application_email

logger = logging.getLogger(__name__)


class TariffListView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = ElectricityTariffSerializer
    
    def get_queryset(self):
        return ElectricityTariff.objects.filter(is_active=True)

class LoanApplicationView(generics.ListCreateAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = LoanApplicationCreateSerializer  

    def get_serializer_class(self):
        if self.request.method == "POST":
            return LoanApplicationCreateSerializer
        return LoanApplicationSerializer  

    def create(self, request, *args, **kwargs):
        try:
            data = request.data

            # Prevent multiple active loans
            from loan.services import user_can_apply_for_loan

            can_apply, apply_message = user_can_apply_for_loan(request.user)
            if not can_apply:
                return Response(
                    {"error": apply_message},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if user has a meter first
            try:
                meter = Meter.objects.get(user=request.user)
            except Meter.DoesNotExist:
                return Response(
                    {"error": "No meter found. Please register your meter before applying for a loan."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)

            from utils.billing import get_active_domestic_tariff

            tariff = get_active_domestic_tariff()

            from loan.services import resolve_user_loan_access

            access = resolve_user_loan_access(request.user)
            credit_signal = get_or_create_credit_signal(request.user)
            credit_score = access["credit_score"]
            credit_breakdown = get_factor_breakdown(credit_signal)

            amount_requested = float(data.get("amount_requested", 0))
            max_eligible = access["max_eligible_amount"]
            tier_name = access["loan_tier"]
            interest_rate = access["interest_rate"] or 12.0

            if not access["is_loan_eligible"]:
                amount_approved = 0
            else:
                amount_approved = min(max_eligible, amount_requested)

            loan = serializer.save(
                user=request.user,
                credit_score=credit_score,
                amount_approved=amount_approved if amount_approved > 0 else None,
                loan_tier=tier_name,
                interest_rate=interest_rate,
                tariff = tariff,
                status="APPROVED" if amount_approved > 0 else "REJECTED",
                rejection_reason="" if amount_approved > 0 else "Loan limit exceeded or account at risk"
            )

            # Log application
            TransactionLog.objects.create(
                user=request.user,
                transaction_type=TransactionType.LOAN_APPLICATION,
                amount=amount_requested,
                status=loan.status,
                reference_id=loan.loan_id,
                details={
                    'purpose': loan.purpose,
                    'tenure_months': loan.tenure_months,
                    'credit_score': credit_score,
                    'loan_tier': tier_name,
                    'amount_approved': float(amount_approved) if amount_approved else 0
                }
            )
            create_system_notification(
                user=request.user,
                notification_type=MeterNotification.TYPE_LOAN_APPLICATION,
                message=(
                    f"Loan application {loan.loan_id}: {loan.status}. "
                    f"Requested UGX {amount_requested:,.2f}, "
                    f"approved UGX {float(amount_approved):,.2f}."
                ),
                units_kwh=Decimal("0"),
            )
            dispatch_task(
                handle_send_loan_application_email,
                request.user.id,
                loan.loan_id,
                loan.status,
                amount_requested,
                float(amount_approved or 0),
            )

            # Loans within the client's credit limit are disbursed immediately;
            # disburse_loan() raises its own notification + email for the disbursement.
            disbursement_result = None
            if loan.status == "APPROVED":
                from loan.services import disburse_loan

                try:
                    disbursement_result = disburse_loan(request.user, loan.id, channel="WEB")
                    loan.refresh_from_db()
                except Exception:
                    # Leave the loan APPROVED rather than failing the application -
                    # it can be disbursed later (e.g. via the admin panel).
                    logger.exception("Auto-disbursement failed for loan %s", loan.loan_id)

            # Calculate units based on tariff (for response)
            if tariff and amount_approved:
                units_calculated = loan.calculate_units_from_amount()
                cost_breakdown = self.get_cost_breakdown(loan, float(amount_approved))
            else:
                units_calculated = amount_approved / 500 
                cost_breakdown = None

            response_data = {
                "loan_id": loan.loan_id,
                "credit_score": credit_score,
                "status": loan.status,
                "amount_requested": amount_requested,
                "amount_approved": float(amount_approved) if amount_approved > 0 else 0,
                "loan_tier": tier_name,
                "max_eligible_amount": max_eligible,
                "interest_rate": interest_rate,
                "tariff_applied": tariff.tariff_code if tariff else None,
                "units_calculated": units_calculated,
                "cost_breakdown": cost_breakdown,
                "credit_factors": {
                    "payment_history": credit_signal.payment_history,
                    "energy_consumption": credit_signal.energy_consumption,
                    "financial_capacity": credit_signal.financial_capacity,
                    "major_weights": FACTOR_WEIGHTS,
                    "factor_scores": credit_breakdown["factor_scores"],
                    "subfactor_scores": credit_breakdown["subfactor_scores"],
                    "threshold": 75,
                    "source": credit_signal.source,
                    "trust_level": access.get("trust_level"),
                    "trust_cap": access.get("trust_cap"),
                    "starter_max_loan": access.get("starter_max_loan"),
                },
            }

            if loan.status == "DISBURSED":
                response_data.update({
                    "message": (
                        f"Loan approved and disbursed! You qualified for {tier_name} tier. "
                        f"{disbursement_result['units_disbursed']} units have been added to your wallet."
                    ),
                    "units_disbursed": disbursement_result["units_disbursed"],
                    "meter_push_ok": disbursement_result["meter_push_ok"],
                })
            elif loan.status == "APPROVED":
                response_data.update({
                    "message": (
                        f"Loan approved! You qualified for {tier_name} tier. "
                        "We're crediting your units now - if they don't arrive shortly, contact support."
                    )
                })
            else:
                response_data.update({
                    "rejection_reason": loan.rejection_reason
                })

            return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Loan application error: {str(e)}")
            return Response(
                {"error": f"Failed to submit loan application: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def calculate_credit_score(self, credit_signal):
        """Compute 0-100 score from weighted third-party factors."""
        return max(0, min(calculate_weighted_credit_score(credit_signal), 100))

    def get_cost_breakdown(self, loan, amount):
        """Calculate detailed cost breakdown for block tariff"""
        if not loan.tariff:
            return None
    
        blocks = loan.tariff.blocks.all().order_by('block_order')
        breakdown = []
        remaining_amount = amount
    
        for block in blocks:
            if remaining_amount <= 0:
                break
            
            if block.max_units:
                block_units_available = block.max_units - block.min_units + 1
                block_cost = block_units_available * float(block.rate_per_unit)
            
                if remaining_amount >= block_cost:
                    # Full block
                    units_from_block = block_units_available
                    cost_from_block = block_cost
                    remaining_amount -= block_cost
                else:
                    # Partial block
                    units_from_block = remaining_amount / float(block.rate_per_unit)
                    cost_from_block = remaining_amount
                    remaining_amount = 0
            else:
                # Last block - use all remaining amount
                units_from_block = remaining_amount / float(block.rate_per_unit)
                cost_from_block = remaining_amount
                remaining_amount = 0
        
            breakdown.append({
                'block_name': block.block_name,
                'units': round(units_from_block, 2),
                'rate': float(block.rate_per_unit),
                'cost': round(cost_from_block, 2),
                'block_range': f"{block.min_units}-{block.max_units if block.max_units else '∞'}"
            })
    
        return breakdown
    # def determine_loan_tier(self, score):
    #     """Determine loan tier, maximum amount, and interest rate based on credit score"""
    #     tiers = [
    #         {'min_score': 75, 'max_score': 79, 'name': 'BRONZE', 'max_amount': 50000, 'interest_rate': 12.0},
    #         {'min_score': 80, 'max_score': 84, 'name': 'SILVER', 'max_amount': 100000, 'interest_rate': 11.0},
    #         {'min_score': 85, 'max_score': 89, 'name': 'GOLD', 'max_amount': 150000, 'interest_rate': 10.0},
    #         {'min_score': 90, 'max_score': 100, 'name': 'PLATINUM', 'max_amount': 200000, 'interest_rate': 9.0}
    #     ]
        
    #     for tier in tiers:
    #         if tier['min_score'] <= score <= tier['max_score']:
    #             return tier['name'], tier['max_amount'], tier['interest_rate']
    #     return None
    def determine_loan_tier(self, score):
        """Determine loan tier, maximum amount, and interest rate based on credit score"""
        tier_info = get_tier_by_score(score)
    
        if tier_info:
            return tier_info['name'], tier_info['max_amount'], tier_info['interest_rate']
        return None

    def determine_approved_amount(self, score, requested_amount):
        """Determine approved loan amount based on credit score tier"""
        tier_info = self.determine_loan_tier(score)
        if not tier_info:
            return 0
        
        tier_name, max_amount, interest_rate = tier_info
        return min(max_amount, requested_amount)

    def get_queryset(self):
        # For GET requests, return user's loans
        if self.request.method == "GET":
            from loan.services import reconcile_user_loan_statuses

            reconcile_user_loan_statuses(self.request.user)
            return LoanApplication.objects.filter(user=self.request.user)
        return LoanApplication.objects.none()

class UserLoansView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = LoanApplicationSerializer
    
    def get_queryset(self):
        from loan.services import reconcile_user_loan_statuses

        reconcile_user_loan_statuses(self.request.user)
        return LoanApplication.objects.filter(user=self.request.user)

class LoanDetailView(generics.RetrieveAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = LoanApplicationSerializer
    
    def get_queryset(self):
        from loan.services import reconcile_user_loan_statuses

        reconcile_user_loan_statuses(self.request.user)
        return LoanApplication.objects.filter(user=self.request.user)


# class LoanRepaymentView(APIView):
#     permission_classes = (IsAuthenticated,)
    
#     def post(self, request, loan_id):
#         try:
#             loan = LoanApplication.objects.get(id=loan_id, user=request.user)
            
#             if loan.status != 'DISBURSED':
#                 return Response(
#                     {"error": "Loan is not disbursed or already completed"}, 
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
            
#             amount = float(request.data.get('amount', 0))
            
#             if amount <= 0:
#                 return Response(
#                     {"error": "Invalid amount"}, 
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
            
#             # Get current outstanding balance
#             current_balance = loan.outstanding_balance
            
#             if amount > current_balance:
#                 return Response(
#                     {"error": f"Amount exceeds outstanding balance of {current_balance} UGX"}, 
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
            
#             payment_source = str(request.data.get('payment_source', 'PHONE')).upper()
#             if payment_source not in {'WALLET', 'PHONE', 'MOBILE_MONEY'}:
#                 return Response(
#                     {"error": "Payment source must be WALLET or PHONE"},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )

#             tariff_info = {
#                 'tariff_code': loan.tariff.tariff_code if loan.tariff else 'DEFAULT',
#             }
            
#             with transaction.atomic():
#                 # Generate payment reference
#                 payment_ref = generate_random_string(12)

#                 if payment_source == 'WALLET':
#                     wallet, _ = MoneyWallet.objects.select_for_update().get_or_create(user=request.user)
#                     payment_amount = Decimal(str(amount))
#                     if wallet.balance < payment_amount:
#                         return Response(
#                             {"error": "Insufficient wallet balance", "wallet_balance": str(wallet.balance)},
#                             status=status.HTTP_400_BAD_REQUEST
#                         )
#                     wallet.deduct(
#                         payment_amount,
#                         description=f"Loan repayment for {loan.loan_id}",
#                         transaction_ref=payment_ref,
#                     )
                
#                 # Create repayment record
#                 repayment = LoanRepayment.objects.create(
#                     loan=loan,
#                     amount_paid=amount,
#                     units_paid=0,
#                     payment_reference=payment_ref,
#                     is_on_time=self.check_payment_timeliness(loan),
#                     payment_method='MOBILE_MONEY' if payment_source != 'WALLET' else 'CASH',
#                     payment_status='SUCCESS'
#                 )
                
#                 # Create Transaction Log - THIS WAS MISSING
#                 TransactionLog.objects.create(
#                     user=request.user,
#                     transaction_type=TransactionType.LOAN_REPAYMENT,
#                     amount=amount,
#                     units=0,
#                     status='COMPLETED',
#                     reference_id=loan.loan_id,
#                     details={
#                         'payment_reference': payment_ref,
#                         'loan_id': loan.loan_id,
#                         'payment_source': payment_source
#                     }
#                 )

#                 # IMPORTANT: Refresh loan from database to get updated state
#                 loan.refresh_from_db()
                
#                 # Check if loan is fully paid - after recording the payment
#                 new_balance = loan.outstanding_balance
                
#                 if new_balance <= 0:
#                     loan.status = 'COMPLETED'
#                     loan.save()
                    
#                     # Log completion
#                     TransactionLog.objects.create(
#                         user=request.user,
#                         transaction_type=TransactionType.LOAN_COMPLETION,
#                         amount=0,
#                         status='COMPLETED',
#                         reference_id=loan.loan_id,
#                         details={'message': 'Loan fully repaid'}
#                     )
                    
#                     message = "Loan fully repaid! Thank you."
#                 else:
#                     message = "Payment successful"
            
#             # Return updated loan info
#             return Response({
#                 "message": message,
#                 "payment_reference": payment_ref,
#                 "tariff_info": tariff_info,
#                 "outstanding_balance": loan.outstanding_balance,
#                 "loan_status": loan.status,  # Return updated status
#                 "total_paid": loan.amount_paid,
#                 "total_due": loan.total_amount_due
#             })
            
#         except LoanApplication.DoesNotExist:
#             return Response(
#                 {"error": "Loan not found"}, 
#                 status=status.HTTP_404_NOT_FOUND
#             )
#         except Exception as e:
#             logger.error(f"Repayment error: {str(e)}")
#             return Response(
#                 {"error": f"Failed to process repayment: {str(e)}"}, 
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
    
#     def get_repayment_breakdown(self, loan, amount):
#         """Calculate breakdown for repayment amount"""
#         if not loan.tariff:
#             return None
#         return loan.calculate_cost_for_units(loan.calculate_units_from_amount(amount))
    
#     def check_payment_timeliness(self, loan):
#         """Check if payment is on time"""
#         if not loan.due_date:
#             return True
#         return timezone.now() <= loan.due_date


# class LoanDisbursementView(APIView):
#     permission_classes = (IsAuthenticated,)
    
#     def get_cost_breakdown(self, loan, amount):
#         """Calculate detailed cost breakdown for block tariff"""
#         if not loan.tariff:
#             return None
        
#         blocks = loan.tariff.blocks.all().order_by('block_order')
#         breakdown = []
#         remaining_amount = amount
        
#         for block in blocks:
#             if remaining_amount <= 0:
#                 break
                
#             if block.max_units:
#                 block_units_available = block.max_units - block.min_units + 1
#                 block_cost = block_units_available * float(block.rate_per_unit)
                
#                 if remaining_amount >= block_cost:
#                     units_from_block = block_units_available
#                     cost_from_block = block_cost
#                     remaining_amount -= block_cost
#                 else:
#                     units_from_block = remaining_amount / float(block.rate_per_unit)
#                     cost_from_block = remaining_amount
#                     remaining_amount = 0
#             else:
#                 units_from_block = remaining_amount / float(block.rate_per_unit)
#                 cost_from_block = remaining_amount
#                 remaining_amount = 0
            
#             breakdown.append({
#                 'block_name': block.block_name,
#                 'units': round(units_from_block, 2),
#                 'rate': float(block.rate_per_unit),
#                 'cost': round(cost_from_block, 2),
#                 'block_range': f"{block.min_units}-{block.max_units if block.max_units else 'inf'}"
#             })
        
#         return breakdown
    
#     def post(self, request, loan_id):
#         try:
#             loan = LoanApplication.objects.get(id=loan_id, user=request.user)
            
#             if loan.status != 'APPROVED':
#                 return Response({"error": "Loan is not approved for disbursement"}, status=status.HTTP_400_BAD_REQUEST)
            
#             if not loan.amount_approved or loan.amount_approved <= 0:
#                 return Response({"error": "Loan amount not approved"}, status=status.HTTP_400_BAD_REQUEST)
            
#             with transaction.atomic():
#                 # Get user's meter
#                 try:
#                     meter = Meter.objects.get(user=request.user)
#                 except Meter.DoesNotExist:
#                     return Response({"error": "Meter not found"}, status=status.HTTP_400_BAD_REQUEST)
                
#                 # Calculate units to disburse based on tariff block rates
#                 if loan.tariff:
#                     units_to_disburse = loan.calculate_units_from_amount()
#                     # FIXED: Now this method exists
#                     cost_breakdown = self.get_cost_breakdown(loan, float(loan.amount_approved))
#                     tariff_info = {
#                         'tariff_code': loan.tariff.tariff_code,
#                         'tariff_name': loan.tariff.tariff_name,
#                         'cost_breakdown': cost_breakdown
#                     }
#                 else:
#                     # Fallback to default calculation (500 UGX per unit)
#                     units_to_disburse = round(float(loan.amount_approved) / 500)
#                     tariff_info = {
#                         'tariff_code': 'DEFAULT',
#                         'rate_per_kwh': 500,
#                         'tariff_name': 'Default Rate'
#                     }

#                 # Create disbursement record
#                 disbursement = LoanDisbursement.objects.create(
#                     loan_application=loan,
#                     disbursed_amount=loan.amount_approved,
#                     units_disbursed=units_to_disburse,
#                     meter=meter
#                 )
#                 token_value = disbursement.token
#                 while MeterToken.objects.filter(token=token_value).exists():
#                     token_value = generate_random_string(10)
#                 if token_value != disbursement.token:
#                     disbursement.token = token_value
#                     disbursement.save(update_fields=['token'])

#                 meter_token = MeterToken.objects.create(
#                     user=request.user,
#                     token=token_value,
#                     units=units_to_disburse,
#                     meter=meter,
#                     source='LOAN',
#                     loan_application=loan,
#                 )
                
#                 # Update loan status to DISBURSED
#                 loan.status = 'DISBURSED'
#                 loan.save()

#                 TransactionLog.objects.create(
#                     user=request.user,
#                     transaction_type=TransactionType.LOAN_DISBURSEMENT,
#                     amount=loan.amount_approved,
#                     units=units_to_disburse,
#                     status='COMPLETED',
#                     reference_id=loan.loan_id,
#                     details={
#                         'units_disbursed': float(units_to_disburse),
#                         'token': meter_token.token
#                     }
#                 )
            
#             return Response({
#                 "message": "Loan disbursed successfully. Use the generated token on your meter.",
#                 "token": meter_token.token,
#                 "disbursement_token": meter_token.token,
#                 "units_disbursed": round(units_to_disburse, 2),
#                 "tariff_info": tariff_info
#             })
            
#         except LoanApplication.DoesNotExist:
#             return Response({"error": "Loan not found"}, status=status.HTTP_404_NOT_FOUND)
#         except Meter.DoesNotExist:
#             return Response({"error": "No meter found for this account. Please register your meter first."}, status=400)

class LoanNotificationView(APIView):
    permission_classes = (IsAuthenticated,)
    
    def post(self, request, loan_id):
        try:
            loan = LoanApplication.objects.get(id=loan_id, user=request.user)
            
            if loan.user_notified:
                return Response({"message": "User already notified"}, status=status.HTTP_200_OK)
            
            # Mark as notified
            loan.user_notified = True
            loan.save()
            
            if loan.status == 'APPROVED' and loan.check_eligibility():
                # For approved loans, we'll handle disbursement in a separate step
                return Response({
                    "message": "Loan approved! You can now disburse the loan to receive units.",
                    "approved": True,
                    "loan_id": loan.id
                })
            else:
                # For rejected loans, suggest buying units
                return Response({
                    "message": "Loan not approved. Consider purchasing units directly.",
                    "approved": False,
                    "suggestion": "buy_units"
                })
                
        except LoanApplication.DoesNotExist:
            return Response({"error": "Loan not found"}, status=status.HTTP_404_NOT_FOUND)
        
class LoanStatsView(APIView):
    permission_classes = (IsAuthenticated,)
    
    def get(self, request):
        try:
            loans = LoanApplication.objects.filter(user=request.user)

            pending_applications = loans.filter(status="PENDING").count()
            active_loans = loans.filter(status__in=["APPROVED", "DISBURSED", "DEFAULTED"]).count()
            approved_loans = loans.filter(status="APPROVED").count()
            total_loans = loans.count()

            total_borrowed = float(
                loans.filter(status__in=["APPROVED", "DISBURSED", "COMPLETED", "DEFAULTED"])
                .aggregate(total=Sum("amount_approved"))["total"] or 0
            )

            total_repayments = float(
                LoanRepayment.objects.filter(loan__user=request.user)
                .aggregate(total=Sum("amount_paid"))["total"] or 0
            )

            outstanding_balance = sum(
                float(l.outstanding_balance)
                for l in loans.exclude(status__in=["COMPLETED", "REJECTED"])
            )

            credit_signal = get_or_create_dummy_credit_signal(request.user)
            credit_score = calculate_weighted_credit_score(credit_signal)

            stats = {
                "active_loans": active_loans,
                "pending_applications": pending_applications,
                "approved_loans": approved_loans,
                "total_loans": total_loans,
                "total_borrowed": total_borrowed,
                "total_repayments": total_repayments,
                "outstanding_balance": outstanding_balance,
                "credit_score": credit_score,
                "has_blocking_loan": active_loans > 0 or pending_applications > 0 or outstanding_balance > 0,
            }

            return Response(stats, status=200)

        except Exception as e:
            logger.exception("Loan stats failed")
            return Response({"error": "Failed to fetch stats"}, status=500)


class LoanDisbursementView(APIView):
    permission_classes = (IsAuthenticated,)
    def post(self, request, loan_id):
        try:
            from loan.services import LoanOperationError, repay_loan

            result = repay_loan(
                request.user,
                loan_id,
                request.data.get("amount", 0),
                channel="WEB",
                payment_method="CASH",
            )
            return Response(
                {
                    "message": result["message"],
                    "units_added": result["units_added"],
                    "payment_reference": result["payment_reference"],
                    "outstanding_balance": result["outstanding_balance"],
                    "loan_status": result["loan_status"],
                }
            )

        except LoanOperationError as exc:
            return Response({"error": exc.message}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Repayment error: {str(e)}")
            return Response(
                {"error": f"Failed to process repayment: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get_repayment_breakdown(self, loan, amount):
        """Calculate breakdown for repayment amount"""
        if not loan.tariff:
            return None
        return loan.calculate_cost_for_units(loan.calculate_units_from_amount(amount))
    
    def check_payment_timeliness(self, loan):
        """Check if payment is on time"""
        if not loan.due_date:
            return True
        return timezone.now() <= loan.due_date


class LoanDisbursementView(APIView):
    permission_classes = (IsAuthenticated,)
    
    def get_cost_breakdown(self, loan, amount):
        """Calculate detailed cost breakdown for block tariff"""
        if not loan.tariff:
            return None
        
        blocks = loan.tariff.blocks.all().order_by('block_order')
        breakdown = []
        remaining_amount = amount
        
        for block in blocks:
            if remaining_amount <= 0:
                break
                
            if block.max_units:
                block_units_available = block.max_units - block.min_units + 1
                block_cost = block_units_available * float(block.rate_per_unit)
                
                if remaining_amount >= block_cost:
                    units_from_block = block_units_available
                    cost_from_block = block_cost
                    remaining_amount -= block_cost
                else:
                    units_from_block = remaining_amount / float(block.rate_per_unit)
                    cost_from_block = remaining_amount
                    remaining_amount = 0
            else:
                units_from_block = remaining_amount / float(block.rate_per_unit)
                cost_from_block = remaining_amount
                remaining_amount = 0
            
            breakdown.append({
                'block_name': block.block_name,
                'units': round(units_from_block, 2),
                'rate': float(block.rate_per_unit),
                'cost': round(cost_from_block, 2),
                'block_range': f"{block.min_units}-{block.max_units if block.max_units else 'inf'}"
            })
        
        return breakdown
    
    def post(self, request, loan_id):
        try:
            loan = LoanApplication.objects.get(id=loan_id, user=request.user)
            
            if loan.status != 'APPROVED':
                return Response({"error": "Loan is not approved for disbursement"}, status=status.HTTP_400_BAD_REQUEST)
            
            if not loan.amount_approved or loan.amount_approved <= 0:
                return Response({"error": "Loan amount not approved"}, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                # Get user's meter
                try:
                    meter = Meter.objects.get(user=request.user)
                except Meter.DoesNotExist:
                    return Response({"error": "Meter not found"}, status=status.HTTP_400_BAD_REQUEST)
                
                # Calculate units to disburse based on tariff block rates
                if loan.tariff:
                    units_to_disburse = loan.calculate_units_from_amount()
                    cost_breakdown = self.get_cost_breakdown(loan, float(loan.amount_approved))
                    tariff_info = {
                        'tariff_code': loan.tariff.tariff_code,
                        'tariff_name': loan.tariff.tariff_name,
                        'cost_breakdown': cost_breakdown
                    }
                else:
                    # Fallback to default calculation (500 UGX per unit)
                    units_to_disburse = round(float(loan.amount_approved) / 500)
                    tariff_info = {
                        'tariff_code': 'DEFAULT',
                        'rate_per_kwh': 500,
                        'tariff_name': 'Default Rate'
                    }
                
                # ADD UNITS TO UNIT BALANCE (for sharing)
                unit_balance, _ = UnitBalance.objects.get_or_create(user=request.user)
                unit_balance.add_units(
                    units_to_disburse,
                    description=f"Loan {loan.loan_id} disbursement",
                    reference=loan.loan_id
                )
                
                # Create numeric token for meter loading
                token_value = generate_numeric_token(10)  # Use numeric token
                while MeterToken.objects.filter(token=token_value).exists():
                    token_value = generate_numeric_token(10)
                
                meter_token = MeterToken.objects.create(
                    user=request.user,
                    token=token_value,
                    units=units_to_disburse,
                    meter=meter,
                    source='LOAN',
                    loan_application=loan,
                    is_used=False  # Token not used yet
                )
                
                # Create disbursement record
                disbursement = LoanDisbursement.objects.create(
                    loan_application=loan,
                    disbursed_amount=loan.amount_approved,
                    units_disbursed=units_to_disburse,
                    token=token_value,
                    meter=meter
                )
                
                # Update loan status to DISBURSED
                loan.status = 'DISBURSED'
                loan.save()
                
                # Log transaction
                TransactionLog.objects.create(
                    user=request.user,
                    transaction_type=TransactionType.LOAN_DISBURSEMENT,
                    amount=loan.amount_approved,
                    units=units_to_disburse,
                    status='COMPLETED',
                    reference_id=loan.loan_id,
                    details={
                        'units_disbursed': float(units_to_disburse),
                        'token': meter_token.token,
                        'unit_balance_after': float(unit_balance.balance)
                    }
                )
                
                logger.info(
                    f"Loan {loan.loan_id} disbursed: "
                    f"Added {units_to_disburse} units to {request.user.email}'s UnitBalance. "
                    f"New unit balance: {unit_balance.balance}. "
                    f"Numeric token: {token_value}"
                )
                
                return Response({
                    "message": "Loan disbursed successfully! Units added to your available balance.",
                    "token": meter_token.token,  # Numeric token
                    "units_disbursed": round(units_to_disburse, 2),
                    "units_available_to_share": float(unit_balance.balance),
                    "tariff_info": tariff_info,
                    "note": "Use the token above to load units to your meter, or share units with others."
                })
                
            from loan.services import LoanOperationError, disburse_loan

            result = disburse_loan(request.user, loan_id, channel="WEB")
            return Response(
                {
                    "message": "Loan disbursed successfully to your unit wallet!",
                    "units_added_to_wallet": result["units_disbursed"],
                    "units_disbursed": result["units_disbursed"],
                    "meter_push": {
                        "status": "OK" if result["meter_push_ok"] else "FAILED",
                        "message": result["meter_push_message"],
                    },
                }
            )

        except LoanOperationError as exc:
            return Response({"error": exc.message}, status=status.HTTP_400_BAD_REQUEST)
        except LoanApplication.DoesNotExist:
            return Response({"error": "Loan not found"}, status=status.HTTP_404_NOT_FOUND)
        except Meter.DoesNotExist:
            return Response({"error": "No meter found for this account. Please register your meter first."}, status=400)
        except Exception as e:
            logger.error(f"Loan disbursement error: {str(e)}")
            return Response({"error": f"Failed to disburse loan: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LoanRepaymentView(APIView):
    permission_classes = (IsAuthenticated,)
    
    def post(self, request, loan_id):
        try:
            loan = LoanApplication.objects.get(id=loan_id, user=request.user)
            
            if loan.status != 'DISBURSED':
                return Response(
                    {"error": "Loan is not disbursed or already completed"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            amount = float(request.data.get('amount', 0))
            
            if amount <= 0:
                return Response(
                    {"error": "Invalid amount"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            current_balance = loan.outstanding_balance
            
            if amount > current_balance:
                return Response(
                    {"error": f"Amount exceeds outstanding balance of {current_balance} UGX"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            payment_source = str(request.data.get('payment_source', 'PHONE')).upper()
            if payment_source not in {'WALLET', 'PHONE', 'MOBILE_MONEY'}:
                return Response(
                    {"error": "Payment source must be WALLET or PHONE"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if payment is on time
            is_on_time = self.check_payment_timeliness(loan)
            days_late = 0
            if not is_on_time and loan.due_date:
                days_late = (timezone.now() - loan.due_date).days
            
            tariff_info = {
                'tariff_code': loan.tariff.tariff_code if loan.tariff else 'DEFAULT',
            }
            
            with transaction.atomic():
                payment_ref = generate_random_string(12)

                if payment_source == 'WALLET':
                    wallet, _ = MoneyWallet.objects.select_for_update().get_or_create(user=request.user)
                    payment_amount = Decimal(str(amount))
                    if wallet.balance < payment_amount:
                        return Response(
                            {"error": "Insufficient wallet balance", "wallet_balance": str(wallet.balance)},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    wallet.deduct(
                        payment_amount,
                        description=f"Loan repayment for {loan.loan_id}",
                        transaction_ref=payment_ref,
                    )
                
                # Create repayment record
                repayment = LoanRepayment.objects.create(
                    loan=loan,
                    amount_paid=amount,
                    units_paid=0,
                    payment_reference=payment_ref,
                    is_on_time=is_on_time,
                    payment_method='MOBILE_MONEY' if payment_source != 'WALLET' else 'CASH',
                    payment_status='SUCCESS'
                )
                
                # Update credit score for repayment
                CreditScoreService.update_credit_score(
                    user=request.user,
                    event_type='LOAN_REPAYMENT',
                    reference_id=loan.loan_id,
                    extra_data={
                        'amount': amount,
                        'is_on_time': is_on_time,
                        'days_late': days_late,
                        'payment_source': payment_source
                    }
                )
                
                # Create Transaction Log
                TransactionLog.objects.create(
                    user=request.user,
                    transaction_type=TransactionType.LOAN_REPAYMENT,
                    amount=amount,
                    units=0,
                    status='COMPLETED',
                    reference_id=loan.loan_id,
                    details={
                        'payment_reference': payment_ref,
                        'loan_id': loan.loan_id,
                        'payment_source': payment_source,
                        'is_on_time': is_on_time
                    }
                )

                loan.refresh_from_db()
                new_balance = loan.outstanding_balance
                
                if new_balance <= 0:
                    loan.status = 'COMPLETED'
                    loan.save()
                    
                    # Bonus credit score for completing loan
                    CreditScoreService.update_credit_score(
                        user=request.user,
                        event_type='LOAN_COMPLETION',
                        reference_id=loan.loan_id,
                        extra_data={'loan_id': loan.loan_id}
                    )
                    
                    TransactionLog.objects.create(
                        user=request.user,
                        transaction_type=TransactionType.LOAN_COMPLETION,
                        amount=0,
                        status='COMPLETED',
                        reference_id=loan.loan_id,
                        details={'message': 'Loan fully repaid'}
                    )
                    
                    message = "Loan fully repaid! Thank you."
                else:
                    message = "Payment successful"
            
            # Get updated credit score
            new_credit_score, _, _ = CreditScoreService.update_credit_score(
                request.user, 'NO_CHANGE'
            )
            
            return Response({
                "message": message,
                "payment_reference": payment_ref,
                "tariff_info": tariff_info,
                "outstanding_balance": loan.outstanding_balance,
                "loan_status": loan.status,
                "total_paid": loan.amount_paid,
                "total_due": loan.total_amount_due,
                "credit_score_updated": True
            })
            
        except LoanApplication.DoesNotExist:
            return Response(
                {"error": "Loan not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Repayment error: {str(e)}")
            return Response(
                {"error": f"Failed to process repayment: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def check_payment_timeliness(self, loan):
        if not loan.due_date:
            return True
        return timezone.now() <= loan.due_date


class CreditScoreView(APIView):
    permission_classes = (IsAuthenticated,)
    
    def get(self, request):
        try:            
            user = request.user
            
            # Get or create credit signal (base score source)
            credit_signal = get_or_create_dummy_credit_signal(user)
            
            # Calculate base score from third-party factors (0-100)
            base_score = calculate_weighted_credit_score(credit_signal)
            
            # Get or create behavioral factors
            factors, _ = CreditScoreFactors.objects.get_or_create(user=user)
            
            # Calculate behavioral bonus (max 40 points)
            behavioral_bonus = min(40, (
                (factors.on_time_payments * 2) +
                (factors.wallet_usage_count * 1) +
                (factors.purchase_frequency * 1) +
                (factors.sharing_count * 1) +
                (factors.loans_completed * 5)
            ))
            
            # Overall score (base + bonus, capped at 100)
            overall_score = min(100, base_score + behavioral_bonus)
            
            # Calculate component scores
            components = {
                'payment_history': base_score,
                'wallet_usage': min(100, factors.wallet_usage_count * 10),
                'purchase_activity': min(100, factors.purchase_frequency * 10),
                'sharing_behavior': min(100, factors.sharing_count * 15),
                'loan_history': min(100, (factors.loans_completed * 20) if factors.loans_taken > 0 else 50),
            }
            
            # Get recent history
            history = CreditScoreHistory.objects.filter(
                user=user
            ).order_by('-created_at')[:10]
            
            history_data = [{
                'previous_score': h.previous_score,
                'new_score': h.new_score,
                'change_amount': h.change_amount,
                'reason': h.reason,
                'event_type': h.event_type,
                'created_at': h.created_at.isoformat()
            } for h in history]
            
            # Log for debugging
            logger.info(f"Credit score for {user.email}: base={base_score}, bonus={behavioral_bonus}, overall={overall_score}")
            
            return Response({
                'overall_score': overall_score,
                'base_score': base_score,
                'behavioral_bonus': behavioral_bonus,
                'components': components,
                'history': history_data,
                'credit_signal': {
                    'payment_history': credit_signal.payment_history,
                    'energy_consumption': credit_signal.energy_consumption,
                    'financial_capacity': credit_signal.financial_capacity,
                }
            })
            
        # try:
        #     from loan.services import get_user_loan_stats

        #     return Response(get_user_loan_stats(request.user), status=200)

        except Exception as e:
            logger.error(f"Error in CreditScoreView: {str(e)}", exc_info=True)
            return Response({
                'overall_score': 50,
                'base_score': 50,
                'behavioral_bonus': 0,
                'components': {
                    'payment_history': 50,
                    'wallet_usage': 0,
                    'purchase_activity': 0,
                    'sharing_behavior': 0,
                    'loan_history': 50,
                },
                'history': [],
                'error': str(e)
            }, status=status.HTTP_200_OK) 

            

class RepayableLoanView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        from loan.services import get_repayable_loan, serialize_repayable_loan

        loan = get_repayable_loan(request.user)
        return Response(
            {"repayable_loan": serialize_repayable_loan(loan)},
            status=status.HTTP_200_OK,
        )


class ActiveLoanRepaymentView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        try:
            from loan.services import LoanOperationError, repay_loan

            result = repay_loan(
                request.user,
                None,
                request.data.get("amount", 0),
                channel="WEB",
                payment_method="CASH",
            )
            return Response(
                {
                    "message": result["message"],
                    "units_added": result["units_added"],
                    "payment_reference": result["payment_reference"],
                    "outstanding_balance": result["outstanding_balance"],
                    "loan_status": result["loan_status"],
                    "loan_id": result["loan_id"],
                }
            )
        except LoanOperationError as exc:
            return Response({"error": exc.message}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Active loan repayment error: {str(e)}")
            return Response(
                {"error": f"Failed to process repayment: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class LoanLookupByPhoneView(APIView):
    """
    GET /loans/lookup-by-phone/?phone=256XXXXXXXXX
    Returns the outstanding loan for the user with that phone number.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from accounts.models import User as UserModel
        phone = request.query_params.get("phone", "").strip()
        if not phone:
            return Response({"error": "phone query parameter is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not phone.startswith("+"):
            phone = "+" + phone

        try:
            owner = UserModel.objects.get(phone_number=phone)
        except UserModel.DoesNotExist:
            return Response({"error": "No registered user found with that phone number."}, status=status.HTTP_404_NOT_FOUND)

        if owner == request.user:
            return Response({"error": "Use the standard repayment flow for your own loans."}, status=status.HTTP_400_BAD_REQUEST)

        from loan.services import get_repayable_loan
        loan = get_repayable_loan(owner)
        if not loan:
            return Response({"error": "This user has no outstanding loan balance."}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "owner": {
                "id": owner.id,
                "name": f"{owner.first_name} {owner.last_name}".strip() or owner.email,
                "phone": str(owner.phone_number),
            },
            "loan": {
                "id": loan.id,
                "loan_id": loan.loan_id,
                "outstanding_balance": float(loan.outstanding_balance),
                "total_amount_due": float(loan.total_amount_due) if hasattr(loan, 'total_amount_due') else float(loan.outstanding_balance),
                "status": loan.status,
            },
        })


class PayForSomeoneView(APIView):
    """
    POST /loans/pay-for-someone/
    Body: { owner_phone, loan_id, amount, is_anonymous }
    Pays off (fully or partially) another user's loan from the payer's wallet.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from accounts.models import User as UserModel
        from loan.services import repay_loan, LoanOperationError

        owner_phone = request.data.get("owner_phone", "").strip()
        loan_id = request.data.get("loan_id")
        amount = request.data.get("amount")
        is_anonymous = bool(request.data.get("is_anonymous", False))

        if not owner_phone or not loan_id or not amount:
            return Response({"error": "owner_phone, loan_id, and amount are required."}, status=status.HTTP_400_BAD_REQUEST)

        if not owner_phone.startswith("+"):
            owner_phone = "+" + owner_phone

        try:
            owner = UserModel.objects.get(phone_number=owner_phone)
        except UserModel.DoesNotExist:
            return Response({"error": "No registered user found with that phone number."}, status=status.HTTP_404_NOT_FOUND)

        if owner == request.user:
            return Response({"error": "Use the standard repayment flow for your own loans."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = repay_loan(
                user=owner,
                loan_id=loan_id,
                amount=amount,
                channel="WEB",
                payment_method="CASH",
                paid_by_user=request.user,
                is_anonymous=is_anonymous,
            )
            owner_name = f"{owner.first_name} {owner.last_name}".strip() or owner.email
            return Response({
                "message": result["message"],
                "owner_name": owner_name,
                "loan_id": result["loan_id"],
                "units_added": result["units_added"],
                "outstanding_balance": result["outstanding_balance"],
                "loan_status": result["loan_status"],
                "payment_reference": result["payment_reference"],
                "is_anonymous": is_anonymous,
            })
        except LoanOperationError as exc:
            return Response({"error": exc.message}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.error("PayForSomeone error: %s", exc)
            return Response({"error": "Payment failed. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
