"""Read-only, identifier-only financial reconciliation inventory."""

import json
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Count, F, Sum

from loan.financial import loan_charges
from loan.models import LoanApplication, LoanRepayment
from meter.models import EnergyAllocation, Transaction as MeterTransaction
from transactions.models import PaymentIntent, UnitTransaction
from wallet.models import UnitBalance


class Command(BaseCommand):
    help = "Dry-run financial reconciliation; reports IDs and totals, never changes records."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100, help="Maximum IDs per category")

    def handle(self, *args, **options):
        limit = max(0, options["limit"])
        report = {"mode": "dry_run", "notes": [
            "UnitBalance values lack reliable historical UGX/kWh provenance; no conversion is inferred.",
            "Legacy purchases without source-linked PaymentIntents require provider/ledger reconciliation.",
            "No pending payment, token, credit, or loan is replayed or modified.",
        ]}
        ambiguous = UnitBalance.objects.exclude(balance=0)
        report["ambiguous_unit_balances"] = {
            "count": ambiguous.count(),
            "total_recorded": str(ambiguous.aggregate(v=Sum("balance"))["v"] or Decimal("0")),
            "ids": list(ambiguous.order_by("id").values_list("id", flat=True)[:limit]),
        }
        purchase_rows = MeterTransaction.objects.filter(
            transaction_type=MeterTransaction.TYPE_PURCHASE,
            status=MeterTransaction.STATUS_COMPLETED,
        )
        duplicates = purchase_rows.exclude(payment_reference="").values(
            "user_id", "payment_reference",
        ).annotate(count=Count("id"), units=Sum("amount_kwh")).filter(count__gt=1)
        duplicate_groups = list(duplicates.order_by("user_id", "payment_reference"))
        linked_refs = set(str(value) for value in EnergyAllocation.objects.filter(
            purchase_intent__isnull=False,
        ).values_list("purchase_intent__provider_reference", flat=True))
        represented = purchase_rows.filter(payment_reference__in=linked_refs)
        report["duplicate_purchase_representations"] = {
            "same_reference_group_count": len(duplicate_groups),
            "same_reference_recorded_units_kwh": str(sum(
                (row["units"] for row in duplicate_groups), Decimal("0"))),
            "same_reference_groups": [
                {"user_id": row["user_id"], "count": row["count"], "units_kwh": str(row["units"])}
                for row in duplicate_groups[:limit]
            ],
            "meter_rows_also_represented_by_allocation": represented.count(),
            "meter_row_ids_also_represented": list(represented.order_by("id").values_list("id", flat=True)[:limit]),
            "meter_rows_without_reference": purchase_rows.filter(payment_reference="").count(),
            "meter_units_without_reference_kwh": str(purchase_rows.filter(
                payment_reference="").aggregate(v=Sum("amount_kwh"))["v"] or Decimal("0")),
            "self_credit_rows_without_economic_source": UnitTransaction.objects.filter(
                sender_id=F("receiver_id"),
                direction="IN", status="COMPLETED",
            ).count(),
        }
        uncertain = LoanRepayment.objects.filter(payment_status="SUCCESS", payment_intent__isnull=True)
        legacy_settled = LoanRepayment.objects.filter(
            payment_status="SUCCESS", payment_intent__status=PaymentIntent.SETTLED,
            amount_applied_ugx__isnull=True,
        )
        pending_intents = PaymentIntent.objects.filter(purpose=PaymentIntent.LOAN_REPAYMENT, status=PaymentIntent.PENDING)
        split_mismatch = [row.id for row in LoanRepayment.objects.filter(payment_status="SUCCESS", amount_applied_ugx__isnull=False)
                          if row.amount_applied_ugx + row.excess_ugx != row.amount_paid]
        report["uncertain_repayments"] = {
            "historical_success_without_intent_count": uncertain.count(),
            "historical_success_without_intent_received_ugx": str(uncertain.aggregate(
                v=Sum("amount_paid"))["v"] or Decimal("0")),
            "historical_success_without_intent_ids": list(uncertain.order_by("id").values_list("id", flat=True)[:limit]),
            "settled_without_applied_split_count": legacy_settled.count(),
            "settled_without_applied_split_ids": list(legacy_settled.order_by("id").values_list("id", flat=True)[:limit]),
            "pending_verified_intent_count": pending_intents.count(),
            "pending_verified_intent_ugx": str(pending_intents.aggregate(
                v=Sum("amount"))["v"] or Decimal("0")),
            "pending_verified_intent_ids": list(pending_intents.order_by("id").values_list("id", flat=True)[:limit]),
            "received_applied_excess_mismatch_ids": split_mismatch[:limit],
            "verified_excess_total_ugx": str(LoanRepayment.objects.filter(
                payment_status="SUCCESS").aggregate(v=Sum("excess_ugx"))["v"] or Decimal("0")),
        }
        inconsistent = []
        for loan in LoanApplication.objects.select_related("disbursement").all().iterator():
            reasons = []
            disbursement = getattr(loan, "disbursement", None)
            if disbursement and loan.amount_approved != disbursement.disbursed_amount:
                reasons.append("principal_disbursement_mismatch")
            if loan.amount_approved and loan.amount_paid > Decimal(loan.amount_approved) + loan_charges(loan):
                reasons.append("applied_more_than_calculated_due")
            if loan.status == "COMPLETED" and loan.outstanding_balance > 0:
                reasons.append("completed_with_debt")
            if reasons:
                inconsistent.append({"loan_id": loan.id, "reasons": reasons,
                                     "principal_ugx": str(loan.amount_approved),
                                     "applied_ugx": str(loan.amount_paid),
                                     "outstanding_ugx": str(loan.outstanding_balance)})
        report["inconsistent_loans"] = {"count": len(inconsistent), "rows": inconsistent[:limit]}
        self.stdout.write(json.dumps(report, indent=2))
