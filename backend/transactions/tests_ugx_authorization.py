"""Approved noncash mapping; every provider/device interaction is synthetic."""
import copy
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch
import uuid
from django.core.exceptions import ImproperlyConfigured, ValidationError as ModelValidationError
from django.db import close_old_connections, transaction, IntegrityError
from django.test import TransactionTestCase, override_settings
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied
from backend.ugx_authorization import POLICY, validate_configuration
from loan.models import SandboxLoan, DemoCreditAssessment, ElectricityTariff
from loan.sandbox_service import create_quote, apply_loan, loan_record
from loan.consumer_summary import consumer_summary
from loan.demo_tariffs import pricing_inputs
from meter.models import EnergyAllocation, EnergyKeypadToken, MeterDelivery
from meter.energy_tokens import token_record
from meter.tests_mtn_device import MTNFixture
from loan.tests_ugx_lab import UGX
from transactions.models import PaymentIntent, SandboxSettlement, SandboxUGXInstruction, SandboxUGXSettlement
from transactions.sandbox_payments import create_payment, receipt
from transactions.payment_settlement import settle_from_provider_evidence, PaymentSettlementError

MAPPING = {**UGX, 'SANDBOX_UGX_AUTHORIZATION_REQUIRED': True, 'SANDBOX_UGX_AUTHORIZATION_ENABLED': True, 'SANDBOX_UGX_AUTHORIZATION_POLICY': POLICY}


