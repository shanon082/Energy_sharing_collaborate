"""Verified MTN Collections → exact SANDBOX token → authenticated device transport.
All provider HTTP is mocked; no board, hosted DB, credentials or real money.
"""
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
import json
import tempfile
import uuid
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import transaction, IntegrityError
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from meter import tests_prototype_device as legacy
from meter.models import EnergyAllocation, EnergyKeypadToken, MeterDelivery, PrototypeDevice
from meter.energy_tokens import token_record, issue_energy_token
from meter.prototype_device import identity
from meter.sandbox_enrollment import enroll_sandbox_meter
from loan.sandbox_service import create_quote
from loan.tests_sandbox import SANDBOX
from transactions.models import PaymentIntent, SandboxSettlement
from transactions.payment_settlement import PaymentSettlementError, settle_from_provider_evidence
from transactions.sandbox_payments import create_payment, reconcile_sandbox_payment

LAB = {**legacy.LAB, **SANDBOX, 'SANDBOX_EUR_LOANS_ENABLED': False}


class MTNFixture(legacy.LabFixtures):
    environment = 'SANDBOX'

    def purchase(self, amount='2.00', meter=None):
        quote = create_quote(self.owner, (meter or self.meter).pk, amount, 'PURCHASE')
        return create_payment(self.owner, {'purpose': 'PURCHASE', 'quote_id': str(quote.pk),
            'terms_hash': quote.terms_hash, 'accept_test_terms': True, 'msisdn': '46733123454',
            'client_request_id': str(uuid.uuid4())})[0]

    def evidence(self, payment, status='SUCCESS', **changes):
        return {'provider': 'MTN_SANDBOX', 'reference_id': str(payment.provider_reference),
            'external_id': payment.provider_external_id, 'amount': str(payment.amount), 'currency': 'EUR',
            'transaction_id': 'synthetic-' + str(payment.provider_reference), 'payer': '46733123454',
            'status': status, **changes}

    def settle(self, payment):
        return settle_from_provider_evidence(payment.pk, self.evidence(payment))

    def due(self, payment):
        PaymentIntent.objects.filter(pk=payment.pk).update(reconcile_after=timezone.now()-timedelta(seconds=1))

    def provider(self, payment, status, **changes):
        self.due(payment)
        token = Mock(status_code=200); token.json.return_value = {'access_token': 'synthetic-only'}
        response = Mock(status_code=200)
        response.json.return_value = {'status': status, 'externalId': payment.provider_external_id,
            'amount': str(payment.amount), 'currency': 'EUR', 'financialTransactionId': 'synthetic-' + str(payment.provider_reference),
            'payer': {'partyId': '46733123454', 'partyIdType': 'MSISDN'}, **changes}
        with patch('mtn_momo.sandbox.requests.post', return_value=token), patch('mtn_momo.sandbox.requests.get', return_value=response):
            return reconcile_sandbox_payment(payment.pk)


