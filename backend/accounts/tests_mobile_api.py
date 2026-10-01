"""Mobile read endpoints and refresh revocation on isolated test data."""

from decimal import Decimal
import uuid

from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch

from accounts.models import User
from accounts.utils import b64encode_user
from utils.auth import token_generator, reset_password_token_generator
from loan.models import ElectricityTariff, LoanApplication, LoanRepayment
from loan.scoring import LOAN_PROFILE_FIELDS
from meter.models import Meter, MeterUsageDaily
from accounts.models import Wallet as AccountWallet
from transactions.models import PaymentIntent, Transaction


@override_settings(FEATURE_FLAGS={
    "peer_sharing": False, "meter_transfers": False, "third_party_repayment": False,
    "ussd": False, "wallet_deposits": False, "wallet_withdrawals": False,
    "external_crb": False,
})
class MobileApiTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="mobile-owner@example.invalid", password="test-only")
        self.other = User.objects.create_user(email="mobile-other@example.invalid", password="test-only")
        self.meter = Meter.objects.create(user=self.owner, meter_no="MOBILE-OWN", architecture=Meter.ARCH_AMI)
        self.other_meter = Meter.objects.create(user=self.other, meter_no="MOBILE-OTHER", architecture=Meter.ARCH_AMI)
        self.client = APIClient()
        self.client.force_authenticate(user=self.owner)

    def test_account_and_consumption_are_owned_and_read_only(self):
        MeterUsageDaily.objects.create(
            meter=self.meter, usage_date="2026-01-01", kwh_used=Decimal("1.2345"),
            source=MeterUsageDaily.SOURCE_SNAPSHOT,
        )
        account = self.client.get("/api/v1/auth/mobile-account/")
        self.assertEqual(account.status_code, 200)
        self.assertEqual(account.data["id"], self.owner.pk)
        self.assertNotIn("wallet", account.data)
        own = self.client.get("/api/v1/meter/mobile-consumption/?meter_no=MOBILE-OWN")
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own.data["daily_usage"][0]["kwh"], "1.2345")
        self.assertEqual(own.data["simulator_telemetry"], [])
        self.assertEqual(self.client.get("/api/v1/meter/mobile-consumption/?meter_no=MOBILE-OTHER").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/meter/mobile-consumption/").status_code, 400)

    def test_loan_history_is_owner_bound_and_does_not_reconcile_status(self):
        loan = LoanApplication.objects.create(
            user=self.owner, amount_requested=Decimal("100.00"),
            amount_approved=Decimal("100.00"), interest_rate=Decimal("0.00"),
            tenure_months=1, purpose="Electricity", status="DISBURSED", intended_meter=self.meter,
        )
        LoanRepayment.objects.create(
            loan=loan, amount_paid=Decimal("20.00"), amount_applied_ugx=Decimal("20.00"),
            payment_status="SUCCESS", payment_method="MOBILE_MONEY", units_paid=0,
            payment_reference="MOBILE-TEST-REPAYMENT",
        )
        LoanApplication.objects.create(
            user=self.other, amount_requested=Decimal("99.00"),
            amount_approved=Decimal("99.00"), interest_rate=Decimal("0.00"),
            tenure_months=1, purpose="Electricity", status="DISBURSED", intended_meter=self.other_meter,
        )
        response = self.client.get("/api/v1/loans/mobile-overview/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["loans"]), 1)
        self.assertEqual(response.data["loans"][0]["outstanding_ugx"], "80.00")
        self.assertEqual(response.data["loans"][0]["repayments"][0]["received_ugx"], "20.00")
        loan.refresh_from_db()
        self.assertEqual(loan.status, "DISBURSED")

    def test_logout_blacklists_only_owned_refresh_token_and_web_refresh_still_works(self):
        owner_refresh = RefreshToken.for_user(self.owner)
        other_refresh = RefreshToken.for_user(self.other)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {owner_refresh.access_token}")
        mismatch = client.post("/api/v1/auth/mobile-logout/", {"refresh": str(other_refresh)})
        self.assertEqual(mismatch.status_code, 403)
        self.assertEqual(client.post("/api/v1/auth/mobile-logout/", {"refresh": str(owner_refresh)}).status_code, 204)
        self.assertEqual(client.post("/api/v1/auth/refresh/token/", {"refresh": str(owner_refresh)}).status_code, 401)
        self.assertEqual(client.post("/api/v1/auth/refresh/token/", {"refresh": str(other_refresh)}).status_code, 200)

    def test_existing_login_contract_opens_mobile_account_with_jwt(self):
        profile = self.owner.profile
        profile.email_verified = True
        profile.save(update_fields=["email_verified"])
        client = APIClient()
        login = client.post("/api/v1/auth/login/", {
            "email": self.owner.email, "password": "test-only", "remember_me": False,
        }, HTTP_ORIGIN="http://localhost")
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login["Access-Control-Allow-Origin"], "http://localhost")
        self.assertEqual(login["Content-Type"], "application/json")
        self.assertEqual(login.data["user"]["user_role"], User.CLIENT)
        self.assertEqual(login.data["user"]["id"], self.owner.pk)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        self.assertEqual(client.get("/api/v1/auth/mobile-account/").data["id"], self.owner.pk)

    def test_anonymous_and_staff_cannot_read_consumer_views(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get("/api/v1/auth/mobile-account/").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/loans/mobile-overview/").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/meter/mobile-consumption/?meter_no=MOBILE-OWN").status_code, 401)
        self.owner.user_role = User.ADMIN
        self.owner.save(update_fields=["user_role"])
        self.client.force_authenticate(user=self.owner)
        self.assertEqual(self.client.get("/api/v1/auth/mobile-account/").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/loans/mobile-overview/").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/meter/mobile-consumption/?meter_no=MOBILE-OWN").status_code, 403)
        self.assertEqual(self.client.post("/api/v1/meter/mobile-consumption/?meter_no=MOBILE-OWN").status_code, 405)

    def test_profile_choices_and_role_fields_cannot_be_changed(self):
        response = self.client.get("/api/v1/auth/mobile-profile/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("monthly_income", response.data["choices"])
        denied = self.client.patch("/api/v1/auth/mobile-profile/", {
            "user_role": User.ADMIN, "monthly_income": "<100,000 UGX",
        })
        self.assertEqual(denied.status_code, 400)
        invalid = self.client.patch("/api/v1/auth/mobile-profile/", {"monthly_income": "fabricated"})
        self.assertEqual(invalid.status_code, 400)
        accepted = self.client.patch("/api/v1/auth/mobile-profile/", {"monthly_income": "<100,000 UGX"})
        self.assertEqual(accepted.status_code, 200)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.user_role, User.CLIENT)
        self.assertEqual(self.owner.monthly_income, "<100,000 UGX")
        self.assertIsNone(self.other.monthly_income)

    def test_mobile_password_requires_current_and_changes_only_owner(self):
        bad = self.client.post("/api/v1/auth/mobile-password/", {
            "current_password": "wrong", "new_password": "New-test-only-123", "confirm_password": "New-test-only-123",
        })
        self.assertEqual(bad.status_code, 400)
        good = self.client.post("/api/v1/auth/mobile-password/", {
            "current_password": "test-only", "new_password": "New-test-only-123", "confirm_password": "New-test-only-123",
        })
        self.assertEqual(good.status_code, 200)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.check_password("New-test-only-123"))
        self.assertTrue(self.other.check_password("test-only"))

    def test_registration_does_not_accept_role_and_tokens_are_one_use(self):
        public = APIClient()
        with patch("accounts.signals.dispatch_task"):
            registration = public.post("/api/v1/auth/register/", {
                "first_name": "Mobile", "last_name": "Test", "email": "new-mobile@example.invalid",
                "phone_number": "+256700123456", "gender": "FEMALE",
                "password": "New-test-only-123", "confirm_password": "New-test-only-123",
                "user_role": User.ADMIN, "is_staff": True,
            })
        self.assertEqual(registration.status_code, 201)
        user = User.objects.get(email="new-mobile@example.invalid")
        self.assertEqual(user.user_role, User.CLIENT)
        self.assertFalse(user.is_staff)
        uid = b64encode_user(str(user.pk))
        token = token_generator.make_token(user)
        url = f"/api/v1/auth/verify-email/?uid={uid}&token={token}"
        with patch("accounts.api.views.handle_post_email_verification"):
            self.assertEqual(public.get(url).status_code, 200)
        self.assertNotEqual(public.get(url).status_code, 200)
        reset_token = reset_password_token_generator.make_token(user)
        reset_url = f"/api/v1/auth/reset-password/?uid={uid}&token={reset_token}"
        self.assertEqual(public.get(reset_url).status_code, 200)
        self.assertEqual(public.patch(reset_url, {
            "password": "Another-test-only-123", "confirm_password": "Another-test-only-123",
        }).status_code, 200)
        self.assertNotEqual(public.patch(reset_url, {
            "password": "Third-test-only-123", "confirm_password": "Third-test-only-123",
        }).status_code, 200)

    def test_eligibility_hides_default_score_and_quote_needs_tariff(self):
        absent = self.client.get("/api/v1/loans/mobile-eligibility/")
        self.assertEqual(absent.status_code, 200)
        self.assertIsNone(absent.data["score"])
        self.assertFalse(absent.data["can_apply"])
        for field in LOAN_PROFILE_FIELDS:
            setattr(self.owner, field, User._meta.get_field(field).choices[0][0])
        self.owner.monthly_income = ">1,000,000 UGX"
        self.owner.income_stability = "Fixed and stable"
        self.owner.consumption_level = "High (>200 kWh)"
        self.owner.purchase_frequency = "Weekly"
        self.owner.save(update_fields=[*LOAN_PROFILE_FIELDS, "modify_date"])
        ready = self.client.get("/api/v1/loans/mobile-eligibility/")
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.data["source"], "PROFILE")
        self.assertIsInstance(ready.data["score"], int)
        self.assertTrue(ready.data["can_apply"])
        quote = self.client.post("/api/v1/loans/mobile-quote/", {
            "amount_requested": "5000", "tenure_months": 6, "meter_no": self.meter.meter_no,
        })
        self.assertEqual(quote.status_code, 200)
        self.assertFalse(quote.data["binding"])
        self.assertFalse(quote.data["application_available"])
        ElectricityTariff.objects.update(is_active=False)
        quote = self.client.post("/api/v1/loans/mobile-quote/", {
            "amount_requested": "5000", "tenure_months": 6, "meter_no": self.meter.meter_no,
        })
        self.assertEqual(quote.status_code, 409)
        self.assertEqual(quote.data["code"], "TARIFF_POLICY_REQUIRED")
        self.assertEqual(LoanApplication.objects.count(), 0)

    def test_payment_receipts_are_exact_owner_bound_and_do_not_settle(self):
        owner_wallet = AccountWallet.objects.create(user=self.owner)
        other_wallet = AccountWallet.objects.create(user=self.other)
        for user, wallet, meter, amount in (
            (self.owner, owner_wallet, self.meter, "123.00"),
            (self.other, other_wallet, self.other_meter, "456.00"),
        ):
            reference = uuid.uuid4()
            purchase = Transaction.objects.create(
                wallet=wallet, amount=Decimal(amount), phone_number="+256700000001",
                status="PENDING", transaction_reference=str(reference),
            )
            PaymentIntent.objects.create(
                owner=user, purpose=PaymentIntent.PURCHASE, amount=Decimal(amount),
                currency="UGX", provider="MTN_PRODUCTION", provider_reference=reference,
                provider_external_id=f"gpawa-purchase-{reference}", purchase=purchase,
                meter=meter, status=PaymentIntent.PENDING,
            )
        result = self.client.get("/api/v1/transactions/mobile-receipts/")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.data["receipts"]), 1)
        self.assertEqual(result.data["receipts"][0]["amount_ugx"], "123.00")
        self.assertEqual(result.data["receipts"][0]["status"], "PENDING")
