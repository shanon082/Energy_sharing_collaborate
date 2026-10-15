"""Offline regression tests: no provider requests or real environment changes."""
import contextlib
import io
import json
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

HELPER = Path(__file__).with_name('provision-mtn-sandbox.py')
LEAK = 'secret-do-not-print'


def response(status, body):
    result = Mock(status_code=status)
    result.json.return_value = body
    return result


class ProvisioningTests(unittest.TestCase):
    def run_helper(self, outcomes, existing_record=False, save_failure=False):
        with tempfile.TemporaryDirectory() as directory:
            env = Path(directory) / 'backend.env'
            original = 'DB_PASSWORD=unchanged\nSMTP_PASSWORD=unchanged\n'
            env.write_text(original)
            env.chmod(0o600)
            record = env.with_name('.mtn-sandbox-provisioning.json')
            if existing_record:
                record.write_text('{}')
            output = io.StringIO()
            with patch('sys.argv', [str(HELPER), '--env-file', str(env), '--provision']), patch('builtins.input', return_value='SANDBOX'), patch('getpass.getpass', return_value=LEAK), patch('requests.post', side_effect=outcomes) as post, contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                with contextlib.ExitStack() as stack:
                    if save_failure:
                        stack.enter_context(patch('os.replace', side_effect=OSError(LEAK)))
                    try:
                        runpy.run_path(str(HELPER), run_name='__main__')
                    except SystemExit as exc:
                        output.write(str(exc))
            text = output.getvalue()
            self.assertNotIn(LEAK, text)
            if record.exists() and not existing_record:
                self.assertNotIn(json.loads(record.read_text())['api_user_reference'], text)
                self.assertEqual(record.stat().st_mode & 0o777, 0o600)
            return text, post.call_count, env.read_text(), record.exists(), original

    def test_http_user_rejection(self):
        text, calls, content, record, original = self.run_helper([response(409, {'code': 'RESOURCE_ALREADY_EXIST', 'message': LEAK})])
        for expected in ('stage=API-user creation', 'HTTP status=409', 'provider code=RESOURCE_ALREADY_EXIST', 'may still have been created'):
            self.assertIn(expected, text)
        self.assertEqual(calls, 1)
        self.assertEqual(content, original)
        self.assertTrue(record)

    def test_unknown_code_withheld(self):
        text, *_ = self.run_helper([response(401, {'code': LEAK, 'message': LEAK})])
        self.assertIn('withheld_or_unavailable', text)

    def test_network_errors(self):
        for exception, category in ((requests.exceptions.SSLError(LEAK), 'TLS error'), (requests.exceptions.Timeout(LEAK), 'network timeout'), (requests.exceptions.ConnectionError(LEAK), 'network connection error')):
            with self.subTest(category=category):
                text, *_ = self.run_helper([exception])
                self.assertIn(category, text)
                self.assertIn('HTTP status=unavailable', text)

    def test_key_rejection(self):
        text, calls, content, record, original = self.run_helper([response(201, {}), response(503, {'errorCode': 'SERVICE_UNAVAILABLE'})])
        self.assertIn('stage=API-key creation', text)
        self.assertIn('HTTP status=503', text)
        self.assertIn('creation was confirmed', text)
        self.assertEqual(content, original)
        self.assertEqual(calls, 2)

    def test_invalid_success(self):
        for body in ({'apiKey': LEAK + '\n'}, [], {}):
            text, *_ = self.run_helper([response(201, {}), response(201, body)])
            self.assertIn('invalid success response', text)
            self.assertIn('HTTP status=201', text)

    def test_retry_blocked(self):
        text, calls, *_ = self.run_helper([], existing_record=True)
        self.assertEqual(calls, 0)
        self.assertIn('resolve remote state', text)

    def test_save_failure(self):
        text, _, content, record, original = self.run_helper([response(201, {}), response(201, {'apiKey': LEAK})], save_failure=True)
        self.assertIn('after remote user/key creation', text)
        self.assertEqual(content, original)
        self.assertTrue(record)

    def test_success_preserves_configuration(self):
        text, calls, content, record, original = self.run_helper([response(201, {}), response(201, {'apiKey': LEAK})])
        self.assertTrue(content.startswith(original))
        self.assertIn("MTN_SANDBOX_API_KEY='" + LEAK + "'", content)
        self.assertFalse(record)
        self.assertEqual(calls, 2)
        self.assertIn('stored privately', text)


if __name__ == '__main__':
    unittest.main()
