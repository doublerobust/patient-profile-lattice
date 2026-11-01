"""Ordinary reviewer-path checks against the shipped golden fixtures."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from app import Engine, canonical, digest

ROOT = Path(__file__).resolve().parent


class LaneViewChecks(unittest.TestCase):
    def setUp(self):
        self.engine = Engine(ROOT / 'data')
        self.spec = self.engine.default_spec()
        self.golden = self.engine.ref.load('expected_results.json')['fixtures']

    def test_reviewer_path_and_replay(self):
        e = self.engine
        baseline = e.evaluate(self.spec)
        for k, v in baseline['analysis'].items():
            self.assertEqual(v, self.golden['F01_counts'][k])
        self.spec['view_state']['patient_sort'][0]['direction'] = 'desc'
        self.assertEqual(e.evaluate(self.spec)['visible_patient_keys'],
                         self.golden['F07_view_replay_picking']['operations'][0]['visible_patient_order'])
        self.spec['view_state']['hidden_lanes'] = ['CM']
        self.spec['view_state']['focus_patient_keys'] = [['SYN-SPIKE', 'SYN-001']]
        state = e.evaluate(self.spec)
        self.assertEqual(state['analysis'], baseline['analysis'])
        self.assertEqual(state['analysis_signature'], baseline['analysis_signature'])
        self.assertEqual(state['lane_order'], ['AE', 'EX', 'RS'])
        evidence = e.pick(self.spec, 'mark:synthetic-spike-v1:AE-001-2')
        self.assertEqual(evidence['source_records'][0]['ref']['row_number'], 2)
        self.assertEqual(evidence['source_records'][0]['ref']['source_key']['AESEQ'], 2)
        saved = e.export_review(self.spec)
        restored = e.replay(json.loads(canonical(saved)))
        self.assertEqual(canonical(restored['spec']), canonical(state['spec']))
        self.assertEqual(restored['analysis'], state['analysis'])
        self.spec['view_state']['hidden_lanes'] = ['CM', 'AE']
        self.assertIsNotNone(e.evaluate(self.spec)['spec']['view_state']['selection'])
        with self.assertRaisesRegex(ValueError, 'mark_not_pickable'):
            e.pick(self.spec, 'mark:synthetic-spike-v1:AE-001-2')
        self.spec['analysis_state']['population'] = [['SYN-SPIKE', 'SYN-002']]
        filtered = e.evaluate(self.spec, analysis_change=True)
        self.assertIsNone(filtered['spec']['view_state']['selection'])
        self.assertEqual(filtered['selection_cleared_reason'], 'analysis_excluded')
        self.assertEqual(filtered['analysis']['qualifying_ae_record_ids'], ['AE-002-1'])
        self.spec = filtered['spec']
        self.spec['view_state']['focus_patient_keys'] = []
        self.spec['view_state']['hidden_lanes'] = []
        self.assertEqual(e.pick(self.spec, 'mark:synthetic-spike-v1:AE-002-1')['source_records'][0]['ref']['row_number'], 4)

    def test_relationships_and_supplement_traceability(self):
        ev = self.engine.pick(self.spec, 'mark:synthetic-spike-v1:AE-001-1')
        rel = ev['relationships'][0]
        self.assertEqual(rel['evidence'], self.golden['F02_group_endpoint'])
        self.assertEqual({r['ref']['record_id'] for r in rel['source_records']},
                         {'REL-1', 'REL-2', 'AE-001-1', 'CM-001-1', 'CM-001-2'})
        self.assertEqual(ev['supplements'][0]['parent_source_record_ids'], ['AE-001-1'])
        self.assertEqual(ev['supplements'][0]['source_record']['values']['QEVAL'], '')
        ev = self.engine.pick(self.spec, 'mark:synthetic-spike-v1:AE-002-1')
        self.assertTrue(any(r['evidence'] == self.golden['F04_undocumented_meaning'] for r in ev['relationships']))

    def test_normalization_sorts_sets_only_and_keeps_fixed_lane_order(self):
        original = copy.deepcopy(self.spec)
        self.spec['analysis_state']['population'].reverse()
        self.spec['view_state']['hidden_lanes'] = ['RS', 'CM']
        normalized = self.engine.normalize(self.spec)
        self.assertEqual(normalized['analysis_state']['population'], original['analysis_state']['population'])
        self.assertEqual(normalized['view_state']['hidden_lanes'], ['CM', 'RS'])
        self.assertEqual(normalized['view_state']['patient_sort'], original['view_state']['patient_sort'])
        # Canonical encoding must NEVER reorder ordered arrays, including future sort priorities.
        ordered = {'patient_sort': ['b', 'a'], 'lane_order': ['EX', 'AE', 'CM']}
        self.assertEqual(json.loads(canonical(ordered)), ordered)
        self.assertEqual(self.engine.evaluate(self.spec)['lane_order'], ['AE', 'EX'])
        self.spec['view_state']['hidden_lanes'] = ['AE', 'AE']
        with self.assertRaises(Exception):
            self.engine.normalize(self.spec)

    def test_replay_tampering_rejected_without_modifying_input(self):
        for mutation, message in [
            (lambda p: p.update(content_sha256='0' * 64), 'content_hash_mismatch'),
            (lambda p: p['source_records'][0]['ref']['source_key'].update(AESEQ=999), 'provenance_mismatch'),
            (lambda p: p['spec'].update(snapshot_sha256='0' * 64), 'snapshot_mismatch'),
            (lambda p: p['spec'].update(rule_bundle_sha256='0' * 64), 'rule_bundle_mismatch'),
        ]:
            with self.subTest(message=message):
                package = self.engine.export_review(self.spec)
                mutation(package)
                if message != 'content_hash_mismatch':
                    package['content_sha256'] = digest({k: v for k, v in package.items() if k != 'content_sha256'})
                with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
                    path = Path(tmp) / 'review.json'
                    path.write_bytes(canonical(package))
                    before = path.read_bytes()
                    result = subprocess.run([sys.executable, 'app.py', '--cohort', 'small', '--verify', str(path)], cwd=ROOT, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn(message, result.stderr)
                    self.assertEqual(path.read_bytes(), before)

    def test_fixture_parent_link_tamper_is_not_repaired(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            data = Path(tmp) / 'data'
            shutil.copytree(ROOT / 'data', data)
            path = data / 'fixtures.json'
            fixture = json.loads(path.read_text())
            fixture['datasets']['SUPPAE'][0]['values']['IDVARVAL'] = '999'
            path.write_bytes(canonical(fixture))
            before = path.read_bytes()
            result = subprocess.run([sys.executable, 'app.py', '--data', str(data), '--verify-data'], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('file_hash_mismatch', result.stderr)
            self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
