"""Source-backed acceptance checks; no network/provider calls or fixture rewrites."""
import copy
from pathlib import Path
import unittest
from app import Engine
from alignment import resolve_alignment
from model_agent import local_tool


class SourceToolAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engines = {cohort: Engine(Path(__file__).parent / 'data', cohort=cohort)
                       for cohort in ('100', 'keynote189')}

    def test_ac3_unsupported_anchor_names_limitation_and_preserves_sources(self):
        for cohort, engine in self.engines.items():
            with self.subTest(cohort=cohort):
                spec = engine.default_spec()
                before = copy.deepcopy((spec, engine.records))
                result = local_tool(engine, spec, 'set_alignment', {'anchor': 'randomization'})
                self.assertEqual(result['status'], 'unsupported')
                self.assertEqual(result['anchor'], 'randomization')
                self.assertEqual(result['denominator'], len(engine.fixtures['population']))
                self.assertIn('unchanged', result['denominator_unit'])
                for disclosure in ('No transform', 'no patients excluded', 'no dates imputed'):
                    self.assertIn(disclosure, result['missing_anchor_handling'])
                self.assertIn('No approximation', result['note'])
                self.assertEqual(result['record_ids'], [])
                self.assertEqual((spec, engine.records), before)

    def test_ac2_proposal_counts_are_computed_from_actual_source_without_mutation(self):
        for engine in self.engines.values():
            spec = engine.default_spec()
            before = copy.deepcopy(spec)
            chosen = spec['analysis_state']['population'][:1]
            proposal = local_tool(engine, spec, 'propose_analysis_subset', {'patients': [chosen[0][1]]})
            after_spec = copy.deepcopy(spec)
            after_spec['analysis_state']['population'] = chosen
            for key, candidate in [('before', spec), ('after', after_spec)]:
                analysis = engine.evaluate(candidate, analysis_change=True)['analysis']
                self.assertEqual(proposal[key], {'patients': len(analysis['qualifying_patient_keys']),
                                                'AE records': len(analysis['qualifying_ae_record_ids'])})
            self.assertEqual(proposal['record_ids'], engine.evaluate(after_spec, analysis_change=True)['analysis']['qualifying_ae_record_ids'])
            self.assertEqual(proposal['status'], 'confirmation_required')
            self.assertEqual(proposal['population'], chosen)
            self.assertEqual(spec, before)

    def test_ac4_inference_and_ambiguity_fail_closed(self):
        engine = self.engines['100']
        spec = engine.default_spec()
        before = copy.deepcopy((spec, engine.records))
        for args in [
            {'scope': 'current_analysis', 'filters': {}},
            {'scope': 'current_analysis', 'unit': 'patients', 'filters': {'caused_by': 'drug'}},
            {'scope': 'current_analysis', 'unit': 'patients', 'filters': {'grade': 'severe'}},
            {'scope': 'current_analysis', 'unit': 'patients', 'filters': {'window': 'after treatment'}}
        ]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                local_tool(engine, spec, 'query_data', args)
            self.assertEqual((spec, engine.records), before)
        result = local_tool(engine, spec, 'clarify_request', {'question': 'Which source anchor and counting unit?'})
        self.assertEqual(result['status'], 'clarification_required')
        self.assertEqual((spec, engine.records), before)

    def test_ac6_count_units_and_contributing_ids_match_actual_source(self):
        for engine in self.engines.values():
            spec = engine.default_spec()
            before = copy.deepcopy(spec)
            results = {}
            for unit in ('patients', 'AE records'):
                result = local_tool(engine, spec, 'query_data', {'scope': 'current_analysis', 'unit': unit, 'filters': {}})
                ids = result['record_ids']
                self.assertTrue(ids)
                self.assertEqual(result['unit'], unit)
                self.assertEqual(len(ids), len(set(ids)))
                patients = set()
                for rid in ids:
                    row = engine.records[rid]
                    self.assertEqual(row['dataset'], 'AE')
                    patients.add((row['values']['STUDYID'], row['values']['USUBJID']))
                self.assertEqual(result['count'], len(ids) if unit == 'AE records' else len(patients))
                results[unit] = result
            self.assertEqual(results['patients']['record_ids'], results['AE records']['record_ids'])
            self.assertEqual(spec, before)

    def test_source_alignment_targets_use_recorded_response_and_preserve_dates(self):
        expected = {'100': {'first_treatment': 100, 'first_PR': 25, 'first_PD': 97, 'death': 0},
                    'keynote189': {'first_treatment': 60, 'first_PR': 23, 'first_PD': 45, 'death': 36}}
        for cohort, engine in self.engines.items():
            before = copy.deepcopy(engine.records)
            for anchor, count in expected[cohort].items():
                with self.subTest(cohort=cohort, anchor=anchor):
                    result = resolve_alignment(engine, anchor)
                    self.assertEqual(result['counts']['resolved'], count)
                    self.assertEqual(sum(result['counts'].values()), result['denominator'])
                    for patient in result['patients']:
                        if patient['status'] != 'resolved':
                            self.assertIsNone(patient['date'])
                        elif anchor == 'first_PR':
                            for rid in patient['record_ids']:
                                row = engine.records[rid]['values']
                                self.assertEqual(row['RSORRES'], 'PR')
                                self.assertEqual(row['RSDTC'], patient['date'])
            self.assertEqual(engine.records, before)


if __name__ == '__main__':
    unittest.main()
