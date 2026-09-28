import logging
from rest_framework import serializers
from transactions.models import Transaction, TransactionLog

class TransactionLogSerializer(serializers.ModelSerializer):
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S')

    class Meta:
        model = TransactionLog
        fields = [
            'id', 'transaction_type', 'transaction_type_display', 'amount', 'units', 
            'status', 'reference_id', 'details', 'created_at'
        ]


class BuyUnitSerializer(serializers.ModelSerializer):
    amount = serializers.CharField(required=True)
    phone_number = serializers.CharField(required=True)    
    
    class Meta:
        model= Transaction
        fields = [
            "amount",
            "phone_number",            
        ]