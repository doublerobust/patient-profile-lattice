"""Data and API checks independent of browser geometry."""
import copy
from pathlib import Path
import unittest
from app import Engine, canonical
from cohort import scale_cohort

ROOT = Path(__file__).resolve().parent


class CohortChecks(unittest.TestCase):
    def setUp(self):
        self.small = Engine(ROOT / 'data')
        self.engine = Engine(ROOT / 'data', cohort='100')

    def test_deterministic_100_patient_fixture_and_original_sources(self):
        e = self.engine
        first = scale_cohort(self.small.fixtures)
        self.assertEqual(canonical(first), canonical(scale_cohort(self.small.fixtures)))
        self.assertEqual(len(first['population']), 100)
        self.assertEqual(len({p['USUBJID'] for p in first['population']}), 100)
        for domain, rows in self.small.fixtures['datasets'].items():
            self.assertEqual(first['datasets'][domain][:len(rows)], rows)
        for domain, rows in first['datasets'].items():
            for index, row in enumerate(rows, 1):
                self.assertEqual(row['row_number'], index)
                self.assertEqual(e.source(row['record_id'])['values'], row['values'])
        state = e.evaluate(e.default_spec())
        self.assertEqual(state['analysis']['population_patient_count'], 100)
        self.assertEqual(state['analysis']['qualifying_patient_count'], 100)
        self.assertEqual(state['analysis']['qualifying_ae_record_count'], 298)
        self.assertEqual(len(state['marks']), sum(len(first['datasets'][d]) for d in ['AE','CM','EX','RS','DS']))
        self.assertNotEqual(e.default_spec()['snapshot_id'], self.small.default_spec()['snapshot_id'])
        self.assertNotEqual(e.default_spec()['snapshot_sha256'], self.small.default_spec()['snapshot_sha256'])

    def test_intervals_preserve_source_boundaries_and_points(self):
        e = self.engine
        state = e.evaluate(e.default_spec())
        for mark in state['marks']:
            source = e.records[mark['record_id']]['values']
            if mark['lane'] in ('RS','DS') or mark['display_kind']=='death':
                self.assertEqual(mark['interval_status'], 'point')
                self.assertFalse(mark['is_interval'])
                self.assertEqual(mark['date'], source['DTHDTC'] if mark['display_kind']=='death' else source['RSDTC' if mark['lane']=='RS' else 'DSSTDTC'])
            else:
                self.assertTrue(mark['is_interval'])
                self.assertEqual(mark['raw_end_date'], source.get(mark['lane']+'ENDTC', ''))
                if mark['interval_status'] == 'complete':
                    self.assertLessEqual(mark['date'], mark['end_date'])
        for end, status in [('', 'missing_end'), ('2025-02','incomplete_end'), ('2024-01-01','reversed')]:
            row = copy.deepcopy(e.records['AE-002-1'])
            row['values']['AEENDTC'] = end
            self.assertEqual(e.interval(row)['interval_status'], status)
            self.assertEqual(e.interval(row)['raw_end_date'], end)
        rs = copy.deepcopy(e.records['RS-002-1'])
        rs['values']['RSENDTC'] = '2025-02-03'
        self.assertEqual(e.interval(rs)['interval_status'], 'complete')

    def test_context_selection_replay_hide_and_analysis_exclusion(self):
        e = self.engine
        spec = e.default_spec()
        for domain in ['AE','CM','EX','RS']:
            rid = domain + '-002-1'
            mark_id = 'mark:' + spec['snapshot_id'] + ':' + rid
            evidence = e.pick(spec, mark_id)
            self.assertEqual(evidence['source_records'][0]['ref']['record_id'], rid)
            spec['view_state']['selection'] = {'mark_id': mark_id, 'source_record_ids': [rid]}
            package = e.export_review(spec)
            self.assertEqual(e.replay(package)['spec'], spec)
        spec['view_state']['hidden_lanes'] = ['RS']
        hidden = e.evaluate(spec)
        self.assertFalse(hidden['selection_visible'])
        self.assertEqual(hidden['spec']['view_state']['selection']['source_record_ids'], ['RS-002-1'])
        with self.assertRaisesRegex(ValueError, 'mark_not_pickable'):
            e.pick(spec, mark_id)
        spec['analysis_state']['population'] = [['SYN-SPIKE','SYN-001']]
        with self.assertRaisesRegex(ValueError, 'selection_not_eligible'):
            e.evaluate(spec)
        cleared = e.evaluate(spec, analysis_change=True)
        self.assertIsNone(cleared['spec']['view_state']['selection'])
        self.assertEqual(cleared['selection_cleared_reason'], 'analysis_excluded')
        with self.assertRaisesRegex(ValueError, 'snapshot_mismatch'):
            self.small.replay(package)

    def test_display_window_includes_crossing_interval_not_only_start(self):
        e = self.small
        spec = e.default_spec()
        spec['view_state']['display_date_window'] = {'start':'2025-01-11','end':'2025-01-11'}
        marks = e.evaluate(spec)['marks']
        self.assertIn('AE-001-1', [m['record_id'] for m in marks])
        self.assertNotIn('AE-001-2', [m['record_id'] for m in marks])
        e.pick(spec, 'mark:synthetic-spike-v1:AE-001-1')


if __name__ == '__main__':
    unittest.main(verbosity=2)
