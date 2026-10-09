"""Stage 2 owner-bound profiles and meters using synthetic PostgreSQL records."""
from decimal import Decimal
from unittest.mock import patch
import uuid

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User, UserAccountDetails, Profile, Wallet as AccountWallet
from meter.models import Meter, EnergyAllocation, MeterDelivery, SimulatedMeter
from transactions.models import PaymentIntent, Transaction
from loan.models import CreditScoreHistory
from loan.scoring import LOAN_PROFILE_FIELDS


@override_settings(DEBUG=True, SIMULATED_METER_ENABLED=True)
class MobileProfileMeterTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="profile-owner@example.invalid", password="Test-only-123")
        self.other = User.objects.create_user(email="profile-other@example.invalid", password="Test-only-123")
        for user in (self.owner, self.other):
            user.profile.email_verified = True
            user.profile.save(update_fields=["email_verified"])
        self.meter = Meter.objects.create(user=self.owner, meter_no="PROFILE-OWN", architecture=Meter.ARCH_AMI,
                                           units=Decimal("999.00"), pending_units=Decimal("33.00"),
                                           static_ip="192.0.2.7", iot_device_token="synthetic-device-secret")
        self.second = Meter.objects.create(user=self.owner, meter_no="PROFILE-SECOND", status=Meter.STATUS_SUSPENDED)
        self.foreign = Meter.objects.create(user=self.other, meter_no="PROFILE-OTHER")
        self.client = self.jwt()

    def jwt(self, user=None):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user or self.owner).access_token}")
        return client

    def dashboard(self, meter=None, client=None):
        return (client or self.client).get(f"/api/v1/meter/mobile-meters/{(meter or self.meter).pk}/")

    def test_meter_list_has_explicit_identity_without_legacy_balances_or_device_configuration(self):
        deleted = Meter.objects.create(user=self.owner, meter_no="PROFILE-DELETED", is_deleted=True)
        result = self.client.get("/api/v1/meter/mobile-meters/?user_id=999")
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.data["data"]["has_meter"])
        self.assertEqual([row["id"] for row in result.data["data"]["meters"]], [self.meter.pk, self.second.pk])
        self.assertNotIn(deleted.pk, [row["id"] for row in result.data["data"]["meters"]])
        for row in result.data["data"]["meters"]:
            self.assertEqual(set(row), {"id", "meter_number", "label", "architecture", "status"})
        self.assertEqual(self.client.post("/api/v1/meter/mobile-meters/", {}).status_code, 405)

    def test_empty_account_has_no_automatic_meter_selection(self):
        Meter.objects.filter(user=self.other).update(user=None)
        response = self.jwt(self.other).get("/api/v1/meter/mobile-meters/")
        self.assertEqual(response.data["data"], {"has_meter": False, "meters": []})

    def test_dashboard_counts_only_owner_source_allocations_and_reads_have_no_side_effects(self):
        reference = uuid.uuid4()
        wallet = AccountWallet.objects.create(user=self.owner)
        purchase = Transaction.objects.create(wallet=wallet, amount=Decimal("1000"), phone_number="+256700000000",
                                               status="COMPLETED", transaction_reference=str(reference))
        intent = PaymentIntent.objects.create(owner=self.owner, purpose=PaymentIntent.PURCHASE, amount=Decimal("1000"),
            currency="UGX", provider="MTN_PRODUCTION", provider_reference=reference,
            provider_external_id=f"gpawa-purchase-{reference}", purchase=purchase, meter=self.meter,
            status=PaymentIntent.SETTLED, provider_transaction_id="synthetic-verified-purchase")
        allocation = EnergyAllocation.objects.create(owner=self.owner, meter=self.meter,
                                                       amount_kwh=Decimal("2.01"), purchase_intent=intent)
        MeterDelivery.objects.create(allocation=allocation, amount_kwh=Decimal("0.31"), status=MeterDelivery.OUTCOME_UNKNOWN)
        MeterDelivery.objects.create(allocation=allocation, amount_kwh=Decimal("0.20"), status=MeterDelivery.APPLIED)
        contact = timezone.now()
        SimulatedMeter.objects.create(meter=self.meter, credential_hash="synthetic-hash", last_contact_at=contact)
        models = (EnergyAllocation, MeterDelivery, PaymentIntent, Transaction, UserAccountDetails)
        before = [model.objects.count() for model in models]
        with patch("requests.sessions.Session.request", side_effect=AssertionError("No network in reads")):
            result = self.dashboard()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["meter"]["id"], self.meter.pk)
        self.assertEqual(result.data["available_kwh"], "1.50")
        self.assertEqual(result.data["pending_kwh"], "0.31")
        self.assertEqual(result.data["confirmed_kwh"], "0.20")
        self.assertEqual(result.data["quantum_kwh"], "0.01")
        self.assertEqual(result.data["contact_source"], "SIMULATOR")
        self.assertEqual(result.data["last_meter_contact"], contact.isoformat())
        self.assertEqual(before, [model.objects.count() for model in models])
        with override_settings(SIMULATED_METER_ENABLED=False):
            unavailable = self.dashboard()
        self.assertEqual(unavailable.data["delivery_environment"], "UNAVAILABLE")
        self.assertEqual(unavailable.data["contact_source"], "SIMULATOR")
        # Changing assignment cannot hand another owner this historical entitlement.
        Meter.objects.filter(pk=self.meter.pk).update(user=self.other)
        self.assertEqual(self.dashboard().status_code, 404)
        received = self.dashboard(client=self.jwt(self.other))
        self.assertEqual(received.data["available_kwh"], "0.00")
        self.assertEqual(received.data["pending_kwh"], "0.00")
        allocation.refresh_from_db()
        self.assertEqual(allocation.owner_id, self.owner.pk)

    def test_dashboard_is_bound_to_current_assignment_and_deleted_meters_are_hidden(self):
        self.assertEqual(self.dashboard(self.foreign).status_code, 404)
        Meter.objects.filter(pk=self.meter.pk).update(user=self.other)
        self.assertEqual(self.dashboard().status_code, 404)
        Meter.objects.filter(pk=self.meter.pk).update(user=self.owner, is_deleted=True)
        self.assertEqual(self.dashboard().status_code, 404)
        replacement = Meter.objects.create(user=self.owner, meter_no="PROFILE-REPLACEMENT")
        self.assertNotEqual(replacement.pk, self.meter.pk)
        self.assertEqual(self.dashboard(replacement).status_code, 200)

    def test_account_details_are_owner_bound_choices_and_privileged_fields_cannot_be_edited(self):
        response = self.client.get(f"/api/v1/auth/mobile-account-details/?user_id={self.other.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["values"]["account_number"], self.owner.account_details.account_number)
        self.assertTrue(response.data["details_available"])
        original = self.owner.account_details.account_number
        for data in ({"user": self.other.pk}, {"account_number": "forged"}, {"email_verified": True},
                     {"payment_method": "invented"}, {}, [{"address": "invalid body"}]):
            self.assertEqual(self.client.patch("/api/v1/auth/mobile-account-details/", data, format="json").status_code, 400)
        updated = self.client.patch("/api/v1/auth/mobile-account-details/", {
            "address": "Synthetic test address", "energy_preference": "HYDRO", "payment_method": "MOBILE_MONEY",
        }, format="json")
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["values"]["address"], "Synthetic test address")
        self.assertEqual(updated.data["values"]["account_number"], original)
        self.other.account_details.refresh_from_db()
        self.assertIsNone(self.other.account_details.address)
        cleared = self.client.patch("/api/v1/auth/mobile-account-details/", {"energy_preference": None}, format="json")
        self.assertIsNone(cleared.data["values"]["energy_preference"])

    def test_missing_account_details_are_reported_without_repair_on_read_or_write(self):
        UserAccountDetails.objects.filter(user=self.owner).delete()
        result = self.client.get("/api/v1/auth/mobile-account-details/")
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.data["details_available"])
        self.assertIsNone(result.data["values"])
        write = self.client.patch("/api/v1/auth/mobile-account-details/", {"address": "Synthetic"}, format="json")
        self.assertEqual(write.status_code, 409)
        self.assertEqual(write.data["code"], "ACCOUNT_DETAILS_MISSING")
        self.assertFalse(UserAccountDetails.objects.filter(user=self.owner).exists())

    def test_assessment_edit_preserves_other_owner_and_historical_scores(self):
        values = {name: User._meta.get_field(name).choices[0][0] for name in LOAN_PROFILE_FIELDS}
        history = CreditScoreHistory.objects.count()
        result = self.client.patch("/api/v1/auth/mobile-profile/", values, format="json")
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.data["complete_for_scoring"])
        self.other.refresh_from_db()
        self.assertFalse(all(getattr(self.other, name) for name in LOAN_PROFILE_FIELDS))
        self.assertEqual(CreditScoreHistory.objects.count(), history)
        self.assertEqual(self.client.patch("/api/v1/auth/mobile-profile/", {"is_staff": True}, format="json").status_code, 400)
        self.assertEqual(self.client.patch("/api/v1/auth/mobile-profile/", [{"monthly_income": "invalid body"}],
                                          format="json").status_code, 400)

    def test_session_auth_enforces_the_same_consumer_state_boundary_as_jwt(self):
        client = APIClient()
        client.force_login(self.owner)
        paths = ["/api/v1/auth/mobile-profile/", "/api/v1/auth/mobile-account-details/",
                 "/api/v1/meter/mobile-meters/", f"/api/v1/meter/mobile-meters/{self.meter.pk}/"]
        for path in paths:
            self.assertEqual(client.get(path).status_code, 200)
        self.owner.must_change_password = True
        self.owner.save(update_fields=["must_change_password"])
        for path in paths:
            self.assertEqual(client.get(path).status_code, 403)
        self.owner.must_change_password = False
        self.owner.save(update_fields=["must_change_password"])
        self.owner.profile.email_verified = False
        self.owner.profile.save(update_fields=["email_verified"])
        for path in paths:
            self.assertEqual(client.get(path).status_code, 403)
        Profile.objects.filter(user=self.owner).delete()
        self.assertEqual(client.get(paths[0]).status_code, 403)

    def test_staff_and_anonymous_requests_cannot_access_mobile_records(self):
        paths = ["/api/v1/auth/mobile-account-details/", "/api/v1/meter/mobile-meters/"]
        for path in paths:
            self.assertEqual(APIClient().get(path).status_code, 401)
        self.owner.is_staff = True
        self.owner.save(update_fields=["is_staff"])
        for path in paths:
            self.assertEqual(self.jwt().get(path).status_code, 403)
