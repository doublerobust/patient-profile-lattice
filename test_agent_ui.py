"""UI privacy and consent regressions against only a local mock model."""
import json
from playwright.sync_api import expect
import test_agent_browser as baseline
from test_model_agent import MockModel


class AgentUIChecks(baseline.AgentBrowserChecks):
    def test_modal_precedes_egress_and_clears_secret(self):
        self.page.locator('#agent-test').click()
        dialog = self.page.locator('#agent-egress-dialog')
        expect(dialog).to_be_visible()
        expect(dialog).to_contain_text(self.endpoint)
        expect(dialog).to_contain_text('local-mock-model')
        expect(dialog).to_contain_text('synthetic')
        expect(dialog).to_contain_text('prompt, relevant view metadata')
        expect(dialog).to_contain_text('not persisted')
        expect(self.page.locator('#agent-key')).to_have_value('')
        self.assertEqual(MockModel.requests, [])
        self.assertNotIn(self.credential, self.page.content())
        self.page.locator('#agent-egress-cancel').click()
        expect(dialog).not_to_be_visible()
        expect(self.page.locator('#agent-status')).to_contain_text('No model is connected')
        self.assertEqual(MockModel.requests, [])

    def test_failed_self_test_clears_credential_and_never_connects(self):
        self.page.route('**/api/agent/model', lambda route: route.fulfill(status=400, json={'error': 'Self-test failed'}))
        self.page.locator('#agent-test').click()
        self.page.locator('#agent-consent').check()
        self.page.locator('#agent-egress-confirm').click()
        expect(self.page.locator('#chat-result')).to_contain_text('Self-test failed')
        expect(self.page.locator('#agent-key')).to_have_value('')
        expect(self.page.locator('#agent-status')).to_contain_text('No model is connected')
        expect(self.page.locator('#agent-send')).to_be_disabled()
        self.assertNotIn(self.credential, self.page.content())

    def test_record_confirmation_cancel_sends_nothing_and_is_request_scoped(self):
        self.connect()
        count = len(MockModel.requests)
        self.page.locator('#chat-request').fill('Return source records for this request')
        self.page.locator('#agent-record-consent').check()
        self.page.locator('#agent-send').click()
        dialog = self.page.locator('#agent-egress-dialog')
        expect(dialog).to_be_visible()
        expect(dialog).to_contain_text(self.endpoint)
        expect(dialog).to_contain_text('local-mock-model')
        expect(dialog).to_contain_text('Return source records for this request')
        expect(dialog).to_contain_text('record-level')
        self.assertEqual(len(MockModel.requests), count)
        self.page.locator('#agent-egress-cancel').click()
        expect(self.page.locator('#agent-record-consent')).not_to_be_checked()
        self.assertEqual(len(MockModel.requests), count)

    def test_false_self_test_result_does_not_connect(self):
        self.page.route('**/api/agent/model', lambda route: route.fulfill(json={'connected': False, 'message': {}}))
        self.page.locator('#agent-test').click()
        self.page.locator('#agent-consent').check()
        self.page.locator('#agent-egress-confirm').click()
        expect(self.page.locator('#chat-result')).to_contain_text('did not confirm')
        expect(self.page.locator('#agent-status')).to_contain_text('No model is connected')

    def test_refusal_prose_is_labeled_not_fabricated_as_a_result(self):
        self.connect()
        before = self.snapshot()
        self.ask('Infer clinical causality', [{'role': 'assistant', 'content': 'I cannot infer causality from this view.'}])
        expect(self.page.locator('#chat-result')).to_contain_text('I cannot infer causality')
        expect(self.page.locator('#chat-result')).to_contain_text('Unverified model message')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(json.loads(self.page.locator('#chat-history').inner_text()), [])

    def test_stale_self_test_cannot_reconnect_after_disconnect(self):
        requests = []
        self.page.route('**/api/agent/model', lambda route: requests.append(route))
        self.page.locator('#agent-test').click()
        self.page.locator('#agent-consent').check()
        self.page.locator('#agent-egress-confirm').click()
        expect(self.page.locator('#agent-status')).to_contain_text('Testing')
        self.page.locator('#agent-disconnect').click()
        self.assertEqual(len(requests), 1)
        requests[0].fulfill(json={'connected': True, 'message': {'role': 'assistant', 'content': 'ok'}})
        expect(self.page.locator('#chat-result')).to_contain_text('self-test response discarded')
        expect(self.page.locator('#agent-status')).to_contain_text('No model is connected')
        expect(self.page.locator('#agent-send')).to_be_disabled()

    def test_dataset_change_requires_new_consent_without_egress(self):
        self.connect()
        count = len(MockModel.requests)
        self.page.evaluate("viewChatBridge.dataset = () => 'different-loaded-dataset'")
        self.page.locator('#chat-request').fill('Sort ascending')
        self.page.locator('#agent-send').click()
        expect(self.page.locator('#chat-result')).to_contain_text('Reconnect explicitly')
        expect(self.page.locator('#agent-status')).to_contain_text('No model is connected')
        self.assertEqual(len(MockModel.requests), count)

    def test_escape_cancels_modal_and_mobile_dialog_fits(self):
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.page.locator('#agent-test').click()
        dialog = self.page.locator('#agent-egress-dialog')
        expect(dialog).to_be_visible()
        box = dialog.bounding_box()
        self.assertGreaterEqual(box['x'], 0)
        self.assertLessEqual(box['x'] + box['width'], 390)
        self.page.keyboard.press('Escape')
        expect(dialog).not_to_be_visible()
        expect(self.page.locator('#chat-result')).to_contain_text('cancelled')
        expect(self.page.locator('#agent-key')).to_have_value('')
        self.assertEqual(MockModel.requests, [])
