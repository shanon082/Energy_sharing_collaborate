"""Real HTTPS MTN sandbox adapter. No fake success or currency conversion."""
import re
import uuid
import requests
from django.conf import settings
from django.views.decorators.debug import sensitive_variables

from backend.sandbox_config import BASE_URL
from backend.demo_config import provider_mode, require_mtn_sandbox
from transactions.payment_settlement import PaymentSettlementError


def configured():
    cfg = getattr(settings, "MTN_SANDBOX_CONFIG", {})
    return bool(provider_mode() == "MTN_SANDBOX" and getattr(settings, "CONSUMER_SANDBOX_ENABLED", False) is True
        and cfg.get("BASE_URL") == BASE_URL and cfg.get("ENVIRONMENT") == "sandbox" and cfg.get("CURRENCY") == "EUR"
        and all(cfg.get(key) for key in ("SUBSCRIPTION_KEY", "API_USER_ID", "API_KEY")))


def test_msisdn(value):
    value = str(value or "").strip()
    if not re.fullmatch(r"[0-9]{10,15}", value):
        raise PaymentSettlementError("Use an MTN sandbox test MSISDN: 10–15 ASCII digits, no plus sign or spaces.")
    return value


class MTNSandbox:
    def __init__(self):
        require_mtn_sandbox()
        if not configured():
            raise PaymentSettlementError("MTN sandbox credentials are missing or its isolated EUR configuration is invalid.")
        self.cfg = settings.MTN_SANDBOX_CONFIG
        uuid.UUID(self.cfg["API_USER_ID"])

    @sensitive_variables()
    def token(self):
        require_mtn_sandbox()
        try:
            response = requests.post(BASE_URL + "/collection/token/", auth=(self.cfg["API_USER_ID"], self.cfg["API_KEY"]),
                headers={"Ocp-Apim-Subscription-Key": self.cfg["SUBSCRIPTION_KEY"], "Content-Type": "application/json"}, timeout=(3, 7), allow_redirects=False)
            data = response.json() if response.status_code == 200 else {}
            if not isinstance(data, dict):
                raise PaymentSettlementError("MTN sandbox authentication unavailable.")
            token = data.get("access_token")
            if not isinstance(token, str) or not token:
                raise PaymentSettlementError("MTN sandbox authentication unavailable.")
            return token
        except (requests.RequestException, ValueError):
            raise PaymentSettlementError("MTN sandbox authentication unavailable.") from None

    @sensitive_variables()
    def headers(self):
        return {"Authorization": "Bearer " + self.token(), "X-Target-Environment": "sandbox",
                "Ocp-Apim-Subscription-Key": self.cfg["SUBSCRIPTION_KEY"], "Content-Type": "application/json"}

    @sensitive_variables()
    def initiate(self, intent):
        require_mtn_sandbox()
        # The caller persists/claims the reference before any network operation.
        try:
            headers = {**self.headers(), "X-Reference-Id": str(intent.provider_reference)}
            response = requests.post(BASE_URL + "/collection/v1_0/requesttopay", headers=headers,
                json={"amount": str(intent.amount), "currency": "EUR", "externalId": intent.provider_external_id,
                      "payer": {"partyIdType": "MSISDN", "partyId": test_msisdn(intent.sandbox_context["msisdn"])},
                      "payerMessage": "SANDBOX NO REAL MONEY", "payeeNote": "gPawa test " + intent.purpose},
                timeout=(3, 7), allow_redirects=False)
            return "ACCEPTED" if response.status_code == 202 else "OUTCOME_UNKNOWN"
        except requests.RequestException:
            return "OUTCOME_UNKNOWN"

    @sensitive_variables()
    def status(self, intent):
        require_mtn_sandbox()
        try:
            response = requests.get(BASE_URL + "/collection/v1_0/requesttopay/" + str(intent.provider_reference),
                headers=self.headers(), timeout=(3, 7), allow_redirects=False)
            if response.status_code != 200:
                return {"status": "UNKNOWN"}
            data = response.json()
            if not isinstance(data, dict):
                return {"status": "UNKNOWN"}
            return {"provider": "MTN_SANDBOX", "reference_id": str(intent.provider_reference),
                "external_id": data.get("externalId"), "currency": data.get("currency"), "amount": data.get("amount"),
                "transaction_id": data.get("financialTransactionId"), "payer": (data.get("payer") or {}).get("partyId"),
                "status": {"SUCCESSFUL": "SUCCESS", "FAILED": "FAILED", "PENDING": "PENDING"}.get(data.get("status"), "UNKNOWN")}
        except (requests.RequestException, ValueError, AttributeError, TypeError):
            return {"status": "UNKNOWN"}
