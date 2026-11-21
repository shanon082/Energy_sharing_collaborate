"""UGX obligations → explicitly authorized SANDBOX Wh; never EUR→UGX money."""
from decimal import Decimal
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from io import StringIO
from unittest.mock import patch
from django.core.management import call_command
from django.db import close_old_connections
from django.test import TransactionTestCase, override_settings
from rest_framework.exceptions import ValidationError
from loan.models import DemoCreditAssessment, ElectricityTariff, SandboxLoan
from loan.sandbox_service import create_quote, apply_loan, assessment
from loan.prototype_lending import CONTRACT, REPAYMENT_MESSAGE
from meter.tests_mtn_device import MTNFixture, LAB
from meter.models import EnergyAllocation, EnergyKeypadToken, MeterDelivery
from meter.energy_tokens import token_record
from meter.allocation_service import authorize_sandbox_loan_allocation
from transactions.models import PaymentIntent
from transactions.sandbox_payments import create_payment
from transactions.tests_demo_payments import DEMO, Fixtures

UGX = {**LAB, 'SANDBOX_UGX_LOANS_ENABLED': True}


@override_settings(**UGX)
class UGXLabTests(MTNFixture, TransactionTestCase):
    def test_capabilities_separate_lending_payments_and_unapproved_ugx_mapping(self):
        flags = self.client.get('/api/v1/features/', **self.headers).data['sandbox']
        self.assertEqual(flags['capability_version'], 'GPAWA-CONSUMER-v2')
        self.assertFalse(flags['loans'])  # Historical EUR origination stays off.
        self.assertTrue(flags['lending']['enabled'])
        self.assertTrue(flags['purchases']); self.assertTrue(flags['repayments'])
        self.assertEqual(flags['currency'], 'EUR')
        self.assertEqual(flags['action_reasons'], {'loan': '', 'purchase': '', 'repayment': ''})
        self.assertFalse(flags['ugx_payments']['enabled'])
        self.assertEqual(flags['ugx_payments']['code'], 'TEST_AUTHORIZATION_MAPPING_REQUIRED')
        with override_settings(MTN_SANDBOX_CONFIG={}):
            unavailable = self.client.get('/api/v1/features/', **self.headers).data['sandbox']
            self.assertTrue(unavailable['lending']['enabled'])
            self.assertFalse(unavailable['purchases']); self.assertFalse(unavailable['repayments'])
            self.assertIn('credentials', unavailable['action_reasons']['purchase'])
        with override_settings(SANDBOX_NEW_PAYMENTS_ENABLED=False):
            paused = self.client.get('/api/v1/features/', **self.headers).data['sandbox']
            self.assertTrue(paused['lending']['enabled'])
            self.assertIn('paused', paused['action_reasons']['purchase'])
            self.assertIn('EUR receipts cannot repay UGX debt', paused['action_reasons']['repayment'])
        with override_settings(ENERGY_TOKEN_ISSUANCE_ENABLED=False):
            unavailable = self.client.get('/api/v1/features/', **self.headers).data['sandbox']
            self.assertFalse(unavailable['lending']['enabled']); self.assertFalse(unavailable['purchases'])
            self.assertIn('token service', unavailable['action_reasons']['loan'])

    def test_high_score_does_not_override_current_limit_or_owned_meter(self):
        self.assertEqual(assessment(self.owner, meter_id=self.meter.pk)['score'], 85)
        limit = Decimal(assessment(self.owner, meter_id=self.meter.pk)['maximum'])
        with self.assertRaises(ValidationError):
            create_quote(self.owner, self.meter.pk, str(limit + 1), 'LOAN')
        from meter.sandbox_enrollment import enroll_sandbox_meter
        other_meter = enroll_sandbox_meter(self.other, '00000000888')[0]
        result = self.client.post('/api/v1/sandbox/quotes/', {'meter_id': other_meter.pk,
            'amount': '10000', 'purpose': 'LOAN', 'loan_contract': CONTRACT}, format='json', **self.headers)
        self.assertIn(result.status_code, (403, 404))
        self.assertFalse(SandboxLoan.objects.exists()); self.assertFalse(EnergyAllocation.objects.exists())

    def loan(self, key=None):
        quote = create_quote(self.owner, self.meter.pk, '10000', 'LOAN')
        return apply_loan(self.owner, quote.pk, quote.terms_hash, key or uuid.uuid4())[0]

    def test_quote_consent_approval_one_token_and_same_device_redemption(self):
        self.assertEqual(assessment(self.owner, meter_id=self.meter.pk)['score'], 85)
        quote = self.client.post('/api/v1/sandbox/quotes/', {'meter_id': self.meter.pk, 'amount': '10000', 'purpose': 'LOAN', 'loan_contract': CONTRACT}, format='json', **self.headers)
        self.assertEqual(quote.status_code, 201, quote.data)
        self.assertEqual(quote.data['terms']['policy']['currency'], 'UGX')
        self.assertEqual(quote.data['terms']['energy_environment'], 'SANDBOX')
        self.assertEqual(quote.data['terms']['policy']['lending_contract'], CONTRACT)
        self.assertIn('pricing', quote.data['terms'])
        data = {'quote_id': quote.data['id'], 'terms_hash': quote.data['terms_hash'], 'client_request_id': str(uuid.uuid4())}
        denied = self.client.post('/api/v1/sandbox/loans/', data, format='json', **self.headers)
        self.assertEqual(denied.status_code, 400)
        data['accept_test_terms'] = True
        first = self.client.post('/api/v1/sandbox/loans/', data, format='json', **self.headers)
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(first.data['loan']['currency'], 'UGX')
        self.assertFalse(first.data['loan']['repayment_available'])
        self.assertEqual(self.client.post('/api/v1/sandbox/loans/', data, format='json', **self.headers).status_code, 200)
        loan = SandboxLoan.objects.get()
        authorize_sandbox_loan_allocation(loan, Decimal(loan.terms['energy_kwh']))
        self.assertEqual(EnergyAllocation.objects.count(), 1); self.assertEqual(EnergyKeypadToken.objects.count(), 1)
        token = EnergyKeypadToken.objects.get()
        self.assertEqual(token.environment, 'SANDBOX')
        self.start(); code = token_record(token)['token']; command = self.redeem(code)['command']
        self.assertEqual(command['credit_wh'], token.amount_wh)
        self.assertEqual(self.redeem(code)['command'], command)
        receipt = self.receipt(command); self.post('ack', receipt); self.post('ack', receipt)
        self.redeem(code, counter=1, status=409)
        self.assertEqual(MeterDelivery.objects.count(), 1)

    def test_legacy_clients_stay_eur_blocked_and_new_clients_select_ugx_explicitly(self):
        flags = self.client.get('/api/v1/features/', **self.headers).data['sandbox']
        self.assertFalse(flags['loans']); self.assertTrue(flags['lending']['enabled'])
        old = self.client.get(f'/api/v1/sandbox/assessment/?meter_id={self.meter.pk}', **self.headers).data
        new = self.client.get(f'/api/v1/sandbox/assessment/?meter_id={self.meter.pk}&lending=ugx', **self.headers).data
        self.assertEqual(old['policy']['currency'], 'EUR'); self.assertFalse(old['assessment']['eligible'])
        self.assertEqual(new['policy']['currency'], 'UGX'); self.assertEqual(new['assessment']['score'], 85)
        self.assertEqual(new['purchase_policy']['currency'], 'EUR')
        denied = self.client.post('/api/v1/sandbox/quotes/', {'purpose': 'LOAN', 'amount': '10000', 'meter_id': self.meter.pk}, format='json', **self.headers)
        self.assertEqual(denied.status_code, 400); self.assertEqual(denied.data['code'], 'LOAN_CONTRACT_REQUIRED')
        self.assertFalse(SandboxLoan.objects.exists())

    def test_missing_assessment_tariff_and_low_score_fail_without_fallback(self):
        row = DemoCreditAssessment.objects.get(owner=self.owner, meter=self.meter)
        row.score = 79; row.save(update_fields=['score'])
        self.assertIn('80%', assessment(self.owner, meter_id=self.meter.pk)['reason'])
        with self.assertRaises(ValidationError): self.loan()
        row.delete()
        self.assertIsNone(assessment(self.owner, meter_id=self.meter.pk)['score'])
        result = self.client.post('/api/v1/sandbox/assessment/', {'meter_id': self.meter.pk, 'score': 100}, format='json', **self.headers)
        self.assertEqual(result.status_code, 400)
        result = self.client.post('/api/v1/sandbox/assessment/', {'meter_id': self.meter.pk}, format='json', **self.headers)
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data['assessment']['score'], 85)
        ElectricityTariff.objects.update(is_active=False)
        with self.assertRaises(ValidationError): self.loan()
        self.assertFalse(SandboxLoan.objects.exists()); self.assertFalse(EnergyAllocation.objects.exists())

    def test_mtn_eur_purchase_stays_eur_and_cannot_reduce_ugx_debt(self):
        # Retain the established per-ledger test policy: a historical EUR loan
        # does not get converted/closed or invent a new cross-currency UGX limit.
        from loan.tests_sandbox import trusted_profile_fixture
        with override_settings(SANDBOX_UGX_LOANS_ENABLED=False, SANDBOX_EUR_LOANS_ENABLED=True):
            trusted_profile_fixture(self.owner)  # Historical fixture, never a consumer questionnaire.
            quote = create_quote(self.owner, self.meter.pk, '2.00', 'LOAN')
            legacy, _ = apply_loan(self.owner, quote.pk, quote.terms_hash, uuid.uuid4())
        legacy_debt = legacy.outstanding
        loan = self.loan()
        before = loan.outstanding
        with self.assertRaises(ValidationError):
            create_payment(self.owner, {'purpose': 'LOAN_REPAYMENT', 'loan_id': str(loan.pk), 'amount': '2.00',
                'msisdn': '46733123454', 'accept_test_terms': True, 'client_request_id': str(uuid.uuid4())})
        payment = self.purchase(); self.settle(payment)
        loan.refresh_from_db()
        self.assertEqual(payment.currency, 'EUR'); self.assertEqual(loan.outstanding, before)
        legacy.refresh_from_db(); self.assertEqual(legacy.outstanding, legacy_debt); self.assertEqual(legacy.status, 'DISBURSED')
        self.assertEqual(EnergyAllocation.objects.count(), 3)

    def test_same_currency_partial_full_repayment_preserves_no_extra_energy(self):
        loan = self.loan()
        count = EnergyAllocation.objects.count(); tokens = EnergyKeypadToken.objects.count()
        # Isolated accounting regression only. Hosted provider stays MTN_SANDBOX.
        with override_settings(**DEMO):
            for amount in ('1000', str(loan.outstanding - 1000)):
                payment = Fixtures.repayment(self, loan, amount)
                Fixtures.settle(self, payment)
                loan.refresh_from_db()
        self.assertEqual(loan.outstanding, 0); self.assertEqual(loan.status, 'COMPLETED')
        self.assertEqual(EnergyAllocation.objects.count(), count); self.assertEqual(EnergyKeypadToken.objects.count(), tokens)

    def test_read_only_audit_never_outputs_token_or_credential(self):
        payment = self.purchase(); self.settle(payment)
        code = token_record(EnergyKeypadToken.objects.get())['token']
        output = StringIO()
        call_command('audit_ac_lab_credit', operator_id=self.operator.pk, owner_id=self.owner.pk, meter_id=self.meter.pk, stdout=output)
        self.assertNotIn(code, output.getvalue())
        report = json.loads(output.getvalue())
        self.assertFalse(report['provider_requeried'])
        self.assertEqual(report['purchases'][0]['checks'], ['STORED_CHAIN_CONSISTENT_PROVIDER_NOT_REQUERIED'])

    def test_concurrent_same_application_grants_one_allocation(self):
        quote = create_quote(self.owner, self.meter.pk, '10000', 'LOAN'); key = uuid.uuid4(); barrier = Barrier(2)
        def submit():
            close_old_connections()
            try:
                barrier.wait(); return apply_loan(self.owner, quote.pk, quote.terms_hash, key)[0].pk
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: submit(), range(2)))
        self.assertEqual(results[0], results[1]); self.assertEqual(EnergyAllocation.objects.count(), 1)
        self.assertEqual(EnergyKeypadToken.objects.count(), 1)

    def test_distinct_accepted_quotes_cannot_bypass_current_debt(self):
        first = create_quote(self.owner, self.meter.pk, '10000', 'LOAN')
        second = create_quote(self.owner, self.meter.pk, '10000', 'LOAN')
        approved = apply_loan(self.owner, first.pk, first.terms_hash, uuid.uuid4())[0]
        rejected = apply_loan(self.owner, second.pk, second.terms_hash, uuid.uuid4())[0]
        self.assertEqual(approved.status, 'DISBURSED'); self.assertEqual(rejected.status, 'REJECTED')
        self.assertEqual(EnergyAllocation.objects.count(), 1)

    def test_token_lookup_diagnostics_preserve_leading_zeros_and_do_not_log_them(self):
        with patch('meter.energy_tokens.secrets.randbelow', return_value=12345):
            payment = self.purchase(); self.settle(payment)
        token = EnergyKeypadToken.objects.get()
        code = token_record(token)['token']
        self.assertEqual(code, '000000000012345')
        self.start()
        with self.assertLogs('meter.device', level='INFO') as logs:
            miss = self.redeem('000000000099999', status=404)
        self.assertEqual(miss['code'], 'TOKEN_UNAVAILABLE')
        self.assertNotIn('000000000099999', ''.join(logs.output))
        self.assertNotIn(code, ''.join(logs.output))
        self.assertIn('operation=redeem http=404 stage=token_lookup code=TOKEN_LOOKUP_MISS', ''.join(logs.output))
        self.assertEqual(self.redeem(code)['command']['credit_wh'], token.amount_wh)


