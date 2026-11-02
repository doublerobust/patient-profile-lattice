"""Deterministic browser -> real adapter -> scripted loopback model acceptance.

No external model, recorded provider responses, or persistent credential fixtures.
Unexpected mock calls fail closed rather than returning a convenient default.
"""
import contextlib
import hashlib
import io
import json
import secrets
import socket
import tempfile
import threading
import unittest
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from playwright.sync_api import expect, sync_playwright
from app import Engine, ROOT, make_handler
from waitfor import wait_for


def tool(name, args):
    return {'role': 'assistant', 'content': None, 'tool_calls': [
        {'id': 'call-' + name, 'type': 'function',
         'function': {'name': name, 'arguments': json.dumps(args)}}]}


def prose(text='Script complete'):
    return {'role': 'assistant', 'content': text}


def scope_tool(prompt, name, args):
    return tool('propose_display_scope', {'intent': 'display_patients' if name == 'set_view' else 'highlight_records',
                'evidence': prompt, 'action': {'tool': name, 'args': args}})


class ScriptedEndpoint(BaseHTTPRequestHandler):
    """All state is per-server; auth is checked but never recorded in a transcript."""
    def do_POST(self):
        server = self.server
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        server.requests.append(body)
        if self.path != '/v1/chat/completions':
            server.failures.append('Wrong OpenAI-compatible path')
        if self.headers.get('Authorization') != 'Bearer ' + server.credential:
            server.failures.append('Missing or incorrect session authentication')
        if body.get('model') != 'scripted-local-model' or body.get('stream') is not False:
            server.failures.append('Wrong model or streaming contract')
        if not server.script:
            server.failures.append('Unexpected model request: script exhausted')
            step = {'status': 500, 'message': prose('Unexpected request')}
        else:
            step = server.script.popleft()
        server.received.set()
        if step.get('gate') and not step['gate'].wait(10):
            server.failures.append('Response gate timed out')
        data = json.dumps({'choices': [{'message': step['message']}]}).encode()
        self.send_response(step.get('status', 200))
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class ModelAgentE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = ThreadingHTTPServer(('127.0.0.1', 0), ScriptedEndpoint)
        cls.model_thread = threading.Thread(target=cls.model.serve_forever, daemon=True)
        cls.model_thread.start()
        cls.endpoint = 'http://127.0.0.1:%d/v1/chat/completions' % cls.model.server_port
        cls.engine = Engine(ROOT / 'data')
        cls.app = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(cls.engine, [cls.endpoint]))
        cls.app_thread = threading.Thread(target=cls.app.serve_forever, daemon=True)
        cls.app_thread.start()
        cls.origin = 'http://127.0.0.1:%d' % cls.app.server_port
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        for server, thread in [(cls.app, cls.app_thread), (cls.model, cls.model_thread)]:
            server.shutdown()
            server.server_close()
            thread.join()

    def setUp(self):
        self.model.requests = []
        self.model.script = deque()
        self.model.failures = []
        self.model.received = threading.Event()
        self.model.credential = secrets.token_urlsafe(32)
        self.gates = []
        self.logs = io.StringIO()
        self.capture = contextlib.redirect_stderr(self.logs)
        self.capture.__enter__()
        self.addCleanup(self.capture.__exit__, None, None, None)
        self.context = self.browser.new_context(viewport={'width': 1440, 'height': 1100}, accept_downloads=True)
        self.page = self.context.new_page()
        self.errors, self.console, self.external = [], [], []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.on('console', lambda message: self.console.append(message.text))
        # A browser-side direct-provider implementation must not silently pass.
        def local_only(route):
            if route.request.url.startswith(self.origin + '/'):
                route.continue_()
            else:
                self.external.append(route.request.url)
                route.abort()
        self.context.route('**/*', local_only)
        self.page.goto(self.origin + '/lattice')
        wait_for(self.page, 'window.viewChatBridge && window.lattice && lattice.ready && !busy')
        self.page.emulate_media(reduced_motion='reduce')
        self.page.locator('#chat-toggle').click()
        self.page.locator('#agent-config summary').click()
        self.page.locator('#agent-endpoint').fill(self.endpoint)
        self.page.locator('#agent-model').fill('scripted-local-model')
        self.page.locator('#agent-key').fill(self.model.credential)

    def tearDown(self):
        for gate in self.gates:
            gate.set()
        self.context.close()
        self.assertEqual(self.errors, [], 'Browser raised an uncaught error')
        self.assertEqual(self.external, [], 'Browser attempted non-adapter egress')
        self.assertEqual(self.model.failures, [])
        self.assertEqual(len(self.model.script), 0, 'Expected model response was never consumed')
        self.no_secret(self.logs.getvalue(), 'server logs')
        self.no_secret(json.dumps(self.console), 'browser console')
        self.no_secret(json.dumps(self.model.requests), 'mock request transcript')

    def no_secret(self, value, surface):
        # Do not echo a credential in a failing unittest assertion.
        needle = self.model.credential.encode() if isinstance(value, bytes) else self.model.credential
        self.assertTrue(needle not in value, 'Session credential leaked into ' + surface)

    def script(self, *messages):
        self.assertFalse(self.model.script, 'Previous request did not finish its script')
        self.model.script.extend({'message': message} for message in messages)

    def settled(self):
        expect(self.page.locator('#agent-test')).to_be_enabled()
        expect(self.page.locator('#chat-tool-status')).not_to_contain_text('validating')

    def confirm_egress(self):
        expect(self.page.locator('#agent-egress-dialog')).to_be_visible()
        self.page.locator('#agent-consent').check()
        self.page.locator('#agent-egress-confirm').click()

    def connect(self):
        self.script(prose('Local self-test succeeded'))
        self.page.locator('#agent-test').click()
        self.confirm_egress()
        self.settled()
        expect(self.page.locator('#agent-status')).to_contain_text('Model-driven agent')

    def ask(self, prompt, *messages):
        self.script(*messages)
        self.page.locator('#chat-request').fill(prompt)
        self.page.locator('#agent-send').click()
        self.settled()

    def snapshot(self):
        return self.page.evaluate('({display:viewChatBridge.snapshot(),analysis:viewChatBridge.analysisSnapshot(),record_ids:viewChatBridge.records(),qualifying:state.analysis.qualifying_ae_record_ids})')

    def history(self):
        return json.loads(self.page.locator('#chat-history').text_content())

    def approve_scope(self, prompt, name, args):
        before = self.snapshot()
        self.ask(prompt, scope_tool(prompt, name, args))
        self.assertEqual(self.snapshot(), before, 'Proposal must not mutate')
        expect(self.page.locator('#agent-scope-proposal')).to_be_visible()
        self.page.locator('#agent-scope-confirm').click()
        self.settled()

    def test_01_multiturn_validated_change_matches_history_and_protocol(self):
        self.connect()
        before = self.snapshot()
        args = {'sort': 'desc', 'layers': ['AE', 'EX'], 'tier': '2'}
        self.ask('Sort descending; show AE and EX at tier 2',
                 tool('get_capabilities', {}), tool('set_view', args), prose())
        after = self.snapshot()
        self.assertEqual(after['analysis'], before['analysis'])
        self.assertEqual(after['display']['sort'], 'desc')
        self.assertEqual(after['display']['tier'], '2')
        self.assertEqual(after['display']['view']['hidden_lanes'], ['CM', 'RS'])
        entries = self.history()
        self.assertEqual([e['action']['tool'] for e in entries], ['get_capabilities', 'set_view'])
        entry = entries[-1]
        self.assertEqual(entry['action']['args'], args)
        self.assertEqual(entry['record_ids'], before['record_ids'])
        self.assertEqual(entry['diff']['display'], {'before': before['display'], 'after': after['display']})
        self.assertNotIn('analysis', entry['diff'])
        self.assertEqual(entry['controls']['undo']['entry_id'], entry['id'])
        requests = self.model.requests
        self.assertEqual(len(requests), 4)
        self.assertEqual(requests[0]['tool_choice'], 'none')
        self.assertEqual([m['role'] for m in requests[-1]['messages']],
                         ['system', 'user', 'assistant', 'tool', 'assistant', 'tool'])
        for index, name in [(2, 'get_capabilities'), (3, 'set_view')]:
            self.assertEqual(requests[index]['messages'][-1]['tool_call_id'], 'call-' + name)
        self.assertEqual(json.loads(requests[-1]['messages'][-1]['content'])['status'], 'executed')
        self.assertNotIn('AE-001-1', json.dumps(requests))
        # A model cannot smuggle an analysis mutation alongside a valid display field.
        self.ask('Malformed mutation', tool('set_view', {'sort': 'asc', 'analysis_state': {}}))
        self.assertEqual(self.snapshot(), after)
        self.assertEqual(self.history(), entries)
        expect(self.page.locator('#chat-result')).to_contain_text('Unsupported fields')

    def test_02_unsupported_alignment_offers_development_without_transform(self):
        self.connect()
        before = self.snapshot()
        self.ask('Align by randomization day', tool('set_alignment', {'anchor': 'randomization'}))
        expect(self.page.locator('#chat-result')).to_contain_text('development task')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.history(), [])
        tools = {t['function']['name'] for t in self.model.requests[-1]['tools']}
        self.assertIn('propose_development_task', tools)
        self.ask('Propose implementation of the unavailable randomization anchor',
                 tool('propose_development_task', {'description': 'Randomization anchor unavailable; add source mapping, not an approximation.'}))
        self.assertEqual(self.snapshot(), before)
        task = json.loads(self.page.locator('#chat-tasks').text_content())[0]
        self.assertFalse(task['result_created'])
        self.assertEqual(task['status'], 'proposed')
        self.assertEqual(self.history()[-1]['action']['args']['task'], task)

    def test_03_analysis_requires_confirmation_cancel_and_undo_restore_ids(self):
        self.connect()
        self.approve_scope('Highlight source IDs AE-002-1', 'highlight_events',
                           {'scope': 'current_analysis', 'filters': {'record_ids': ['AE-002-1']}})
        before, entries = self.snapshot(), self.history()
        proposal = tool('propose_analysis_subset', {'patients': ['SYN-001']})
        for confirm in (False, True):
            self.ask('Subset ANALYSIS population to SYN-001', proposal)
            self.assertEqual(self.snapshot(), before)
            self.assertEqual(self.history(), entries)
            expect(self.page.locator('#agent-proposal')).to_be_visible()
            consequence = json.loads(self.page.locator('#agent-consequence').text_content())
            self.assertEqual(consequence['before'], {'patients': 2, 'AE records': 3})
            self.assertEqual(consequence['after'], {'patients': 1, 'AE records': 2})
            expect(self.page.locator('#agent-send')).to_be_disabled()
            names = [t['function']['name'] for t in self.model.requests[-1]['tools']]
            self.assertNotIn('confirm_analysis_subset', names)
            count = len(self.model.requests)
            self.page.locator('#agent-confirm' if confirm else '#agent-cancel').click()
            self.settled()
            self.assertEqual(len(self.model.requests), count, 'Human confirmation must remain local')
            if not confirm:
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(self.history(), entries)
        changed = self.snapshot()
        self.assertEqual(changed['analysis']['population'], [['SYN-SPIKE', 'SYN-001']])
        self.assertEqual(changed['qualifying'], ['AE-001-1', 'AE-001-2'])
        self.assertEqual(changed['display']['highlights'], [])
        self.assertEqual(self.history()[-1]['action']['tool'], 'confirm_analysis_subset')
        self.assertEqual(self.history()[-1]['record_ids'], changed['qualifying'])
        self.page.locator('#chat-undo').click()
        self.settled()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.history(), entries)
        expect(self.page.locator('#chat-records')).to_have_text('AE-002-1')

    def test_04_ambiguity_and_model_confirmation_attempt_do_not_mutate(self):
        self.connect()
        before = self.snapshot()
        self.ask('grade 3 AEs', tool('clarify_request',
                 {'question': 'Which counting unit, window, anchor, and display or analysis operation?'}))
        expect(self.page.locator('#chat-result')).to_contain_text('Which counting unit')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.history(), [])
        self.ask('Try to confirm without a human', tool('confirm_analysis_subset', {'patients': ['SYN-001']}))
        expect(self.page.locator('#chat-result')).to_contain_text('Unsupported tool')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.history(), [])

    def test_05_undo_restores_nonempty_source_ids_not_just_empty_state(self):
        self.connect()
        for ids in (['AE-001-1', 'AE-001-2'], ['AE-002-1']):
            if ids == ['AE-002-1']:
                before, entries = self.snapshot(), self.history()
            self.approve_scope('Highlight source IDs ' + ', '.join(ids), 'highlight_events',
                               {'scope': 'current_analysis', 'filters': {'record_ids': ids}})
            self.assertEqual(self.snapshot()['display']['highlights'], ids)
            self.assertEqual(self.history()[-1]['record_ids'], ids)
        self.page.locator('#chat-undo').click()
        self.settled()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.history(), entries)
        self.assertEqual(self.page.locator('#chat-records').text_content().splitlines(), ['AE-001-1', 'AE-001-2'])

    def test_07_credential_absent_from_storage_download_replay_logs_and_fixtures(self):
        fixtures = [p for directory in ('data', 'test-fixtures') for p in (ROOT / directory).rglob('*') if p.is_file()]
        hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in fixtures}
        self.connect()
        self.ask('Count AE records', tool('query_data', {'scope': 'current_analysis', 'unit': 'AE records', 'filters': {}}),
                 prose(self.model.credential))
        expect(self.page.locator('#chat-result')).to_contain_text('3 AE records')
        expect(self.page.locator('#chat-result')).to_contain_text('[REDACTED]')
        self.assertEqual(self.history()[-1]['record_ids'], ['AE-001-1', 'AE-001-2', 'AE-002-1'])
        self.page.locator('#chat-toggle').click()
        self.page.locator('#save').click()
        expect(self.page.locator('#replay-result')).to_contain_text('Saved exact normalized review')
        stored = self.page.evaluate('Object.values(localStorage)')
        self.assertTrue(stored, 'Save must produce a real localStorage package')
        with self.page.expect_download() as downloaded:
            self.page.locator('#download').click()
        with tempfile.TemporaryDirectory(prefix='e2e-download-', dir=ROOT) as directory:
            path = Path(directory) / 'review.json'
            downloaded.value.save_as(path)
            package_text = path.read_text()
            package = json.loads(package_text)
            self.assertEqual(package['spec'], json.loads(stored[0])['spec'])
            self.no_secret(package_text, 'downloaded review')
            # Import the actual downloaded bytes and exercise the replay endpoint.
            self.page.locator('#import').set_input_files(str(path))
            expect(self.page.locator('#replay-result')).to_contain_text('Replay verified')
        for label, value in [('localStorage', json.dumps(stored)),
                             ('sessionStorage', self.page.evaluate('JSON.stringify(sessionStorage)')),
                             ('history', json.dumps(self.history())), ('DOM', self.page.content()),
                             ('replay state', json.dumps(self.snapshot()))]:
            self.no_secret(value, label)
        self.page.reload()
        wait_for(self.page, 'window.viewChatBridge && window.lattice && lattice.ready')
        self.page.locator('#chat-toggle').click()
        expect(self.page.locator('#agent-status')).to_contain_text('No model is connected')
        expect(self.page.locator('#agent-key')).to_have_value('')
        expect(self.page.locator('#agent-send')).to_be_disabled()
        for path in fixtures:
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), hashes[path], 'Fixture changed: ' + str(path.relative_to(ROOT)))
            self.no_secret(path.read_bytes(), 'fixture ' + str(path.relative_to(ROOT)))

    def test_08_http_endpoint_policy_rejects_ssrf_before_socket_creation(self):
        # Deterministic DNS answers: never resolve or contact a real public host.
        endpoints = ['http://public.example/v1/chat/completions',
                     'file:///etc/passwd', 'https://user:pw@public.example/v1/chat/completions',
                     'https://public.example:8443/v1/chat/completions',
                     'http://127.0.0.1:1/v1/chat/completions',
                     'http://localhost:%d/v1/chat/completions' % self.model.server_port,
                     'https://public.example/v1/chat/completions?token=bad',
                     'https://public.example/v1/chat/completions#fragment']
        body = {'model': 'scripted-local-model', 'credential': '', 'dataset': self.engine.snapshot_sha256,
                'acknowledged': True, 'mode': 'test', 'messages': []}
        def submit(endpoint):
            return self.page.evaluate('''async body => {const r=await fetch('/api/agent/model', {
                method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
                return {status:r.status,body:await r.json()};}''', {**body, 'endpoint': endpoint})
        with patch('model_agent.socket.create_connection', side_effect=AssertionError('Unexpected outbound socket')) as connect:
            for endpoint in endpoints:
                with self.subTest(endpoint=endpoint):
                    self.assertEqual(submit(endpoint)['status'], 400)
            for ips in (['10.0.0.1'], ['172.16.0.1'], ['192.168.1.1'], ['169.254.169.254'],
                        ['127.0.0.2'], ['0.0.0.0'], ['::1'], ['fc00::1'], ['fe80::1'],
                        ['::ffff:127.0.0.1'], ['93.184.216.34', '10.0.0.1'], []):
                answers = [(socket.AF_INET6 if ':' in ip else socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, 443)) for ip in ips]
                with self.subTest(addresses=ips), patch('model_agent.socket.getaddrinfo', return_value=answers):
                    response = submit('https://public.example/v1/chat/completions')
                    self.assertEqual(response['status'], 400)
                    self.assertIn('public Internet addresses', response['body']['error'])
            connect.assert_not_called()
        self.assertEqual(self.model.requests, [])
        # Exact loopback startup allowlist succeeds through the same HTTP path.
        self.connect()
        self.assertEqual(len(self.model.requests), 1)

    def test_09_status_waits_for_successful_self_test_and_consent(self):
        gate = threading.Event()
        self.gates.append(gate)
        self.model.script.append({'message': prose('Connected'), 'gate': gate})
        expect(self.page.locator('#agent-status')).to_contain_text('No model is connected')
        self.page.locator('#agent-test').click()
        dialog = self.page.locator('#agent-egress-dialog')
        expect(dialog).to_contain_text(self.endpoint)
        expect(dialog).to_contain_text('scripted-local-model')
        expect(dialog).to_contain_text('synthetic')
        expect(self.page.locator('#agent-egress-confirm')).to_be_disabled()
        self.assertEqual(self.model.requests, [])
        self.confirm_egress()
        self.assertTrue(self.model.received.wait(5), 'Self-test never reached local endpoint')
        expect(self.page.locator('#agent-status')).to_contain_text('No model is connected. Testing')
        expect(self.page.locator('#agent-send')).to_be_disabled()
        expect(self.page.locator('#agent-key')).to_have_value('')
        gate.set()
        self.settled()
        expect(self.page.locator('#agent-status')).to_contain_text('Model-driven agent')
        self.page.locator('#agent-model').fill('changed-model')
        expect(self.page.locator('#agent-status')).to_contain_text('No model is connected')
        expect(self.page.locator('#agent-send')).to_be_disabled()

    def test_09b_failed_endpoint_self_test_never_claims_model_status(self):
        self.model.script.append({'message': prose(self.model.credential), 'status': 401})
        self.page.locator('#agent-test').click()
        self.confirm_egress()
        self.settled()
        expect(self.page.locator('#agent-status')).to_contain_text('No model is connected')
        expect(self.page.locator('#agent-send')).to_be_disabled()
        expect(self.page.locator('#chat-result')).to_contain_text('Model request failed')
        self.no_secret(self.page.content(), 'failed self-test UI')


if __name__ == '__main__':
    unittest.main()
