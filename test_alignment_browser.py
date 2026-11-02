"""KN189 demo alignment through a real browser and local mock model only."""
import json
import secrets
import threading
from http.server import ThreadingHTTPServer
from playwright.sync_api import expect, sync_playwright
from app import Engine, ROOT, make_handler
from test_browser import BrowserFixture
import test_agent_browser as agent_tests
from test_model_agent import MockModel


class AlignmentBrowserChecks(BrowserFixture):
    initial_counts = '60 qualifying patients · 260 qualifying AE source records'
    @classmethod
    def setUpClass(cls):
        cls.mock = ThreadingHTTPServer(('127.0.0.1', 0), MockModel)
        cls.mock_thread = threading.Thread(target=cls.mock.serve_forever, daemon=True); cls.mock_thread.start()
        cls.endpoint = 'http://127.0.0.1:%d/v1/chat/completions' % cls.mock.server_port
        cls.engine = Engine(ROOT / 'data', 'keynote189')
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(cls.engine, [cls.endpoint]))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
        cls.playwright = sync_playwright().start(); cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.mock.shutdown(); cls.mock.server_close(); cls.mock_thread.join()

    def setUp(self):
        super().setUp()
        self.page.goto('http://127.0.0.1:%d/lattice' % self.server.server_port)
        self.page.wait_for_function('window.viewChatBridge !== undefined && window.lattice.ready')
        self.page.emulate_media(reduced_motion='reduce')
        self.page.locator('#chat-toggle').click()
        self.page.locator('#agent-config summary').click()
        MockModel.requests = []; MockModel.replies = []
        self.credential = secrets.token_urlsafe(32)
        self.page.locator('#agent-endpoint').fill(self.endpoint)
        self.page.locator('#agent-model').fill('local-mock-model')
        self.page.locator('#agent-key').fill(self.credential)

    connect = agent_tests.AgentBrowserChecks.connect
    ask = agent_tests.AgentBrowserChecks.ask
    snapshot = agent_tests.AgentBrowserChecks.snapshot

    def test_model_alignment_source_dates_denominators_projections_undo(self):
        self.connect()
        self.ask('Show tier 2', [agent_tests.call('set_view', {'tier': '2'})])
        baseline = self.snapshot()
        original = self.page.evaluate('({spec:state.spec,analysis:state.analysis,marks:state.marks})')
        coordinates = self.page.evaluate('lattice.stats().coordinates')
        self.ask('Align display to first recorded PR, not analysis', [
            agent_tests.call('get_capabilities', {}), agent_tests.call('set_alignment', {'anchor': 'first_PR'}),
            {'role': 'assistant', 'content': 'Done'}])
        expect(self.page.locator('#lattice-alignment')).to_contain_text('days since first recorded PR')
        expect(self.page.locator('#lattice-alignment')).to_contain_text('23/60 visible patients resolved; 37 no qualifying event recorded; 0 event recorded but date unresolved')
        self.assertEqual(self.page.evaluate('({spec:state.spec,analysis:state.analysis,marks:state.marks})'), original)
        after = self.page.evaluate('lattice.stats()')
        self.assertEqual(len(after['patientOrder']), 60)
        self.assertTrue(any(a['x'] != b['x'] for a,b in zip(after['coordinates'], coordinates)))
        self.assertTrue(any(c['time'] == 0 for c in after['coordinates']))
        self.assertTrue(any(c['time'] is None for c in after['coordinates']))
        self.assertNotIn('RS:189-', json.dumps(MockModel.requests))
        self.assertNotIn('patient_key', json.dumps(MockModel.requests))
        history = json.loads(self.page.locator('#chat-history').text_content())
        self.assertEqual(history[-1]['action']['tool'], 'set_alignment')
        self.assertIn('display', history[-1]['diff']); self.assertNotIn('analysis', history[-1]['diff'])
        self.assertTrue(history[-1]['record_ids'])
        self.page.locator('#chat-undo').click()
        expect(self.page.locator('#chat-result')).to_contain_text('Undo:')
        self.assertEqual(self.snapshot(), baseline)
        self.page.wait_for_function('lattice.stats().alignment === "calendar"')
        self.assertEqual(self.page.evaluate('lattice.stats().coordinates'), coordinates)
        # Exercise every projection with aligned coordinates; no records disappear.
        self.ask('Align by first PR', [agent_tests.call('set_alignment', {'anchor': 'first_PR'})])
        self.page.locator('#chat-toggle').click()
        for projection in ('patient-time', 'patient-layer', 'layer-time', 'full'):
            self.page.locator('#lattice-'+projection).click()
            self.page.wait_for_function('p=>lattice.stats().projection===p', arg=projection)
            self.assertEqual(self.page.evaluate('state.analysis'), original['analysis'])
            if projection == 'layer-time':
                cells = self.page.evaluate('lattice.stats().cells')
                self.assertTrue(all(c['denominator']==23 for c in cells if c['bin'] is not None))
                missing = [c for c in cells if c['bucket']=='no_qualifying_event']
                self.assertTrue(missing); self.assertTrue(all(c['denominator']==37 for c in missing))
                self.page.locator('#lattice-cell').select_option(missing[0]['id'])
                self.page.locator('#lattice-inspect').click()
                expect(self.page.locator('#lattice-contributors')).to_contain_text('no qualifying event recorded')
                self.assertEqual(len({rid for c in cells for rid in c['recordIds']}), len({c['record_id'] for c in after['coordinates']}))
        self.page.locator('#chat-toggle').click()
        self.ask('Align to randomization', [agent_tests.call('set_alignment', {'anchor':'randomization'})])
        expect(self.page.locator('#chat-result')).to_contain_text('development task')
        self.assertEqual(self.page.evaluate('lattice.stats().alignment'), 'first_PR')
        self.ask('Count AEs in days 0 to 30 after first PR', [agent_tests.call('propose_development_task', {'description':'Anchor-relative analytical windows are unsupported; development task required. Display alignment does not change analysis.'})])
        self.assertEqual(self.page.evaluate('state.analysis'), original['analysis'])
        self.assertEqual(self.page.evaluate('lattice.stats().alignment'), 'first_PR')
        self.assertNotIn(self.credential, self.page.locator('#chat-body').text_content())
        self.assertFalse(self.errors)

    def test_treatment_pd_death_and_legacy_renderer_refusal(self):
        self.connect()
        original = self.page.evaluate('state.analysis')
        for anchor, count in [('first_dose',60),('first_PD',45),('death',36)]:
            self.ask('Align display '+anchor, [agent_tests.call('set_alignment', {'anchor': anchor})])
            expect(self.page.locator('#lattice-alignment')).to_contain_text(f'{count}/60 visible patients resolved')
            self.assertEqual(self.page.evaluate('state.analysis'), original)
        self.ask('Restore absolute dates', [agent_tests.call('set_alignment', {'anchor':'calendar'})])
        expect(self.page.locator('#lattice-alignment')).to_contain_text('Calendar date (absolute)')
        self.page.goto('http://127.0.0.1:%d/3d' % self.server.server_port)
        self.page.wait_for_function('window.viewChatBridge !== undefined')
        result = self.page.evaluate("async()=>{const r=await viewChatBridge.agentTool('set_alignment',{anchor:'first_PR'});try{viewChatBridge.setAlignment(r)}catch(e){return e.message}}")
        self.assertIn('supported on /lattice only', result)
        self.assertIsNone(self.snapshot()['display']['alignment'])
