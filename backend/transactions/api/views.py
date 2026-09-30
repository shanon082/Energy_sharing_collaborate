import requests
import logging
from datetime import date
from decimal import Decimal
from django.utils.timezone import now
from django.conf import settings
from django.http import JsonResponse
from meter.models import Meter, MeterToken, generate_random_string
from transactions.models import UnitTransaction, TransactionLog, TransactionType
from .serializers import BuyUnitSerializer
from rest_framework.generics import (
    GenericAPIView,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import uuid

from rest_framework.views import APIView
from django.db.models import Q
from datetime import datetime
from transactions.unified_history import collect_unified_history, filter_history, paginate_history, summarize_history
from transactions.tasks import handle_send_transaction_statement_email
from utils.general import dispatch_task

logger = logging.getLogger(__name__)
class TransactionHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            transaction_type = request.query_params.get('type')
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 5))

            entries = collect_unified_history(user)
            entries = filter_history(
                entries,
                transaction_type=transaction_type,
                start_date=start_date,
                end_date=end_date,
            )
            summary = summarize_history(entries)
            page_entries, total = paginate_history(entries, page, page_size)

            return Response({
                'success': True,
                'total': total,
                'page': page,
                'page_size': page_size,
                'transactions': page_entries,
                'summary': summary,
            }, status=status.HTTP_200_OK)

        except ValueError as ve:
            logger.warning(f"Invalid filter params: {str(ve)}")
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)
        except Exception as e:
            logger.error(f"Error fetching history: {str(e)}")
            return Response({'error': 'Failed to fetch transaction history'}, status=500)


class TransactionStatementEmailView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        start_date = str(request.data.get("start_date") or "").strip()
        end_date = str(request.data.get("end_date") or "").strip()
        if not start_date or not end_date:
            return Response({"error": "start_date and end_date are required (YYYY-MM-DD)."}, status=400)
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)
        if end_date < start_date:
            return Response({"error": "end_date cannot be before start_date."}, status=400)

        dispatch_task(handle_send_transaction_statement_email, user.id, start_date, end_date)
        return Response(
            {
                "success": True,
                "message": f"Statement request received. PDF will be sent to {user.email}.",
            },
            status=status.HTTP_200_OK,
        )

def is_start_of_new_month():
    today = now().date()
    return today.day == 1 


def create_purchase_token(user, meter, units_purchased):
    token_value = generate_random_string(10)
    while MeterToken.objects.filter(token=token_value).exists():
        token_value = generate_random_string(10)

    return MeterToken.objects.create(
        user=user,
        token=token_value,
        units=Decimal(str(units_purchased)),
        meter=meter,
        source='PURCHASE',
    )


class BuyUnitsView(GenericAPIView):

    permission_classes = (IsAuthenticated,)
    serializer_class = BuyUnitSerializer

    def post(self, request, *args, **kwargs):
        return Response({
            "code": "LEGACY_PURCHASE_DISABLED",
            "message": "This purchase route cannot verify payment. Use the verified meter purchase flow.",
        }, status=status.HTTP_409_CONFLICT)
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        amount = request.data.get("amount")
        phone_number = request.data.get("phone_number")
        user = request.user

        try:
            meter = Meter.objects.get(user=user)
        except Meter.DoesNotExist:
            return Response({
                "error": "No meter found. Please register your meter before purchasing units."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Tariff rates
        first_8_unit_rate = 250
        additional_unit_rate = 775.7
        min_purchase_amount = 5000

       
        if is_start_of_new_month():
            user.monthly_unit_balance = 0  
        
        if user.monthly_unit_balance < 8:
            amount_first_8_units = (8-user.monthly_unit_balance) * first_8_unit_rate
            first_8_units = amount_first_8_units / first_8_unit_rate
            print("Monthly units_balance:", user.monthly_unit_balance)
            print("amount of 1st 8 units",amount_first_8_units)
            print("first 8",first_8_units)
            print("other",8-(user.monthly_unit_balance))
            units_purchased = first_8_units
            user.monthly_unit_balance += first_8_units
            user.save()
            print("Monthly units_balance after", user.monthly_unit_balance)

            if (amount-amount_first_8_units) > min_purchase_amount:
                additional_units = (amount-amount_first_8_units) / additional_unit_rate
                units_purchased += additional_units

            token = create_purchase_token(user, meter, units_purchased)

            TransactionLog.objects.create(
                user=user,
                transaction_type=TransactionType.UNIT_PURCHASE,
                amount=amount,
                units=units_purchased,
                status='COMPLETED',
                reference_id=f"PUR-{uuid.uuid4().hex[:8].upper()}",
                details={'meter_no': meter.meter_no, 'phone_number': phone_number, 'discounted': True, 'token': token.token}
            )
            
            response_data = {
                "Units purchased": "{:.2f}".format(units_purchased),
                "message": "You have successfully purchased units. Use the generated token on your meter.",
                "token": token.token
            }
            return Response(response_data, status=status.HTTP_200_OK)

        # If the user has already purchased the first 8 units in the month
        units_purchased = amount / additional_unit_rate
        token = create_purchase_token(user, meter, units_purchased)

        TransactionLog.objects.create(
            user=user,
            transaction_type=TransactionType.UNIT_PURCHASE,
            amount=amount,
            units=units_purchased,
            status='COMPLETED',
            reference_id=f"PUR-{uuid.uuid4().hex[:8].upper()}",
            details={'meter_no': meter.meter_no, 'phone_number': phone_number, 'token': token.token}
        )
        
        response_data = {
            "Units purchased": "{:.2f}".format(units_purchased),
            "message": "You have successfully purchased units. Use the generated token on your meter.",
            "token": token.token
        }
        return Response(response_data, status=status.HTTP_200_OK)
    
    
    
