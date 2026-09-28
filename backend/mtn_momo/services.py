import base64
import logging
import uuid

import requests
from django.conf import settings

from .config import MTN_MOMO_CONFIG, MTN_TEST_NUMBERS

logger = logging.getLogger(__name__)


class MTNMoMoService:
  def __init__(self):
    cfg = getattr(settings, "MTN_MOMO_CONFIG", MTN_MOMO_CONFIG)
    self.base_url = cfg["BASE_URL"]
    self.subscription_key = cfg.get("SUBSCRIPTION_KEY") or cfg.get("PRIMARY_KEY") or cfg.get("SECONDARY_KEY", "")
    self.api_user_id = cfg.get("API_USER_ID", "")
    self.api_key = cfg.get("API_KEY", "")
    self.callback_host = cfg.get("CALLBACK_HOST", "")
    self.environment = cfg.get("ENVIRONMENT", "sandbox")

  def _normalize_phone(self, phone_number):
    phone = str(phone_number or "").replace(" ", "").replace("-", "").replace("+", "")
    if phone.startswith("0") and len(phone) == 10:
      phone = f"256{phone[1:]}"
    return phone

  def _charge_amount_and_currency(self, ugx_amount):
    """Sandbox MoMo only accepts EUR; production uses UGX."""
    if self.environment == "sandbox":
      return "1", "EUR"
    return str(int(ugx_amount)), "UGX"

  def get_api_token(self):
    if not self.api_user_id or not self.api_key:
      logger.error("MTN API user id or API key not configured")
      return None

    url = f"{self.base_url}/collection/token/"
    credentials = f"{self.api_user_id}:{self.api_key}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    headers = {
      "Authorization": f"Basic {encoded_credentials}",
      "Ocp-Apim-Subscription-Key": self.subscription_key,
    }

    try:
      response = requests.post(url, headers=headers, timeout=15)
      if response.status_code == 200:
        token = response.json().get("access_token")
        if token:
          return token
      logger.error("Token request failed: %s - %s", response.status_code, response.text)
    except requests.RequestException as exc:
      logger.error("Token request error: %s", exc)
    return None

  def request_payment(self, amount, phone_number, reference_id, external_id, payer_message=None):
    """
    Initiate request-to-pay. `reference_id` is sent as X-Reference-Id (used for status polling).
    `external_id` is your own transaction identifier in the MoMo payload.
    """
    phone_number = self._normalize_phone(phone_number)
    if self.environment == "sandbox":
      if not phone_number.isdigit() or len(phone_number) < 10:
        return {"status": "FAILED", "message": "Invalid phone number for MoMo sandbox"}
    elif not phone_number.startswith("256") or len(phone_number) != 12:
      return {"status": "FAILED", "message": "Invalid Uganda phone number (use 256XXXXXXXXX)"}

    token = self.get_api_token()
    if not token:
      return {"status": "FAILED", "message": "Could not get MTN API token. Check MoMo credentials."}

    if not reference_id:
      reference_id = str(uuid.uuid4())

    momo_amount, currency = self._charge_amount_and_currency(amount)
    url = f"{self.base_url}/collection/v1_0/requesttopay"
    headers = {
      "Authorization": f"Bearer {token}",
      "X-Reference-Id": reference_id,
      "X-Target-Environment": self.environment,
      "Content-Type": "application/json",
      "Ocp-Apim-Subscription-Key": self.subscription_key,
    }
    payload = {
      "amount": momo_amount,
      "currency": currency,
      "externalId": str(external_id),
      "payer": {
        "partyIdType": "MSISDN",
        "partyId": phone_number,
      },
      "payerMessage": payer_message or f"Energy wallet top-up {external_id}",
      "payeeNote": "gPAWA electricity units purchase",
    }

    logger.info("MoMo requesttopay ref=%s external=%s payload=%s", reference_id, external_id, payload)

    try:
      response = requests.post(url, headers=headers, json=payload, timeout=20)
      if response.status_code == 202:
        sandbox_hint = ""
        if self.environment == "sandbox":
          sandbox_hint = (
            " Sandbox: approve the payment in the MTN Developer portal simulator "
            "or enter the PIN on the sandbox test handset."
          )
        return {
          "status": "PENDING",
          "message": "Payment request sent to your phone.",
          "reference_id": reference_id,
          "external_id": str(external_id),
          "user_prompt": (
            "Check your phone now and enter your Mobile Money PIN to approve the payment."
            + sandbox_hint
          ),
        }
      logger.error("Payment request failed: %s - %s", response.status_code, response.text)
      return {
        "status": "FAILED",
        "message": f"Payment request failed ({response.status_code}): {response.text}",
      }
    except requests.RequestException as exc:
      logger.error("Payment request error: %s", exc)
      return {"status": "FAILED", "message": str(exc)}

  def get_payment_status(self, reference_id):
    """Poll MoMo using the X-Reference-Id from requesttopay."""
    token = self.get_api_token()
    if not token:
      # Return UNKNOWN rather than FAILED — a token error doesn't mean the
      # payment itself failed; the caller should keep polling or retry later.
      return {"status": "UNKNOWN", "message": "Could not get API token"}

    url = f"{self.base_url}/collection/v1_0/requesttopay/{reference_id}"
    headers = {
      "Authorization": f"Bearer {token}",
      "X-Target-Environment": self.environment,
      "Ocp-Apim-Subscription-Key": self.subscription_key,
    }

    try:
      response = requests.get(url, headers=headers, timeout=15)
      if response.status_code == 200:
        data = response.json()
        raw_status = data.get("status", "FAILED")
        status_map = {
          "SUCCESSFUL": "SUCCESS",
          "PENDING": "PENDING",
          "FAILED": "FAILED",
        }
        return {
          "status": status_map.get(raw_status, "FAILED"),
          "transaction_id": data.get("financialTransactionId"),
          "amount": data.get("amount"),
          "currency": data.get("currency"),
          "payer": (data.get("payer") or {}).get("partyId"),
          "message": f"Payment {raw_status.lower()}",
        }
      logger.error("Status check failed: %s - %s", response.status_code, response.text)
      return {
        "status": "FAILED",
        "message": f"Status check failed ({response.status_code}): {response.text}",
      }
    except requests.RequestException as exc:
      logger.error("Status check error: %s", exc)
      return {"status": "FAILED", "message": str(exc)}
