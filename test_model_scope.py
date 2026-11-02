"""F1 adversarial local-model probes: schemas are not semantic authorization."""
import unittest
from playwright.sync_api import expect
import test_agent_e2e as harness


def proposal(prompt, action=None):
    return harness.tool('propose_display_scope', {
        'intent': 'display_patients', 'evidence': prompt,
        'action': action or {'tool': 'set_view', 'args': {'subset': ['SYN-001']}}})


class ModelScopeChecks(harness.ModelAgentE2E):
    # Reuse transport/setup, not inherited acceptance test discovery.
    def test_ambiguous_valid_subset_cannot_change_view(self):
        self.connect()
        before = self.snapshot()
        self.ask('grade 3 AEs', harness.tool('set_view', {'subset': ['SYN-001']}))
        self.assertEqual(self.snapshot(), before)
        expect(self.page.locator('#chat-result')).to_contain_text('Clarification required')
        self.assertEqual(self.history(), [])

    def test_causal_valid_subset_cannot_change_view(self):
        self.connect()
        before = self.snapshot()
        self.ask('Show only patients whose nausea was caused by treatment',
                 harness.tool('set_view', {'subset': ['SYN-001']}))
        self.assertEqual(self.snapshot(), before)
        expect(self.page.locator('#chat-result')).to_contain_text('Unsupported clinical predicate')
        self.assertEqual(self.history(), [])

    def test_scope_approval_applies_exact_action_and_undo(self):
        self.connect()
        before = self.snapshot()
        prompt = 'Show only patients SYN-001'
        self.ask(prompt, proposal(prompt))
        self.assertEqual(self.snapshot(), before)
        expect(self.page.locator('#agent-scope-proposal')).to_be_visible()
        expect(self.page.locator('#agent-scope-mapping')).to_contain_text(prompt)
        expect(self.page.locator('#agent-scope-mapping')).to_contain_text('SYN-001')
        count = len(self.model.requests)
        self.page.locator('#agent-scope-confirm').click()
        self.settled()
        self.assertEqual(len(self.model.requests), count)
        self.assertEqual(self.snapshot()['display']['view']['focus_patient_keys'], [['SYN-SPIKE', 'SYN-001']])
        self.assertEqual(self.snapshot()['analysis'], before['analysis'])
        self.page.locator('#chat-undo').click()
        self.settled()
        self.assertEqual(self.snapshot(), before)

    def test_approval_is_not_reused_for_later_request(self):
        self.connect()
        prompt = 'Show only patients SYN-001'
        self.ask(prompt, proposal(prompt))
        self.page.locator('#agent-scope-confirm').click()
        self.settled()
        before = self.snapshot()
        self.ask('Show only patients SYN-002', harness.tool('set_view', {'subset': ['SYN-001', 'SYN-002']}))
        self.assertEqual(self.snapshot(), before)
        expect(self.page.locator('#chat-result')).to_contain_text('Clarification required')


    def test_direct_focus_and_record_selection_cannot_bypass_gate(self):
        self.connect()
        before = self.snapshot()
        for name, args in [('set_view', {'focus': 'SYN-001'}),
                           ('set_view', {'focus': None}),
                           ('highlight_events', {'scope': 'current_analysis', 'filters': {'record_ids': ['AE-001-1']}})]:
            with self.subTest(tool=name, args=args):
                self.ask('grade 3 AEs', harness.tool(name, args))
                self.assertEqual(self.snapshot(), before)
                expect(self.page.locator('#chat-result')).to_contain_text('Clarification required')
        self.assertEqual(self.history(), [])

    def test_proposals_cannot_launder_causality_or_widen_scope(self):
        self.connect()
        before = self.snapshot()
        for prompt, reply in [
            ('Show only patients whose nausea was caused by treatment', proposal('Show only patients whose nausea was caused by treatment')),
            ('Show only patients SYN-002', proposal('Show only patients SYN-002')),
            ('Show only patients SYN-001', proposal('Show only patients SYN-002')),
            ('Show only patients SYN-001', proposal('Show only patients SYN-001', {'tool': 'set_view', 'args': {'subset': ['SYN-001', 'SYN-002']}})),
        ]:
            with self.subTest(prompt=prompt):
                self.ask(prompt, reply)
                self.assertEqual(self.snapshot(), before)
                expect(self.page.locator('#agent-scope-proposal')).not_to_be_visible()
        self.assertEqual(self.history(), [])

    def test_cancel_and_prompt_edit_invalidate_pending_scope(self):
        self.connect()
        before = self.snapshot()
        prompt = 'Show only patients SYN-001'
        self.ask(prompt, proposal(prompt))
        self.page.locator('#agent-scope-cancel').click()
        self.assertEqual(self.snapshot(), before)
        self.ask(prompt, proposal(prompt))
        self.page.locator('#chat-request').fill('Show only patients SYN-002')
        expect(self.page.locator('#agent-scope-proposal')).not_to_be_visible()
        self.page.evaluate("document.getElementById('agent-scope-confirm').click()")
        self.settled()
        self.assertEqual(self.snapshot(), before)
        expect(self.page.locator('#chat-result')).to_contain_text('expired')

    def test_configuration_change_invalidates_pending_scope(self):
        self.connect()
        before = self.snapshot()
        prompt = 'Show only patients SYN-001'
        self.ask(prompt, proposal(prompt))
        self.page.locator('#agent-disconnect').click()
        self.page.evaluate("document.getElementById('agent-scope-confirm').click()")
        self.settled()
        self.assertEqual(self.snapshot(), before)
        expect(self.page.locator('#chat-result')).to_contain_text('expired')

    def test_record_approval_then_undo_restores_nonempty_highlights(self):
        self.connect()
        self.approve_scope('Highlight source IDs AE-002-1', 'highlight_events',
                           {'scope': 'current_analysis', 'filters': {'record_ids': ['AE-002-1']}})
        before = self.snapshot()
        self.approve_scope('Highlight grade 3 AE records', 'highlight_events',
                           {'scope': 'current_analysis', 'filters': {'grade': 3}})
        self.assertNotEqual(self.snapshot()['display']['highlights'], before['display']['highlights'])
        self.page.locator('#chat-undo').click()
        self.settled()
        self.assertEqual(self.snapshot(), before)


# The superclass is a transport fixture, not a second run of its acceptance suite.
for name in dir(harness.ModelAgentE2E):
    if name.startswith('test_'):
        setattr(ModelScopeChecks, name, None)

if __name__ == '__main__':
    unittest.main()
