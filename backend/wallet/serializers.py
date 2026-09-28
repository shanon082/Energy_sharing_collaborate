from rest_framework import serializers
from .models import Wallet, Transaction, MeterBalance, MeterTransaction
from decimal import Decimal

class WalletSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    user_email = serializers.SerializerMethodField()
    
    class Meta:
        model = Wallet
        fields = [
            'id',
            'user',
            'user_email',
            'balance',
            'is_active',
            'created_at',
        ]
        read_only_fields = fields
    
    def get_user_email(self, obj):
        return obj.user.email

class TransactionSerializer(serializers.ModelSerializer):
    wallet = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = Transaction
        fields = [
            'id',
            'wallet',
            'amount',
            'transaction_type',
            'balance_after',
            'description',
            'reference',
            'metadata',
            'created_at',
        ]
        read_only_fields = fields

class MeterBalanceSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = MeterBalance
        fields = [
            'id',
            'user',
            'meter_number',
            'balance',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

class MeterTransactionSerializer(serializers.ModelSerializer):
    meter = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = MeterTransaction
        fields = [
            'id',
            'meter',
            'amount',
            'operation',
            'balance_after',
            'description',
            'reference',
            'created_at',
        ]
        read_only_fields = fields