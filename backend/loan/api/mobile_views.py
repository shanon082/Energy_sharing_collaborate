"""Read-only consumer loan and repayment history without status reconciliation."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from loan.models import LoanApplication
from loan.services import get_loan_eligibility, user_can_apply_for_loan
from loan.scoring import profile_scoring_fields_complete
from meter.models import Meter
from utils.billing import calculate_units_from_payment, get_active_domestic_tariff
from loan.financial import interest_charge, money
from loan.api.serializers import LoanApplicationCreateSerializer
from decimal import Decimal
from types import SimpleNamespace
from django.utils import timezone


class MobileLoanOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.user_role != User.CLIENT:
            return Response({"code": "CONSUMER_ONLY"}, status=403)
        loans = LoanApplication.objects.filter(user=request.user).prefetch_related(
            "repayments", "disbursement",
        ).order_by("-created_at")
        items = []
        for loan in loans:
            repayments = sorted(loan.repayments.all(), key=lambda row: row.payment_date, reverse=True)
            items.append({
                "id": loan.pk,
                "loan_id": loan.loan_id,
                "status": loan.status,
                "amount_approved_ugx": str(loan.amount_approved) if loan.amount_approved is not None else None,
                "outstanding_ugx": str(loan.outstanding_balance) if loan.amount_approved is not None else None,
                "due_at": loan.due_date.isoformat() if loan.due_date else None,
                "repayments": [{
                    "id": row.pk,
                    "status": row.payment_status,
                    "received_ugx": str(row.amount_paid),
                    "applied_ugx": str(row.amount_applied_ugx) if row.amount_applied_ugx is not None else None,
                    "excess_ugx": str(row.excess_ugx) if row.amount_applied_ugx is not None else None,
                    "paid_at": row.payment_date.isoformat(),
                } for row in repayments],
            })
        return Response({"loans": items})


class MobileLoanEligibilityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.user_role != User.CLIENT:
            return Response({"code": "CONSUMER_ONLY"}, status=403)
        if not profile_scoring_fields_complete(request.user):
            return Response({"score": None, "eligible": False, "can_apply": False,
                             "reason": "Complete the loan assessment profile before a score is available.",
                             "source": None})
        access = get_loan_eligibility(request.user)
        if access.get("credit_signal_source") != "PROFILE":
            return Response({"score": None, "eligible": False, "can_apply": False,
                             "reason": "The score source needs review before mobile use.",
                             "source": access.get("credit_signal_source")})
        can_apply, reason = user_can_apply_for_loan(request.user)
        return Response({
            "score": access["credit_score"], "eligible": access["is_loan_eligible"],
            "can_apply": bool(can_apply and access["is_loan_eligible"]),
            "reason": reason or None,
            "source": "PROFILE", "tier": access["loan_tier"],
            "min_loan_ugx": str(access["min_loan_amount"]),
            "max_loan_ugx": str(access["max_eligible_amount"]),
            "interest_rate_percent": str(access["interest_rate"]) if access["interest_rate"] is not None else None,
        })


class MobileLoanQuoteView(APIView):
    """Informational quote using the same tariff and stored-rate calculation paths."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        eligibility = MobileLoanEligibilityView().get(request)
        if eligibility.status_code != 200 or not eligibility.data.get("can_apply"):
            return Response({"code": "LOAN_NOT_ELIGIBLE", "message": eligibility.data.get("reason") or
                             "Loan application is unavailable."}, status=409)
        serializer = LoanApplicationCreateSerializer(data={
            "purpose": "Electricity", "amount_requested": request.data.get("amount_requested"),
            "tenure_months": request.data.get("tenure_months"), "meter_no": request.data.get("meter_no"),
        })
        serializer.is_valid(raise_exception=True)
        meter_no = serializer.validated_data["meter_no"]
        meter = Meter.objects.filter(user=request.user, meter_no=meter_no,
                                     status=Meter.STATUS_ACTIVE, is_deleted=False).first()
        if meter is None:
            return Response({"code": "METER_UNAVAILABLE"}, status=409)
        tariff = get_active_domestic_tariff()
        if tariff is None:
            return Response({"code": "TARIFF_POLICY_REQUIRED",
                             "message": "A current domestic tariff is required for a mobile quote."}, status=409)
        requested = serializer.validated_data["amount_requested"]
        max_eligible = Decimal(str(eligibility.data["max_loan_ugx"]))
        approved = min(requested, max_eligible)
        rate = Decimal(str(eligibility.data["interest_rate_percent"]))
        tenure = serializer.validated_data["tenure_months"]
        units, bill = calculate_units_from_payment(
            approved, request.user, tariff=tariff, apply_deductions=False,
        )
        interest = money(interest_charge(SimpleNamespace(
            amount_approved=approved, interest_rate=rate, tenure_months=tenure,
        )))
        return Response({
            "requested_ugx": str(requested), "estimated_approved_ugx": str(approved),
            "interest_rate_percent": str(rate), "estimated_interest_ugx": str(interest),
            "estimated_total_due_ugx": str(money(approved + interest)),
            "tenure_months": tenure, "meter_no": meter_no,
            "estimated_energy_kwh": str(units), "purchase_billed_ugx": str(bill.total),
            "unallocated_ugx": str(approved - bill.total),
            "tariff_id": tariff.pk, "tariff_code": tariff.tariff_code,
            "quoted_at": timezone.now().isoformat(), "binding": False,
            "application_available": False,
            "application_blocker": "Mobile loan submission awaits idempotency and financial-policy approval.",
        })
