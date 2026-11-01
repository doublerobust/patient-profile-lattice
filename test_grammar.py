"""Source projection contract: never invent absent clinical values."""
import unittest
from pathlib import Path
from app import Engine

class AnnotationChecks(unittest.TestCase):
    def setUp(self):
        self.engine = Engine(Path(__file__).parent / 'data', cohort='100')
        self.state = self.engine.evaluate(self.engine.default_spec())
        self.marks = {m['record_id']: m for m in self.state['marks']}

    def test_annotation_preserves_source_values_and_counts(self):
        self.assertEqual(self.state['analysis']['qualifying_patient_count'], 100)
        self.assertEqual(self.state['analysis']['qualifying_ae_record_count'], 298)
        for m in self.state['marks']:
            annotation = m['annotation']
            values = self.engine.records[m['record_id']]['values']
            for field, value in annotation['fields'].items():
                self.assertEqual(value, values[field])
            self.assertEqual(self.engine.evidence(m['record_id'])['source_records'][0]['values'], values)
        self.assertEqual(self.marks['AE-004-1']['annotation']['term'], 'SYNTHETIC EVENT')
        self.assertEqual(self.marks['AE-004-1']['annotation']['fields']['AESER'], 'Y')
        self.assertEqual(self.marks['RS-004-1']['annotation']['fields']['RSORRES'], 'CR')
        self.assertEqual(self.marks['EX-004-2']['annotation']['fields']['EXADJ'], 'INTERRUPTION')
        self.assertNotIn('EXDOSE', self.marks['EX-004-2']['annotation']['fields'])

    def test_sentinel_annotations_keep_record_identity(self):
        for sentinel in self.state['sentinels']:
            self.assertEqual(sentinel['annotation'], self.marks[sentinel['record_id']]['annotation'])
            self.assertEqual(sentinel['source_ref'], self.marks[sentinel['record_id']]['source_ref'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
