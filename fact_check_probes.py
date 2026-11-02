"""Independent review probes for 0eb084b; local mocks only, no provider secrets.
Run the selected classes below; inherited producer tests are NOT part of ProbeBrowser.
"""
import copy
from datetime import date, timedelta
import json
from pathlib import Path
import unittest

from app import Engine, ROOT
from alignment import resolve_alignment, alignment_capabilities
from playwright.sync_api import expect
from test_agent_e2e import ModelAgentE2E, tool, prose


class SourceReview(unittest.TestCase):
    def test_supported_anchor_requires_loaded_source_fields(self):
        fields = {'first_treatment': ('EX', ('EXSTDTC',)),
                  'first_PR': ('RS', ('RSTESTCD', 'RSORRES', 'RSDTC')),
                  'first_PD': ('RS', ('RSTESTCD', 'RSORRES', 'RSDTC')),
                  'death': ('DS', ('DSDECOD', 'DSSTDTC'))}
        for cohort in ('small', '100', 'keynote189'):
            engine = Engine(ROOT / 'data', cohort)
            for anchor in alignment_capabilities(engine)['supported_anchors']:
                if anchor == 'calendar':
                    continue
                domain, required = fields[anchor]
                rows = engine.fixtures['datasets'].get(domain, [])
                self.assertTrue(any(all(f in r['values'] for f in required) for r in rows),
                                f'DEFECT: {cohort} advertises {anchor} without any loaded {domain} record exposing required source fields')

    def test_original_raw_anchor_counts_and_dates(self):
        raw = json.loads((ROOT / 'fixtures/keynote189-synthetic/raw.json').read_text())
        engine = Engine(ROOT / 'data', 'keynote189')
        candidates = {
            'first_treatment': lambda p: [e['d'] for e in p['ex']],
            'first_PR': lambda p: [r['d'] for r in p['tr'] if r['resp'] == 'PR'],
            'first_PD': lambda p: [r['d'] for r in p['tr'] if r['resp'] == 'PD'],
            'death': lambda p: [] if p['ds']['death'] is None else [p['ds']['death']],
        }
        counts = {}
        for anchor, select in candidates.items():
            expected = {p['id']: (date(2025, 1, 1) + timedelta(days=p['enr'] + min(select(p)))).isoformat()
                        for p in raw['PTS'] if select(p)}
            result = resolve_alignment(engine, anchor)
            actual = {p['patient_key'][1]: p['date'] for p in result['patients'] if p['status'] == 'resolved'}
            self.assertEqual(actual, expected)
            counts[anchor] = len(expected)
        self.assertEqual(counts, {'first_treatment': 60, 'first_PR': 23, 'first_PD': 45, 'death': 36})
        generic = Engine(ROOT / 'data', '100')
        # Count directly from the records, without asking the alignment resolver.
        prs = {r['values']['USUBJID'] for r in generic.records.values()
               if r['dataset'] == 'RS' and r['values'].get('RSTESTCD') == 'OVRLRESP'
               and r['values'].get('RSORRES') == 'PR'}
        self.assertEqual(len(prs), 25)
        print('Original raw KN189 date/count cross-check:', json.dumps(counts, sort_keys=True))
        print('Generic source-qualified PR patients:', len(prs))

    def test_unresolved_candidate_is_not_imputed(self):
        engine = Engine(ROOT / 'data', 'keynote189')
        records = copy.deepcopy(engine.records)
        # An in-memory copy only: no fixture mutation.
        pr = next(r for r in records.values() if r['dataset'] == 'RS' and r['values'].get('RSORRES') == 'PR')
        patient = pr['values']['USUBJID']
        pr['values']['RSDTC'] = '2025-02'
        engine.records = records
        result = resolve_alignment(engine, 'first_PR')
        p = next(p for p in result['patients'] if p['patient_key'][1] == patient)
        self.assertEqual(p['status'], 'event_date_unresolved')
        self.assertIsNone(p['date'])

    def test_selected_review_contains_synthetic_source_values(self):
        engine = Engine(ROOT / 'data')
        state = engine.evaluate(engine.default_spec())
        spec = copy.deepcopy(state['spec'])
        mark = state['marks'][0]
        spec['view_state']['selection'] = {'mark_id': mark['mark_id'], 'source_record_ids': [mark['record_id']]}
        package = engine.export_review(spec)
        self.assertTrue(package['synthetic_only'])
        self.assertTrue(package['source_records'])
        self.assertTrue(package['source_records'][0]['values'])
        self.assertTrue(package['selection_evidence']['source_records'])
        engine.replay(package)
        print('Selected local review/replay intentionally includes synthetic raw source values: confirmed')


class ProbeBrowser(ModelAgentE2E):
    # Reuse only server/browser fixture and helpers; command selects these exact probes.
    def test_ambiguous_request_must_not_mutate_with_valid_but_inferred_call(self):
        self.connect()
        before = self.snapshot()
        # Integrated F1 stops at refusal: no follow-up model response is authorized.
        self.ask('grade 3 AEs', tool('set_view', {'subset': ['SYN-001']}))
        self.assertTrue(self.snapshot() == before,
                        'DEFECT: ambiguous prompt changed displayed population via a schema-valid inferred subset')
        expect(self.page.locator('#chat-result')).to_contain_text('Clarification required')
        self.assertEqual(self.history(), [])
        self.assertEqual(len(self.model.requests), 2)  # connection test + one request

    def test_clinically_inferential_request_must_not_mutate(self):
        self.connect()
        before = self.snapshot()
        self.ask('Show only patients whose nausea was caused by treatment',
                 tool('set_view', {'subset': ['SYN-001']}))
        self.assertTrue(self.snapshot() == before,
                        'DEFECT: unsupported clinical-causality request changed view via a valid inferred subset')
        expect(self.page.locator('#chat-result')).to_contain_text('Unsupported clinical predicate')
        self.assertEqual(self.history(), [])
        self.assertEqual(len(self.model.requests), 2)  # refusal must not continue egress

    def test_default_egress_has_no_local_raw_values_or_ids(self):
        self.connect()
        self.ask('Count AE records', tool('get_view_state', {}),
                 tool('query_data', {'scope': 'current_analysis', 'unit': 'AE records', 'filters': {}}), prose())
        sent = json.dumps(self.model.requests)
        for forbidden in ('SYNTHETIC NAUSEA', 'AE-001-1', 'SYN-001', 'original_source', 'AETERM'):
            self.assertTrue(forbidden not in sent, 'Default egress included local source content')

    def test_selected_source_save_has_no_session_credential(self):
        self.connect()
        self.page.evaluate('''async()=>{const spec=structuredClone(state.spec);const m=state.marks[0];spec.view_state.selection={mark_id:m.mark_id,source_record_ids:[m.record_id]};state=await (await fetch('/api/evaluate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({spec})})).json();render();}''')
        self.page.locator('#chat-toggle').click()
        self.page.locator('#save').click()
        expect(self.page.locator('#replay-result')).to_contain_text('Saved')
        stored = self.page.evaluate('Object.values(localStorage)')
        self.assertTrue(stored)
        package = json.loads(stored[0])
        self.assertTrue(package['source_records'][0]['values'])
        self.no_secret(json.dumps(package), 'selected-source localStorage review')


if __name__ == '__main__':
    unittest.main()
