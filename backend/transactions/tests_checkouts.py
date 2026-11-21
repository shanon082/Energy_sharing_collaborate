"""Isolated checkout expiry/replacement races; provider/device traffic is mocked."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Barrier, Event
from unittest.mock import patch
import uuid

from django.core.management import call_command
from django.db import close_old_connections, transaction
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied

from loan.models import SandboxLoan
from loan.sandbox_service import create_quote, apply_loan
from meter.models import EnergyAllocation, EnergyKeypadToken
from meter.tests_mtn_device import MTNFixture
from transactions.models import PaymentIntent, SandboxCheckout, SandboxUGXSettlement, SandboxSettlement
from transactions.checkouts import deadline, checkout_info, expire_checkout, retry_checkout
from transactions.sandbox_payments import create_payment, reconcile_sandbox_payment, receipt
from transactions.payment_settlement import settle_from_provider_evidence
from transactions.tests_ugx_authorization import MAPPING


@override_settings(**MAPPING)
class CheckoutTests(MTNFixture, TransactionTestCase):
    def purchase(self, amount='10000', meter=None):
        return super().purchase(amount, meter)

    def age(self, payment, state='ACCEPTED'):
        PaymentIntent.objects.filter(pk=payment.pk).update(initiated_at=timezone.now()-timedelta(seconds=301),
            reconcile_after=timezone.now()-timedelta(seconds=1), submission_state=state,
            reconcile_attempts=0 if state == 'NEW' else 1)
        return PaymentIntent.objects.get(pk=payment.pk)

    def retry(self, payment, key=None, owner=None):
        return retry_checkout(owner or self.owner, payment.provider_reference,
            {'client_request_id':str(key or uuid.uuid4()), 'accept_test_terms':True})

    def loan(self):
        quote=create_quote(self.owner,self.meter.pk,'10000','LOAN')
        return apply_loan(self.owner,quote.pk,quote.terms_hash,uuid.uuid4())[0]

    def repayment(self, loan, amount):
        return create_payment(self.owner, {'purpose':'LOAN_REPAYMENT','loan_id':str(loan.pk),'amount':amount,
            'client_request_id':str(uuid.uuid4()),'msisdn':'46733123454','accept_test_terms':True})[0]

    def test_299_300_boundary_read_only_get_original_deadline(self):
        payment=self.purchase(); end=deadline(payment)
        for seconds,expired in ((-1,False),(0,True)):
            with patch('django.utils.timezone.now',return_value=end+timedelta(seconds=seconds)):
                self.assertEqual(checkout_info(payment)['expired'],expired)
                response=self.client.get(f'/api/v1/sandbox/payments/{payment.provider_reference}/',**self.headers)
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.data['payment']['checkout']['expired'],expired)
                self.assertEqual(response.data['payment']['checkout']['expires_at'],end.isoformat())
        self.assertIsNone(SandboxCheckout.objects.get(intent=payment).expired_at)
        key=payment.client_request_id
        quote=payment.sandbox_quote
        again,_=create_payment(self.owner,{'purpose':'PURCHASE','quote_id':str(quote.pk),'terms_hash':quote.terms_hash,
            'client_request_id':str(key),'accept_test_terms':True,'msisdn':'46733123454'})
        self.assertEqual(deadline(again),end)
        self.assertFalse(EnergyAllocation.objects.exists())

    def test_never_submitted_expiry_prevents_worker_submission(self):
        payment=self.age(self.purchase(),'NEW')
        before=payment.status
        expire_checkout(payment.pk)
        with patch('transactions.sandbox_payments.MTNSandbox') as provider:
            row,effect=reconcile_sandbox_payment(payment.pk)
        provider.assert_not_called();self.assertFalse(effect)
        self.assertEqual(row.status,before);self.assertEqual(row.submission_state,'NEW')
        self.assertTrue(row.checkout.initiation_cancelled_at)
        self.assertFalse(checkout_info(row)['provider_cancelled'])

    def test_historical_new_without_pre_io_proof_remains_uncertain_and_late_payable(self):
        payment=self.purchase();context=dict(payment.sandbox_context)
        context.pop('checkout_submission_proof')
        PaymentIntent.objects.filter(pk=payment.pk).update(sandbox_context=context)
        with override_settings(SANDBOX_NEW_PAYMENTS_ENABLED=False), patch('transactions.sandbox_payments.MTNSandbox') as adapter:
            adapter.return_value.status.return_value={'status':'PENDING'}
            call_command('reconcile_sandbox_payments',run=True,limit=2,max_seconds=50,stdout=StringIO())
            adapter.return_value.initiate.assert_not_called();adapter.return_value.status.assert_called_once()
        payment=self.age(payment,'NEW')
        expire_checkout(payment.pk)
        row=PaymentIntent.objects.get(pk=payment.pk)
        self.assertIsNone(row.checkout.initiation_cancelled_at)
        self.assertEqual(checkout_info(row)['classification'],'SUBMISSION_UNKNOWN')
        with patch('transactions.sandbox_payments.MTNSandbox') as adapter:
            adapter.return_value.status.return_value={'status':'UNKNOWN'}
            row,effect=reconcile_sandbox_payment(row.pk)
            adapter.return_value.initiate.assert_not_called();adapter.return_value.status.assert_called_once()
        self.assertFalse(effect);self.settle(row)
        self.assertEqual(EnergyAllocation.objects.count(),1)

    def test_submitted_unknown_and_stale_lease_are_not_cancelled(self):
        for state in ['ACCEPTED','SUBMITTING','OUTCOME_UNKNOWN','NEW']:
            payment=self.age(self.purchase(),state)
            PaymentIntent.objects.filter(pk=payment.pk).update(reconcile_attempts=1,reconcile_lease_id=uuid.uuid4(),
                reconcile_lease_until=timezone.now()-timedelta(seconds=1))
            expire_checkout(payment.pk)
            row=PaymentIntent.objects.get(pk=payment.pk)
            self.assertIsNone(row.checkout.initiation_cancelled_at)
            with patch('transactions.sandbox_payments.MTNSandbox') as adapter:
                adapter.return_value.status.return_value={'status':'UNKNOWN'}
                row,effect=reconcile_sandbox_payment(row.pk)
                adapter.return_value.initiate.assert_not_called()
                adapter.return_value.status.assert_called_once()
            self.assertFalse(effect);self.assertEqual(row.status,'PENDING')
            self.assertEqual(row.reconciliation_error,'STATUS_UNAVAILABLE')
            self.assertIn('confirmation is still being checked',checkout_info(row)['message'])
            # Separate isolated business operation; this loop does not retry a charge.
            PaymentIntent.objects.filter(pk=row.pk).update(status='FAILED')

    def test_submission_expiry_race_preserves_inflight_reference(self):
        payment=self.purchase(); entered=Event(); finish=Event()
        def send():
            close_old_connections()
            try:
                def initiate(row):
                    self.assertFalse(transaction.get_connection().in_atomic_block)
                    entered.set();self.assertTrue(finish.wait(10));return 'ACCEPTED'
                with patch('transactions.sandbox_payments.MTNSandbox') as adapter:
                    adapter.return_value.initiate.side_effect=initiate
                    return reconcile_sandbox_payment(payment.pk)
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(send);self.assertTrue(entered.wait(10))
            with patch('django.utils.timezone.now',return_value=deadline(payment)):
                checkout=expire_checkout(payment.pk)
                self.assertIsNone(checkout.initiation_cancelled_at)
            finish.set();row,_=future.result(timeout=10)
        self.assertEqual(row.provider_reference,payment.provider_reference)
        self.assertEqual(row.submission_state,'ACCEPTED');self.assertEqual(row.status,'PENDING')

    def test_closed_app_scheduler_expires_new_without_submitting(self):
        payment=self.age(self.purchase(),'NEW');out=StringIO()
        with patch('transactions.management.commands.reconcile_sandbox_payments.MTNSandbox') as adapter:
            call_command('reconcile_sandbox_payments',run=True,limit=2,max_seconds=50,stdout=out)
        adapter.return_value.initiate.assert_not_called()
        self.assertTrue(SandboxCheckout.objects.get(intent=payment).initiation_cancelled_at)
        self.assertEqual(PaymentIntent.objects.get(pk=payment.pk).status,'PENDING')

    def test_explicit_replacement_and_late_success_either_order_one_token(self):
        for original_first in [True,False]:
            with self.subTest(original_first=original_first):
                original=self.age(self.purchase());replacement,created=self.retry(original)
                self.assertTrue(created);self.assertNotEqual(original.provider_reference,replacement.provider_reference)
                self.assertEqual(original.ugx_instruction.snapshot['terms'],replacement.ugx_instruction.snapshot['terms'])
                first,second=(original,replacement) if original_first else (replacement,original)
                before=EnergyAllocation.objects.count()
                self.assertTrue(self.settle(first)[1]);self.assertFalse(self.settle(second)[1]);self.assertFalse(self.settle(second)[1])
                self.assertEqual(EnergyAllocation.objects.count(),before+1)
                self.assertEqual(SandboxUGXSettlement.objects.filter(instruction__intent__in=[original,replacement]).count(),1)
                self.assertEqual(SandboxSettlement.objects.filter(intent__in=[original,replacement]).count(),2)
                second=PaymentIntent.objects.get(pk=second.pk)
                result=receipt(second)
                self.assertEqual(result['status'],'SETTLED');self.assertIsNone(result['allocation_id'])
                self.assertEqual(result['checkout']['business_effect'],'ADDITIONAL_AUTHORIZATION_REVIEW')
                self.assertEqual(result['checkout']['fulfilled_reference'],str(first.provider_reference))
                self.assertEqual(EnergyKeypadToken.objects.count(),EnergyAllocation.objects.count())

    def test_concurrent_late_success_and_replacement_one_business_effect(self):
        original=self.age(self.purchase());replacement,_=self.retry(original);barrier=Barrier(2)
        def settle(row):
            close_old_connections()
            try:barrier.wait();return self.settle(row)[0].status
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(settle,[original,replacement])),['SETTLED','SETTLED'])
        self.assertEqual(SandboxUGXSettlement.objects.count(),1)
        self.assertEqual(SandboxSettlement.objects.count(),2)
        self.assertEqual(EnergyAllocation.objects.count(),1);self.assertEqual(EnergyKeypadToken.objects.count(),1)

    def test_retry_consent_idempotency_doubleclick_owner_and_domain(self):
        payment=self.age(self.purchase());key=uuid.uuid4()
        with self.assertRaises(NotFound):self.retry(payment,owner=self.other)
        with self.assertRaises(ValidationError):retry_checkout(self.owner,payment.provider_reference,{'client_request_id':str(key)})
        replacement,created=self.retry(payment,key);again,reused=self.retry(payment,key)
        self.assertTrue(created);self.assertFalse(reused);self.assertEqual(replacement.pk,again.pk)
        with self.assertRaises(ValidationError):self.retry(payment)
        with override_settings(ALWAYSDATA_TESTING=False):
            from transactions.payment_settlement import PaymentSettlementError
            with self.assertRaises(PaymentSettlementError):self.retry(payment)

    def test_unrelated_pending_purchase_does_not_block_loan_or_another_meter(self):
        self.purchase()
        loan=self.loan();self.assertEqual(loan.status,'DISBURSED')
        # A self repayment is a distinct debt operation, not the pending purchase.
        self.assertEqual(self.repayment(loan,'4000').status,'PENDING')

    def test_partial_full_repayment_replacements_never_double_reduce_or_issue_energy(self):
        loan=self.loan();initial=EnergyAllocation.objects.count()
        for amount,outstanding in [('4000',6500),('6500',0)]:
            original=self.age(self.repayment(loan,amount));replacement,_=self.retry(original)
            self.settle(replacement);self.settle(original);loan.refresh_from_db()
            self.assertEqual(loan.outstanding,outstanding)
        self.assertEqual(loan.status,'COMPLETED');closed=loan.closed_at
        self.settle(original);loan.refresh_from_db();self.assertEqual(loan.closed_at,closed)
        self.assertEqual(EnergyAllocation.objects.count(),initial);self.assertEqual(EnergyKeypadToken.objects.count(),initial)
        self.assertEqual(sum(x.applied for x in SandboxUGXSettlement.objects.all()),10500)

    def test_preview_report_and_historical_providers_no_token_or_phone_output(self):
        payment=self.age(self.purchase(),'NEW');SandboxCheckout.objects.filter(intent=payment).delete()
        out=StringIO();call_command('review_sandbox_checkouts',stdout=out)
        self.assertIn(str(payment.provider_reference),out.getvalue());self.assertIn('NEVER_SUBMITTED',out.getvalue())
        self.assertNotIn('46733123454',out.getvalue());self.assertNotIn('msisdn',out.getvalue())
        self.assertFalse(SandboxCheckout.objects.filter(intent=payment).exists())
        call_command('review_sandbox_checkouts',expire=True,stdout=StringIO())
        self.assertTrue(SandboxCheckout.objects.get(intent=payment).initiation_cancelled_at)
        self.assertFalse(SandboxSettlement.objects.exists());self.assertFalse(EnergyAllocation.objects.exists())

    def test_retry_route_is_narrowly_allowed_and_freezes_original_terms(self):
        original=self.age(self.purchase());key=uuid.uuid4()
        with patch('transactions.sandbox_payments.MTNSandbox') as adapter:
            adapter.return_value.initiate.return_value='ACCEPTED'
            response=self.client.post(f'/api/v1/sandbox/payments/{original.provider_reference}/retry/',
                {'client_request_id':str(key),'accept_test_terms':True},format='json',**self.headers)
        self.assertEqual(response.status_code,202)
        result=response.data['payment'];self.assertEqual(result['status'],'PENDING')
        self.assertEqual(result['checkout']['operation_reference'],str(original.provider_reference))
        self.assertEqual(result['checkout']['replaces_reference'],str(original.provider_reference))
        self.assertEqual(result['provider_receipt']['amount'],'1.00')
        self.assertIsNone(result['allocation_id'])

    def test_early_retry_and_duplicate_concurrent_retry_rejected_without_charge(self):
        payment=self.purchase()
        with self.assertRaises(ValidationError):self.retry(payment)
        payment=self.age(payment);barrier=Barrier(2)
        def retry():
            close_old_connections()
            try:
                barrier.wait()
                try:return self.retry(payment)[0].pk
                except ValidationError:return None
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:retry(),range(2)))
        self.assertEqual(sum(x is not None for x in results),1)
        self.assertEqual(PaymentIntent.objects.count(),2);self.assertFalse(SandboxSettlement.objects.exists())

    def test_original_settled_before_retry_submission_closes_unused_attempt(self):
        original=self.age(self.purchase());replacement,_=self.retry(original)
        self.settle(original)
        with patch('transactions.sandbox_payments.MTNSandbox') as adapter:
            row,effect=reconcile_sandbox_payment(replacement.pk)
        adapter.assert_not_called();self.assertFalse(effect)
        self.assertEqual(row.status,'PENDING')
        row.refresh_from_db();self.assertEqual(row.checkout.closure_reason,'OPERATION_ALREADY_FULFILLED')
        self.assertFalse(receipt(row)['checkout']['provider_cancelled'])
        self.assertEqual(EnergyAllocation.objects.count(),1)

    def test_success_racing_retry_request_has_durable_closed_handle_recovery(self):
        original=self.age(self.purchase());expire_checkout(original.pk);self.settle(original)
        key=uuid.uuid4()
        replacement,created=self.retry(original,key)
        self.assertTrue(created);self.assertTrue(replacement.checkout.initiation_cancelled_at)
        with patch('transactions.sandbox_payments.MTNSandbox') as provider:
            row,effect=reconcile_sandbox_payment(replacement.pk)
        provider.assert_not_called();self.assertFalse(effect)
        again,reused=self.retry(original,key);self.assertFalse(reused);self.assertEqual(again.pk,row.pk)
        response=self.client.get(f'/api/v1/sandbox/payment-recovery/{key}/',**self.headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['payment']['checkout']['state'],'LOCAL_INITIATION_CANCELLED')
        self.assertEqual(response.data['payment']['checkout']['fulfilled_reference'],str(original.provider_reference))
        self.assertEqual(EnergyAllocation.objects.count(),1);self.assertEqual(SandboxUGXSettlement.objects.count(),1)

    def test_concurrent_expiry_and_success_retains_one_settlement(self):
        original=self.age(self.purchase());barrier=Barrier(2)
        def work(settle):
            close_old_connections()
            try:
                barrier.wait()
                return self.settle(original) if settle else expire_checkout(original.pk)
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(work,[True,False]))
        original.refresh_from_db();self.assertEqual(original.status,'SETTLED')
        self.assertEqual(EnergyAllocation.objects.count(),1);self.assertEqual(SandboxUGXSettlement.objects.count(),1)

    def test_old_local_demo_and_eur_history_keep_their_original_provider(self):
        from backend.demo_config import LOCAL_DEMO
        from transactions.demo_payments import complete_demo_payment
        from loan.tests_demo_assessment import DEMO
        with override_settings(**{**DEMO, 'SANDBOX_UGX_AUTHORIZATION_ENABLED':False, 'SANDBOX_UGX_AUTHORIZATION_REQUIRED':False}):
            from loan.sandbox_service import create_quote
            quote=create_quote(self.owner,self.meter.pk,'10000','PURCHASE')
            old,_=create_payment(self.owner,{'purpose':'PURCHASE','quote_id':str(quote.pk),'terms_hash':quote.terms_hash,
                'client_request_id':str(uuid.uuid4()),'accept_test_terms':True})
        # Histories are never relabelled, and delayed local simulation is not MTN.
        old=self.age(old,'DEMO_PENDING')
        with patch('requests.sessions.Session.request') as external:
            row,effect=complete_demo_payment(old.pk)
        external.assert_not_called();self.assertFalse(effect);self.assertEqual(row.provider,LOCAL_DEMO)
        self.assertEqual(row.currency,'UGX');self.assertEqual(row.status,'PENDING')
