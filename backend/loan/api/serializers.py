from rest_framework import serializers
from django.db.utils import OperationalError, ProgrammingError
from loan.models import ElectricityTariff, LoanApplication, LoanDisbursement, LoanRepayment, TariffBlock, LoanTier
from loan.tenure import validate_tenure_months

# class TariffBlockSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = TariffBlock
#         fields = ['id', 'block_name', 'min_units', 'max_units', 'rate_per_unit', 'block_order']

# class ElectricityTariffSerializer(serializers.ModelSerializer):
#     blocks = TariffBlockSerializer(many=True, read_only=True)
    
#     class Meta:
#         model = ElectricityTariff
#         fields = [
#             'id', 'tariff_code', 'tariff_name', 'tariff_type', 'voltage_level', 'voltage_value', 'service_charge', 'blocks', 'is_active'
#         ]


class TariffBlockSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = TariffBlock
        fields = [
            "id",
            "block_name",
            "min_units",
            "max_units",
            "rate_per_unit",
            "block_order",
            "is_lifeline_block",
            "non_lifeline_rate",
        ]

    def validate(self, data):
        if data['min_units'] < 0:
            raise serializers.ValidationError({"min_units": "Cannot be negative"})
        if data.get('max_units') is not None and data['max_units'] <= data['min_units']:
            raise serializers.ValidationError({"max_units": "Must be > min_units"})
        return data

