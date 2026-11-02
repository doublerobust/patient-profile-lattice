"""Real Chromium zoom, glyph, collision and provenance checks in both views.
Screenshots are synthetic-only; no cloud/image model is involved.
"""
import json
import unittest
from playwright.sync_api import expect
from test_browser import BrowserFixture, EVIDENCE
from waitfor import wait_for

class GrammarBrowserChecks(BrowserFixture):
    cohort = '100'
    initial_counts = '100 qualifying patients · 298 qualifying AE source records'
    default_overview = True

    def settle(self, gpu):
        if gpu:
            wait_for(self.page, '() => clinical3d.ready && !clinical3d.stats().animating')
            self.page.wait_for_timeout(100)
        else:
            expect(self.page.locator('#timeline')).to_have_attribute('data-animating','false')

    def capture(self, name, gpu):
        target=self.page.locator('.scene-frame' if gpu else '.timeline-wrap')
        target.scroll_into_view_if_needed()
        target.screenshot(path=str(EVIDENCE/(name+'.png')))

    def check_layout(self):
        boxes=self.page.locator('.annotation-bg').evaluate_all('es=>es.map(e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}})')
        self.assertGreater(len(boxes),0)
        for i,a in enumerate(boxes):
            for b in boxes[i+1:]:
                self.assertFalse(a['x']<b['x']+b['w'] and a['x']+a['w']>b['x'] and a['y']<b['y']+b['h'] and a['y']+a['h']>b['y'],(a,b))
        return len(boxes)

    def test_shared_grammar_zoom_annotations_selection(self):
        p=self.page
        report={}
        for gpu in (False,True):
            name='3d' if gpu else 'clinical'
            p.goto('http://127.0.0.1:%d%s'%(self.server.server_port,'/3d' if gpu else '/'))
            expect(p.locator('#counts')).to_have_text(self.initial_counts)
            p.emulate_media(reduced_motion='reduce')
            self.settle(gpu)
            initial=p.request.get('http://127.0.0.1:%d/api/initial'%self.server.server_port).json()
            signature=p.locator('#diagnostics').text_content()
            expect(p.locator('[data-legend-domain]')).to_have_count(5)
            config=p.evaluate('ClinicalGrammar.domains')
            self.assertEqual(len({d['color'] for d in config.values()}),5)
            self.assertEqual(len({d['path'] for d in config.values()}),5)
            expect(p.locator('.annotation')).to_have_count(0)
            self.capture(name+'-overview',gpu)
            self.select('tiers','2')
            self.settle(gpu)
            expect(p.locator('.annotation')).to_have_count(0)
            expect(p.locator('.followup-label,.end-unknown')).to_have_count(0)
            if not gpu:
                for lane,d in config.items():
                    expect(p.locator('.mark[data-domain="'+lane+'"]').first).to_have_attribute('data-symbol',d['symbol'])
                for record,line in [('AE-004-1','round'),('CM-004-1','dashed'),('EX-004-2','double')]:
                    expect(p.locator('[data-record-id="'+record+'"] .interval-body')).to_have_attribute('data-line-treatment',line)
            self.select('focus','[["SYN-SPIKE","SYN-004"]]')
            self.select('event-selector','AE-004-1')
            self.settle(gpu)
            baseline=self.spec()
            if gpu:
                p.click('#readable');self.settle(gpu)
                p.click('#zoom-out');self.settle(gpu)
            else:
                p.click('#reset-zoom');self.settle(gpu)
                # Pointer anchored at the source onset, not at an interval's midpoint.
                point=p.locator('[data-record-id="AE-004-1"]').evaluate('e=>{const p=new DOMPoint(+e.dataset.x,+e.dataset.y).matrixTransform(e.ownerSVGElement.getScreenCTM());return {clientX:p.x,clientY:p.y}}')
                p.locator('#timeline').dispatch_event('wheel',dict(point,deltaY=-330))
                self.settle(gpu)
            expect(p.locator('.annotation-layer')).to_have_attribute('data-annotation-level','1')
            mid=self.check_layout()
            self.assertTrue(all('Severity' not in s for s in p.locator('.annotation').all_text_contents()))
            self.capture(name+'-mid',gpu)
            if gpu:
                p.click('#readable');self.settle(gpu)
            else:
                point=p.locator('[data-record-id="AE-004-1"]').evaluate('e=>{const p=new DOMPoint(+e.dataset.x,+e.dataset.y).matrixTransform(e.ownerSVGElement.getScreenCTM());return {clientX:p.x,clientY:p.y}}')
                p.locator('#timeline').dispatch_event('wheel',dict(point,deltaY=-400))
                self.settle(gpu)
            expect(p.locator('.annotation-layer')).to_have_attribute('data-annotation-level','2')
            close=self.check_layout()
            expect(p.locator('.annotation[data-annotation-for="AE-004-1"]')).to_contain_text('Severity SEVERE')
            expect(p.locator('.annotation[data-annotation-for="AE-004-1"]')).to_contain_text('2025-01-11')
            self.assertEqual(self.spec(),baseline)
            self.capture(name+'-close',gpu)
            checks=[('AE-004-2',['SYNTHETIC EVENT','ongoing at last observed 2025-02-05 (AEFUDTC)','serious no']),
                    ('AE-004-3',['end unknown','no duration imputed']),
                    ('CM-004-1',['SYNTHETIC MEDICATION','CMFUDTC']),
                    ('EX-004-2',['SYNTHETIC TREATMENT','INTERRUPTION','Dose not recorded']),
                    ('RS-004-1',['OVRLRESP','CR']),('DS-004-1',['TREATMENT DISCONTINUATION','PROGRESSIVE DISEASE'])]
            for record,contents in checks:
                self.select('event-selector',record)
                for text in contents:expect(p.locator('#selected-annotation')).to_contain_text(text)
                source=json.loads(p.locator('#sources > .source-card pre').first.text_content())
                expected=p.request.post('http://127.0.0.1:%d/api/source'%self.server.server_port,data={'record_id':record}).json()
                self.assertEqual(source,expected)
            # Recheck actual selection after camera move, not just the dropdown.
            if gpu:
                self.select('event-selector','AE-004-1');p.click('#readable');self.settle(gpu)
                p.click('#oblique');self.settle(gpu)
                p.click('#peel');self.settle(gpu)
                p.locator('#scene').scroll_into_view_if_needed()
                point=p.evaluate("clinical3d.projectRecord('RS-004-1')")
                p.mouse.click(point['x'],point['y'])
                chooser=p.locator('#coincident-events')
                if chooser.is_visible():chooser.get_by_role('button',name=__import__('re').compile('RS-004-1')).click()
                expect(p.locator('#sources')).to_contain_text('RS-004-1')
                self.check_layout()
                self.capture(name+'-rotated',gpu)
            else:
                self.select('event-selector','AE-004-1')
                p.locator('[data-record-id="AE-004-1"] .domain-symbol').click(force=True)
                expect(p.locator('#sources')).to_contain_text('AE-004-1')
            self.assertEqual(p.locator('#diagnostics').text_content(),signature)
            expect(p.locator('#counts')).to_have_text(self.initial_counts)
            p.click('#reset-zoom');self.settle(gpu)
            expect(p.locator('.annotation')).to_have_count(0)
            report[name]={'mid_labels':mid,'close_labels':close,'source_checks':len(checks),'analysis_unchanged':True,'config':config,'browser_errors':list(self.errors)}
        (EVIDENCE/'grammar-interactions.json').write_text(json.dumps({'browser':self.browser.version,'viewport':{'width':1440,'height':1100},'views':report},indent=2)+'\n')

    def test_collision_allocator_and_missing_values(self):
        p=self.page
        result=p.evaluate('''()=>{
            const m={lane:'EX',record_id:'EX-synthetic-test',display_id:'test',patient_key:['SYN','TEST'],tier:1,annotation:{term:'TEST DRUG',fields:{EXDOSE:0,EXDOSU:'mg',EXADJ:'INTERRUPTION'}},raw_date:'2025-01-01',is_interval:true,end_state:'unknown'};
            const candidates=Array.from({length:50},(_,i)=>({mark:{...m,display_id:'test'+i,record_id:'test'+i},x:200+i%2,y:100}));
            return {detail:ClinicalGrammar.lines(m,2),overview:ClinicalGrammar.layout(candidates,{left:0,right:900,top:0,bottom:250},0),close:ClinicalGrammar.layout(candidates,{left:0,right:900,top:0,bottom:250},2)};
        }''')
        self.assertIn('Dose 0 mg · INTERRUPTION',result['detail'])
        self.assertEqual(result['overview'],[])
        self.assertGreater(len(result['close']),0)
        self.assertLessEqual(len(result['close']),4)

if __name__=='__main__':unittest.main(verbosity=2)
