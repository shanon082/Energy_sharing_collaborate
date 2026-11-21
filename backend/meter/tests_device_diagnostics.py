"""Correlation/stage visibility with no sensitive messages or traceback locals."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch
import uuid

from django.http import HttpResponse
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from rest_framework.test import APIRequestFactory
from backend.hosting_middleware import FreeTestingMiddleware
from meter.api.prototype_views import PrototypeRedeemView
from meter.diagnostics import mark_stage
from meter.prototype_device import fail
from meter.tests_mtn_device import LAB, MTNFixture
from meter.models import MeterDelivery, PrototypeCommand

RID = '10000000-0000-4000-8000-000000000001'
SECRET = 'private-test-credential-never-log'
TOKEN = '000123456789012'


class DeviceDiagnosticTests(SimpleTestCase):
    def request(self, rid=RID, body=None):
        return APIRequestFactory().post('/api/v1/prototype-device/v1/redeem/', body or {'token': TOKEN}, format='json',
                                       HTTP_X_REQUEST_ID=rid, HTTP_X_DEVICE_TOKEN=SECRET, HTTP_AUTHORIZATION='Bearer '+SECRET)

    def call_failure(self, code, stage='authentication', rid=RID):
        def rejected(_request):
            mark_stage(stage)
            fail(code, SECRET+' '+TOKEN, 404)
        with patch('meter.prototype_device.authenticate', side_effect=rejected), self.assertLogs('meter.device', level='WARNING') as logs:
            response = PrototypeRedeemView.as_view()(self.request(rid))
        return response, logs

    def assert_redacted(self, logs):
        text='\n'.join(logs.output)
        self.assertNotIn(SECRET,text);self.assertNotIn(TOKEN,text)
        for record in logs.records:
            self.assertIsNone(record.exc_info)
            self.assertNotIn('request',record.__dict__)

    def test_known_failure_visible_without_enabling_debug_or_global_info(self):
        response, logs = self.call_failure('TOKEN_LOOKUP_MISS', 'token_lookup')
        self.assertEqual(response['X-Request-ID'],RID)
        self.assertEqual(response.data['request_id'],RID)
        self.assertEqual(response.data['code'],'TOKEN_UNAVAILABLE')
        self.assertIn('stage=token_lookup code=TOKEN_LOOKUP_MISS',logs.output[0])
        self.assert_redacted(logs)

    def test_arbitrary_code_and_sensitive_message_are_never_logged(self):
        response,logs=self.call_failure(TOKEN+'-untrusted-content')
        self.assertEqual(response.data['code'],'HTTP_404')
        self.assert_redacted(logs)

    def test_credit_reconciliation_failure_keeps_its_fixed_protocol_code(self):
        _,logs=self.call_failure('CREDIT_CONSERVATION','credit_reconciliation')
        self.assertIn('stage=credit_reconciliation code=CREDIT_CONSERVATION',logs.output[0])
        for code in ('DEVICE_STORAGE_REQUIRED','DEVICE_STORAGE_RESET'):
            _,logs=self.call_failure(code,'request_validation')
            self.assertIn('stage=credit_reconciliation code='+code,logs.output[0])

    def test_missing_and_other_meter_tokens_have_identical_public_errors(self):
        missing, a=self.call_failure('TOKEN_UNAVAILABLE','token_lookup')
        elsewhere,b=self.call_failure('TOKEN_UNAVAILABLE','meter_environment_mismatch')
        self.assertEqual(missing.data,elsewhere.data)
        self.assertEqual(missing.status_code,elsewhere.status_code)
        self.assertIn('stage=token_lookup code=TOKEN_LOOKUP_MISS',a.output[0])
        self.assertIn('stage=meter_environment_mismatch code=TOKEN_UNAVAILABLE',b.output[0])

    def test_invalid_correlation_header_never_echoes_or_logs_input(self):
        response,logs=self.call_failure('DEVICE_UNAUTHORIZED',rid=TOKEN)
        generated=response['X-Request-ID']
        self.assertEqual(uuid.UUID(generated).version,4)
        self.assertNotEqual(generated,TOKEN);self.assert_redacted(logs)

    def test_unexpected_exception_is_generic_with_sanitized_stack_only(self):
        def broken(_device,_body):
            secret_local=SECRET+' '+TOKEN
            mark_stage('token_lookup')
            raise RuntimeError(secret_local)
        broken.__name__='redeem'
        for debug in (False,True):
            with override_settings(DEBUG=debug), patch('meter.prototype_device.authenticate',return_value=object()), patch.object(PrototypeRedeemView,'operation',staticmethod(broken)), self.assertLogs('meter.device',level='ERROR') as logs:
                response=PrototypeRedeemView.as_view()(self.request())
            self.assertEqual(response.status_code,500)
            self.assertEqual(response.data['code'],'INTERNAL_ERROR')
            self.assertEqual(response.data['request_id'],RID)
            self.assertIn('stage=token_lookup code=INTERNAL_ERROR traceback=',logs.output[0])
            self.assertIn('tests_device_diagnostics.py:',logs.output[0])
            self.assertNotIn(SECRET,str(response.data));self.assertNotIn(TOKEN,str(response.data));self.assert_redacted(logs)

    def test_unserializable_response_is_generic_and_does_not_escape_with_locals(self):
        import json
        def malformed(_device,_body):
            secret_local=SECRET
            return {'value':object(), 'private':secret_local}
        malformed.__name__='redeem'
        with patch('meter.prototype_device.authenticate',return_value=object()),patch.object(PrototypeRedeemView,'operation',staticmethod(malformed)),self.assertLogs('meter.device',level='ERROR') as logs:
            response=PrototypeRedeemView.as_view()(self.request())
        self.assertEqual(response.status_code,500)
        self.assertEqual(json.loads(response.content)['request_id'],RID)
        self.assertIn('stage=response_serialization code=INTERNAL_ERROR',logs.output[0])
        self.assert_redacted(logs);self.assertNotIn(SECRET,response.content.decode())

    def test_success_is_observable_if_device_later_rejects_the_command(self):
        from meter.diagnostics import logger
        def result(_device,_body):return {'ok':True}
        result.__name__='redeem'
        with patch('meter.prototype_device.authenticate',return_value=object()),patch.object(PrototypeRedeemView,'operation',staticmethod(result)),patch.object(logger,'handle') as records:
            response=PrototypeRedeemView.as_view()(self.request())
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data,{'ok':True})
        self.assertEqual(records.call_count,1)
        record=records.call_args.args[0]
        self.assertIn('http=200 stage=complete code=HTTP_200',record.getMessage())
        self.assertIn('request_id='+RID,record.getMessage())
        self.assertNotIn(SECRET,record.getMessage());self.assertNotIn(TOKEN,record.getMessage())

    def test_bad_json_is_request_validation_not_transport_or_token_lookup(self):
        request=APIRequestFactory().post('/api/v1/prototype-device/v1/redeem/',data='{'+TOKEN,content_type='application/json',HTTP_X_REQUEST_ID=RID)
        with patch('meter.prototype_device.authenticate',return_value=object()), self.assertLogs('meter.device',level='WARNING') as logs:
            response=PrototypeRedeemView.as_view()(request)
        self.assertEqual(response.status_code,400)
        self.assertIn('stage=request_validation code=REQUEST_INVALID',logs.output[0]);self.assert_redacted(logs)

    def test_concurrent_request_context_does_not_cross_ids_or_stages(self):
        barrier=Barrier(2)
        def rejected(_device,body):
            mark_stage(body['stage']);barrier.wait(timeout=10)
            fail('TOKEN_UNAVAILABLE','Generic token rejection',404)
        rejected.__name__='redeem'
        items=[(RID,'token_lookup'),('10000000-0000-4000-8000-000000000002','meter_environment_mismatch')]
        def call(item):return PrototypeRedeemView.as_view()(self.request(item[0],{'stage':item[1]}))
        with patch('meter.prototype_device.authenticate',return_value=object()),patch.object(PrototypeRedeemView,'operation',staticmethod(rejected)),self.assertLogs('meter.device',level='WARNING') as logs,ThreadPoolExecutor(max_workers=2) as pool:
            replies=list(pool.map(call,items))
        for rid,stage in items:
            lines=[line for line in logs.output if 'request_id='+rid in line]
            self.assertEqual(len(lines),1);self.assertIn('stage='+stage,lines[0])
        self.assertEqual([reply['X-Request-ID'] for reply in replies],[item[0] for item in items])

    @override_settings(CONSUMER_SANDBOX_ENABLED=False)
    def test_hosting_denial_correlates_without_enabling_route(self):
        downstream=SimpleNamespace(called=False)
        def never(_request):downstream.called=True;raise AssertionError('Must remain blocked')
        with self.assertLogs('meter.device',level='WARNING') as logs:
            response=FreeTestingMiddleware(never)(self.request())
        self.assertFalse(downstream.called);self.assertEqual(response.status_code,503)
        self.assertEqual(response['X-Request-ID'],RID);self.assertIn('stage=hosting_policy',logs.output[0])

    def test_missing_route_correlates_and_other_routes_are_unchanged(self):
        with patch('meter.prototype_device.enabled',return_value=True),self.assertLogs('meter.device',level='WARNING') as logs:
            response=FreeTestingMiddleware(lambda _:HttpResponse(status=404))(self.request())
        self.assertEqual(response.status_code,404);self.assertEqual(response['X-Request-ID'],RID)
        self.assertIn('stage=request_routing',logs.output[0])
        response=FreeTestingMiddleware(lambda _:HttpResponse())(APIRequestFactory().get('/api/v1/features/'))
        self.assertFalse(response.has_header('X-Request-ID'))


@override_settings(**LAB)
class DeviceDiagnosticFlowTests(MTNFixture, TransactionTestCase):
    def test_real_lookup_and_meter_mismatch_stage_and_redaction(self):
        code=self.token();self.start()
        with self.assertLogs('meter.device',level='WARNING') as logs:
            unknown=self.redeem('000000000000000',status=404)
        self.assertEqual(unknown['code'],'TOKEN_UNAVAILABLE')
        self.assertIn('stage=token_lookup code=TOKEN_LOOKUP_MISS',logs.output[0])
        from meter.sandbox_enrollment import enroll_sandbox_meter
        other_meter, _ = enroll_sandbox_meter(self.owner, '00000000991')
        payment=self.purchase(meter=other_meter);self.settle(payment)
        from meter.models import EnergyKeypadToken
        from meter.energy_tokens import token_record
        other_code=token_record(EnergyKeypadToken.objects.get(allocation__purchase_intent=payment))['token']
        with self.assertLogs('meter.device',level='WARNING') as logs:
            mismatch=self.redeem(other_code,status=404)
        self.assertEqual(mismatch['code'],unknown['code'])
        self.assertEqual(mismatch['message'],unknown['message'])
        self.assertIn('stage=meter_environment_mismatch code=TOKEN_UNAVAILABLE',logs.output[0])
        self.assertNotIn(other_code,'\n'.join(logs.output));self.assertFalse(MeterDelivery.objects.exists())

    def test_source_used_pending_and_conflicting_stages_preserve_credit_checks(self):
        first=self.token();self.start()
        with patch('meter.prototype_device.authorized_source',return_value=False),self.assertLogs('meter.device',level='WARNING') as logs:
            self.redeem(first,status=409)
        self.assertIn('stage=source_eligibility code=TOKEN_SOURCE_UNVERIFIED',logs.output[0])
        self.assertFalse(MeterDelivery.objects.exists())
        command=self.redeem(first)['command']
        second=self.token()
        with self.assertLogs('meter.device',level='WARNING') as logs:
            self.redeem(second,status=409)
        self.assertIn('stage=pending_delivery code=PENDING_COMMAND',logs.output[0])
        self.post('ack',self.receipt(command))
        with self.assertLogs('meter.device',level='WARNING') as logs:
            self.redeem(first,counter=1,status=409)
        self.assertIn('stage=already_used_token code=TOKEN_ALREADY_USED',logs.output[0])
        with self.assertLogs('meter.device',level='WARNING') as logs:
            self.redeem(second,counter=0,status=409)
        self.assertIn('stage=conflicting_command code=RECONCILIATION_REQUIRED',logs.output[0])
        self.assertEqual(MeterDelivery.objects.count(),1)

    def test_request_ids_do_not_change_pending_command_digest_or_ack_idempotency(self):
        code=self.token();self.start()
        ids=[str(uuid.uuid4()) for _ in range(4)]
        self.device_headers['HTTP_X_REQUEST_ID']=ids[0];first=self.redeem(code)
        self.assertNotIn('request_id',first)
        self.device_headers['HTTP_X_REQUEST_ID']=ids[1];retry=self.redeem(code)
        self.assertEqual(first,retry);self.assertEqual(len(first['command']),14)
        receipt=self.receipt(first['command'])
        for rid in ids[2:]:
            self.device_headers['HTTP_X_REQUEST_ID']=rid;self.post('ack',receipt)
        self.assertEqual(MeterDelivery.objects.count(),1);self.assertEqual(PrototypeCommand.objects.count(),1)
        self.device.refresh_from_db();self.assertEqual(self.device.application_counter,1)
