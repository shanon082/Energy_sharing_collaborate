"""MTN transition tests: real adapter/settlement, synthetic HTTP and isolated data."""
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import Mock, patch

import requests
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from loan.tests_sandbox import Fixtures, SANDBOX, POLICY
from loan.sandbox_service import create_quote
from transactions.models import PaymentIntent, SandboxSettlement
from transactions.sandbox_payments import reconcile_sandbox_payment, receipt
from transactions.demo_payments import complete_demo_payment
from meter.models import EnergyAllocation, EnergyKeypadToken


@override_settings(**SANDBOX)
class MTNTransitionTests(Fixtures, TestCase):
    def setUp(self):
        self.create_fixture()

    def due(self, intent):
        PaymentIntent.objects.filter(pk=intent.pk).update(reconcile_after=timezone.now()-timedelta(seconds=1))

    def provider_body(self, intent, status, **changes):
        return {"externalId": intent.provider_external_id, "currency": "EUR", "amount": str(intent.amount),
                "financialTransactionId": "synthetic-" + str(intent.provider_reference),
                "payer": {"partyId": "46733123454", "partyIdType": "MSISDN"}, "status": status, **changes}

    def http(self, status=200, body=None):
        result = Mock(status_code=status)
        result.json.return_value = body
        return result

    def reconcile(self, intent, status, **changes):
        self.due(intent)
        with patch("mtn_momo.sandbox.requests.post", return_value=self.http(body={"access_token": "synthetic-only"})), \
             patch("mtn_momo.sandbox.requests.get", return_value=self.http(body=self.provider_body(intent, status, **changes))) as get:
            result = reconcile_sandbox_payment(intent.pk)
            if get.called:
                self.assertTrue(get.call_args.args[0].endswith("/" + str(intent.provider_reference)))
                self.assertFalse(get.call_args.kwargs["allow_redirects"])
            else:
                self.assertNotEqual(result[0].status, "PENDING")
            return result

    def submitted(self, intent):
        with patch("mtn_momo.sandbox.requests.post", side_effect=[
            self.http(body={"access_token": "synthetic-only"}), self.http(202)]) as post:
            row, effect = reconcile_sandbox_payment(intent.pk)
            self.assertFalse(effect)
            self.assertEqual(row.status, "PENDING")
            self.assertEqual(row.submission_state, "ACCEPTED")
            self.assertEqual(post.call_args.kwargs["headers"]["X-Reference-Id"], str(intent.provider_reference))
            self.assertEqual(post.call_args.kwargs["json"]["externalId"], intent.provider_external_id)

    def test_202_pending_success_and_duplicate_receipt(self):
        intent = self.purchase()
        self.submitted(intent)
        row, effect = self.reconcile(intent, "PENDING")
        self.assertEqual(row.status, "PENDING"); self.assertFalse(effect)
        self.assertFalse(EnergyAllocation.objects.exists())
        row, effect = self.reconcile(intent, "SUCCESSFUL")
        self.assertTrue(effect); self.assertEqual(row.status, "SETTLED")
        again, effect = self.reconcile(intent, "SUCCESSFUL")
        self.assertFalse(effect)
        self.assertEqual(receipt(row)["allocation_id"], receipt(again)["allocation_id"])
        self.assertEqual(SandboxSettlement.objects.count(), 1)
        self.assertEqual(EnergyAllocation.objects.count(), 1)
        before = receipt(row)
        stored = self.client.get(f"/api/v1/sandbox/payments/{row.provider_reference}/", **self.headers).data["payment"]
        for key in ("reference", "status", "amount", "currency", "environment", "billed", "allocation_id"):
            self.assertEqual(stored[key], before[key])

    def test_http_200_failed_has_no_financial_effect(self):
        intent = self.purchase(); self.submitted(intent)
        row, effect = self.reconcile(intent, "FAILED")
        self.assertEqual(row.status, "FAILED"); self.assertFalse(effect)
        self.assertFalse(SandboxSettlement.objects.exists()); self.assertFalse(EnergyAllocation.objects.exists())

    def test_timeout_and_app_closed_recovery_never_charge_twice(self):
        intent = self.purchase()
        with patch("mtn_momo.sandbox.requests.post", side_effect=[self.http(body={"access_token": "synthetic-only"}), requests.Timeout()]) as post:
            row, _ = reconcile_sandbox_payment(intent.pk)
            self.assertEqual(post.call_count, 2)
            self.assertEqual(row.submission_state, "OUTCOME_UNKNOWN")
        self.due(intent)
        with patch("mtn_momo.sandbox.requests.post", return_value=self.http(body={"access_token": "synthetic-only"})) as post, \
             patch("mtn_momo.sandbox.requests.get", return_value=self.http(body=self.provider_body(intent, "SUCCESSFUL"))):
            call_command("reconcile_sandbox_payments", run=True, limit=1, stdout=StringIO())
            self.assertTrue(all(call.args[0].endswith("/collection/token/") for call in post.call_args_list))
        intent.refresh_from_db(); self.assertEqual(intent.status, "SETTLED")
        self.assertEqual(EnergyAllocation.objects.count(), 1)

    def test_currency_mismatch_and_simulated_completion_cannot_settle_mtn(self):
        intent = self.purchase(); self.submitted(intent)
        row, effect = self.reconcile(intent, "SUCCESSFUL", currency="UGX")
        self.assertEqual(row.status, "PENDING"); self.assertFalse(effect)
        self.assertTrue(row.reconciliation_error)
        from rest_framework.exceptions import NotFound
        with self.assertRaises(NotFound): complete_demo_payment(intent.pk, owner=self.owner)
        self.assertFalse(SandboxSettlement.objects.exists())

    def test_eur_self_repayment_closes_debt_without_token_or_energy(self):
        loan = self.loan(); allocations = EnergyAllocation.objects.count(); tokens = EnergyKeypadToken.objects.count()
        intent = self.repayment(loan, "2.10"); self.submitted(intent)
        row, effect = self.reconcile(intent, "SUCCESSFUL")
        self.assertTrue(effect); self.assertIsNone(receipt(row)["allocation_id"])
        loan.refresh_from_db(); self.assertEqual(loan.outstanding, Decimal("0")); self.assertEqual(loan.status, "COMPLETED")
        self.assertEqual(EnergyAllocation.objects.count(), allocations)
        self.assertEqual(EnergyKeypadToken.objects.count(), tokens)

    def test_missing_credentials_fail_closed_and_pricing_gap_blocks_new_energy(self):
        with override_settings(MTN_SANDBOX_CONFIG={}):
            features = self.client.get("/api/v1/features/", **self.headers).data["sandbox"]
            self.assertEqual(features["payment_message"], "Sandbox payments unavailable")
            self.assertFalse(features["purchases"]); self.assertFalse(features["repayments"])
            from transactions.payment_settlement import PaymentSettlementError
            with self.assertRaisesRegex(PaymentSettlementError, "Sandbox payments unavailable"): self.purchase()
        with override_settings(SANDBOX_POLICY={**POLICY, "rate_per_kwh": None}):
            with self.assertRaises(ValidationError): create_quote(self.owner, self.meter.pk, "2", "PURCHASE")
            self.assertFalse(self.client.get("/api/v1/features/", **self.headers).data["sandbox"]["purchases"])
        self.assertFalse(PaymentIntent.objects.exists())

    def test_legacy_demo_pending_settles_in_original_domain_after_switch(self):
        from transactions.tests_demo_payments import Fixtures as DemoFixtures, DEMO
        with override_settings(**DEMO):
            fixture = DemoFixtures()
            # The fixture needs only TestCase cleanup support, never external I/O.
            fixture.addCleanup = self.addCleanup
            fixture.setUp()
            intent = fixture.purchase()
        PaymentIntent.objects.filter(pk=intent.pk).update(initiated_at=timezone.now()-timedelta(seconds=10), demo_eligible_at=timezone.now()-timedelta(seconds=5))
        with patch("requests.sessions.Session.request", side_effect=AssertionError("No network for old demo")):
            call_command("complete_demo_payments", run=True, stdout=StringIO())
        intent.refresh_from_db(); self.assertEqual(intent.status, "SETTLED"); self.assertEqual(intent.provider, "LOCAL_DEMO")
        self.assertEqual(intent.energy_allocation.accounting_environment, "UGX_DEMO")

    def test_status_get_is_read_only_and_no_client_success_authority(self):
        intent = self.purchase()
        with patch("mtn_momo.sandbox.requests.get") as get:
            self.client.get(f"/api/v1/sandbox/payments/{intent.provider_reference}/?success=true", **self.headers)
            get.assert_not_called()
        intent.refresh_from_db(); self.assertEqual(intent.status, "PENDING")
        self.assertFalse(EnergyAllocation.objects.exists())

    def test_https_login_preflight_and_validation_response_remain_readable(self):
        origin = "http://localhost"
        options = self.client.options("/api/v1/auth/login/", HTTP_ORIGIN=origin,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST", HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type", **self.headers)
        self.assertEqual(options.status_code, 200)
        self.assertEqual(options["Access-Control-Allow-Origin"], origin)
        response = self.client.post("/api/v1/auth/login/", {}, format="json", HTTP_ORIGIN=origin, **self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response["Access-Control-Allow-Origin"], origin)

    def test_pausing_new_mtn_collections_does_not_block_submitted_recovery(self):
        intent = self.purchase(); self.submitted(intent)
        with override_settings(PROTOTYPE_PAYMENT_PROVIDER="LOCAL_DEMO"):
            row, effect = self.reconcile(intent, "SUCCESSFUL")
        self.assertTrue(effect); self.assertEqual(row.currency, "EUR")
        self.assertEqual(row.energy_allocation.accounting_environment, "SANDBOX")

    def test_paused_new_intent_does_not_starve_older_submitted_recovery(self):
        submitted = self.purchase(); self.submitted(submitted)
        # Simulate a separately durable NEW obligation from before the mode switch.
        other = self.purchase_record_for_other_owner()
        self.due(submitted)
        PaymentIntent.objects.filter(pk=other.pk).update(reconcile_after=timezone.now()-timedelta(hours=1))
        with override_settings(PROTOTYPE_PAYMENT_PROVIDER="LOCAL_DEMO"), \
             patch("mtn_momo.sandbox.requests.post", return_value=self.http(body={"access_token": "synthetic-only"})) as post, \
             patch("mtn_momo.sandbox.requests.get", return_value=self.http(body=self.provider_body(submitted, "SUCCESSFUL"))):
            call_command("reconcile_sandbox_payments", run=True, limit=1, stdout=StringIO())
            self.assertTrue(all(call.args[0].endswith("/collection/token/") for call in post.call_args_list))
        submitted.refresh_from_db(); other.refresh_from_db()
        self.assertEqual(submitted.status, "SETTLED"); self.assertEqual(other.submission_state, "NEW")

    def purchase_record_for_other_owner(self):
        # Retain source bindings while making a distinct, valid owned meter.
        from meter.sandbox_enrollment import enroll_sandbox_meter
        from transactions.sandbox_payments import create_payment
        import uuid
        meter, _ = enroll_sandbox_meter(self.other, "00000007654")
        quote = create_quote(self.other, meter.pk, "2", "PURCHASE")
        return create_payment(self.other, {"purpose": "PURCHASE", "quote_id": str(quote.pk), "terms_hash": quote.terms_hash,
            "accept_test_terms": True, "msisdn": "46733123454", "client_request_id": str(uuid.uuid4())})[0]

    @override_settings(SANDBOX_EUR_LOANS_ENABLED=False)
    def test_new_eur_loans_fail_closed_without_automatic_assessment_policy(self):
        from loan.sandbox_service import assessment
        result = assessment(self.owner, meter_id=self.meter.pk)
        self.assertFalse(result["eligible"]); self.assertIsNone(result["score"]); self.assertIsNone(result["maximum"])
        with self.assertRaises(ValidationError): self.loan()
        features = self.client.get("/api/v1/features/", **self.headers).data["sandbox"]
        self.assertFalse(features["loans"]); self.assertTrue(features["purchases"]); self.assertTrue(features["repayments"])
