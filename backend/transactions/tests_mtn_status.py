"""Official Collections response examples, safe status-only diagnostics; no live I/O."""
from datetime import timedelta
from io import StringIO
import json
from unittest.mock import Mock, patch

import requests
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from loan.tests_sandbox import Fixtures, SANDBOX
from transactions.models import PaymentIntent, SandboxSettlement
from transactions.sandbox_payments import reconcile_sandbox_payment
from meter.models import EnergyAllocation


@override_settings(**SANDBOX)
class StatusContractTests(Fixtures, TestCase):
    def setUp(self):
        self.create_fixture()

    def http(self, body=None, status=200):
        response = Mock(status_code=status)
        response.json.return_value = body
        return response

    def submitted(self):
        row = self.purchase()
        with patch('mtn_momo.sandbox.requests.post', side_effect=[self.http({'access_token': 'synthetic-only'}), self.http(status=202)]):
            row, _ = reconcile_sandbox_payment(row.pk)
        self.assertEqual(row.submission_state, 'ACCEPTED')
        self.assertLessEqual((row.reconcile_after - timezone.now()).total_seconds(), 5)
        return row

    def body(self, row, **changes):
        return {'status': 'SUCCESSFUL', 'externalId': row.provider_external_id,
                'amount': '1' if row.amount == 1 else str(row.amount), 'currency': 'EUR',
                'financialTransactionId': 'synthetic-receipt',
                'payer': {'partyIdType': 'MSISDN', 'partyId': row.sandbox_context['msisdn']}, **changes}

    def lookup(self, row, *, response=None, failure=None):
        PaymentIntent.objects.filter(pk=row.pk).update(reconcile_after=timezone.now()-timedelta(seconds=1))
        with patch('mtn_momo.sandbox.requests.post', return_value=self.http({'access_token': 'synthetic-only'})) as post, \
             patch('mtn_momo.sandbox.requests.get', return_value=response, side_effect=failure) as get:
            result = reconcile_sandbox_payment(row.pk)
        self.assertTrue(all(call.args[0].endswith('/collection/token/') for call in post.call_args_list))
        if get.called:
            self.assertTrue(get.call_args.args[0].endswith('/'+str(row.provider_reference)))
        else:
            self.assertNotEqual(result[0].status, 'PENDING')
        return result

    def test_documented_integer_identifiers_settle_once_without_wait_for_expiry(self):
        row = self.submitted()
        response = self.http(self.body(row, financialTransactionId=23503452,
            payer={'partyIdType': 'MSISDN', 'partyId': int(row.sandbox_context['msisdn'])}))
        row, effect = self.lookup(row, response=response)
        self.assertEqual(row.status, 'SETTLED'); self.assertTrue(effect)
        self.assertEqual(row.provider_transaction_id, '23503452')
        again, effect = self.lookup(row, response=response)
        self.assertFalse(effect); self.assertEqual(again.pk, row.pk)
        self.assertEqual(SandboxSettlement.objects.count(), 1)
        self.assertEqual(EnergyAllocation.objects.count(), 1)

    def test_failed_response_needs_no_financial_transaction_id(self):
        row = self.submitted(); body = self.body(row, status='FAILED', reason={'code': 'PAYER_NOT_FOUND', 'message': 'secret-body'})
        body.pop('financialTransactionId')
        with self.assertLogs('mtn_momo.diagnostics', level='WARNING') as logs:
            row, effect = self.lookup(row, response=self.http(body))
        self.assertEqual(row.status, 'FAILED'); self.assertFalse(effect)
        self.assertIn('provider_status=FAILED code=PAYER_NOT_FOUND', '\n'.join(logs.output))
        self.assertNotIn('secret-body', '\n'.join(logs.output))
        self.assertFalse(SandboxSettlement.objects.exists())

    def test_http_error_is_not_a_provider_failure(self):
        row = self.submitted()
        for status in (401, 403, 404, 500):
            with self.subTest(status=status), self.assertLogs('mtn_momo.diagnostics', level='WARNING') as logs:
                row, effect = self.lookup(row, response=self.http({'status': 'FAILED', 'message': 'secret'}, status))
                self.assertEqual(row.status, 'PENDING'); self.assertFalse(effect)
                self.assertEqual(row.reconciliation_error, 'MTN_STATUS_HTTP')
                self.assertIn(f'http_status={status}', '\n'.join(logs.output))

    def test_authentication_error_retains_uncertain_reference_and_redacts_secrets(self):
        row = self.submitted()
        PaymentIntent.objects.filter(pk=row.pk).update(reconcile_after=timezone.now()-timedelta(seconds=1))
        response = self.http({'access_token': 'never-print-this', 'message': 'private-body'}, 401)
        with self.assertLogs('mtn_momo.diagnostics', level='WARNING') as logs, \
             patch('mtn_momo.sandbox.requests.post', return_value=response), patch('mtn_momo.sandbox.requests.get') as get:
            result, effect = reconcile_sandbox_payment(row.pk)
        get.assert_not_called(); self.assertFalse(effect)
        self.assertEqual(result.status, 'PENDING'); self.assertEqual(result.reconciliation_error, 'MTN_AUTH_HTTP')
        text = '\n'.join(logs.output)
        self.assertIn('stage=AUTHENTICATION http_status=401', text)
        for value in ('never-print-this', 'private-body', row.sandbox_context['msisdn']):
            self.assertNotIn(value, text)

    def test_pending_remains_prompt_and_timeout_then_late_success_recovers(self):
        row = self.submitted()
        PaymentIntent.objects.filter(pk=row.pk).update(reconcile_attempts=12)
        row, effect = self.lookup(row, response=self.http(self.body(row, status='PENDING')))
        self.assertFalse(effect); self.assertEqual(row.status, 'PENDING')
        self.assertLessEqual((row.reconcile_after-timezone.now()).total_seconds(), 15)
        row, effect = self.lookup(row, failure=requests.Timeout('sensitive-provider-text'))
        self.assertEqual(row.status, 'PENDING'); self.assertEqual(row.reconciliation_error, 'MTN_STATUS_TRANSPORT')
        PaymentIntent.objects.filter(pk=row.pk).update(initiated_at=timezone.now()-timedelta(seconds=301),
                                                      reconcile_after=timezone.now()-timedelta(seconds=1))
        with patch('mtn_momo.sandbox.requests.post', return_value=self.http({'access_token': 'synthetic-only'})), \
             patch('mtn_momo.sandbox.requests.get', return_value=self.http(self.body(row))):
            call_command('reconcile_sandbox_payments', run=True, stdout=StringIO())
        row.refresh_from_db(); self.assertEqual(row.status, 'SETTLED')
        self.assertEqual(EnergyAllocation.objects.count(), 1)

    def test_status_only_command_never_submits_settles_or_exposes_transaction_details(self):
        row = self.purchase(); output = StringIO()
        before = PaymentIntent.objects.values().get(pk=row.pk)
        with patch('mtn_momo.sandbox.requests.post', return_value=self.http({'access_token': 'private-access-token'})) as post, \
             patch('mtn_momo.sandbox.requests.get', return_value=self.http(self.body(row))) as get:
            call_command('inspect_mtn_sandbox_payment', reference=str(row.provider_reference), stdout=output)
            post.assert_not_called(); get.assert_not_called()
            output = StringIO()
            call_command('inspect_mtn_sandbox_payment', reference=str(row.provider_reference), lookup=True, stdout=output)
        self.assertEqual(PaymentIntent.objects.values().get(pk=row.pk), before)
        self.assertEqual(post.call_count, 1); self.assertTrue(post.call_args.args[0].endswith('/collection/token/'))
        data = json.loads(output.getvalue())
        self.assertEqual(data['provider_status'], 'SUCCESSFUL'); self.assertIn('MATCHED', data['validation'])
        self.assertFalse(data['writes']); self.assertFalse(data['submission_performed'])
        for secret in (row.sandbox_context['msisdn'], row.provider_external_id, 'private-access-token', 'synthetic-receipt'):
            self.assertNotIn(secret, output.getvalue())
        self.assertFalse(SandboxSettlement.objects.exists())

    def test_malformed_and_missing_identity_do_not_settle(self):
        row = self.submitted()
        for changes, code in (({'financialTransactionId': None}, 'EVIDENCE_TRANSACTION_ID'),
                              ({'financialTransactionId': 1.5}, 'EVIDENCE_TRANSACTION_ID'),
                              ({'financialTransactionId': True}, 'EVIDENCE_TRANSACTION_ID'),
                              ({'currency': 'UGX'}, 'EVIDENCE_CURRENCY'),
                              ({'externalId': 'wrong'}, 'EVIDENCE_EXTERNAL_ID'),
                              ({'payer': {'partyId': '0'+row.sandbox_context['msisdn']}}, 'EVIDENCE_PAYER'),
                              ({'amount': '999'}, 'EVIDENCE_AMOUNT')):
            with self.subTest(code=code):
                row, effect = self.lookup(row, response=self.http(self.body(row, **changes)))
                self.assertFalse(effect); self.assertEqual(row.status, 'PENDING')
                self.assertEqual(row.reconciliation_error, code)
        self.assertFalse(EnergyAllocation.objects.exists())

    def test_invalid_json_and_schema_are_not_transport_or_financial_failure(self):
        row = self.submitted()
        malformed = self.http()
        malformed.json.side_effect = requests.exceptions.JSONDecodeError('private-parser-body', 'private-document', 0)
        row, effect = self.lookup(row, response=malformed)
        self.assertFalse(effect); self.assertEqual(row.status, 'PENDING')
        self.assertEqual(row.reconciliation_error, 'MTN_STATUS_JSON')
        for body in ([], {'status': ['FAILED']}, {'status': 'unrecognized-private-value'}, {'status':'SUCCESSFUL', 'payer': ['private-data']}):
            with self.assertLogs('mtn_momo.diagnostics', level='WARNING') as logs:
                row, effect = self.lookup(row, response=self.http(body))
            self.assertFalse(effect); self.assertEqual(row.status, 'PENDING')
            self.assertEqual(row.reconciliation_error, 'MTN_STATUS_SCHEMA')
            self.assertNotIn('private', '\n'.join(logs.output))

    def test_unallowlisted_failure_reason_is_not_logged(self):
        row = self.submitted()
        with self.assertLogs('mtn_momo.diagnostics', level='WARNING') as logs:
            row, _ = self.lookup(row, response=self.http(self.body(row, status='FAILED',
                reason={'code':'secret-do-not-log', 'message':row.sandbox_context['msisdn']})))
        self.assertEqual(row.status, 'FAILED')
        self.assertIn('code=UNRECOGNIZED', '\n'.join(logs.output))
        self.assertNotIn('secret-do-not-log', '\n'.join(logs.output))

    def test_targeted_status_only_recovery_bypasses_old_backoff_without_submitting(self):
        row = self.purchase()
        PaymentIntent.objects.filter(pk=row.pk).update(reconcile_after=timezone.now()+timedelta(hours=1))
        with patch('mtn_momo.sandbox.requests.post', return_value=self.http({'access_token':'synthetic-only'})) as post, \
             patch('mtn_momo.sandbox.requests.get', return_value=self.http(self.body(row))) as get:
            output = StringIO()
            call_command('reconcile_sandbox_payments', reference=str(row.provider_reference), status_only=True, stdout=output)
            post.assert_not_called(); get.assert_not_called()
            self.assertIn(str(row.pk), output.getvalue())
            call_command('reconcile_sandbox_payments', reference=str(row.provider_reference), status_only=True, run=True, stdout=StringIO())
        self.assertEqual(post.call_count, 1)
        self.assertTrue(post.call_args.args[0].endswith('/collection/token/'))
        row.refresh_from_db(); self.assertEqual(row.status, 'SETTLED')
        self.assertEqual(EnergyAllocation.objects.count(), 1)
