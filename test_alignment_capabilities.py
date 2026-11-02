"""Loaded mapping availability is distinct from patient event/date availability."""
import copy
from pathlib import Path
import unittest

from app import Engine
from alignment import alignment_capabilities, resolve_alignment
from model_agent import local_tool

ROOT = Path(__file__).resolve().parent


class AlignmentCapabilities(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engines = {c: Engine(ROOT / 'data', c) for c in ('small', '100', 'keynote189')}

    def test_catalogue_and_resolver_agree_for_every_cohort(self):
        for cohort, engine in self.engines.items():
            with self.subTest(cohort=cohort):
                before = copy.deepcopy(engine.fixtures)
                expected = ['calendar', 'first_treatment', 'first_PR', 'first_PD']
                if cohort == 'keynote189':
                    expected.append('death')
                catalogue = local_tool(engine, engine.default_spec(), 'get_capabilities', {})['alignment']
                self.assertEqual(catalogue['supported_anchors'], expected)
                self.assertEqual(set(catalogue['anchors']), set(expected) - {'calendar'})
                for anchor in (*expected, 'death', 'randomization'):
                    result = local_tool(engine, engine.default_spec(), 'set_alignment', {'anchor': anchor})
                    self.assertEqual(result['status'], 'resolved' if anchor in expected else 'unsupported')
                    if anchor not in expected:
                        self.assertIn(anchor, catalogue['unsupported'])
                        self.assertEqual(result['limitation'], 'source_mapping_unavailable')
                        self.assertIn('development task', result['note'])
                        self.assertIn('No transform', result['missing_anchor_handling'])
                        self.assertNotIn('counts', result)
                        self.assertEqual(result['record_ids'], [])
                        self.assertNotIn('patients', result)
                self.assertEqual(engine.fixtures, before)

    def test_supported_patient_states_and_supported_empty_event(self):
        engine = self.engines['small']
        pr = resolve_alignment(engine, 'first_PR')
        self.assertEqual(pr['counts'], dict(resolved=1, no_qualifying_event=2, event_date_unresolved=0))
        self.assertEqual({p['status'] for p in pr['patients']}, {'resolved', 'no_qualifying_event'})
        pd = resolve_alignment(engine, 'first_PD')
        self.assertEqual(pd['status'], 'resolved')
        self.assertEqual(pd['counts'], dict(resolved=0, no_qualifying_event=3, event_date_unresolved=0))

    def test_mapping_requires_fields_not_cohort_name_or_nonempty_domain(self):
        for anchor, domain, field in [('first_treatment', 'EX', 'EXSTDTC'),
                                       ('first_PR', 'RS', 'RSORRES'),
                                       ('first_PD', 'RS', 'RSDTC'),
                                       ('death', 'DS', 'DSSTDTC')]:
            with self.subTest(anchor=anchor):
                engine = copy.deepcopy(self.engines['keynote189'].records)
                # Isolated in-memory records, never change source fixtures.
                from types import SimpleNamespace
                fixture = self.engines['keynote189'].fixtures
                proxy = SimpleNamespace(records=engine, fixtures=fixture)
                for row in engine.values():
                    if row['dataset'] == domain:
                        row['values'].pop(field, None)
                self.assertEqual(resolve_alignment(proxy, anchor)['status'], 'unsupported')
                self.assertNotIn(anchor, alignment_capabilities(proxy)['supported_anchors'])

    def test_partial_or_blank_dates_do_not_remove_mapping_or_impute_date(self):
        from types import SimpleNamespace
        engine = self.engines['small']
        for date_value in ('2025-01', '', None):
            with self.subTest(date=date_value):
                records = copy.deepcopy(engine.records)
                for row in records.values():
                    if row['dataset'] == 'RS' and row['values'].get('RSORRES') == 'PR':
                        row['values']['RSDTC'] = date_value
                proxy = SimpleNamespace(records=records, fixtures=engine.fixtures)
                result = resolve_alignment(proxy, 'first_PR')
                self.assertEqual(result['status'], 'resolved')
                self.assertEqual(result['counts'], dict(resolved=0, no_qualifying_event=2, event_date_unresolved=1))
                self.assertTrue(all(p['date'] is None for p in result['patients']))

    def test_death_mapping_is_not_fatal_ae_or_other_disposition(self):
        engine = self.engines['100']
        self.assertTrue(engine.fixtures['datasets']['DS'])
        self.assertTrue(any('DTHDTC' in r['values'] for r in engine.records.values()))
        self.assertEqual(resolve_alignment(engine, 'death')['status'], 'unsupported')
        death = resolve_alignment(self.engines['keynote189'], 'death')
        self.assertEqual(death['counts'], dict(resolved=36, no_qualifying_event=24, event_date_unresolved=0))

    def test_response_mapping_does_not_require_a_pr_or_pd_event(self):
        from types import SimpleNamespace
        records = copy.deepcopy(self.engines['small'].records)
        for row in records.values():
            if row['dataset'] == 'RS':
                row['values']['RSORRES'] = 'SD'
        proxy = SimpleNamespace(records=records, fixtures=self.engines['small'].fixtures)
        for anchor in ('first_PR', 'first_PD'):
            result = resolve_alignment(proxy, anchor)
            self.assertEqual(result['status'], 'resolved')
            self.assertEqual(result['counts']['no_qualifying_event'], 3)


if __name__ == '__main__':
    unittest.main()
