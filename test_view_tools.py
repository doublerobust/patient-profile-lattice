import unittest
from pathlib import Path
from app import Engine
from view_tools import query_records

class ToolChecks(unittest.TestCase):
    def setUp(self):
        self.engine = Engine(Path(__file__).parent / 'data', cohort='100')
        self.spec = self.engine.default_spec()

    def test_units_and_ids(self):
        args = {'scope':'current_analysis','filters':{'grade':3},'unit':'AE records'}
        a = query_records(self.engine, self.spec, args)
        b = query_records(self.engine, self.spec, {**args,'unit':'patients'})
        self.assertEqual(a['record_ids'], b['record_ids'])
        self.assertEqual(a['count'], len(a['record_ids']))
        self.assertEqual(b['count'], len(b['patient_keys']))
        self.assertEqual(a['unit'], 'AE records')
        self.assertEqual(b['unit'], 'patients')
        self.assertGreater(a['count'], 0)

    def test_refuse_ambiguity(self):
        for args in [{'filters':{'grade':3}}, {'scope':'current_analysis','unit':'patients','filters':{'window':'after treatment'}}, {'scope':'current_analysis','unit':'patients','filters':{'grade':True}}]:
            with self.assertRaises(ValueError): query_records(self.engine,self.spec,args)

    def test_dates_linked_cm_and_missing_grade(self):
        args={'scope':'current_analysis','unit':'AE records','filters':{'patient':'SYN-001','linked_cm':'SYNTHETIC MED A'}}
        result=query_records(self.engine,self.spec,args)
        # REL-1 selects AESEQ=1 (not the whole AEGRPID); only CM-001-1 has MED A.
        self.assertEqual(result['record_ids'],['AE-001-1'])
        self.assertEqual(result['linked_record_ids'],['CM-001-1'])
        args['filters']['date_window']={'anchor':'AESTDTC','start':'2025-01-10','end':'2025-01-10'}
        self.assertEqual(query_records(self.engine,self.spec,args)['record_ids'],['AE-001-1'])
        args['filters']={'patient':'SYN-001','grade':3}
        result=query_records(self.engine,self.spec,args)
        self.assertEqual(result['count'],0) # SEVERE is not grade 3.
        self.assertGreater(result['excluded_missing_grade'],0)
        for window in [None,{'start':'2025-01-01','end':'2025-01-31'}, {'anchor':'EXSTDTC','start':'2025-01-01','end':'2025-01-31'}, {'anchor':'AESTDTC','start':'2025-02-30','end':'2025-03-31'}]:
            args['filters']={'date_window':window}
            with self.assertRaises(ValueError):query_records(self.engine,self.spec,args)

    def test_view_independent(self):
        args={'scope':'current_analysis','unit':'AE records','filters':{}}
        before=query_records(self.engine,self.spec,args)
        self.spec['view_state']['hidden_lanes']=['AE']
        self.assertEqual(before,query_records(self.engine,self.spec,args))
