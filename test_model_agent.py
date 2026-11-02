"""Local-only adapter security and capability tests; never contacts a provider."""
import copy
import json
import secrets
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from app import Engine, ROOT
from model_agent import ModelAdapter, validate_endpoint, capabilities, local_tool


class MockModel(BaseHTTPRequestHandler):
    requests = []
    replies = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        type(self).requests.append(body)
        message = type(self).replies.pop(0) if type(self).replies else {'role': 'assistant', 'content': 'Connected'}
        data = json.dumps({'choices': [{'message': message}]}).encode()
        self.send_response(200)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class AdapterChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), MockModel)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.endpoint = 'http://127.0.0.1:%d/v1/chat/completions' % cls.server.server_port
        cls.engine = Engine(ROOT / 'data')

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def setUp(self):
        MockModel.requests = []; MockModel.replies = []
        self.adapter = ModelAdapter([self.endpoint])
        self.body = {'endpoint': self.endpoint, 'model': 'local-mock', 'credential': secrets.token_urlsafe(24),
                     'dataset': self.engine.snapshot_sha256, 'acknowledged': True, 'record_egress': False,
                     'mode': 'test', 'messages': []}

    def test_consent_precedes_every_network_path(self):
        for update in ({'acknowledged': False}, {'dataset': 'other-dataset'}):
            with self.assertRaises(ValueError):
                self.adapter.complete(self.engine, {**self.body, **update})
        self.assertEqual(MockModel.requests, [])
        self.adapter.complete(self.engine, self.body)
        self.assertEqual(len(MockModel.requests), 1)
        self.assertNotIn(self.body['credential'], json.dumps(MockModel.requests))
        self.assertNotIn('SYN-001', json.dumps(MockModel.requests))

    def test_endpoint_policy(self):
        for endpoint in ('http://example.com/v1/chat/completions', 'https://127.0.0.1/v1/chat/completions',
                         'https://169.254.169.254/v1/chat/completions', 'https://user:pw@example.com/v1/chat/completions',
                         'https://example.com:8443/v1/chat/completions', 'https://example.com/v1/chat/completions?x=1',
                         'file:///etc/passwd', self.endpoint):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                validate_endpoint(endpoint, [])
        self.assertEqual(validate_endpoint(self.endpoint, [self.endpoint])[1], '127.0.0.1')
        with patch('model_agent.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('93.184.216.34', 443))]):
            self.assertEqual(validate_endpoint('https://example.com/v1/chat/completions', [])[1], '93.184.216.34')
        with patch('model_agent.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('10.0.0.1', 443))]):
            with self.assertRaises(ValueError): validate_endpoint('https://example.com/v1/chat/completions', [])

    def test_unsupported_alignment_and_source_units(self):
        spec = self.engine.default_spec()
        for anchor in ('randomization', 'unmapped_anchor'):
            result = local_tool(self.engine, spec, 'set_alignment', {'anchor': anchor})
            self.assertEqual(result['status'], 'unsupported')
            self.assertIn('development task', result['note'])
        self.assertIn('first_PR', capabilities(self.engine)['alignment']['supported_anchors'])
        for anchor in ('first_dose', 'first_PR'):
            self.assertEqual(local_tool(self.engine, spec, 'set_alignment', {'anchor': anchor})['status'], 'resolved')
        q = local_tool(self.engine, spec, 'query_data', {'scope': 'current_analysis', 'unit': 'AE records', 'filters': {}})
        self.assertEqual(q['count'], len(q['record_ids']))
        self.assertEqual(q['record_ids'], ['AE-001-1', 'AE-001-2', 'AE-002-1'])
        original = copy.deepcopy(spec)
        proposal = local_tool(self.engine, spec, 'propose_analysis_subset', {'patients': ['SYN-001']})
        self.assertEqual(spec, original)
        self.assertEqual(proposal['status'], 'confirmation_required')
        self.assertEqual(proposal['after']['patients'], 1)

    def test_tool_results_minimized_and_credentials_redacted(self):
        self.body.update(mode='turn', spec=self.engine.default_spec(), view={'sort': 'asc', 'tier': 'auto'},
                         messages=[{'role': 'user', 'content': 'count AE records'},
                                   {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'c', 'type': 'function', 'function': {'name': 'query_data', 'arguments': '{}'}}]},
                                   {'role': 'tool', 'tool_call_id': 'c', 'content': json.dumps({'count': 3, 'unit': 'AE records', 'record_ids': ['AE-001-1'], 'patient_keys': [['SYN-SPIKE', 'SYN-001']]})}])
        MockModel.replies = [{'role': 'assistant', 'content': self.body['credential']}]
        result = self.adapter.complete(self.engine, self.body)
        self.assertNotIn(self.body['credential'], json.dumps(result))
        sent = MockModel.requests[0]
        self.assertNotIn('AE-001-1', json.dumps(sent))
        self.assertNotIn('SYN-001', json.dumps(sent))
        self.assertIn('AE records', json.dumps(sent))
        self.body['record_egress'] = True
        self.adapter.complete(self.engine, self.body)
        self.assertIn('AE-001-1', json.dumps(MockModel.requests[-1]))


if __name__ == '__main__':
    unittest.main()