@override_settings(**MAPPING)
class UGXAuthorizationTests(MTNFixture, TransactionTestCase):
    def purchase(self, amount='10000', meter=None):
        return super().purchase(amount, meter)

    def loan(self):
        q = create_quote(self.owner, self.meter.pk, '10000', 'LOAN')
        return apply_loan(self.owner, q.pk, q.terms_hash, uuid.uuid4())[0]

    def repayment(self, loan, amount, key=None):
        return create_payment(self.owner, {'purpose':'LOAN_REPAYMENT','loan_id':str(loan.pk),'amount':amount,
            'msisdn':'46733123454','client_request_id':str(key or uuid.uuid4()),'accept_test_terms':True})[0]

    def test_purchase_provider_eur1_business_ugx_frozen_admin_tariff_one_token_device_recovery(self):
        before = Decimal(pricing_inputs(self.owner)['monthly_purchased_kwh'])
        payment = self.purchase()
        instruction = payment.ugx_instruction
        self.assertEqual((payment.currency, payment.amount), ('EUR', Decimal('1.00')))
        self.assertEqual((instruction.currency, instruction.amount), ('UGX', 10000))
        self.assertIn('pricing', instruction.snapshot['terms'])
        self.assertEqual(receipt(payment)['amount'], '10000')
        self.assertEqual(receipt(payment)['provider_receipt']['currency'], 'EUR')
        self.assertFalse(EnergyAllocation.objects.exists())
        self.provider(payment, 'PENDING'); self.assertFalse(EnergyAllocation.objects.exists())
        self.provider(payment, 'SUCCESSFUL'); self.provider(payment, 'SUCCESSFUL')
        payment.refresh_from_db()
        effect = SandboxUGXSettlement.objects.get()
        self.assertEqual(effect.authorized, effect.billed + effect.residual)
        provider_receipt = SandboxSettlement.objects.get(intent=payment)
        self.assertEqual(provider_receipt.received, 1); self.assertEqual(provider_receipt.residual, 1)
        self.assertEqual(EnergyAllocation.objects.count(), 1); self.assertEqual(EnergyKeypadToken.objects.count(), 1)
        allocation = EnergyAllocation.objects.get(); self.assertEqual(allocation.accounting_environment, 'SANDBOX')
        self.assertEqual(Decimal(pricing_inputs(self.owner)['monthly_purchased_kwh']), before + allocation.amount_kwh)
        self.start(); token = token_record(EnergyKeypadToken.objects.get())['token']
        command = self.redeem(token)['command']; self.assertEqual(self.redeem(token)['command'], command)
        ack = self.receipt(command); self.post('ack', ack); self.post('ack', ack)
        self.assertEqual(MeterDelivery.objects.count(), 1)
        result = receipt(PaymentIntent.objects.get(pk=payment.pk))
        self.assertEqual(result['currency'], 'UGX'); self.assertEqual(result['authorization_policy'], POLICY)
        self.assertEqual(result['provider_receipt']['amount'], '1.00')
        self.assertEqual(result['provider_receipt']['status'], 'SETTLED')

    def test_pending_failed_mismatch_and_client_success_cannot_grant_credit(self):
        for changes in ({'amount':'10000'}, {'currency':'UGX'}, {'external_id':'wrong'}, {'reference_id':str(uuid.uuid4())},
                        {'transaction_id':''}, {'status':'200'}):
            payment = self.purchase()
            with self.assertRaises(PaymentSettlementError):
                settle_from_provider_evidence(payment.pk, self.evidence(payment, **changes))
            self.assertFalse(EnergyAllocation.objects.exists()); self.assertFalse(SandboxUGXSettlement.objects.exists())
            PaymentIntent.objects.filter(pk=payment.pk).update(status='FAILED')  # Isolated case cleanup, no provider.
        payment = self.purchase(); self.provider(payment, 'PENDING'); self.provider(payment, 'FAILED')
        payment.refresh_from_db(); self.assertEqual(payment.status, 'FAILED')
        self.assertFalse(EnergyKeypadToken.objects.exists())

    def test_loan_no_payment_partial_full_repayment_one_receipt_per_currency_no_energy(self):
        loan = self.loan(); self.assertEqual(loan.outstanding, 10500)
        self.assertFalse(PaymentIntent.objects.exists())
        count = EnergyAllocation.objects.count(); tokens = EnergyKeypadToken.objects.count()
        self.assertTrue(loan_record(loan)['repayment_available'])
        payment = self.repayment(loan, '4000'); self.provider(payment, 'PENDING')
        loan.refresh_from_db(); self.assertEqual(loan.outstanding, 10500)
        self.provider(payment, 'SUCCESSFUL'); loan.refresh_from_db()
        self.assertEqual(loan.outstanding, 6500)
        self.assertEqual(consumer_summary(self.owner, 'UGX_DEMO')['outstanding'], '6500.000000')
        row = receipt(PaymentIntent.objects.get(pk=payment.pk))
        self.assertEqual(Decimal(row['applied']), 4000); self.assertEqual(Decimal(row['provider_receipt']['amount']), 1)
        self.assertIsNone(row['allocation_id'])
        final = self.repayment(loan, '6500'); self.provider(final, 'PENDING'); self.provider(final, 'SUCCESSFUL')
        loan.refresh_from_db(); self.assertEqual(loan.status, 'COMPLETED'); self.assertEqual(loan.outstanding, 0)
        self.assertIsNotNone(loan.closed_at)
        self.assertEqual(EnergyAllocation.objects.count(), count); self.assertEqual(EnergyKeypadToken.objects.count(), tokens)
        with self.assertRaises(ValidationError): self.repayment(loan, '1')
        self.assertEqual(loan.outstanding, 0)

    def test_duplicate_request_concurrent_confirmation_and_provider_replay_one_effect(self):
        payment = self.purchase(); data = {'purpose':'PURCHASE','quote_id':str(payment.sandbox_quote_id),
            'terms_hash':payment.sandbox_quote.terms_hash,'client_request_id':str(payment.client_request_id),
            'msisdn':'46733123454','accept_test_terms':True}
        self.assertEqual(create_payment(self.owner, data)[0].pk, payment.pk)
        barrier = Barrier(2); evidence = self.evidence(payment)
        def settle():
            close_old_connections()
            try:
                barrier.wait(); return settle_from_provider_evidence(payment.pk, evidence)[1]
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda _:settle(),range(2)))
        self.assertEqual(sorted(results),[False,True]); self.assertEqual(SandboxUGXSettlement.objects.count(),1)
        self.assertEqual(EnergyAllocation.objects.count(),1); self.assertEqual(EnergyKeypadToken.objects.count(),1)
        other = self.purchase()
        with self.assertRaises(PaymentSettlementError):
            settle_from_provider_evidence(other.pk,self.evidence(other,transaction_id=evidence['transaction_id']))
        self.assertEqual(SandboxUGXSettlement.objects.count(),1)

    def test_immutable_instruction_and_frozen_quote_tamper_rejected(self):
        payment = self.purchase(); instruction=payment.ugx_instruction
        instruction.amount=9000
        with self.assertRaises(ModelValidationError): instruction.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            SandboxUGXInstruction.objects.filter(pk=instruction.pk).update(amount=9000)
        quote=payment.sandbox_quote; terms=copy.deepcopy(quote.terms);terms['billed']='0'
        type(quote).objects.filter(pk=quote.pk).update(terms=terms)
        with self.assertRaises(PaymentSettlementError): self.settle(payment)
        self.assertFalse(EnergyAllocation.objects.exists())

    def test_cross_account_and_eur_debt_ugx_instruction_rejected(self):
        loan=self.loan()
        with self.assertRaises(NotFound):
            create_payment(self.other,{'purpose':'LOAN_REPAYMENT','loan_id':str(loan.pk),'amount':'4000',
                'msisdn':'46733123454','client_request_id':str(uuid.uuid4()),'accept_test_terms':True})
        payment=self.repayment(loan,'4000')
        self.client.force_authenticate(self.other)
        denied=self.client.get(f'/api/v1/sandbox/payments/{payment.provider_reference}/',**self.headers)
        self.assertEqual(denied.status_code,404)
        with override_settings(SANDBOX_UGX_AUTHORIZATION_ENABLED=False):
            with self.assertRaises(PermissionDenied): self.repayment(loan,'4000')

    def test_recovery_after_disabling_new_instructions_keeps_original_policy(self):
        payment=self.purchase(); PaymentIntent.objects.filter(pk=payment.pk).update(submission_state='ACCEPTED')
        with override_settings(SANDBOX_UGX_AUTHORIZATION_ENABLED=False,SANDBOX_NEW_PAYMENTS_ENABLED=False):
            self.provider(payment,'SUCCESSFUL')
        payment.refresh_from_db();self.assertEqual(payment.status,'SETTLED')
        self.assertEqual(receipt(payment)['currency'],'UGX')
        self.assertEqual(SandboxUGXSettlement.objects.count(),1)
        with override_settings(ALWAYSDATA_TESTING=False):
            with self.assertRaises(ImproperlyConfigured):validate_configuration()
            # Test receipt may never settle in a production/core profile.
            with self.assertRaises(PaymentSettlementError):
                from transactions.ugx_authorization import validate_instruction
                validate_instruction(payment)

    def test_capabilities_ugx_currency_and_lending_not_legacy_mobile_flags(self):
        flags=self.client.get('/api/v1/features/',**self.headers).data
        cap=flags['sandbox']
        self.assertEqual(cap['provider'],'MTN_SANDBOX');self.assertEqual(cap['currency'],'UGX')
        self.assertEqual(cap['authorization']['amount'],'1.00');self.assertTrue(cap['ugx_payments']['enabled'])
        self.assertTrue(cap['purchases']);self.assertTrue(cap['repayments']);self.assertTrue(cap['lending']['enabled'])
        self.assertFalse(cap['loans']);self.assertFalse(flags['mobile_actions']['purchase'])
        self.assertFalse(cap['ac_lab']['physical_output'])
        with override_settings(PROTOTYPE_PAYMENT_PROVIDER='LOCAL_DEMO'):
            with self.assertRaises(ImproperlyConfigured):validate_configuration()
        with override_settings(MTN_SANDBOX_CONFIG={'BASE_URL':'https://proxy.momoapi.mtn.com','CURRENCY':'UGX','ENVIRONMENT':'production'}):
            with self.assertRaises(ImproperlyConfigured):validate_configuration()

    def test_purchase_context_does_not_call_failed_assessment(self):
        with patch('loan.sandbox_api.assessment', side_effect=RuntimeError('synthetic unavailable')) as scoring:
            response=self.client.get(f'/api/v1/sandbox/assessment/?meter_id={self.meter.pk}&purpose=PURCHASE',**self.headers)
        self.assertEqual(response.status_code,200);scoring.assert_not_called()
        self.assertIsNone(response.data['assessment']);self.assertTrue(response.data['pricing']['available'])
        self.assertEqual(response.data['policy']['currency'],'UGX')
        ElectricityTariff.objects.update(is_active=False)
        with self.assertRaises(ValidationError):self.purchase()
        self.assertFalse(PaymentIntent.objects.exists());self.assertFalse(EnergyAllocation.objects.exists())

    def test_exact_202_pending_success_adapter_payload_and_restart_scheduler(self):
        from io import StringIO
        from unittest.mock import Mock
        from django.core.management import call_command
        from transactions.sandbox_payments import reconcile_sandbox_payment
        from django.utils import timezone
        payment=self.purchase()
        auth=Mock(status_code=200);auth.json.return_value={'access_token':'synthetic-only'}
        accepted=Mock(status_code=202)
        def collect(*args,**kwargs):
            self.assertTrue(SandboxUGXInstruction.objects.filter(intent=payment).exists())
            self.assertFalse(transaction.get_connection().in_atomic_block)
            self.assertEqual(kwargs['json']['amount'],'1.00');self.assertEqual(kwargs['json']['currency'],'EUR')
            return accepted
        with patch('mtn_momo.sandbox.requests.post',side_effect=[auth,accepted]) as post:
            row,_=reconcile_sandbox_payment(payment.pk)
        self.assertEqual(post.call_count,2);self.assertEqual(row.submission_state,'ACCEPTED')
        self.assertEqual(row.status,'PENDING');self.assertFalse(EnergyAllocation.objects.exists())
        self.provider(payment,'PENDING');self.assertFalse(EnergyAllocation.objects.exists())
        # No browser/controller exists here. A fresh scheduled process recovers from DB.
        self.due(payment)
        status=Mock(status_code=200);status.json.return_value={'status':'SUCCESSFUL','externalId':payment.provider_external_id,
            'amount':'1.00','currency':'EUR','financialTransactionId':'scheduler-'+str(payment.provider_reference),
            'payer':{'partyId':'46733123454'}}
        with patch('mtn_momo.sandbox.requests.post',return_value=auth),patch('mtn_momo.sandbox.requests.get',return_value=status):
            call_command('reconcile_sandbox_payments',run=True,limit=2,max_seconds=50,stdout=StringIO())
        self.assertEqual(PaymentIntent.objects.get(pk=payment.pk).status,'SETTLED')
        self.assertEqual(SandboxUGXSettlement.objects.count(),1);self.assertEqual(EnergyKeypadToken.objects.count(),1)

    def test_concurrent_distinct_authorizations_preserve_ugx_excess_and_close_once(self):
        loan=self.loan();a=self.repayment(loan,'7000')
        # Isolated recovery fixture for two pre-existing authorized pending records;
        # normal initiation's owner lock deliberately forbids a second pending charge.
        PaymentIntent.objects.filter(pk=a.pk).update(status='FAILED')
        b=self.repayment(loan,'7000');PaymentIntent.objects.filter(pk=a.pk).update(status='PENDING')
        barrier=Barrier(2)
        def settle(payment):
            close_old_connections()
            try:
                barrier.wait();return settle_from_provider_evidence(payment.pk,self.evidence(payment))[1]
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(settle,[a,b]))
        self.assertEqual(results,[True,True]);loan.refresh_from_db()
        self.assertEqual(loan.outstanding,0);self.assertEqual(loan.status,'COMPLETED')
        effects=SandboxUGXSettlement.objects.filter(instruction__loan=loan)
        self.assertEqual(sum(x.applied for x in effects),10500)
        self.assertEqual(sum(x.excess for x in effects),3500)
        self.assertEqual(sum(x.received for x in SandboxSettlement.objects.all()),2)
        self.assertEqual(EnergyAllocation.objects.count(),1);self.assertEqual(EnergyKeypadToken.objects.count(),1)
        closed_at=loan.closed_at
        from django.utils import timezone
        from datetime import timedelta
        with patch('django.utils.timezone.now',return_value=timezone.now()+timedelta(days=100)):
            self.assertEqual(loan.outstanding,0)
        self.assertEqual(loan.closed_at,closed_at)

    def test_old_eur_debt_is_not_relabelled_or_repaid_by_ugx_instruction(self):
        from loan.tests_sandbox import trusted_profile_fixture
        with override_settings(SANDBOX_UGX_AUTHORIZATION_REQUIRED=False,SANDBOX_UGX_AUTHORIZATION_ENABLED=False,SANDBOX_UGX_LOANS_ENABLED=False,SANDBOX_EUR_LOANS_ENABLED=True):
            trusted_profile_fixture(self.owner)
            q=create_quote(self.owner,self.meter.pk,'2.00','LOAN')
            historical,_=apply_loan(self.owner,q.pk,q.terms_hash,uuid.uuid4())
        before=historical.outstanding
        with self.assertRaises(ValidationError) as denied:self.repayment(historical,'1')
        self.assertEqual(denied.exception.detail['code'],'TEST_CURRENCY_MISMATCH')
        historical.refresh_from_db();self.assertEqual(historical.currency,'EUR');self.assertEqual(historical.outstanding,before)
        self.assertFalse(PaymentIntent.objects.exists())

    def test_purchase_bonus_source_is_once_and_tariff_does_not_count_delivery_twice(self):
        payment=self.purchase('20000');self.settle(payment);self.settle(payment)
        assessment=DemoCreditAssessment.objects.get(owner=self.owner,meter=self.meter)
        self.assertEqual(assessment.purchase_source_count,1)
        old_points=assessment.purchase_points
        from loan.demo_assessment import refresh_demo_purchase_contribution
        refresh_demo_purchase_contribution(self.owner,self.meter)
        assessment.refresh_from_db();self.assertEqual(assessment.purchase_points,old_points)
        allocation=EnergyAllocation.objects.get()
        self.start();code=token_record(EnergyKeypadToken.objects.get())['token'];command=self.redeem(code)['command']
        self.post('ack',self.receipt(command))
        self.assertEqual(Decimal(pricing_inputs(self.owner)['monthly_purchased_kwh']),allocation.amount_kwh)

    def test_mapping_does_not_override_explicit_ugx_lending_switch(self):
        from rest_framework.exceptions import PermissionDenied
        quote=create_quote(self.owner,self.meter.pk,'10000','LOAN')
        with override_settings(SANDBOX_UGX_LOANS_ENABLED=False):
            with self.assertRaises(PermissionDenied):create_quote(self.owner,self.meter.pk,'10000','LOAN')
            with self.assertRaises(PermissionDenied):apply_loan(self.owner,quote.pk,quote.terms_hash,uuid.uuid4())
            flags=self.client.get('/api/v1/features/',**self.headers).data['sandbox']
            self.assertFalse(flags['lending']['enabled']);self.assertFalse(flags['loans']);self.assertTrue(flags['purchases'])
        self.assertFalse(SandboxLoan.objects.exists())

    def test_disabled_authorization_keeps_ugx_reads_and_cannot_reopen_eur_charges(self):
        from rest_framework.exceptions import PermissionDenied
        from backend.demo_config import test_domain
        with override_settings(SANDBOX_UGX_AUTHORIZATION_ENABLED=False):
            self.assertEqual(test_domain(),('UGX','UGX_DEMO','MTN_SANDBOX'))
            flags=self.client.get('/api/v1/features/',**self.headers).data['sandbox']
            self.assertEqual(flags['currency'],'UGX');self.assertFalse(flags['purchases']);self.assertFalse(flags['repayments'])
            self.assertIn('activate SANDBOX_UGX_AUTHORIZATION_ENABLED',flags['action_reasons']['purchase'])
            with self.assertRaises(PermissionDenied):self.purchase()
            loan=self.loan()  # Approved loans are independent of payment availability.
            self.assertEqual(Decimal(consumer_summary(self.owner,'UGX_DEMO')['energy']['available_kwh']),loan.energy_allocation.amount_kwh)
            with self.assertRaises(PermissionDenied):self.repayment(loan,'1000')
        self.assertFalse(PaymentIntent.objects.exists())
