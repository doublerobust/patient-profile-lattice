"""Synthetic real-Chromium V-set and click-focus acceptance checks."""
import json
import os
import unittest
from collections import Counter
from datetime import datetime, timezone
from playwright.sync_api import expect
from test_browser import BrowserFixture, EVIDENCE


def stamp(value):
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp()*1000 if value else None


class FocusChecks(BrowserFixture):
    cohort = '100'
    initial_counts = '100 qualifying patients · 298 qualifying AE source records'
    default_overview = True

    def settle(self, gpu):
        if gpu:
            self.page.wait_for_function('() => clinical3d.ready && !clinical3d.stats().animating')
        else:
            expect(self.page.locator('#timeline')).to_have_attribute('data-animating', 'false')
        self.page.wait_for_timeout(60)

    def route(self, gpu):
        self.page.goto(f'http://127.0.0.1:{self.server.server_port}' + ('/3d' if gpu else '/'))
        expect(self.page.locator('#counts')).to_have_text(self.initial_counts)
        self.page.emulate_media(reduced_motion='reduce')
        self.settle(gpu)

    def measure(self, gpu):
        p = self.page
        data = p.evaluate('state')
        if gpu:
            audit = p.evaluate('clinical3d.auditGeometry()')
            actual_marks = audit['marks']
            tier = audit['lastTier']
            v = audit['view']
            half_x = v['span']*audit['width']/audit['height']/2
            left, right = v['x']-half_x, v['x']+half_x
            bottom, top = v['y']-v['span']/2, v['y']+v['span']/2
            row = {tuple(k): -i*14 for i, k in enumerate(audit['patients'])}
            self.assertEqual([v['yaw'],v['pitch'],v['peel']],[0,0,0])
            scale = min(1, v['span']/audit['height'])
            def intersects(m):
                x = 120+(stamp(m['date'])-audit['minDate'])/(audit['maxDate']-audit['minDate'])*1640 if m['date'] else 1860
                end = 120+(stamp(m['end_date'])-audit['minDate'])/(audit['maxDate']-audit['minDate'])*1640 if m['interval_status'] in ('complete','ongoing') else x
                y=row[tuple(m['patient_key'])]
                # Pixel-capped domain/end/sentinel quads (31 Oct), independently
                # reconstructed from the documented sizes, not audit's owner set.
                rects: list[tuple[float,float,float,float]]=[(x,y,13*scale,13*scale)]
                if m['display_kind'] in data['display_config']['tiers'][0]['kinds']:
                    rects.append((x+12*scale,y,11*scale,11*scale))
                selected=m['mark_id']==data['spec']['view_state']['selection']['mark_id']
                low=m['lane'] in ('AE','CM') and m['tier']!=0 and not selected
                if m['interval_status'] in ('complete','ongoing'):
                    rects.append((end,y,16*scale,16*scale))
                    if m['lane']=='CM' and audit['fullSpan']/v['span']>=2:
                        start=x
                        while start<end:
                            stop=min(end,start+5)
                            width=stop-start
                            rects.append(((start+stop)/2,y,width*(scale if width<=1.5 else 1),(1.25 if low else 2.5)*scale))
                            start+=9
                    else:
                        width=max(1,end-x)
                        for dy in ([-2,2] if m['lane']=='EX' else [0]):
                            rects.append(((x+end)/2,y+dy,width*(scale if width<=1.5 else 1),(1.25 if low else 1.2 if m['lane']=='EX' else 2.5)*scale))
                elif m['is_interval']:
                    rects.append((x+14*scale,y,16*scale,16*scale))
                if selected:
                    width=13*scale
                    rects.append((x,y-6*scale,width*(scale if width<=1.5 else 1),1.5*scale))
                return any(cx-w/2<=right and cx+w/2>=left and cy-h/2<=top and cy+h/2>=bottom for cx,cy,w,h in rects)
        else:
            audit = p.evaluate('({start:camera.start,end:camera.end,tier:+document.querySelector("#timeline").dataset.maxTier})')
            tier = audit['tier']
            actual_marks = p.locator('.mark').evaluate_all('es=>es.map(e=>({record_id:e.dataset.recordId||e.dataset.sourceRecordId,lane:e.dataset.domain,keys:e.dataset.recordKeys?JSON.parse(e.dataset.recordKeys):[e.dataset.recordId||e.dataset.sourceRecordId]}))')
            def intersects(m):
                if not m['date']:
                    return True  # dedicated incomplete-date column, no invented date
                end = m['end_date'] if m['interval_status'] in ('complete', 'ongoing') else m['date']
                return stamp(end) >= audit['start'] and stamp(m['date']) <= audit['end']
        candidates = [m for m in data['marks']+data['sentinels'] if not m.get('display_suppressed') and (m['tier'] <= tier or m['lane'] in ('AE','CM'))]
        expected = {key for m in candidates if intersects(m) for key in m.get('related_death_record_ids',[m['record_id']])}
        actual = {key for m in actual_marks for key in m['keys']}
        return {'tier':tier,'counts':dict(Counter(m['lane'] for m in actual_marks)), 'actual_keys':len(actual), 'expected_keys':len(expected), 'missing':sorted(expected-actual),'unexpected':sorted(actual-expected),'pass':actual==expected,'analysis_counts':[data['analysis']['qualifying_patient_count'],data['analysis']['qualifying_ae_record_count']]}

    def test_vsets(self):
        report = {}
        for gpu in (False, True):
            self.route(gpu)
            # Keep identical selected record in both builds; selection is not an analysis filter.
            self.select('event-selector','AE-004-1');self.settle(gpu)
            initial = self.spec()
            signature = self.page.locator('#diagnostics').text_content()
            results = []
            for days, label in [(None,'overview'),(90,'mid'),(30,'close')]:
                self.page.click('#reset-zoom');self.settle(gpu)
                if days:
                    if gpu:
                        self.page.click('#readable');self.settle(gpu)
                        self.page.evaluate('(days)=>{const a=clinical3d.auditGeometry();clinical3d.zoom(days*86400000/(a.maxDate-a.minDate)*a.fullSpan/a.view.span)}',days)
                    else:
                        self.page.evaluate('(days)=>{const start=Date.parse("2025-01-11T00:00:00Z")-days*86400000/2;animateCamera({start,end:start+days*86400000})}',days)
                self.settle(gpu)
                for mode in ('auto','0','1','2'):
                    self.select('tiers', mode);self.settle(gpu)
                    result = self.measure(gpu)
                    result.update(days=days,state=label,mode=mode)
                    results.append(result)
                    self.assertEqual(result['analysis_counts'],[100,298])
                    self.assertEqual(self.spec(),initial)
                    self.assertEqual(self.page.locator('#diagnostics').text_content(),signature)
            report['gpu' if gpu else 'clinical'] = results
        suffix = 'before' if os.getenv('FOCUS_BASELINE') else 'after'
        (EVIDENCE/f'focus-vsets-{suffix}.json').write_text(json.dumps(report,indent=2)+'\n')
        failures = [(route,r['state'],r['mode'],r['missing'],r['unexpected']) for route,results in report.items() for r in results if not r['pass']]
        self.assertEqual(failures,[])

if __name__ == '__main__':
    unittest.main(verbosity=2)
