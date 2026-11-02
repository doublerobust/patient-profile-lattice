"""Unavailable loaded mappings must not replace a valid browser alignment."""
import json
from playwright.sync_api import expect
from test_browser import BrowserFixture


class UnavailableMappingBrowser(BrowserFixture):
    def test_small_death_is_development_limitation_without_state_or_history_change(self):
        self.page.goto('http://127.0.0.1:%d/lattice' % self.server.server_port)
        self.page.wait_for_function('window.viewChatBridge !== undefined && window.lattice.ready')
        self.page.emulate_media(reduced_motion='reduce')
        self.page.locator('#chat-toggle').click()

        def run(anchor):
            self.page.locator('#chat-request').fill(json.dumps({'tool': 'set_alignment', 'args': {'anchor': anchor}}))
            self.page.locator('#chat-form button[type=submit]').click()
            expect(self.page.locator('#chat-tool-status')).not_to_contain_text('validating')

        run('first_PR')
        expect(self.page.locator('#lattice-alignment')).to_contain_text('days since first recorded PR')
        baseline = self.page.evaluate('({display:viewChatBridge.snapshot(),analysis:viewChatBridge.analysisSnapshot(),marks:state.marks})')
        history = self.page.locator('#chat-history').text_content()
        run('death')
        expect(self.page.locator('#chat-result')).to_contain_text('development task required')
        expect(self.page.locator('#chat-result')).to_contain_text('No source mapping')
        self.assertEqual(self.page.evaluate('({display:viewChatBridge.snapshot(),analysis:viewChatBridge.analysisSnapshot(),marks:state.marks})'), baseline)
        self.assertEqual(self.page.locator('#chat-history').text_content(), history)
        self.assertEqual(self.page.evaluate('lattice.stats().alignment'), 'first_PR')
        catalogue = self.page.evaluate("viewChatBridge.agentTool('get_capabilities', {})")
        self.assertNotIn('death', catalogue['alignment']['supported_anchors'])
        self.assertEqual(catalogue['alignment']['unavailable_anchors']['death']['limitation'], 'source_mapping_unavailable')
