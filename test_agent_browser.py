"""Actual browser -> loopback adapter -> local mock -> validated bridge integration."""
import json
import secrets
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import expect, sync_playwright
from app import Engine, ROOT, make_handler
from test_browser import BrowserFixture
from test_model_agent import MockModel


def call(name, args):
    return {'role': 'assistant', 'content': None, 'tool_calls': [
        {'id': 'call-' + name, 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]}


class AgentBrowserChecks(BrowserFixture):
    @classmethod
    def setUpClass(cls):
        cls.mock = ThreadingHTTPServer(('127.0.0.1', 0), MockModel)
        cls.mock_thread = threading.Thread(target=cls.mock.serve_forever, daemon=True); cls.mock_thread.start()
        cls.endpoint = 'http://127.0.0.1:%d/v1/chat/completions' % cls.mock.server_port
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(Engine(ROOT / 'data'), [cls.endpoint]))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
        cls.playwright = sync_playwright().start(); cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.mock.shutdown(); cls.mock.server_close(); cls.mock_thread.join()

    def setUp(self):
        super().setUp()
        self.page.goto('http://127.0.0.1:%d/lattice' % self.server.server_port)
        self.page.wait_for_function('window.viewChatBridge !== undefined')
        self.page.emulate_media(reduced_motion='reduce')
        self.page.locator('#chat-toggle').click()
        self.page.locator('#agent-config summary').click()
        MockModel.requests = []; MockModel.replies = []
        self.credential = secrets.token_urlsafe(32)
        self.page.locator('#agent-endpoint').fill(self.endpoint)
        self.page.locator('#agent-model').fill('local-mock-model')
        self.page.locator('#agent-key').fill(self.credential)

    def connect(self):
        self.page.locator('#agent-test').click()
        self.page.locator('#agent-consent').check()
        self.page.locator('#agent-egress-confirm').click()
        expect(self.page.locator('#agent-status')).to_contain_text('Model-driven agent')
        expect(self.page.locator('#agent-key')).to_have_value('')

    def snapshot(self):
        return self.page.evaluate('({display:viewChatBridge.snapshot(),analysis:viewChatBridge.analysisSnapshot()})')

    def ask(self, prompt, replies):
        MockModel.replies = replies
        self.page.locator('#chat-request').fill(prompt)
        record_egress = self.page.locator('#agent-record-consent').is_checked()
        self.page.locator('#agent-send').click()
        if record_egress:
            expect(self.page.locator('#agent-egress-dialog')).to_be_visible()
            self.page.locator('#agent-consent').check()
            self.page.locator('#agent-egress-confirm').click()
        expect(self.page.locator('#chat-tool-status')).not_to_contain_text('validating')

    def test_consent_multiturn_view_undo_privacy(self):
        self.page.locator('#agent-test').click()
        expect(self.page.locator('#agent-egress-dialog')).to_be_visible()
        expect(self.page.locator('#agent-egress-confirm')).to_be_disabled()
        self.assertEqual(MockModel.requests, [])
        expect(self.page.locator('#agent-status')).to_contain_text('No model is connected')
        self.page.locator('#agent-egress-cancel').click()
        self.page.locator('#agent-key').fill(self.credential)
        self.connect()
        baseline = self.snapshot()
        self.ask('Sort descending and show only AE and EX at tier 2', [
            call('get_capabilities', {}), call('set_view', {'sort': 'desc', 'layers': ['AE', 'EX'], 'tier': '2'}),
            {'role': 'assistant', 'content': 'Done'}])
        self.assertEqual(self.snapshot()['analysis'], baseline['analysis'])
        self.assertEqual(self.snapshot()['display']['sort'], 'desc')
        self.assertEqual(self.snapshot()['display']['view']['hidden_lanes'], ['CM', 'RS'])
        self.assertEqual(len(MockModel.requests), 4)
        history = json.loads(self.page.locator('#chat-history').text_content())
        self.assertEqual(history[-1]['action']['tool'], 'set_view'); self.assertIn('display', history[-1]['diff'])
        self.assertTrue(history[-1]['record_ids'])
        sent = json.dumps(MockModel.requests)
        self.assertNotIn('AE-001-1', sent); self.assertNotIn(self.credential, sent)
        self.page.locator('#chat-undo').click()
        expect(self.page.locator('#chat-result')).to_contain_text('Undo:')
        self.assertEqual(self.snapshot(), baseline)
        self.page.locator('#chat-toggle').click()
        self.page.locator('#save').click()
        expect(self.page.locator('#replay-result')).to_contain_text('Saved')
        persistence = self.page.evaluate('JSON.stringify(localStorage)')
        export = self.page.evaluate("async()=>{const r=await fetch('/api/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({spec:state.spec})});return await r.text();}")
        self.assertNotIn(self.credential, persistence + export + self.page.locator('#chat-history').text_content())
        self.page.locator('#chat-toggle').click()
        self.page.locator('#agent-model').fill('another-model')
        expect(self.page.locator('#agent-status')).to_contain_text('No model is connected')
        expect(self.page.locator('#agent-consent')).not_to_be_checked()

    def test_analysis_proposal_confirm_and_undo(self):
        self.connect(); baseline = self.snapshot()
        self.ask('Subset the ANALYSIS population to SYN-001', [call('propose_analysis_subset', {'patients': ['SYN-001']})])
        self.assertEqual(self.snapshot(), baseline)
        expect(self.page.locator('#agent-proposal')).to_be_visible()
        expect(self.page.locator('#agent-consequence')).to_contain_text('"patients": 1')
        expect(self.page.locator('#counts')).to_have_text('2 qualifying patients · 3 qualifying AE source records')
        self.page.locator('#agent-confirm').click()
        expect(self.page.locator('#counts')).to_have_text('1 qualifying patients · 2 qualifying AE source records')
        history = json.loads(self.page.locator('#chat-history').text_content())
        self.assertEqual(history[-1]['action']['tool'], 'confirm_analysis_subset')
        self.assertIn('analysis', history[-1]['diff'])
        self.page.locator('#chat-undo').click()
        expect(self.page.locator('#chat-result')).to_contain_text('Undo:')
        self.assertEqual(self.snapshot(), baseline)

    def test_unsupported_ambiguous_and_invalid_tools_do_not_change_view(self):
        self.connect(); baseline = self.snapshot()
        self.ask('Align by randomization day', [call('set_alignment', {'anchor': 'randomization'}), {'role': 'assistant', 'content': 'unsupported'}])
        expect(self.page.locator('#chat-result')).to_contain_text('development task')
        self.assertEqual(self.snapshot(), baseline)
        self.ask('grade 3 AEs', [call('clarify_request', {'question': 'Which counting unit: patients or AE records? Which window and anchor?'})])
        expect(self.page.locator('#chat-result')).to_contain_text('Which counting unit')
        self.assertEqual(self.snapshot(), baseline)
        self.ask('run browser code', [call('execute_javascript', {'code': 'document.body.remove()'})])
        expect(self.page.locator('#chat-result')).to_contain_text('Unsupported tool')
        self.assertEqual(self.snapshot(), baseline)
        self.ask('malformed view mutation', [call('set_view', {'sort': 'asc', 'analysis_state': {}})])
        expect(self.page.locator('#chat-result')).to_contain_text('Unsupported fields')
        self.assertEqual(self.snapshot(), baseline)
        self.ask('clinical inference', [call('propose_development_task', {'description': 'Clinical inference is unsupported; this is a development suggestion, not a clinical result.'})])
        self.assertEqual(self.snapshot(), baseline)
        task=json.loads(self.page.locator('#chat-history').text_content())[-1]['action']['args']['task']
        self.assertFalse(task['result_created'])
        self.assertEqual(json.loads(self.page.locator('#chat-tasks').text_content())[-1]['id'], task['id'])

    def test_source_ids_units_highlights_and_record_egress(self):
        self.connect(); baseline = self.snapshot()
        for unit, count in [('AE records', 3), ('patients', 2)]:
            self.ask('Count ' + unit + ' in current analysis', [call('query_data', {'scope': 'current_analysis', 'unit': unit, 'filters': {}}), {'role': 'assistant', 'content': 'Done'}])
            expect(self.page.locator('#chat-result')).to_contain_text(f'{count} {unit}')
            expect(self.page.locator('#chat-records')).to_contain_text('AE-001-1')
            self.assertEqual(self.snapshot(), baseline)
        self.ask('highlight exact term SYNTHETIC NAUSEA', [call('propose_display_scope', {
            'intent': 'highlight_records', 'evidence': 'highlight exact term SYNTHETIC NAUSEA',
            'action': {'tool': 'highlight_events', 'args': {'scope': 'current_analysis', 'filters': {'term': 'SYNTHETIC NAUSEA'}}}})])
        self.assertEqual(self.snapshot(), baseline)
        self.page.locator('#agent-scope-confirm').click()
        expect(self.page.locator('#chat-result')).to_contain_text('explicitly approved')
        self.assertEqual(self.snapshot()['display']['highlights'], ['AE-001-1', 'AE-001-2'])
        self.assertEqual(self.snapshot()['analysis'], baseline['analysis'])
        self.assertNotIn('AE-001-1', json.dumps(MockModel.requests))
        self.ask('show source rows', [call('query_data', {'scope': 'current_analysis', 'unit': 'AE records', 'filters': {}, 'include_records': True})])
        expect(self.page.locator('#chat-result')).to_contain_text('separate egress confirmation')
        self.page.locator('#agent-record-consent').check()
        self.ask('I explicitly request the source rows', [call('query_data', {'scope': 'current_analysis', 'unit': 'AE records', 'filters': {}, 'include_records': True}), {'role': 'assistant', 'content': 'Done'}])
        self.assertIn('AE-001-1', json.dumps(MockModel.requests[-1]))
        expect(self.page.locator('#agent-record-consent')).not_to_be_checked()
        self.page.locator('#chat-reset').click()
        expect(self.page.locator('#chat-result')).to_contain_text('Reset:')
        self.assertEqual(self.snapshot(), baseline)

    def test_display_subset_not_analysis_and_secret_echo(self):
        self.connect(); baseline = self.snapshot()
        self.ask('Display only SYN-001', [call('propose_display_scope', {
            'intent': 'display_patients', 'evidence': 'Display only SYN-001',
            'action': {'tool': 'set_view', 'args': {'subset': ['SYN-001']}}})])
        self.assertEqual(self.snapshot(), baseline)
        self.page.locator('#agent-scope-confirm').click()
        expect(self.page.locator('#chat-result')).to_contain_text('explicitly approved')
        self.ask('Read view state', [call('get_view_state', {}), {'role': 'assistant', 'content': self.credential}])
        self.assertEqual(self.snapshot()['display']['view']['focus_patient_keys'], [['SYN-SPIKE', 'SYN-001']])
        self.assertEqual(self.snapshot()['analysis'], baseline['analysis'])
        self.assertNotIn(self.credential, self.page.locator('#chat-body').text_content())
        self.page.locator('#agent-disconnect').click()
        expect(self.page.locator('#agent-status')).to_contain_text('No model is connected')
        self.assertNotIn(self.credential, self.page.locator('#chat-body').text_content())
