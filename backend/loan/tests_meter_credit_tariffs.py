"""Meter-specific stored evidence + existing tariff engine; no external systems."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from threading import Barrier
from unittest.mock import patch
import uuid

from django.core.management import call_command
from django.db import close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied

from loan.demo_assessment import complete_demo_assessment
from loan.demo_tariffs import pricing_inputs
from loan.models import DemoCreditAssessment, ElectricityTariff, SandboxLoan, TariffBlock
from loan.sandbox_service import assessment, create_quote, apply_loan
from meter.models import EnergyAllocation
from meter.sandbox_enrollment import enroll_sandbox_meter
from transactions.models import SandboxSettlement
from transactions.sandbox_payments import create_payment, receipt
from transactions.tests_demo_payments import DEMO, Fixtures


@override_settings(**DEMO)
class MeterCreditTariffTests(Fixtures, TestCase):
    def setUp(self):
        super().setUp()
        vat = patch("utils.billing.VAT_RATE", Decimal("0.18")); vat.start(); self.addCleanup(vat.stop)
        self.second = enroll_sandbox_meter(self.owner, "00005678")[0]
        self.tariff = ElectricityTariff.objects.get(tariff_code="DEMO-FIXTURE")
        self.tariff.service_charge = Decimal("3360"); self.tariff.save(update_fields=["service_charge"])
        self.tariff.blocks.all().delete()
        self.first_band = TariffBlock.objects.create(tariff=self.tariff, block_order=1, min_units=0, max_units=15,
            rate_per_unit="250", is_lifeline_block=True, non_lifeline_rate="756.20")
        TariffBlock.objects.create(tariff=self.tariff, block_order=2, min_units=16, max_units=None, rate_per_unit="756.20")

    def eligibility(self, meter=None):
        return assessment(self.owner, meter_id=(meter or self.meter).pk)

    def row(self, meter=None):
        return DemoCreditAssessment.objects.get(owner=self.owner, scope="METER", meter=meter or self.meter)

    def purchase_for(self, meter, amount="8390"):
        quote = create_quote(self.owner, meter.pk, amount, "PURCHASE")
        return create_payment(self.owner, {"purpose": "PURCHASE", "quote_id": str(quote.pk), "terms_hash": quote.terms_hash,
            "accept_test_terms": True, "client_request_id": str(uuid.uuid4())})[0]

    def test_two_meters_have_independent_evidence_not_copied_account_scores(self):
        one, two = self.row(), self.row(self.second)
        self.assertNotEqual(one.pk, two.pk)
        self.assertEqual(one.inputs["categories"], two.inputs["categories"])
        self.assertNotEqual(one.inputs["meter_evidence"], two.inputs["meter_evidence"])
        self.assertEqual(one.inputs["meter_evidence"]["ownership_source"], "SELF_DECLARED")
        self.assertFalse(one.inputs["verified_external_records"])
        self.assertEqual(one.score, 85); self.assertEqual(two.score, 85)
        self.assertEqual(self.eligibility()["meter_id"], self.meter.pk)
        self.assertIsNone(assessment(self.owner)["score"])

    def test_historical_declaration_for_another_owner_is_not_current_provenance(self):
        from accounts.models import User
        from meter.models import SandboxMeterEnrollment, MeterEnrollmentRequest, MeterEnrollmentReview
        self.row().delete()  # Isolated fixture: no historical production row is touched.
        SandboxMeterEnrollment.objects.filter(meter=self.meter).update(owner=self.other)
        staff = User.objects.create_user(email="reviewer-fixture@example.invalid", password="isolated-test-only", user_role=User.OPERATOR, is_staff=True)
        request = MeterEnrollmentRequest.objects.create(owner=self.owner, meter_no=self.meter.meter_no)
        MeterEnrollmentReview.objects.create(request=request, meter=self.meter, decision="APPROVED", reviewed_by=staff,
            evidence_type="SANDBOX_AUTHORIZATION", evidence_reference="synthetic-owned-meter-review")
        row = complete_demo_assessment(self.owner, self.meter)
        self.assertEqual(row.inputs["meter_evidence"]["ownership_source"], "SANDBOX_REVIEW")

    def test_owned_meter_is_required_on_all_assessment_routes(self):
        foreign = enroll_sandbox_meter(self.other, "00003456")[0]
        for route in ("sandbox/assessment/", "loans/mobile-eligibility/", "loans/credit-score/"):
            with transaction.atomic():
                result = self.client.get(f"/api/v1/{route}?meter_id={foreign.pk}", **self.headers)
            self.assertEqual(result.status_code, 403, route)
            self.assertNotIn(self.other.email, str(result.data))
        for meter_id in ("abc", "-1", "99999999999999999999999999999"):
            with transaction.atomic():
                self.assertEqual(self.client.get(f"/api/v1/sandbox/assessment/?meter_id={meter_id}", **self.headers).status_code, 403)
        with self.assertRaises(PermissionDenied): complete_demo_assessment(self.other, self.meter)

    def test_threshold_79_80_85_and_no_starter_exception(self):
        row = self.row()
        for score in (79, 80, 85):
            row.score = row.base_score = score; row.save()
            result = self.eligibility()
            self.assertEqual(result["eligible"], score >= 80)
            self.assertFalse(result["starter"])
            if score < 80:
                self.assertEqual(result["reason"], "This meter’s credit score is 79%. A minimum of 80% is required to apply for a loan.")
                with self.assertRaises(ValidationError): create_quote(self.owner, self.meter.pk, "10000", "LOAN")
            else:
                self.assertIsNotNone(create_quote(self.owner, self.meter.pk, "10000", "LOAN"))
        self.assertFalse(SandboxLoan.objects.exists())

    def test_unavailable_assessment_has_no_fallback_and_blocks_direct_quote(self):
        row = self.row(); row.status = "UNAVAILABLE"; row.score = row.base_score = None; row.assessed_at = None; row.save()
        result = self.eligibility()
        self.assertIsNone(result["score"]); self.assertFalse(result["eligible"])
        with self.assertRaises(ValidationError): create_quote(self.owner, self.meter.pk, "10000", "LOAN")

    def test_debt_and_limit_still_apply_and_submission_rechecks(self):
        with self.assertRaises(ValidationError): create_quote(self.owner, self.meter.pk, "50000", "LOAN")
        first = create_quote(self.owner, self.meter.pk, "10000", "LOAN")
        other = create_quote(self.owner, self.second.pk, "10000", "LOAN")
        self.assertEqual(apply_loan(self.owner, first.pk, first.terms_hash, uuid.uuid4())[0].status, "DISBURSED")
        rejected = apply_loan(self.owner, other.pk, other.terms_hash, uuid.uuid4())[0]
        self.assertEqual(rejected.status, "REJECTED")
        self.assertIn("Repay", rejected.decision_reason)
        self.assertEqual(EnergyAllocation.objects.count(), 1)
        self.assertFalse(self.eligibility(self.second)["eligible"])

    def test_assessment_change_invalidates_quote_and_cannot_disburse(self):
        quote = create_quote(self.owner, self.meter.pk, "10000", "LOAN")
        row = self.row(); row.score = row.base_score = 79; row.save()
        with self.assertRaises(ValidationError) as error: apply_loan(self.owner, quote.pk, quote.terms_hash, uuid.uuid4())
        self.assertEqual(error.exception.detail["code"], "QUOTE_STALE")
        self.assertFalse(EnergyAllocation.objects.exists())

    def test_configured_tariff_boundary_charges_and_exact_remainder(self):
        quote = create_quote(self.owner, self.meter.pk, "8390", "PURCHASE")
        self.assertEqual(Decimal(quote.terms["energy_kwh"]), Decimal("15.00"))
        self.assertEqual(Decimal(quote.terms["billed"]), Decimal("8389.80"))
        self.assertEqual(Decimal(quote.terms["residual"]), Decimal("0.20"))
        bill = quote.terms["pricing"]["breakdown"]
        self.assertEqual(Decimal(bill["energy_cost"]), Decimal("3750"))
        self.assertEqual(Decimal(bill["service_charge"]), Decimal("3360"))
        self.assertEqual(Decimal(bill["vat"]), Decimal("1279.80"))
        self.assertEqual(quote.terms["pricing"]["inputs"]["tariff"]["id"], self.tariff.pk)

    def test_owner_bands_shared_between_meters_but_only_demo_paid_purchases_count(self):
        loan_quote = create_quote(self.owner, self.meter.pk, "8390", "LOAN")
        apply_loan(self.owner, loan_quote.pk, loan_quote.terms_hash, uuid.uuid4())
        self.assertEqual(Decimal(pricing_inputs(self.owner)["monthly_purchased_kwh"]), 0)
        self.settle(self.purchase_for(self.meter))
        self.assertEqual(Decimal(pricing_inputs(self.owner)["monthly_purchased_kwh"]), 15)
        second = create_quote(self.owner, self.second.pk, "1000", "PURCHASE")
        self.assertEqual(Decimal(second.terms["energy_kwh"]), Decimal("1.12"))
        self.assertEqual(Decimal(second.terms["pricing"]["breakdown"]["service_charge"]), 0)
        self.assertEqual(Decimal(second.terms["billed"]), Decimal("999.39"))

    def test_purchase_bonus_bound_to_receiving_meter_exactly_once(self):
        intent = self.purchase_for(self.second, "20000")
        self.settle(intent); self.settle(intent)
        self.assertEqual(self.row().purchase_points, 0)
        self.assertEqual((self.row(self.second).purchase_points, self.row(self.second).purchase_source_count), (1, 1))
        self.assertEqual(self.row(self.second).qualifying_billed_ugx, SandboxSettlement.objects.get(intent=intent).billed)

    def test_tariff_change_rejects_new_initiation_and_honors_already_pending_terms(self):
        stale = create_quote(self.owner, self.meter.pk, "8390", "PURCHASE")
        self.first_band.rate_per_unit = Decimal("260"); self.first_band.save()
        with self.assertRaises(ValidationError):
            create_payment(self.owner, {"purpose": "PURCHASE", "quote_id": str(stale.pk), "terms_hash": stale.terms_hash,
                "accept_test_terms": True, "client_request_id": str(uuid.uuid4())})
        intent = self.purchase_for(self.meter, "10000")
        original = intent.sandbox_context["terms"]
        self.first_band.rate_per_unit = Decimal("270"); self.first_band.save()
        with patch("utils.billing.VAT_RATE", Decimal("0.2")): self.settle(intent)
        intent.refresh_from_db()
        self.assertEqual(intent.sandbox_context["terms"], original)
        self.assertEqual(receipt(intent)["pricing"], original["pricing"])
        self.assertEqual(intent.energy_allocation.amount_kwh, Decimal(original["energy_kwh"]))

    def test_no_tariff_no_expired_future_or_fallback_rate(self):
        self.tariff.is_active = False; self.tariff.save()
        self.assertFalse(self.client.get(f"/api/v1/sandbox/assessment/?meter_id={self.meter.pk}", **self.headers).data["pricing"]["available"])
        with self.assertRaises(ValidationError): create_quote(self.owner, self.meter.pk, "10000", "PURCHASE")
        self.tariff.is_active = True; self.tariff.effective_from = timezone.localdate() + timedelta(days=1); self.tariff.save()
        with self.assertRaises(ValidationError): create_quote(self.owner, self.meter.pk, "10000", "PURCHASE")
        self.tariff.effective_from = timezone.localdate() - timedelta(days=5); self.tariff.effective_to = timezone.localdate() - timedelta(days=1); self.tariff.save()
        with self.assertRaises(ValidationError): create_quote(self.owner, self.meter.pk, "10000", "PURCHASE")

    def test_preview_initialization_preserves_legacy_account_and_all_meter_records(self):
        old = self.row(); old.scope = "ACCOUNT_LEGACY"; old.save()
        original = (old.score, old.inputs, old.updated_at)
        count = DemoCreditAssessment.objects.count()
        output = StringIO(); call_command("initialize_demo_assessments", user_id=self.owner.pk, stdout=output)
        self.assertEqual(DemoCreditAssessment.objects.count(), count)
        self.assertIn(f"meter_id={self.meter.pk} assessment=MISSING", output.getvalue())
        call_command("initialize_demo_assessments", user_id=self.owner.pk, apply=True, stdout=output)
        self.assertEqual(self.row().score, 85)
        old.refresh_from_db(); self.assertEqual((old.score, old.inputs, old.updated_at), original)


@override_settings(**DEMO)
class MeterAssessmentConcurrencyTests(Fixtures, TransactionTestCase):
    def test_same_meter_initialization_has_one_record(self):
        DemoCreditAssessment.objects.filter(owner=self.owner, meter=self.meter, scope="METER").delete()
        barrier = Barrier(2)
        def run(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return complete_demo_assessment(self.owner, self.meter).pk
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(run, range(2)))
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(DemoCreditAssessment.objects.filter(owner=self.owner, meter=self.meter, scope="METER").count(), 1)


class LegacyAssessmentMigrationTests(TransactionTestCase):
    def test_migration_tags_old_rows_without_changing_scores_or_evidence(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        executor = MigrationExecutor(connection)
        other_leaves = [node for node in executor.loader.graph.leaf_nodes() if node[0] != "loan"]
        before = other_leaves + [("loan", "0025_democreditassessment")]
        after = other_leaves + [("loan", "0027_alter_democreditassessment_scoring_policy_version")]
        try:
            executor.migrate(before)
            apps = executor.loader.project_state(before).apps
            owner = apps.get_model("accounts", "User").objects.create(email="legacy-score@example.invalid", password="isolated-only", monthly_unit_balance=Decimal(0))
            old = apps.get_model("loan", "DemoCreditAssessment").objects.create(owner=owner, scenario="APPROVAL_V1",
                status="READY", score=85, base_score=85, assessed_at=timezone.now(), inputs={"preserve": "historical evidence"})
            original = (old.score, old.inputs, old.assessed_at, old.updated_at, old.scoring_policy_version)
            executor = MigrationExecutor(connection); executor.migrate(after)
            row = executor.loader.project_state(after).apps.get_model("loan", "DemoCreditAssessment").objects.get(pk=old.pk)
            self.assertEqual(row.scope, "ACCOUNT_LEGACY")
            self.assertEqual((row.score, row.inputs, row.assessed_at, row.updated_at, row.scoring_policy_version), original)
        finally:
            MigrationExecutor(connection).migrate(after)
