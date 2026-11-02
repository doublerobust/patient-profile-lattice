"""Synthetic derivative integrity and source-term tool acceptance; no trial rates."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from app import Engine, ROOT
from model_agent import local_tool


FIXTURE = ROOT / 'fixtures/keynote189-synthetic'
UPSTREAM_HASH = '4dd5639d3b9799ee6c8b31615659d2433452fd6e077aca1ba8cb7d26064fbb54'


class TableS4Checks(unittest.TestCase):
    def test_derivative_preserves_upstream_and_only_changes_mapped_fields(self):
        from populate_ae_table_s4 import populate, TABLE_S4
        content = (FIXTURE / 'raw.json').read_bytes()
        self.assertEqual(hashlib.sha256(content).hexdigest(), UPSTREAM_HASH)
        upstream = json.loads(content)
        derivative = json.loads((FIXTURE / 'table-s4-synthetic.json').read_text())
        self.assertEqual(populate(upstream), derivative)
        self.assertEqual(json.loads(content), upstream, 'populate must not mutate its input')
        restored = copy.deepcopy(derivative)
        terms = {row['term'] for p in derivative['PTS'] for row in p['ae']}
        self.assertEqual(terms, {row[0] for row in TABLE_S4})
        self.assertEqual(len(terms), 40)
        self.assertEqual(sum(len(p['ae']) for p in derivative['PTS']), 260)
        for old, new in zip(upstream['PTS'], restored['PTS']):
            for old_row, new_row in zip(old['ae'], new['ae']):
                for key in ('term', 'soc', 'ir'):
                    new_row[key] = old_row[key]
        self.assertEqual(restored, upstream)

    def test_manifest_pins_both_files_and_distinguishes_categories(self):
        from populate_ae_table_s4 import TABLE_S4, DERIVATIVE_SHA256
        manifest = json.loads((FIXTURE / 'provenance.json').read_text())
        self.assertEqual(manifest['raw_sha256'], UPSTREAM_HASH)
        derived = manifest['local_derivative']
        self.assertEqual(derived['sha256'], DERIVATIVE_SHA256)
        self.assertEqual(hashlib.sha256((FIXTURE / derived['file']).read_bytes()).hexdigest(), derived['sha256'])
        self.assertEqual(derived['assignment'], 'unweighted source-order round-robin across existing AE rows; independent of arm')
        self.assertEqual(len(TABLE_S4), 40)
        self.assertEqual(sum(row[2] for row in TABLE_S4), 12)
        self.assertIn('not trial data', derived['warning'])
        self.assertIn('related terms', derived['event_category_note'])

    def test_loader_rejects_corrupt_derivative(self):
        original = Path.read_bytes
        def corrupt(path):
            data = original(path)
            return data + b' ' if path.name == 'table-s4-synthetic.json' else data
        with patch.object(Path, 'read_bytes', corrupt), self.assertRaisesRegex(ValueError, 'scenario_derivative_hash_mismatch'):
            Engine(ROOT / 'data', 'keynote189')

    def test_term_query_and_highlight_retain_units_and_derivative_provenance(self):
        engine = Engine(ROOT / 'data', 'keynote189')
        spec = engine.default_spec()
        before = copy.deepcopy(spec)
        term = 'Lacrimation increased'
        expected = sorted(rid for rid, row in engine.records.items()
                          if row['dataset'] == 'AE' and row['values']['AETERM'] == term)
        self.assertTrue(expected, 'New Table S4 term must be present')
        filters = {'term': term}
        highlight = local_tool(engine, spec, 'highlight_events', {'scope': 'current_analysis', 'filters': filters})
        self.assertEqual(sorted(highlight['record_ids']), expected)
        self.assertEqual(highlight['unit'], 'AE records')
        self.assertIn('not trial prevalence', highlight['note'])
        for unit in ('patients', 'AE records'):
            result = local_tool(engine, spec, 'query_data', {'scope': 'current_analysis', 'unit': unit, 'filters': filters, 'include_records': True}, record_egress=True)
            self.assertEqual(sorted(result['record_ids']), expected)
            self.assertEqual(result['unit'], unit)
            count = len(expected) if unit == 'AE records' else len({engine.records[r]['values']['USUBJID'] for r in expected})
            self.assertEqual(result['count'], count)
        for rid in expected:
            source = engine.original_sources[rid]
            self.assertEqual(source['fixture'], 'fixtures/keynote189-synthetic/table-s4-synthetic.json')
            self.assertEqual(source['upstream_fixture'], 'fixtures/keynote189-synthetic/raw.json')
            self.assertEqual(source['upstream_raw_sha256'], UPSTREAM_HASH)
            self.assertTrue(source['synthetic_only'])
            self.assertEqual(source['row']['term'], term)
            self.assertEqual(source['term_provenance']['literal_term'], term)
            self.assertIn('not trial data', source['term_provenance']['warning'])
        self.assertEqual(spec, before)

    def test_reextract_does_not_erase_derivative_manifest(self):
        import extract_scenario
        import tempfile
        import contextlib
        import io
        from types import SimpleNamespace
        raw = (FIXTURE / 'raw.json').read_text()
        metadata = (FIXTURE / 'provenance.json').read_text()
        # Unit-test extraction I/O with explicitly mocked generator/network.
        fake_source = b'// test-only generator\n// ---------- Derived per-patient metrics + signal engine ----------'
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            target = Path(directory)
            (target / 'provenance.json').write_text(metadata)
            with patch.object(extract_scenario, 'ROOT', target), \
                 patch.object(extract_scenario, 'SOURCE_SHA256', hashlib.sha256(fake_source).hexdigest()), \
                 patch.object(extract_scenario, 'urlopen') as fetch, \
                 patch.object(extract_scenario.subprocess, 'run', return_value=SimpleNamespace(stdout=raw)):
                fetch.return_value.read.return_value = fake_source
                with contextlib.redirect_stdout(io.StringIO()):
                    extract_scenario.extract()
            after = json.loads((target / 'provenance.json').read_text())
            self.assertEqual(after['local_derivative'], json.loads(metadata)['local_derivative'])
            self.assertEqual(after['imported_at_utc'], json.loads(metadata)['imported_at_utc'])
            self.assertEqual(hashlib.sha256((target / 'raw.json').read_bytes()).hexdigest(), UPSTREAM_HASH)

    def test_category_not_claimed_as_single_preferred_term(self):
        engine = Engine(ROOT / 'data', 'keynote189')
        sources = [s for s in engine.original_sources.values() if s['group'] == 'ae' and s['row']['term'] == 'Severe skin reactions']
        self.assertTrue(sources)
        for source in sources:
            self.assertEqual(source['term_provenance']['kind'], 'event category including related terms')
            self.assertTrue(source['row']['ir'])


if __name__ == '__main__':
    unittest.main()
