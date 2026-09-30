"""Isolated checks for deferred entry points; no database or provider is used."""

from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from backend.feature_config import FEATURE_ENV_VARS, load_feature_flags, parse_feature_bool
from backend.features import FeatureDisabled


OFF = {feature: False for feature in FEATURE_ENV_VARS}


def call_view(method, path, *, user=None, data=None):
    """Exercise the real URL/view without ATOMIC_REQUESTS or a live database."""
    factory = APIRequestFactory()
    request = getattr(factory, method)(path, data=data or {}, format="json")
    if user is not None:
        force_authenticate(request, user=user)
    match = resolve(urlsplit(path).path)
    return match.func(request, *match.args, **match.kwargs)


class FeatureConfigurationTests(SimpleTestCase):
    def test_explicit_boolean_parsing_and_disabled_defaults(self):
        self.assertEqual(load_feature_flags({}), OFF)
        for value in ("true", "TRUE", "1", "yes", "on", True):
            self.assertTrue(parse_feature_bool(value))
        for value in ("false", "FALSE", "0", "no", "off", "", False):
            self.assertFalse(parse_feature_bool(value))
        with self.assertRaises(ImproperlyConfigured):
            parse_feature_bool("sometimes")

    @override_settings(FEATURE_FLAGS=OFF)
    def test_request_parameters_cannot_enable_features(self):
        response = call_view("get", "/api/v1/features/?peer_sharing=true&ussd=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["features"], OFF)


@override_settings(FEATURE_FLAGS=OFF)
class DeferredRouteTests(SimpleTestCase):
    def setUp(self):
        self.user = User(id=101, email="test@example.invalid")

    def assert_disabled(self, method, path, feature, data=None):
        response = call_view(method, path, user=self.user, data=data)
        self.assertEqual(response.status_code, 403, (method, path, response.data))
        self.assertEqual(response.data["code"], "FEATURE_DISABLED")
        self.assertEqual(response.data["feature"], feature)

    def test_direct_and_legacy_routes_reject_before_side_effects(self):
        routes = (
            ("get", "/api/v1/share/receiver-preview/?meter_number=123", "peer_sharing"),
            ("post", "/api/v1/share/share-units/", "peer_sharing"),
            ("post", "/api/v1/meter/send-units/", "peer_sharing"),
            ("post", "/api/v1/meter/receive-units/", "peer_sharing"),
            ("post", "/api/v1/share/transfer-units/", "meter_transfers"),
            ("get", "/api/v1/loans/lookup-by-phone/?phone=123", "third_party_repayment"),
            ("post", "/api/v1/loans/pay-for-someone/", "third_party_repayment"),
            ("post", "/api/v1/wallet/deposit/", "wallet_deposits"),
            ("post", "/api/v1/wallet/withdraw/", "wallet_withdrawals"),
            ("post", "/api/v1/ussd/entry/", "ussd"),
            ("get", "/api/v1/ussd/phones/", "ussd"),
            ("get", "/api/v1/ussd/meters/", "ussd"),
        )
        with patch("share.views.VerificationCode.create_code") as otp, \
                patch("meter.api.views.requests.post") as device_post, \
                patch("loan.services.repay_loan") as repayment, \
                patch("wallet.views.Wallet.objects.get_or_create") as wallet_create:
            for method, path, feature in routes:
                with self.subTest(path=path):
                    self.assert_disabled(method, path, feature, {"verification_code": "123456"})
            otp.assert_not_called()
            device_post.assert_not_called()
            repayment.assert_not_called()
            wallet_create.assert_not_called()

    def test_confirmation_paths_cannot_complete_prior_pending_activity(self):
        for path, feature in (
            ("/api/v1/share/share-units/", "peer_sharing"),
            ("/api/v1/share/transfer-units/", "meter_transfers"),
        ):
            with self.subTest(path=path):
                self.assert_disabled("post", path, feature, {"verification_code": "123456"})

    def test_public_ussd_entry_is_disabled_without_authentication(self):
        response = call_view("post", "/api/v1/ussd/entry/", data={"text": "1"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "FEATURE_DISABLED")

    def test_flag_can_be_reenabled_by_server_configuration(self):
        with override_settings(FEATURE_FLAGS={**OFF, "peer_sharing": True}):
            response = call_view("get", "/api/v1/share/receiver-preview/", user=self.user)
        self.assertEqual(response.status_code, 400)
        self.assertNotEqual(response.data.get("code"), "FEATURE_DISABLED")

    def test_ussd_meter_lookup_needs_peer_sharing_as_well(self):
        with override_settings(FEATURE_FLAGS={**OFF, "ussd": True}):
            response = call_view("get", "/api/v1/ussd/meters/", user=self.user)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["feature"], "peer_sharing")

    def test_ussd_menu_hides_peer_sharing_when_only_ussd_is_enabled(self):
        from ussd.views import _main_menu_text
        with override_settings(FEATURE_FLAGS={**OFF, "ussd": True}):
            self.assertNotIn("Share Units", _main_menu_text())

    def test_own_meter_loading_and_self_repayment_remain_available(self):
        from meter.models import Meter
        with patch("meter.api.views.Meter.objects.get", side_effect=Meter.DoesNotExist):
            response = call_view("post", "/api/v1/meter/apply-wallet-units/", user=self.user, data={"meter_no": "missing"})
        self.assertEqual(response.status_code, 503)
        self.assertNotEqual(response.data.get("code"), "FEATURE_DISABLED")
        response = call_view("post", "/api/v1/loans/repay/7/", user=self.user, data={"amount": 1})
        self.assertEqual(response.status_code, 409)
        self.assertNotEqual(response.data.get("code"), "FEATURE_DISABLED")

    def test_history_requires_authentication_and_uses_authenticated_user(self):
        with patch("transactions.api.views.collect_unified_history", return_value=[]) as collect, \
                patch("transactions.api.views.filter_history", return_value=[]), \
                patch("transactions.api.views.summarize_history", return_value={}), \
                patch("transactions.api.views.paginate_history", return_value=([], 0)):
            response = call_view("get", "/api/v1/transactions/history/", user=self.user)
            self.assertEqual(response.status_code, 200)
            collect.assert_called_once_with(self.user)
        response = call_view("get", "/api/v1/transactions/history/")
        self.assertIn(response.status_code, (401, 403))


@override_settings(FEATURE_FLAGS=OFF, CRB_PROVIDER="missing.module.Provider")
class DeferredServiceTests(SimpleTestCase):
    def test_third_party_service_is_blocked_before_lookup(self):
        from loan.services import repay_loan
        with patch("loan.services._resolve_loan_for_repay") as lookup:
            with self.assertRaises(FeatureDisabled):
                repay_loan(SimpleNamespace(pk=1), 7, 100, paid_by_user=SimpleNamespace(pk=2))
            with self.assertRaises(FeatureDisabled):
                repay_loan(SimpleNamespace(pk=1), 7, 100, is_anonymous=True)
            lookup.assert_not_called()

    def test_self_repayment_service_reaches_loan_validation(self):
        from loan.services import LoanOperationError, repay_loan
        with patch("loan.services._resolve_loan_for_repay", return_value=SimpleNamespace(status="PENDING")) as lookup:
            with self.assertRaises(LoanOperationError):
                repay_loan(SimpleNamespace(pk=1), 7, 100, paid_by_user=SimpleNamespace(pk=1))
            lookup.assert_called_once()

    def test_external_crb_is_dormant_without_affecting_internal_scoring(self):
        from loan.crb import NoOpCreditBureauProvider, get_crb_provider
        self.assertIsInstance(get_crb_provider(), NoOpCreditBureauProvider)
        self.assertIsNone(get_crb_provider().fetch_report("test"))
