"""Synthetic fixtures on isolated PostgreSQL; no real account-information queries."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from io import StringIO
from threading import Barrier
from unittest.mock import patch
import uuid

from django.core.management import call_command, CommandError
from django.db import close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from accounts.models import User
from loan.account_data import AccountDataUnavailable, SimulatedAccountDataProvider
from loan.demo_assessment import initialize_demo_assessment, complete_demo_assessment
from loan.models import DemoCreditAssessment, UserCreditSignal, CreditScoreHistory, CreditScoreFactors, SandboxLoan
from loan.sandbox_service import assessment, create_quote, apply_loan, policy
from loan.scoring import calculate_weighted_credit_score
from meter.sandbox_enrollment import enroll_sandbox_meter
from meter.models import EnergyAllocation
from transactions.tests_demo_payments import DEMO, Fixtures


@override_settings(**DEMO)
class AutomaticAssessmentTests(Fixtures, TestCase):
    def test_registration_creates_pending_without_provider_or_core_score(self):
        with patch("loan.demo_assessment.account_data_provider", side_effect=AssertionError("No data lookup at signup")):
            response = APIClient().post("/api/v1/auth/register/", {
                "email": "automatic-signup@example.invalid", "first_name": "Demo", "last_name": "Consumer",
                "phone_number": "+256700001219", "gender": "MALE", "password": "Synthetic-password-123",
                "confirm_password": "Synthetic-password-123", "score": 100, "approved": True,
            }, format="json", **self.headers)
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="automatic-signup@example.invalid")
        row = DemoCreditAssessment.objects.get(owner=user)
        self.assertEqual(row.status, "PENDING"); self.assertIsNone(row.score)
        self.assertFalse(UserCreditSignal.objects.filter(user=user).exists())
        self.assertFalse(CreditScoreFactors.objects.filter(user=user).exists())
        self.assertFalse(user.profile.email_verified)

    def test_enrollment_uses_existing_calculator_without_questionnaire(self):
        row = DemoCreditAssessment.objects.get(owner=self.owner)
        from types import SimpleNamespace
        expected = calculate_weighted_credit_score(SimpleNamespace(**row.inputs["categories"]))
        self.assertEqual((row.status, row.score, expected), ("READY", 85, 85))
        self.assertEqual(row.meter_id, self.meter.pk); self.assertEqual(row.provider, "SIMULATED_ACCOUNT_V1")
        self.assertFalse(row.inputs["verified_external_records"])
        self.assertEqual(row.scoring_policy_version, "DEMO-SCORE-v1"); self.assertIsNotNone(row.assessed_at)
        self.assertIsNone(self.owner.monthly_income)
        self.assertTrue(assessment(self.owner)["eligible"])
        self.assertEqual(self.loan().status, "DISBURSED")

    def test_initialization_and_enrollment_retry_preserve_score_and_binding(self):
        before = DemoCreditAssessment.objects.get(owner=self.owner)
        with patch("loan.demo_assessment.account_data_provider", side_effect=AssertionError("No repeat fetch")):
            row, created = initialize_demo_assessment(self.owner)
            self.assertFalse(created); self.assertEqual(row.pk, before.pk)
            self.assertFalse(enroll_sandbox_meter(self.owner, self.meter.meter_no)[1])
            new_meter, _ = enroll_sandbox_meter(self.owner, "00009992")
        row.refresh_from_db()
        self.assertEqual((row.meter_id, row.assessed_at, row.updated_at), (before.meter_id, before.assessed_at, before.updated_at))
        self.assertNotEqual(new_meter.pk, row.meter_id)

    def test_reads_login_and_client_answers_do_not_award_or_rewrite_score(self):
        before = DemoCreditAssessment.objects.get(owner=self.owner)
        with patch("loan.demo_assessment.account_data_provider", side_effect=AssertionError("GET/login cannot fetch evidence")):
            for _ in range(2):
                result = self.client.get("/api/v1/sandbox/assessment/?user_id="+str(self.other.pk), **self.headers)
                self.assertEqual(result.data["assessment"]["assessment_id"], before.pk)
                self.assertEqual(result.data["assessment"]["score"], 85)
                stats = self.client.get("/api/v1/loans/stats/", **self.headers)
                self.assertEqual(stats.status_code, 200); self.assertIsNone(stats.data["credit_score"])
                self.assertEqual(stats.data["accounting_environment"], "CORE")
                legacy = self.client.get("/api/v1/loans/credit-score/", **self.headers)
                self.assertEqual(legacy.data["demo_assessment"]["assessment_id"], before.pk)
                result = APIClient().post("/api/v1/auth/login/", {"email": self.owner.email, "password": "test-only"}, format="json", **self.headers)
                self.assertEqual(result.status_code, 200)
        before.refresh_from_db(); self.assertEqual(before.purchase_points, 0)
        self.assertFalse(UserCreditSignal.objects.filter(user=self.owner).exists())
        self.assertFalse(CreditScoreHistory.objects.filter(user=self.owner).exists())

    def test_questionnaire_rejected_but_ordinary_account_preferences_work(self):
        result = self.client.patch("/api/v1/auth/mobile-profile/", {"monthly_income": ">1,000,000 UGX"}, format="json", **self.headers)
        self.assertEqual(result.status_code, 403)
        self.assertEqual(result.data["code"], "QUESTIONNAIRE_RETIRED")
        result = self.client.post("/api/v1/auth/user-profile/", {"monthly_income": ">1,000,000 UGX"}, format="json", **self.headers)
        self.assertEqual(result.status_code, 403)
        self.owner.refresh_from_db(); self.assertIsNone(self.owner.monthly_income)
        result = self.client.patch("/api/v1/auth/mobile-account-details/", {"address": "Synthetic test address"}, format="json", **self.headers)
        self.assertEqual(result.status_code, 200)
        self.assertFalse(UserCreditSignal.objects.filter(user=self.owner).exists())

    def test_missing_provider_is_unavailable_not_zero_or_starter_and_retry_heals(self):
        with patch("loan.demo_assessment.account_data_provider") as factory:
            factory.return_value.fetch.side_effect = AccountDataUnavailable("Synthetic unavailable fixture")
            meter, _ = enroll_sandbox_meter(self.other, "00009993")
        result = assessment(self.other)
        self.assertEqual(result["assessment_status"], "UNAVAILABLE")
        self.assertIsNone(result["score"]); self.assertIsNone(result["maximum"]); self.assertFalse(result["eligible"])
        with self.assertRaises(ValidationError): create_quote(self.other, meter.pk, "1000", "LOAN")
        self.assertFalse(SandboxLoan.objects.filter(owner=self.other).exists())
        enroll_sandbox_meter(self.other, meter.meter_no)
        self.assertEqual(assessment(self.other)["score"], 85)

    def test_malformed_provider_data_rejected_as_unavailable(self):
        for value in (None, {"categories": []}, {"provider": "REAL_CRB", "categories": {}},
                      {**SimulatedAccountDataProvider().fetch("APPROVAL_V1"), "categories": {"payment_history": [], "energy_consumption": "MODERATE", "financial_capacity": "STRONG"}}):
            with patch("loan.demo_assessment.account_data_provider") as factory:
                factory.return_value.fetch.return_value = value
                row = complete_demo_assessment(self.other, enroll_sandbox_meter(self.other, "00009994")[0])
            self.assertEqual(row.status, "UNAVAILABLE"); self.assertIsNone(row.score)

    def test_stable_profiles_do_not_use_personal_identifiers(self):
        enroll_sandbox_meter(self.other, "00009995")
        original = DemoCreditAssessment.objects.get(owner=self.other)
        self.other.first_name = "Completely different"; self.other.phone_number = "+256700123456"
        self.other.save(update_fields=["first_name", "phone_number"])
        self.assertEqual(assessment(self.other)["score"], 85)
        self.assertEqual(original.inputs, DemoCreditAssessment.objects.get(owner=self.owner).inputs)
        self.assertNotIn(self.other.email, str(original.inputs))

    def test_rejection_fixture_uses_stored_assessment_despite_forged_client_score(self):
        with override_settings(DEMO_ACCOUNT_PROFILE="REJECTION_V1"):
            owner = User.objects.create_user(email="rejected-test@example.invalid", password="test-only")
        owner.profile.email_verified = True; owner.profile.save(update_fields=["email_verified"])
        meter, _ = enroll_sandbox_meter(owner, "00009996")
        self.assertEqual(assessment(owner)["score"], 41)
        quote = create_quote(owner, meter.pk, "1000", "LOAN")
        self.client.force_authenticate(owner)
        result = self.client.post("/api/v1/sandbox/loans/", {"quote_id": str(quote.pk), "terms_hash": quote.terms_hash,
            "client_request_id": str(uuid.uuid4()), "accept_test_terms": True, "score": 100, "approved": True,
            "account_history": {"payment_history": "GOOD"}}, format="json", **self.headers)
        self.assertEqual(result.status_code, 201); self.assertEqual(result.data["loan"]["status"], "REJECTED")
        self.assertFalse(EnergyAllocation.objects.filter(owner=owner).exists())

    def test_settlement_purchase_contribution_once_not_pending_or_screen_refresh(self):
        intent = self.purchase("10000")
        self.assertEqual(assessment(self.owner)["purchase_points"], 0)
        self.settle(intent); self.settle(intent)
        row = DemoCreditAssessment.objects.get(owner=self.owner)
        self.assertEqual((row.purchase_points, row.score, row.purchase_source_count), (1, 86, 1))
        self.assertEqual(row.qualifying_billed_ugx, Decimal(10000))
        for _ in range(3): self.assertEqual(assessment(self.owner)["score"], 86)
        latest = DemoCreditAssessment.objects.get(pk=row.pk)
        self.assertEqual(latest.updated_at, row.updated_at)
        loan = self.loan(); self.settle(self.repayment(loan, "300"))
        self.assertEqual(assessment(self.owner)["purchase_points"], 1)

    def test_preview_then_repair_existing_user_preserves_core_evidence(self):
        DemoCreditAssessment.objects.filter(owner=self.owner).delete()
        core = UserCreditSignal.objects.create(user=self.owner, payment_history="POOR", energy_consumption="ERRATIC", financial_capacity="WEAK", source="PROFILE")
        output = StringIO(); call_command("initialize_demo_assessments", user_id=self.owner.pk, stdout=output)
        self.assertIn("MISSING", output.getvalue()); self.assertFalse(DemoCreditAssessment.objects.filter(owner=self.owner).exists())
        call_command("initialize_demo_assessments", apply=True, user_id=self.owner.pk, stdout=output)
        self.assertEqual(assessment(self.owner)["score"], 85)
        core.refresh_from_db(); self.assertEqual(core.payment_history, "POOR")
        with self.assertRaises(CommandError): call_command("initialize_demo_assessments", apply=True, user_id=self.owner.pk, scenario="REJECTION_V1", stdout=output)
        self.assertEqual(assessment(self.owner)["score"], 85)
        self.other.profile.delete()  # An incomplete isolated historical account must remain pending.
        call_command("initialize_demo_assessments", apply=True, user_id=self.other.pk, stdout=output)
        self.assertEqual(DemoCreditAssessment.objects.get(owner=self.other).status, "PENDING")

    def test_multiple_owned_meters_require_explicit_repair_selection(self):
        enroll_sandbox_meter(self.owner, "00009997")
        DemoCreditAssessment.objects.filter(owner=self.owner).delete()
        call_command("initialize_demo_assessments", apply=True, user_id=self.owner.pk, stdout=StringIO())
        self.assertEqual(assessment(self.owner)["assessment_status"], "PENDING")
        call_command("initialize_demo_assessments", apply=True, user_id=self.owner.pk, meter_id=self.meter.pk, stdout=StringIO())
        self.assertEqual(assessment(self.owner)["score"], 85)

    def test_policy_version_change_unavailable_and_current_debt_checked_at_submission(self):
        quote = create_quote(self.owner, self.meter.pk, "1000", "LOAN")
        self.loan()
        loan, _ = apply_loan(self.owner, quote.pk, quote.terms_hash, uuid.uuid4())
        self.assertEqual(loan.status, "REJECTED")
        cfg = {**policy(), "id": "DEMO-UGX-future"}
        self.assertIsNone(assessment(self.owner, cfg)["score"])
        self.assertEqual(assessment(self.owner, cfg)["assessment_status"], "UNAVAILABLE")

    def test_current_limit_is_rechecked_not_the_old_quote_limit(self):
        quote = create_quote(self.owner, self.meter.pk, "2000", "LOAN")
        with override_settings(DEMO_POLICY={**policy(), "maximum": "2000"}):
            loan, _ = apply_loan(self.owner, quote.pk, quote.terms_hash, uuid.uuid4())
        self.assertEqual(loan.status, "REJECTED")
        self.assertFalse(EnergyAllocation.objects.filter(sandbox_loan=loan).exists())
        self.assertEqual(loan.terms["policy"]["maximum"], "50000")
        self.assertEqual(loan.assessment["maximum"], "1500")

    def test_changed_assessment_policy_does_not_use_old_quote_as_a_fallback(self):
        quote = create_quote(self.owner, self.meter.pk, "1000", "LOAN")
        with override_settings(DEMO_POLICY={**policy(), "id": "DEMO-UGX-future"}):
            with self.assertRaises(ValidationError):
                apply_loan(self.owner, quote.pk, quote.terms_hash, uuid.uuid4())
        self.assertFalse(SandboxLoan.objects.filter(owner=self.owner).exists())

    def test_unverified_or_anonymous_cannot_read_assessment(self):
        public = APIClient()
        with transaction.atomic():
            self.assertEqual(public.get("/api/v1/sandbox/assessment/", **self.headers).status_code, 401)
        self.other.profile.email_verified = False; self.other.profile.save(update_fields=["email_verified"])
        public.force_authenticate(self.other)
        with transaction.atomic():
            self.assertEqual(public.get("/api/v1/sandbox/assessment/", **self.headers).status_code, 403)


@override_settings(**DEMO)
class AutomaticAssessmentConcurrencyTests(Fixtures, TransactionTestCase):
    def test_simultaneous_initialization_and_enrollment_are_idempotent(self):
        # Setup itself creates pending records; remove only isolated demo fixture evidence.
        DemoCreditAssessment.objects.filter(owner=self.other).delete()
        barrier = Barrier(2)
        def run(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                owner = User.objects.get(pk=self.other.pk)
                initialize_demo_assessment(owner)
                return enroll_sandbox_meter(owner, "00009998")[0].pk
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(run, range(2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(DemoCreditAssessment.objects.filter(owner=self.other).count(), 1)
        self.assertEqual(assessment(self.other)["score"], 85)