@override_settings(**UGX)
class UGXOnlyPauseTests(MTNFixture, TransactionTestCase):
    def test_new_payment_and_quote_denied_before_provider_or_records_but_ugx_loan_works(self):
        quote = create_quote(self.owner, self.meter.pk, '2.00', 'PURCHASE')
        with override_settings(SANDBOX_NEW_PAYMENTS_ENABLED=False), patch('mtn_momo.sandbox.requests.post') as post:
            flags = self.client.get('/api/v1/features/', **self.headers).data['sandbox']
            self.assertTrue(flags['new_payments_paused']); self.assertFalse(flags['purchases']); self.assertFalse(flags['repayments'])
            self.assertTrue(flags['lending']['enabled'])
            for purpose in ('PURCHASE', 'LOAN_REPAYMENT'):
                denied = self.client.post('/api/v1/sandbox/payments/', {'purpose': purpose, 'client_request_id': str(uuid.uuid4()), 'quote_id': str(quote.pk), 'terms_hash': quote.terms_hash, 'msisdn': '46733123454'}, format='json', **self.headers)
                self.assertEqual(denied.status_code, 403); self.assertEqual(denied.data['code'], 'NEW_PAYMENTS_PAUSED')
            denied = self.client.post('/api/v1/sandbox/quotes/', {'purpose': 'PURCHASE', 'amount': '2.00', 'meter_id': self.meter.pk}, format='json', **self.headers)
            self.assertEqual(denied.status_code, 403)
            self.assertFalse(PaymentIntent.objects.exists()); post.assert_not_called()
            quote = create_quote(self.owner, self.meter.pk, '10000', 'LOAN')
            loan, _ = apply_loan(self.owner, quote.pk, quote.terms_hash, uuid.uuid4())
            self.assertEqual(loan.currency, 'UGX'); self.assertEqual(EnergyAllocation.objects.get().accounting_environment, 'SANDBOX')

    def test_submitted_payment_recovers_without_another_charge_when_new_payments_paused(self):
        payment = self.purchase()
        PaymentIntent.objects.filter(pk=payment.pk).update(submission_state='ACCEPTED')
        with override_settings(SANDBOX_NEW_PAYMENTS_ENABLED=False):
            self.provider(payment, 'SUCCESSFUL')
            payment.refresh_from_db(); self.assertEqual(payment.status, 'SETTLED')
            self.provider(payment, 'SUCCESSFUL')
            self.assertEqual(EnergyAllocation.objects.count(), 1); self.assertEqual(EnergyKeypadToken.objects.count(), 1)
            rows = self.client.get('/api/v1/sandbox/payments/', **self.headers).data['payments']
            self.assertEqual(rows[0]['currency'], 'EUR'); self.assertEqual(rows[0]['status'], 'SETTLED')

    def test_unsubmitted_existing_intent_is_preserved_without_dispatch(self):
        from rest_framework.exceptions import PermissionDenied
        from transactions.sandbox_payments import reconcile_sandbox_payment
        payment = self.purchase()
        with override_settings(SANDBOX_NEW_PAYMENTS_ENABLED=False), patch('mtn_momo.sandbox.requests.post') as post:
            with self.assertRaises(PermissionDenied): reconcile_sandbox_payment(payment.pk)
            payment.refresh_from_db(); self.assertEqual(payment.status, 'PENDING'); self.assertEqual(payment.submission_state, 'NEW')
            post.assert_not_called(); self.assertFalse(EnergyAllocation.objects.exists())
