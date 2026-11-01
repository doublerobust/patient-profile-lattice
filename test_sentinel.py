import copy
import unittest
from pathlib import Path
from app import Engine

ROOT = Path(__file__).resolve().parent

class SentinelChecks(unittest.TestCase):
    def setUp(self):
        self.e = Engine(ROOT / 'data', cohort='100')

    def test_config_and_sentinel_budget(self):
        state = self.e.evaluate(self.e.default_spec())
        self.assertEqual(state['display_config']['version'], '1.0.0')
        marks = state['marks'] + state['sentinels']
        kinds = {m['display_kind'] for m in marks if m['tier'] == 0}
        self.assertTrue({'treatment_start','first_response','first_pd','death','last_dose','trial_withdrawal','subsequent_therapy'} <= kinds)
        for patient in state['visible_patient_keys']:
            self.assertLessEqual(sum(m['patient_key']==patient and m['tier']==0 for m in marks), 8)
        for m in marks:
            if m['record_id'].startswith('AE-') and m['display_kind']=='death':
                self.assertFalse(m['is_interval'])
                self.assertEqual(m['tier'], 0)

    def test_end_states_and_no_rfendtc_fallback(self):
        row = copy.deepcopy(self.e.records['AE-002-1'])
        v = row['values']
        self.assertEqual(self.e.interval(row)['end_state'], 'recorded')
        v.pop('AEENDTC')
        v['RFENDTC'] = '2026-01-01'
        unknown = self.e.interval(row)
        self.assertEqual(unknown['end_state'], 'unknown')
        self.assertIsNone(unknown['end_date'])
        v.update(AEONGO='Y', AEFUDTC='2025-02-10')
        ongoing = self.e.interval(row)
        self.assertEqual(ongoing['end_state'], 'ongoing')
        self.assertEqual(ongoing['end_date'], v['AEFUDTC'])
        self.assertEqual(ongoing['end_source'], 'AEFUDTC')
        v['AEONGO'] = 'N'
        self.assertEqual(self.e.interval(row)['end_state'], 'unknown')
        row['dataset']='CM'
        row['values']={'CMSTDTC':'2025-01-01','CMONGO':'Y','CMFUDTC':'2025-02-01'}
        self.assertEqual(self.e.interval(row)['end_state'], 'ongoing')

    def test_source_derived_sort_metrics_and_severity(self):
        state = self.e.evaluate(self.e.default_spec())
        metrics = state['patient_summaries']
        self.assertEqual(len(metrics),100)
        self.assertGreater(len({m['treatment_duration'] for m in metrics}), 10)
        self.assertTrue(any(m['time_to_pd'] is not None for m in metrics))
        self.assertTrue(any(m['best_response']=='CR' for m in metrics))
        self.assertTrue(any(m['discontinuation_reason']=='WITHDRAWAL BY SUBJECT' for m in metrics))
        for mark in state['marks']:
            v=self.e.records[mark['record_id']]['values']
            if mark['lane']=='AE' and v.get('AETOXGR') != '5':
                expected=1 if v.get('AESER')=='Y' or int(v.get('AETOXGR','0'))>=3 or v.get('AESEV')=='SEVERE' else 2
                self.assertEqual(mark['tier'],expected)

if __name__=='__main__': unittest.main(verbosity=2)