class ElectricityTariffSerializer(serializers.ModelSerializer):
    blocks = TariffBlockSerializer(many=True, read_only=False)

    class Meta:
        model = ElectricityTariff
        fields = [
            "id",
            "tariff_code",
            "tariff_name",
            "tariff_type",
            "voltage_level",
            "voltage_value",
            "service_charge",
            "blocks",
            "is_active",
            "effective_date",
            "effective_from",
            "effective_to",
        ]
        read_only_fields = ["id"]

    def validate(self, data):
        from loan.tariff_utils import TariffActivationError, validate_can_deactivate

        instance = getattr(self, "instance", None)
        will_be_active = data.get("is_active", instance.is_active if instance else False)
        if instance and instance.is_active and will_be_active is False:
            try:
                validate_can_deactivate(instance)
            except TariffActivationError as exc:
                raise serializers.ValidationError({"is_active": str(exc)}) from exc
        return data

    def create(self, validated_data):
        from loan.tariff_utils import ensure_single_active_on_save

        blocks_data = validated_data.pop("blocks", [])
        tariff = ElectricityTariff.objects.create(**validated_data)
        ensure_single_active_on_save(tariff, activating=True)
        for block_data in blocks_data:
            TariffBlock.objects.create(tariff=tariff, **block_data)
        return tariff

    def update(self, instance, validated_data):
        from loan.tariff_utils import ensure_single_active_on_save

        blocks_data = validated_data.pop("blocks", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        ensure_single_active_on_save(instance, activating=True)

        if blocks_data is not None:
            existing_blocks_map = {b.id: b for b in instance.blocks.all()}
            seen_ids = set()

            for block_data in blocks_data:
                block_id = block_data.get('id')  

                if block_id:
                    try:
                        block = existing_blocks_map[block_id]
                    except KeyError:
                        raise serializers.ValidationError(
                            f"Block with id {block_id} not found for this tariff"
                        )

                    for attr, value in block_data.items():
                        if attr != 'id':         
                            setattr(block, attr, value)
                    block.save()

                    seen_ids.add(block_id)

                else:
                    TariffBlock.objects.create(tariff=instance, **block_data)

            for block_id, block in existing_blocks_map.items():
                if block_id not in seen_ids:
                    block.delete()

        return instance

class LoanRepaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanRepayment
        fields = ['id', 'amount_paid', 'amount_applied_ugx', 'excess_ugx', 'payment_status',
                  'payment_date', 'units_paid', 'is_on_time', 'payment_reference']

class LoanApplicationSerializer(serializers.ModelSerializer):
    repayments = LoanRepaymentSerializer(many=True, read_only=True)
    outstanding_balance = serializers.SerializerMethodField()
    amount_paid = serializers.SerializerMethodField()
    total_amount_due = serializers.SerializerMethodField()
    get_total_amount_due = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_eligible = serializers.SerializerMethodField()
    disbursement_token = serializers.SerializerMethodField()
    disbursement_units = serializers.SerializerMethodField()
    tier_display = serializers.CharField(source='get_loan_tier_display', read_only=True)
    
    user_profile_data = serializers.SerializerMethodField()

    #tariff fields
    tariff_details = ElectricityTariffSerializer(source='tariff', read_only=True)
    units_calculated = serializers.SerializerMethodField()
    cost_breakdown = serializers.SerializerMethodField()
    due_date = serializers.SerializerMethodField()

    class Meta:
        model = LoanApplication
        fields = '__all__'
        read_only_fields = ('user', 'status', 'credit_score', 'amount_approved', 'loan_id', 'rejection_reason', 'user_notified', 'loan_tier', 'interest_rate', 'outstanding_balance', 'total_amount_due')
    
    def get_user_profile_data(self, obj):
        """Include legacy profile fields and third-party credit signals in response."""
        user = obj.user
        try:
            credit_signal = getattr(user, 'credit_signal', None)
        except (OperationalError, ProgrammingError):
            # Migration not applied yet; avoid crashing serializer responses.
            credit_signal = None
        return {
            'monthly_expenditure': user.monthly_expenditure,
            'purchase_frequency': user.purchase_frequency,
            'payment_consistency': user.payment_consistency,
            'disconnection_history': user.disconnection_history,
            'meter_sharing': user.meter_sharing,
            'monthly_income': user.monthly_income,
            'income_stability': user.income_stability,
            'consumption_level': user.consumption_level,
            'credit_signal': {
                'payment_history': credit_signal.payment_history if credit_signal else None,
                'energy_consumption': credit_signal.energy_consumption if credit_signal else None,
                'financial_capacity': credit_signal.financial_capacity if credit_signal else None,
                'source': credit_signal.source if credit_signal else None,
            }
        }

    def get_outstanding_balance(self, obj):
        return obj.outstanding_balance

    def get_amount_paid(self, obj):
        return obj.amount_paid
    
    def get_total_amount_due(self, obj):
        return obj.total_amount_due
    
    def get_is_eligible(self, obj):
        return obj.check_eligibility()
    
    def get_disbursement_token(self, obj):
        # LoanDisbursement.token is a legacy database placeholder, not a
        # validated STS/keypad token. Keep historical rows but do not present
        # newly generated placeholders as meter-load credentials.
        return None
    
    def get_disbursement_units(self, obj):
        if hasattr(obj, 'disbursement') and obj.disbursement:
            return obj.disbursement.units_disbursed
        return None
    
    def get_units_calculated(self, obj):
        """Calculate units based on tariff block rates"""
        if obj.amount_approved:
            return obj.calculate_units_from_amount()
        return None
    
    def get_cost_breakdown(self, obj):
        """Get detailed cost breakdown for the approved amount"""
        if not obj.amount_approved or not obj.tariff:
            return None
        
        amount = float(obj.amount_approved)
        blocks = obj.tariff.blocks.all().order_by('block_order')
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
                'cost': round(cost_from_block, 2)
            })
        
        return breakdown

    def get_due_date(self, obj):
        return obj.due_date

class LoanApplicationCreateSerializer(serializers.ModelSerializer):
    meter_no = serializers.CharField(write_only=True)
    tariff_id = serializers.PrimaryKeyRelatedField(
        queryset=ElectricityTariff.objects.filter(is_active=True),
        source='tariff',
        required=False,
        allow_null=True
    )
    tenure_months = serializers.IntegerField(min_value=1, max_value=12)

    class Meta:
        model = LoanApplication
        fields = [
            'purpose', 'amount_requested', 'tenure_months', 'tariff_id', 'meter_no',
        ]
    
    def validate_amount_requested(self, value):
        if value != value.to_integral_value():
            raise serializers.ValidationError("Use whole UGX for a loan application.")
        if value < 5000:
            raise serializers.ValidationError("Minimum loan amount is 5,000 UGX")
        if value > 200000:
            raise serializers.ValidationError("Maximum loan amount is 200,000 UGX")
        return value

    def validate_tenure_months(self, value):
        try:
            return validate_tenure_months(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
    
class LoanTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanTier
        fields = '__all__'

    def validate(self, data):
        if data['min_score'] >= data['max_score']:
            raise serializers.ValidationError("min_score must be less than max_score")
        return data


class LoanDisbursementSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanDisbursement
        fields = '__all__'

class LoanRepaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanRepayment
        fields = ['amount_paid']