@override_settings(**LAB)
class MTNDeviceTests(MTNFixture, TransactionTestCase):
    def test_existing_mtn_recovery_keeps_its_token_domain_when_new_collections_are_paused(self):
        payment = self.purchase()
        PaymentIntent.objects.filter(pk=payment.pk).update(submission_state='ACCEPTED')
        with override_settings(PROTOTYPE_PAYMENT_PROVIDER='LOCAL_DEMO', ENERGY_TOKEN_ISSUANCE_ENABLED=False):
            row, effect = self.provider(payment, 'SUCCESSFUL')
            self.assertEqual(row.status, 'PENDING')
            self.assertFalse(effect)
            self.assertFalse(EnergyAllocation.objects.exists())
        with override_settings(PROTOTYPE_PAYMENT_PROVIDER='LOCAL_DEMO'):
            row, effect = self.provider(payment, 'SUCCESSFUL')
            self.assertTrue(effect)
            self.assertEqual(row.currency, 'EUR')
            token = EnergyKeypadToken.objects.get()
            self.assertEqual(token.environment, 'SANDBOX')
            self.assertFalse(token_record(token)['redemption_enabled'])

    def test_purchase_token_is_mandatory_even_when_device_capability_is_off(self):
        with override_settings(PROTOTYPE_AC_LAB_ENABLED=False):
            payment = self.purchase()
            paid, effect = self.settle(payment)
            self.assertTrue(effect)
            self.assertEqual(paid.status, 'SETTLED')
            self.assertEqual(EnergyAllocation.objects.count(), 1)
            token = EnergyKeypadToken.objects.get()
            self.assertEqual(token.environment, 'SANDBOX')
            self.assertFalse(token_record(token)['redemption_enabled'])
            response = self.client.post('/api/v1/prototype-device/v1/session/', self.handshake, format='json', **self.device_headers)
            self.assertEqual(response.status_code, 503)

    def test_verified_purchase_lost_response_ack_restart_and_owner_read(self):
        # Actual API initiation and actual adapter parsing; only HTTP transport mocked.
        quote = self.client.post('/api/v1/sandbox/quotes/', {'meter_id': self.meter.pk, 'amount': '2.00', 'purpose': 'PURCHASE'}, format='json', **self.headers).data
        token = Mock(status_code=200); token.json.return_value = {'access_token': 'synthetic-only'}
        accepted = Mock(status_code=202)
        with patch('mtn_momo.sandbox.requests.post', side_effect=[token, accepted]):
            response = self.client.post('/api/v1/sandbox/payments/', {'purpose': 'PURCHASE', 'quote_id': quote['id'],
                'terms_hash': quote['terms_hash'], 'accept_test_terms': True, 'msisdn': '46733123454',
                'client_request_id': str(uuid.uuid4())}, format='json', **self.headers)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data['payment']['status'], 'PENDING')
        payment = PaymentIntent.objects.get(provider_reference=response.data['payment']['reference'])
        self.assertFalse(EnergyAllocation.objects.exists()); self.assertFalse(EnergyKeypadToken.objects.exists())
        self.provider(payment, 'PENDING')
        self.assertFalse(EnergyKeypadToken.objects.exists())
        paid, effect = self.provider(payment, 'SUCCESSFUL')
        self.assertTrue(effect); self.assertEqual(paid.status, 'SETTLED')
        self.settle(payment)
        self.assertEqual(EnergyAllocation.objects.count(), 1); self.assertEqual(EnergyKeypadToken.objects.count(), 1)
        record = EnergyKeypadToken.objects.get()
        self.assertEqual(record.environment, 'SANDBOX'); self.assertEqual(record.amount_wh, 2000)
        self.assertEqual(record.allocation.amount_kwh, Decimal(quote['terms']['energy_kwh']))
        code = token_record(record)['token']; self.assertEqual(len(code), 15)
        self.start()
        command = self.redeem(code)['command']
        self.assertEqual(command['environment'], 'SANDBOX'); self.assertEqual(command['protocol'], 'GPAWA_PZEM_V2')
        self.assertEqual(self.redeem(code)['command'], command)
        receipt = self.receipt(command)
        # Board persisted the command, then reset before ACK reached Django.
        self.boot = str(uuid.uuid4())
        handshake = {**self.handshake, 'boot_id': self.boot, 'boot_counter': 2, 'initialize': False, 'ack_pending': True,
            'application_counter': command['command_sequence'], 'credited_uwh': command['credit_wh']*1_000_000,
            'last_command_id': command['command_id'], 'last_payload_digest': command['payload_digest'], 'last_receipt_id': receipt['receipt_id']}
        self.device = PrototypeDevice.objects.get(pk=self.device.pk)
        self.post('session', handshake)
        self.assertEqual(self.redeem(code, counter=1)['command'], command)
        self.assertEqual(self.post('ack', receipt), self.post('ack', receipt))
        self.redeem(code, counter=1, status=409)
        self.assertEqual(MeterDelivery.objects.count(), 1)
        self.assertEqual(MeterDelivery.objects.get().status, 'APPLIED')
        sample = {**self.sample(command), 'boot_counter': 2}
        self.post('telemetry', sample); self.post('telemetry', sample)
        read = self.client.get(f'/api/v1/meter/mobile-meters/{self.meter.pk}/?environment=SANDBOX', **self.headers)
        self.assertEqual(read.data['lab_environment'], 'SANDBOX')
        self.assertEqual(read.data['lab_protocol'], 'GPAWA_PZEM_V2')
        self.assertEqual(read.data['lab_consumed_uwh'], '1000000')
        self.assertFalse(read.data['output_enabled']); self.assertEqual(read.data['reported_relay_state'], 'UNKNOWN')
        history = self.client.get(f'/api/v1/meter/mobile-consumption/?meter_id={self.meter.pk}&environment=SANDBOX', **self.headers)
        self.assertEqual(history.data['ac_lab_telemetry'][0]['environment'], 'SANDBOX')
        other = APIClient(); other.force_authenticate(self.other)
        self.assertEqual(other.get(f'/api/v1/meter/mobile-meters/{self.meter.pk}/?environment=SANDBOX', **self.headers).status_code, 404)
        old = self.client.get(f'/api/v1/meter/mobile-meters/{self.meter.pk}/?environment=UGX_DEMO', **self.headers)
        self.assertNotIn('lab_environment', old.data)

    def test_http200_pending_failed_and_mismatched_success_never_issue_credit(self):
        payment = self.purchase()
        PaymentIntent.objects.filter(pk=payment.pk).update(submission_state='ACCEPTED')
        self.provider(payment, 'PENDING')
        for fields in ({'currency': 'UGX'}, {'amount': '9.00'}, {'externalId': 'wrong'}, {'financialTransactionId': ''}):
            row, effect = self.provider(payment, 'SUCCESSFUL', **fields)
            self.assertEqual(row.status, 'PENDING'); self.assertFalse(effect)
        failed, effect = self.provider(payment, 'FAILED')
        self.assertEqual(failed.status, 'FAILED'); self.assertFalse(effect)
        self.assertFalse(EnergyAllocation.objects.exists()); self.assertFalse(EnergyKeypadToken.objects.exists())

    def test_wrong_meter_environment_protocol_revocation_and_consumer_denied(self):
        code = self.token(); self.start()
        meter = enroll_sandbox_meter(self.owner, '00000009876')[0]
        other = self.purchase(meter=meter); self.settle(other)
        foreign = token_record(EnergyKeypadToken.objects.get(allocation__purchase_intent=other))['token']
        self.redeem(foreign, status=404)
        wrong = {**identity(self.device), 'token': code, 'application_counter': 0, 'environment': 'UGX_DEMO'}
        self.post('redeem', wrong, 403)
        self.post('redeem', {**wrong, 'environment': 'SANDBOX', 'protocol': 'GPAWA_PZEM_V1'}, 403)
        self.post('session', self.handshake, 401, **self.headers)
        PrototypeDevice.objects.filter(pk=self.device.pk).update(active=False, revoked_at=timezone.now())
        self.redeem(code, status=401)
        self.assertFalse(MeterDelivery.objects.exists())

    def test_historical_ugx_token_is_rejected_with_correct_sandbox_request_identity(self):
        from loan.models import SandboxQuote, SandboxLoan
        # Explicit historical fixture, not new lending or a currency conversion.
        terms = {'policy': {'id': 'DEMO-UGX-historical', 'currency': 'UGX'}, 'energy_kwh': '1.00'}
        quote = SandboxQuote.objects.create(owner=self.owner, meter=self.meter, purpose='LOAN', amount='1000', currency='UGX',
            environment='UGX_DEMO', terms=terms, terms_hash='a'*64, expires_at=timezone.now()+timedelta(minutes=15))
        loan = SandboxLoan.objects.create(owner=self.owner, meter=self.meter, quote=quote, client_request_id=uuid.uuid4(),
            currency='UGX', environment='UGX_DEMO', principal='1000', total_due='1050', terms=terms,
            assessment={'fixture': 'historical'}, status='DISBURSED', decision_reason='Historical test fixture', due_at=timezone.now()+timedelta(days=7))
        allocation = EnergyAllocation.objects.create(owner=self.owner, meter=self.meter, sandbox_loan=loan, amount_kwh='1.00', accounting_environment='UGX_DEMO')
        token = issue_energy_token(allocation)
        self.start(); self.redeem(token_record(token)['token'], status=404)
        token.refresh_from_db(); self.assertEqual(token.state, 'ISSUED')
        self.assertFalse(MeterDelivery.objects.exists())

    def test_v2_counter_reset_and_reordered_telemetry_are_not_fresh_credit(self):
        code = self.token(); self.start(); command = self.redeem(code)['command']
        self.post('ack', self.receipt(command))
        sample = self.sample(command); self.post('telemetry', sample)
        self.post('telemetry', {**sample, 'sequence': 2, 'pzem_wh': 499}, status=409)
        self.post('telemetry', {**sample, 'sequence': 2, 'measured_at': (timezone.now()-timedelta(minutes=1)).isoformat()}, status=409)
        self.post('telemetry', {**sample, 'pzem_wh': 501}, status=409)
        self.assertEqual(self.device.telemetry.count(), 1)
        self.assertEqual(EnergyAllocation.objects.count(), 1)

    def test_device_amount_contract_is_checked_before_new_collection(self):
        from loan.tests_sandbox import POLICY
        with override_settings(SANDBOX_POLICY={**POLICY, 'rate_per_kwh': '0.0001'}):
            with self.assertRaises(PaymentSettlementError): self.purchase()
        self.assertFalse(PaymentIntent.objects.exists())

    def test_existing_eur_self_repayment_stays_available_without_purchase_token_keys(self):
        from loan.models import SandboxQuote, SandboxLoan
        from loan.tests_sandbox import POLICY
        terms = {'policy': POLICY, 'energy_kwh': '2.00'}
        quote = SandboxQuote.objects.create(owner=self.owner, meter=self.meter, purpose='LOAN', amount='2.00', currency='EUR',
            environment='MTN_SANDBOX', terms=terms, terms_hash='b'*64, expires_at=timezone.now()+timedelta(minutes=15))
        loan = SandboxLoan.objects.create(owner=self.owner, meter=self.meter, quote=quote, client_request_id=uuid.uuid4(),
            currency='EUR', environment='MTN_SANDBOX', principal='2.00', total_due='2.10', terms=terms,
            assessment={'fixture': 'historical EUR approval'}, status='DISBURSED', decision_reason='Existing approved EUR fixture', due_at=timezone.now()+timedelta(days=7))
        EnergyAllocation.objects.create(owner=self.owner, meter=self.meter, sandbox_loan=loan, amount_kwh='2.00', accounting_environment='SANDBOX')
        with override_settings(ENERGY_TOKEN_ISSUANCE_ENABLED=False, ENERGY_TOKEN_ENCRYPTION_KEYS=[]):
            for amount in ('1.00', '1.10'):
                payment = create_payment(self.owner, {'purpose': 'LOAN_REPAYMENT', 'loan_id': str(loan.pk), 'amount': amount,
                    'accept_test_terms': True, 'msisdn': '46733123454', 'client_request_id': str(uuid.uuid4())})[0]
                self.settle(payment)
        loan.refresh_from_db(); self.assertEqual(loan.outstanding, Decimal('0')); self.assertEqual(loan.status, 'COMPLETED')
        self.assertEqual(EnergyAllocation.objects.count(), 1); self.assertFalse(EnergyKeypadToken.objects.exists())

    def test_provisioning_explicit_environment_private_unique_and_no_rebind(self):
        meter = enroll_sandbox_meter(self.owner, '00000001235')[0]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'private.json'; output = StringIO()
            kwargs = dict(environment='SANDBOX', owner_id=self.owner.pk, operator_id=self.operator.pk,
                private_config=str(path), confirm_output_disabled=True, stdout=output)
            call_command('provision_ac_lab_device', meter.pk, **kwargs)
            data = json.loads(path.read_text())
            self.assertEqual(data['environment'], 'SANDBOX'); self.assertEqual(data['protocol'], 'GPAWA_PZEM_V2')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600); self.assertNotIn(data['device_secret'], output.getvalue())
            self.assertFalse(data['output_enabled'])
            kwargs['private_config'] = str(Path(folder)/'wrong.json')
            with self.assertRaises(CommandError): call_command('provision_ac_lab_device', self.meter.pk, **kwargs)
            kwargs['environment'] = 'UGX_DEMO'
            with self.assertRaises(CommandError): call_command('provision_ac_lab_device', meter.pk, **kwargs)

    def test_token_configuration_failure_blocks_new_collection_and_retains_late_success(self):
        with override_settings(ENERGY_TOKEN_ISSUANCE_ENABLED=False):
            with self.assertRaises(PaymentSettlementError): self.purchase()
            flags = self.client.get('/api/v1/features/', **self.headers).data['sandbox']
            self.assertFalse(flags['purchases']); self.assertTrue(flags['repayments'])
        payment = self.purchase()
        with override_settings(ENERGY_TOKEN_ENCRYPTION_KEYS=[]):
            with self.assertRaises(PaymentSettlementError): self.settle(payment)
        payment.refresh_from_db(); self.assertEqual(payment.status, 'PENDING')
        self.assertFalse(EnergyAllocation.objects.exists())
        self.settle(payment)
        self.assertEqual(EnergyKeypadToken.objects.count(), 1)

    def test_wrong_reference_and_cross_intent_transaction_replay_are_rejected(self):
        paid = self.purchase()
        with self.assertRaises(PaymentSettlementError): settle_from_provider_evidence(paid.pk, self.evidence(paid, reference_id=str(uuid.uuid4())))
        self.settle(paid)
        another = self.purchase()
        with self.assertRaises(PaymentSettlementError): settle_from_provider_evidence(another.pk,
            self.evidence(another, transaction_id=self.evidence(paid)['transaction_id']))
        self.assertEqual(EnergyKeypadToken.objects.count(), 1); self.assertEqual(SandboxSettlement.objects.count(), 1)

    def test_sandbox_schema_keeps_physical_output_disabled(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            PrototypeDevice.objects.filter(pk=self.device.pk).update(output_enabled=True)
        self.device.refresh_from_db(); self.assertFalse(self.device.output_enabled)
        for environment in ('CORE', 'MTN_SANDBOX'):
            with self.assertRaises(IntegrityError), transaction.atomic():
                PrototypeDevice.objects.filter(pk=self.device.pk).update(environment=environment)

    def test_firmware_digest_vectors_match_the_actual_backend_digest(self):
        from meter.bench_device import payload_digest
        path = Path(__file__).resolve().parents[2]/'firmware/ac-lab-domain/tests/protocol-vectors.json'
        for vector in json.loads(path.read_text()):
            command = json.loads(vector['payload']); digest = command.pop('payload_digest')
            self.assertEqual(payload_digest(command), digest)
            self.assertEqual(command['environment'], vector['environment'])
            self.assertEqual(len(command), 13)


@override_settings(**LAB)
class MTNDeviceConcurrencyTests(MTNFixture, legacy.PrototypeConcurrencyTests):
    """Reuse the actual PostgreSQL concurrent redemption/ACK invariant for V2."""
