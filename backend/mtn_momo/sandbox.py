"""Real HTTPS MTN sandbox adapter. No fake success or currency conversion."""
import re
import uuid
from decimal import Decimal
import requests
from django.conf import settings
from django.views.decorators.debug import sensitive_variables

from backend.sandbox_config import BASE_URL
from backend.demo_config import provider_mode, require_mtn_sandbox
from transactions.payment_settlement import PaymentSettlementError
from mtn_momo.diagnostics import diagnostic, provider_code, record


class SandboxProviderError(PaymentSettlementError):
    def __init__(self, code):
        self.code = code
        super().__init__('MTN sandbox confirmation unavailable; status remains unconfirmed.')


def transaction_identity(value):
    # MTN publishes both a string schema and an integer-valued success example.
    # Exact integers are losslessly representable; floats/bools/containers are not IDs.
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        value = str(value)
    return value if isinstance(value, str) and value.strip() and len(value) <= 100 else None


def configured(*, recovery=False):
    cfg = getattr(settings, "MTN_SANDBOX_CONFIG", {})
    try:
        uuid.UUID(str(cfg.get("API_USER_ID", "")))
    except (ValueError, TypeError, AttributeError):
        return False
    return bool((recovery or provider_mode() == "MTN_SANDBOX") and getattr(settings, "CONSUMER_SANDBOX_ENABLED", False) is True
        and cfg.get("BASE_URL") == BASE_URL and cfg.get("ENVIRONMENT") == "sandbox" and cfg.get("CURRENCY") == "EUR"
        and all(cfg.get(key) for key in ("SUBSCRIPTION_KEY", "API_USER_ID", "API_KEY")))


def test_msisdn(value):
    value = str(value or "").strip()
    if not re.fullmatch(r"[0-9]{10,15}", value):
        raise PaymentSettlementError("Use an MTN sandbox test MSISDN: 10–15 ASCII digits, no plus sign or spaces.")
    return value


class MTNSandbox:
    def __init__(self, *, recovery=False):
        self.recovery = recovery
        require_mtn_sandbox(recovery=recovery)
        if not configured(recovery=recovery):
            raise PaymentSettlementError("Sandbox payments unavailable")
        self.cfg = settings.MTN_SANDBOX_CONFIG
        uuid.UUID(self.cfg["API_USER_ID"])
        self.last_diagnostic = diagnostic('CONFIGURATION')

    def observe(self, stage, *, http_status=None, status='UNKNOWN', code='NONE'):
        self.last_diagnostic = diagnostic(stage, http_status=http_status, status=status, code=code)

    @sensitive_variables()
    def token(self):
        require_mtn_sandbox(recovery=self.recovery)
        try:
            response = requests.post(BASE_URL + "/collection/token/", auth=(self.cfg["API_USER_ID"], self.cfg["API_KEY"]),
                headers={"Ocp-Apim-Subscription-Key": self.cfg["SUBSCRIPTION_KEY"], "Content-Type": "application/json"}, timeout=(3, 7), allow_redirects=False)
            self.observe('AUTHENTICATION', http_status=response.status_code, code='MTN_AUTH_HTTP')
            if response.status_code != 200:
                raise SandboxProviderError('MTN_AUTH_HTTP')
            try:
                data = response.json(parse_float=Decimal)
            except ValueError:
                self.observe('AUTHENTICATION', http_status=200, code='MTN_AUTH_JSON')
                raise SandboxProviderError('MTN_AUTH_JSON') from None
            if not isinstance(data, dict):
                self.observe('AUTHENTICATION', http_status=200, code='MTN_AUTH_SCHEMA')
                raise SandboxProviderError('MTN_AUTH_SCHEMA')
            token = data.get("access_token")
            if not isinstance(token, str) or not token:
                self.observe('AUTHENTICATION', http_status=200, code='MTN_AUTH_SCHEMA')
                raise SandboxProviderError('MTN_AUTH_SCHEMA')
            return token
        except requests.RequestException:
            self.observe('AUTHENTICATION', code='MTN_AUTH_TRANSPORT')
            raise SandboxProviderError('MTN_AUTH_TRANSPORT') from None
        except ValueError:
            self.observe('AUTHENTICATION', http_status=200, code='MTN_AUTH_JSON')
            raise SandboxProviderError('MTN_AUTH_JSON') from None

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
                      "payerMessage": "SANDBOX NO REAL MONEY", "payeeNote": "EnergyFlex test " + intent.purpose},
                timeout=(3, 7), allow_redirects=False)
            self.observe('SUBMISSION', http_status=response.status_code,
                         status='PENDING' if response.status_code == 202 else 'UNKNOWN',
                         code='NONE' if response.status_code == 202 else 'MTN_SUBMISSION_HTTP')
            return "ACCEPTED" if response.status_code == 202 else "OUTCOME_UNKNOWN"
        except requests.RequestException:
            self.observe('SUBMISSION', code='MTN_SUBMISSION_TRANSPORT')
            return "OUTCOME_UNKNOWN"
        finally:
            record(intent, self.last_diagnostic)

    @sensitive_variables()
    def status(self, intent):
        require_mtn_sandbox(recovery=self.recovery)
        try:
            response = requests.get(BASE_URL + "/collection/v1_0/requesttopay/" + str(intent.provider_reference),
                headers=self.headers(), timeout=(3, 7), allow_redirects=False)
            if response.status_code != 200:
                self.observe('STATUS_LOOKUP', http_status=response.status_code, code='MTN_STATUS_HTTP')
                return {"status": "UNKNOWN"}
            self.observe('STATUS_LOOKUP', http_status=200, code='MTN_STATUS_JSON')
            try:
                data = response.json(parse_float=Decimal)
            except ValueError:
                self.observe('STATUS_LOOKUP', http_status=200, code='MTN_STATUS_JSON')
                return {'status': 'UNKNOWN'}
            if not isinstance(data, dict):
                self.observe('STATUS_LOOKUP', http_status=200, code='MTN_STATUS_SCHEMA')
                return {"status": "UNKNOWN"}
            status = data.get('status')
            if not isinstance(status, str) or status not in {'SUCCESSFUL', 'FAILED', 'PENDING'}:
                self.observe('STATUS_LOOKUP', http_status=200, code='MTN_STATUS_SCHEMA')
                return {'status': 'UNKNOWN'}
            self.observe('STATUS_LOOKUP', http_status=200, status=status,
                         code=provider_code(data) if status == 'FAILED' else 'NONE')
            return {"provider": "MTN_SANDBOX", "reference_id": str(intent.provider_reference),
                "external_id": data.get("externalId"), "currency": data.get("currency"), "amount": data.get("amount"),
                "transaction_id": transaction_identity(data.get("financialTransactionId")), "payer": transaction_identity((data.get("payer") or {}).get("partyId")),
                "status": {"SUCCESSFUL": "SUCCESS", "FAILED": "FAILED", "PENDING": "PENDING"}.get(data.get("status"), "UNKNOWN")}
        except requests.RequestException:
            self.observe('STATUS_LOOKUP', code='MTN_STATUS_TRANSPORT')
            return {"status": "UNKNOWN"}
        except (ValueError, AttributeError, TypeError):
            self.observe('STATUS_LOOKUP', http_status=200, code='MTN_STATUS_SCHEMA')
            return {"status": "UNKNOWN"}
        finally:
            record(intent, self.last_diagnostic)
