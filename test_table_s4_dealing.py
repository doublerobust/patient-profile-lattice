"""Construction guards, not tests of statistical neutrality or trial incidence."""
import ast
from collections import Counter
import copy
import hashlib
import inspect
import json
import random
import subprocess
import unittest
from unittest.mock import patch

import populate_ae_table_s4 as generator

BASELINE = 'fe42e74'
PREVIOUS_SHA256 = '4cd25aba56fd5163b99f6fee0ef76796dac53b03cc93b89c55284f3d87b11557'
CONSTRAINT = ('Uniform per-arm term dealing to ensure vocabulary coverage in both arms; '
              'arm is used as a balancing key, with no source incidence weights. '
              'Patient-level and arm-level patterns remain synthetic.')


def encode(data):
    return (json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n').encode()


class PerArmDealingChecks(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((generator.ROOT / 'raw.json').read_bytes())

    def test_every_term_covered_uniformly_in_each_arm(self):
        result = generator.populate(self.raw)
        terms = {term for term, _, _ in generator.TABLE_S4}
        self.assertEqual(len(terms), 40)
        for arm, total, minimum in [('P', 179, 4), ('B', 81, 2)]:
            counts = Counter(row['term'] for p in result['PTS'] if p['arm'] == arm for row in p['ae'])
            self.assertEqual(sum(counts.values()), total)
            self.assertEqual(set(counts), terms, arm)
            self.assertEqual(min(counts.values()), minimum)
            self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)

    def test_shuffle_receives_finished_assignments_not_just_deck(self):
        original_shuffle = random.Random.shuffle
        seen = []

        def capture(rng, assignments):
            seen.append(list(assignments))
            original_shuffle(rng, assignments)

        with patch.object(random.Random, 'shuffle', capture):
            result = generator.populate(self.raw)
        self.assertEqual(sorted(map(len, seen)), [81, 179])
        for assignments in seen:
            self.assertEqual(assignments, [generator.TABLE_S4[i % 40] for i in range(len(assignments))])
        for arm in ('P', 'B'):
            terms = [row['term'] for p in result['PTS'] if p['arm'] == arm for row in p['ae']]
            self.assertNotEqual(terms[:40], terms[40:80], 'must not repeat a shuffled deck')

    def test_same_seed_identical_bytes_and_no_global_rng_effect(self):
        state = random.getstate()
        first = encode(generator.populate(self.raw, seed=20261102))
        second = encode(generator.populate(self.raw, seed=20261102))
        self.assertEqual(first, second)
        self.assertEqual(first, (generator.ROOT / 'table-s4-synthetic.json').read_bytes())
        self.assertEqual(hashlib.sha256(first).hexdigest(), generator.DERIVATIVE_SHA256)
        self.assertEqual(state, random.getstate())

    def test_generator_inputs_exclude_source_incidence(self):
        # Inspect the actual API, map schema and data reads, not output frequencies.
        self.assertEqual(list(inspect.signature(generator.populate).parameters), ['raw', 'seed'])
        self.assertEqual(inspect.signature(generator.populate).parameters['seed'].default, 20261102)
        for entry in generator.TABLE_S4:
            self.assertEqual(len(entry), 3)
            self.assertEqual(tuple(map(type, entry)), (str, str, bool))
        tree = ast.parse(inspect.getsource(generator.populate))
        reads = {node.slice.value for node in ast.walk(tree)
                 if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load)
                 and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str)}
        self.assertEqual(reads, {'PTS', 'arm', 'ae'})
        calls = {ast.unparse(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
        self.assertEqual(calls, {'copy.deepcopy', 'rows_by_arm.setdefault', 'rows_by_arm[patient[\'arm\']].extend',
                                'random.Random', 'sorted', 'range', 'len', 'rng.shuffle', 'zip'})
        # With only those structural inputs, assignments must be identical.
        minimal = {'PTS': [{'arm': p['arm'], 'ae': [{} for _ in p['ae']]} for p in self.raw['PTS']]}
        result = generator.populate(minimal)
        full = generator.populate(self.raw)
        self.assertEqual([[row for row in p['ae']] for p in result['PTS']],
                         [[{key: row[key] for key in ('term', 'soc', 'ir')} for row in p['ae']] for p in full['PTS']])

    def test_previous_derivative_non_target_fields_and_vocabulary_unchanged(self):
        # Pin the actual previous published bytes, not a reconstructed baseline.
        previous = subprocess.check_output(['git', 'show', BASELINE + ':fixtures/keynote189-synthetic/table-s4-synthetic.json'])
        self.assertEqual(hashlib.sha256(previous).hexdigest(), PREVIOUS_SHA256)
        before = json.loads(previous)
        after = generator.populate(self.raw)
        old_mapping = {(r['term'], r['soc'], r['ir']) for p in before['PTS'] for r in p['ae']}
        self.assertEqual(old_mapping, set(generator.TABLE_S4))
        for data in (before, after):
            for patient in data['PTS']:
                for row in patient['ae']:
                    for key in ('term', 'soc', 'ir'):
                        del row[key]
        self.assertEqual(before, after, 'dates, grades, seriousness, IDs, order, row counts and other domains')
        self.assertEqual(hashlib.sha256((generator.ROOT / 'raw.json').read_bytes()).hexdigest(), generator.UPSTREAM_SHA256)

    def test_manifest_records_demo_constraint_and_seed(self):
        manifest = json.loads((generator.ROOT / 'provenance.json').read_text())['local_derivative']
        self.assertEqual(manifest['assignment'], CONSTRAINT)
        self.assertEqual(manifest['assignment_seed'], 20261102)


if __name__ == '__main__':
    unittest.main()
