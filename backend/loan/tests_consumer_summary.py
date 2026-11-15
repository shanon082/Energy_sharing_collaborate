"""Read-only parity, full-ledger scope and tenant separation on isolated data."""
from decimal import Decimal
from datetime import timedelta
import uuid
from django.test import TestCase, override_settings
from django.utils import timezone
from loan.models import SandboxLoan, SandboxQuote
from loan.sandbox_service import apply_loan, create_quote
from meter.sandbox_enrollment import enroll_sandbox_meter
from transactions.models import PaymentIntent, SandboxSettlement
from transactions.tests_demo_payments import DEMO, Fixtures


@override_settings(**DEMO)
class ConsumerSummaryTests(Fixtures, TestCase):
    def summary(self, **params):
        return self.client.get("/api/v1/sandbox/summary/", params, **self.headers)

    def test_partial_repayment_matches_summary_and_details_without_mutating(self):
        quote = create_quote(self.owner, self.meter.pk, "5000", "LOAN")
        loan = apply_loan(self.owner, quote.pk, quote.terms_hash, uuid.uuid4())[0]
        self.settle(self.repayment(loan, "2500"))
        before = (PaymentIntent.objects.count(), SandboxSettlement.objects.count())
        response = self.summary(environment="UGX_DEMO")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(response.data["total_due"]), Decimal("5250"))
        self.assertEqual(Decimal(response.data["applied_repayments"]), Decimal("2500"))
        self.assertEqual(Decimal(response.data["outstanding"]), Decimal("2750"))
        self.assertEqual(response.data["scope"], "OWNER")
        self.assertEqual(response.data["active_loan_count"], 1)
        details = self.client.get("/api/v1/sandbox/loans/", **self.headers).data["loans"][0]
        self.assertEqual(Decimal(details["outstanding"]), Decimal(response.data["outstanding"]))
        self.assertEqual(Decimal(details["applied_repayments"]), Decimal(response.data["applied_repayments"]))
        self.assertEqual(before, (PaymentIntent.objects.count(), SandboxSettlement.objects.count()))
        self.assertIn("no-store", response["Cache-Control"])

    def historical_rows(self, count, *, environment="UGX_DEMO", currency="UGX", owner=None):
        owner = owner or self.owner
        meter = self.meter if owner == self.owner else enroll_sandbox_meter(owner, "00000000999")[0]
        quotes = SandboxQuote.objects.bulk_create([SandboxQuote(owner=owner, meter=meter, purpose="LOAN",
            amount=1, currency=currency, environment=environment, terms={}, terms_hash="fixture",
            expires_at=timezone.now()) for _ in range(count)])
        loans = SandboxLoan.objects.bulk_create([SandboxLoan(owner=owner, meter=meter, quote=quote,
            client_request_id=uuid.uuid4(), currency=currency, environment=environment, principal=1, total_due=1,
            terms={}, assessment={}, status="COMPLETED", decision_reason="Isolated history fixture", due_at=timezone.now(), closed_at=timezone.now()) for quote in quotes])
        provider = "LOCAL_DEMO" if environment == "UGX_DEMO" else "MTN_SANDBOX"
        payments = PaymentIntent.objects.bulk_create([PaymentIntent(owner=owner, sandbox_quote=loan.quote, sandbox_loan=loan,
            sandbox_context={"meter_id": meter.pk},
            purpose="LOAN_REPAYMENT", provider=provider, provider_reference=uuid.uuid4(), client_request_id=uuid.uuid4(),
            amount=1, currency=currency, status="SETTLED",
            demo_eligible_at=timezone.now() + timedelta(minutes=5) if provider == "LOCAL_DEMO" else None) for loan in loans])
        if provider == "LOCAL_DEMO":
            # Synthetic historical receipts still obey the five-second invariant.
            past = timezone.now() - timedelta(days=1)
            PaymentIntent.objects.filter(pk__in=[row.pk for row in payments]).update(initiated_at=past,
                demo_eligible_at=past + timedelta(seconds=5), settled_at=past + timedelta(seconds=6))
        SandboxSettlement.objects.bulk_create([SandboxSettlement(intent=payment, environment=environment,
            currency=currency, received=1, applied=1) for payment in payments])

    def test_summary_is_not_limited_to_the_history_page(self):
        self.historical_rows(103)
        self.assertEqual(len(self.client.get("/api/v1/sandbox/loans/", **self.headers).data["loans"]), 100)
        value = self.summary(environment="UGX_DEMO").data
        self.assertEqual(value["loan_count"], 103)
        self.assertEqual(Decimal(value["principal"]), 103)
        self.assertEqual(Decimal(value["applied_repayments"]), 103)
        self.assertEqual(Decimal(value["outstanding"]), 0)

    def test_owner_meter_and_currency_are_separate(self):
        self.historical_rows(2)
        self.historical_rows(3, environment="MTN_SANDBOX", currency="EUR")
        self.historical_rows(4, owner=self.other)
        self.assertEqual(self.summary(environment="UGX_DEMO", owner_id=self.other.pk).data["loan_count"], 2)
        self.assertEqual(self.summary(environment="MTN_SANDBOX").data["loan_count"], 3)
        other_meter = enroll_sandbox_meter(self.other, "00000000999")[0]
        self.assertEqual(self.summary(meter_id=other_meter.pk).status_code, 404)
        self.assertEqual(self.summary(meter_id=self.meter.pk).data["scope"], "METER")
        self.assertEqual(self.summary(environment="CORE").status_code, 400)
        self.client.force_authenticate(None)
        self.assertEqual(self.summary().status_code, 401)

    def test_successful_empty_summary_is_a_real_zero(self):
        value = self.summary().data
        self.assertEqual(value["active_loan_count"], 0)
        self.assertEqual(Decimal(value["outstanding"]), 0)
        self.assertEqual(value["owner_id"], self.owner.pk)
