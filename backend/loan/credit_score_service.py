import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from loan.models import CreditScoreHistory, CreditScoreFactors
from loan.scoring import calculate_weighted_credit_score, get_or_create_dummy_credit_signal

logger = logging.getLogger(__name__)


class CreditScoreService:
    """
    Service to manage dynamic credit scoring based on user behavior
    """
    
    # Weight configurations
    WEIGHTS = {
        'on_time_payments': 0.25,
        'wallet_usage': 0.20,
        'purchase_frequency': 0.15,
        'sharing_behavior': 0.10,
        'loan_history': 0.20,
        'account_age': 0.10,
    }
    
    @classmethod
    def update_credit_score(cls, user, event_type, reference_id=None, extra_data=None):
        """
        Update user's credit score based on their actions
        """
        try:
            # Get current score
            credit_signal = get_or_create_dummy_credit_signal(user)
            current_score = calculate_weighted_credit_score(credit_signal)
            
            # Get or create factors
            factors, _ = CreditScoreFactors.objects.get_or_create(user=user)
            
            # Calculate new score based on event
            new_score, change_amount, reason = cls._calculate_score_change(
                user, factors, event_type, extra_data
            )
            
            # Update factors based on event
            cls._update_factors(factors, event_type, extra_data)
            
            # Ensure score is within 0-100 range
            new_score = max(0, min(100, new_score))
            
            # Update credit signal if needed (for backward compatibility)
            if hasattr(user, 'credit_signal'):
                signal = user.credit_signal
                # Update signal based on new score
                if new_score >= 80:
                    signal.payment_history = 'GOOD'
                    signal.financial_capacity = 'STRONG'
                elif new_score >= 60:
                    signal.payment_history = 'FAIR'
                    signal.financial_capacity = 'AVERAGE'
                else:
                    signal.payment_history = 'POOR'
                    signal.financial_capacity = 'WEAK'
                signal.save()
            
            # Record history
            if change_amount != 0:
                CreditScoreHistory.objects.create(
                    user=user,
                    previous_score=current_score,
                    new_score=new_score,
                    change_amount=change_amount,
                    reason=reason,
                    event_type=event_type,
                    reference_id=reference_id
                )
                
                logger.info(
                    f"Credit score updated for {user.email}: "
                    f"{current_score} → {new_score} ({change_amount:+d}) - {reason}"
                )
            
            return new_score, change_amount, reason
            
        except Exception as e:
            logger.error(f"Error updating credit score for {user.email}: {str(e)}")
            return None, 0, None
    
    @classmethod
    def _calculate_score_change(cls, user, factors, event_type, extra_data):
        """
        Calculate how much the score should change based on event
        """
        current_score = calculate_weighted_credit_score(get_or_create_dummy_credit_signal(user))
        
        if event_type == 'UNIT_PURCHASE':
            # Purchasing units increases score
            amount = extra_data.get('amount', 0) if extra_data else 0
            payment_source = extra_data.get('payment_source', '')
            
            # Using wallet gives more points
            if payment_source == 'WALLET':
                increase = min(5, int(amount / 10000))  # Up to 5 points
                reason = f"Purchased UGX {amount:,.0f} units using wallet"
            else:
                increase = min(3, int(amount / 20000))  # Up to 3 points
                reason = f"Purchased UGX {amount:,.0f} units"
            
            # Bonus for first purchase
            if factors.purchase_frequency == 0:
                increase += 5
                reason += " (First purchase bonus)"
            
            return current_score + increase, increase, reason
            
        elif event_type == 'LOAN_REPAYMENT':
            # Loan repayment behavior
            amount = extra_data.get('amount', 0) if extra_data else 0
            is_on_time = extra_data.get('is_on_time', True)
            payment_source = extra_data.get('payment_source', '')
            
            if is_on_time:
                # On-time payment increases score
                increase = min(10, int(amount / 10000))
                
                # Extra points for wallet usage
                if payment_source == 'WALLET':
                    increase += 2
                    reason = f"On-time loan repayment of UGX {amount:,.0f} using wallet"
                else:
                    reason = f"On-time loan repayment of UGX {amount:,.0f}"
                
                return current_score + increase, increase, reason
            else:
                # Late payment decreases score
                days_late = extra_data.get('days_late', 30)
                decrease = min(15, int(days_late / 2))
                reason = f"Late loan repayment of UGX {amount:,.0f} ({days_late} days late)"
                return current_score - decrease, -decrease, reason
                
        elif event_type == 'LOAN_COMPLETION':
            # Completing a loan gives a boost
            increase = 10
            reason = "Loan fully repaid and completed"
            return current_score + increase, increase, reason
            
        elif event_type == 'WALLET_USAGE':
            # Using wallet for transactions
            amount = extra_data.get('amount', 0) if extra_data else 0
            transaction_type = extra_data.get('transaction_type', '')
            
            if transaction_type in ['DEPOSIT', 'WITHDRAWAL']:
                increase = min(3, int(amount / 50000))
                reason = f"Wallet {transaction_type.lower()} of UGX {amount:,.0f}"
            else:
                increase = min(2, int(amount / 20000))
                reason = f"Wallet usage for {transaction_type}"
            
            return current_score + increase, increase, reason
            
        elif event_type == 'SHARE_UNITS':
            # Sharing units (positive behavior)
            units = extra_data.get('units', 0) if extra_data else 0
            increase = min(3, int(units / 50))
            reason = f"Shared {units} units with others"
            return current_score + increase, increase, reason
            
        elif event_type == 'METER_REGISTRATION':
            # First meter registration
            increase = 5
            reason = "Meter registered successfully"
            return current_score + increase, increase, reason
            
        elif event_type == 'LOAN_APPLICATION':
            # Applying for loan (neutral, but track)
            return current_score, 0, "Loan application submitted"
            
        return current_score, 0, "No change"
    
    @classmethod
    def _update_factors(cls, factors, event_type, extra_data):
        """
        Update the user's credit factors based on their actions
        """
        if event_type == 'UNIT_PURCHASE':
            units = extra_data.get('units', 0) if extra_data else 0
            amount = extra_data.get('amount', 0) if extra_data else 0
            payment_source = extra_data.get('payment_source', '')
            
            factors.total_units_purchased += Decimal(str(units))
            factors.purchase_frequency += 1
            
            if payment_source == 'WALLET':
                factors.wallet_usage_count += 1
                factors.wallet_transaction_volume += Decimal(str(amount))
                
        elif event_type == 'LOAN_REPAYMENT':
            amount = extra_data.get('amount', 0) if extra_data else 0
            is_on_time = extra_data.get('is_on_time', True)
            payment_source = extra_data.get('payment_source', '')
            
            factors.total_repayments += Decimal(str(amount))
            
            if is_on_time:
                factors.on_time_payments += 1
            else:
                factors.late_payments += 1
                
            if payment_source == 'WALLET':
                factors.wallet_usage_count += 1
                factors.wallet_transaction_volume += Decimal(str(amount))
                
        elif event_type == 'LOAN_COMPLETION':
            factors.loans_completed += 1
            
        elif event_type == 'SHARE_UNITS':
            units = extra_data.get('units', 0) if extra_data else 0
            factors.units_shared += Decimal(str(units))
            factors.sharing_count += 1
            
        elif event_type == 'LOAN_APPLICATION':
            amount = extra_data.get('amount', 0) if extra_data else 0
            factors.loans_taken += 1
            factors.total_loan_amount += Decimal(str(amount))
            
        elif event_type == 'WALLET_USAGE':
            amount = extra_data.get('amount', 0) if extra_data else 0
            factors.wallet_usage_count += 1
            factors.wallet_transaction_volume += Decimal(str(amount))
            
        # Update account age
        if factors.created_at:
            factors.account_age_days = (timezone.now() - factors.created_at).days
            
        factors.save()
    
    @classmethod
    def calculate_detailed_score(cls, user):
        """
        Calculate detailed credit score breakdown for display
        """
        factors, _ = CreditScoreFactors.objects.get_or_create(user=user)
        
        # Calculate individual component scores
        components = {}
        
        # On-time payment score (0-100)
        total_payments = factors.on_time_payments + factors.late_payments
        if total_payments > 0:
            on_time_ratio = (factors.on_time_payments / total_payments) * 100
            components['payment_history'] = round(on_time_ratio)
        else:
            components['payment_history'] = 50  # Neutral starting point
        
        # Wallet usage score
        if factors.wallet_usage_count > 0:
            wallet_score = min(100, factors.wallet_usage_count * 5 + int(factors.wallet_transaction_volume / 100000))
            components['wallet_usage'] = round(wallet_score)
        else:
            components['wallet_usage'] = 30
        
        # Purchase frequency score
        if factors.purchase_frequency > 0:
            purchase_score = min(100, factors.purchase_frequency * 10)
            components['purchase_activity'] = round(purchase_score)
        else:
            components['purchase_activity'] = 20
        
        # Sharing behavior score
        if factors.sharing_count > 0:
            sharing_score = min(100, factors.sharing_count * 15)
            components['sharing_behavior'] = round(sharing_score)
        else:
            components['sharing_behavior'] = 40
        
        # Loan history score
        if factors.loans_taken > 0:
            completion_ratio = (factors.loans_completed / factors.loans_taken) * 100 if factors.loans_taken > 0 else 0
            loan_score = (completion_ratio * 0.7) + (min(100, factors.on_time_payments * 5) * 0.3)
            components['loan_history'] = round(loan_score)
        else:
            components['loan_history'] = 50
        
        # Weighted total
        final_score = (
            components['payment_history'] * cls.WEIGHTS['on_time_payments'] +
            components['wallet_usage'] * cls.WEIGHTS['wallet_usage'] +
            components['purchase_activity'] * cls.WEIGHTS['purchase_frequency'] +
            components['sharing_behavior'] * cls.WEIGHTS['sharing_behavior'] +
            components['loan_history'] * cls.WEIGHTS['loan_history']
        )
        
        return round(final_score), components










        