"""Real KN189 browser + local scripted endpoint; no external model tested."""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from playwright.sync_api import Page, expect, sync_playwright
from app import Engine, ROOT, make_handler
import test_agent_e2e as helpers


class TableS4Browser(unittest.TestCase):
    page: Page
    model: Any
    # Share lifecycle/helpers only; do not inherit small-fixture test cases.
    setUp = helpers.ModelAgentE2E.setUp
    tearDown = helpers.ModelAgentE2E.tearDown
    no_secret = helpers.ModelAgentE2E.no_secret
    script = helpers.ModelAgentE2E.script
    settled = helpers.ModelAgentE2E.settled
    confirm_egress = helpers.ModelAgentE2E.confirm_egress
    connect = helpers.ModelAgentE2E.connect
    ask = helpers.ModelAgentE2E.ask
    snapshot = helpers.ModelAgentE2E.snapshot
    history = helpers.ModelAgentE2E.history
    approve_scope = helpers.ModelAgentE2E.approve_scope

    @classmethod
    def setUpClass(cls):
        cls.model = ThreadingHTTPServer(('127.0.0.1', 0), helpers.ScriptedEndpoint)
        cls.model_thread = threading.Thread(target=cls.model.serve_forever, daemon=True)
        cls.model_thread.start()
        cls.endpoint = 'http://127.0.0.1:%d/v1/chat/completions' % cls.model.server_port
        cls.engine = Engine(ROOT / 'data', 'keynote189')
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

    def test_s4_highlight_query_and_credential_free_saved_download_replay(self):
        self.connect()
        baseline = self.snapshot()
        term = 'Lacrimation increased'
        expected = sorted(rid for rid, row in self.engine.records.items()
                          if row['dataset'] == 'AE' and row['values']['AETERM'] == term)
        self.assertTrue(expected)
        args = {'scope': 'current_analysis', 'filters': {'term': term}}
        self.approve_scope('Highlight exact term ' + term, 'highlight_events', args)
        self.assertEqual(self.snapshot()['display']['highlights'], expected)
        self.assertEqual(self.snapshot()['analysis'], baseline['analysis'])
        for unit in ('AE records', 'patients'):
            count = len(expected) if unit == 'AE records' else len({self.engine.records[r]['values']['USUBJID'] for r in expected})
            self.ask('Count ' + unit + ' with exact term ' + term,
                     helpers.tool('query_data', {**args, 'unit': unit}), helpers.prose())
            expect(self.page.locator('#chat-result')).to_contain_text(f'{count} {unit}')
            expect(self.page.locator('#chat-result')).to_contain_text('not trial prevalence')
            self.assertEqual(self.history()[-1]['record_ids'], expected)
        self.assertNotIn(expected[0], json.dumps(self.model.requests))
        # Select a contributing source for a real source-bearing exported package.
        self.page.evaluate('''async rid => {
            const mark=state.marks.find(m=>m.record_id===rid);
            const spec=JSON.parse(JSON.stringify(state.spec));
            spec.view_state.selection={mark_id:mark.mark_id,source_record_ids:[rid]};
            state=await api('evaluate',{spec});render();
        }''', expected[0])
        self.page.locator('#chat-toggle').click()
        self.page.locator('#save').click()
        expect(self.page.locator('#replay-result')).to_contain_text('Saved exact normalized review')
        stored = self.page.evaluate('JSON.stringify(localStorage)')
        self.no_secret(stored, 'saved review')
        with self.page.expect_download() as downloaded:
            self.page.locator('#download').click()
        with tempfile.TemporaryDirectory(prefix='s4-replay-', dir=ROOT) as directory:
            path = Path(directory) / 'review.json'
            downloaded.value.save_as(path)
            text = path.read_text()
            self.no_secret(text, 'exported review')
            package = json.loads(text)
            self.assertTrue(package['synthetic_only'])
            self.assertIn('table-s4-synthetic.json', text)
            self.assertIn('upstream_raw_sha256', text)
            self.assertIn('not trial data', text)
            self.assertIn(term, text)
            self.page.locator('#import').set_input_files(str(path))
            expect(self.page.locator('#replay-result')).to_contain_text('Replay verified')
            self.no_secret(json.dumps(self.snapshot()), 'replay state')
        self.no_secret(json.dumps(self.history()), 'history')
        self.page.reload()
        expect(self.page.locator('#counts')).to_have_text('60 qualifying patients · 260 qualifying AE source records')
        self.page.locator('#chat-toggle').click()
        expect(self.page.locator('#agent-status')).to_contain_text('No model is connected')
        for selector in ('#agent-endpoint', '#agent-model', '#agent-key'):
            expect(self.page.locator(selector)).to_have_value('')
        expect(self.page.locator('#agent-send')).to_be_disabled()


if __name__ == '__main__':
    unittest.main()
