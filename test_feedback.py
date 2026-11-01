"""Regression tests for Yue's sidebar/scale/interval/selection feedback."""
import unittest
import json
import time
import statistics
from playwright.sync_api import expect
from test_browser import BrowserFixture, EVIDENCE


class SelectionFeedbackChecks(BrowserFixture):
    def test_rs_selection_replaces_ae_everywhere(self):
        p = self.page
        self.pixel_pick('AE-002-1')
        p.locator('#open-source').click()
        expect(p.locator('#sources')).to_contain_text('AE-002-1 · AE original row 4')
        p.locator('[data-cluster="SYN-SPIKE/SYN-002/2025-01-31"]').click()
        p.locator('#coincident-events button').filter(has_text='RS-002-1').click()
        expect(p.locator('#selection')).to_contain_text('Selected RS-002-1')
        expect(p.locator('#selection')).not_to_contain_text('AE-002-1')
        expect(p.locator('#event-selector')).to_have_value('RS-002-1')
        expect(p.locator('#sources > .source-card > summary')).to_have_text('RS-002-1 · RS original row 2')
        self.assertEqual(self.spec()['view_state']['selection']['source_record_ids'], ['RS-002-1'])
        expect(p.locator('.mark.selected')).to_have_attribute('data-record-id', 'RS-002-1')
        p.locator('#save').click()
        expect(p.locator('#replay-result')).to_contain_text('Saved exact normalized review')
        p.locator('#event-selector').select_option('AE-002-1')
        expect(p.locator('#selection')).to_contain_text('Selected AE-002-1')
        p.locator('#replay').click()
        expect(p.locator('#replay-result')).to_contain_text('exact specification restored')
        expect(p.locator('#event-selector')).to_have_value('RS-002-1')
        expect(p.locator('#selection')).to_contain_text('Selected RS-002-1')
        p.locator('#open-source').click()
        expect(p.locator('#sources > .source-card > summary')).to_have_text('RS-002-1 · RS original row 2')


class PanFeedbackChecks(BrowserFixture):
    def bounds(self):
        return self.page.locator('#timeline').evaluate('el => [Number(el.dataset.start),Number(el.dataset.end)]')

    def pan_from_record(self, record, delta):
        mark = self.page.locator('[data-record-id="'+record+'"]')
        mark.scroll_into_view_if_needed()
        box = mark.bounding_box()
        assert box is not None
        x, y = box['x']+box['width']/2, box['y']+box['height']/2
        self.page.mouse.move(x, y)
        self.page.mouse.down()
        self.page.mouse.move(x+delta, y, steps=8)
        self.page.mouse.up()

    def test_pan_at_overview_and_close_then_ordinary_click_selection(self):
        p = self.page
        self.check('CM', True)
        self.check('EX', True)
        baseline = self.spec()
        counts = p.locator('#counts').text_content()
        signature = p.locator('#diagnostics').text_content()
        for close in [False, True]:
            if close:
                point = p.locator('[data-record-id="AE-001-1"]').evaluate('el=>{const p=new DOMPoint(Number(el.dataset.x),Number(el.dataset.y)).matrixTransform(el.getScreenCTM());return {clientX:p.x,clientY:p.y};}')
                p.locator('#timeline').dispatch_event('wheel', dict(point, deltaY=-1000))
                expect(p.locator('#timeline')).to_have_attribute('data-animating','false')
            before = self.bounds()
            self.pan_from_record('AE-001-1', 30)
            after = self.bounds()
            self.assertLess(after[0], before[0])
            self.assertAlmostEqual(after[1]-after[0], before[1]-before[0], delta=1)
            self.assertEqual(self.spec(), baseline)  # No accidental selection from drag.
            self.assertEqual(p.locator('#counts').text_content(), counts)
            self.assertEqual(p.locator('#diagnostics').text_content(), signature)
        self.pixel_pick('AE-001-1')
        expect(p.locator('#event-selector')).to_have_value('AE-001-1')
        expect(p.locator('#sources > .source-card > summary').first).to_have_text('AE-001-1 · AE original row 1')
        expect(p.locator('#sources > .source-card > summary').nth(1)).to_have_text('SUPPAE-001-1 · SUPPAE original row 1')
        before = self.bounds()
        self.pan_from_record('AE-001-1', 2)  # Sub-threshold hand motion is still a click.
        self.assertEqual(self.bounds(), before)
        expect(p.locator('#selection')).to_contain_text('Selected AE-001-1')
        p.locator('#reset-zoom').click()
        expect(p.locator('#timeline')).to_have_attribute('data-animating','false')


class ScaleFeedbackChecks(BrowserFixture):
    cohort = '100'
    initial_counts = '100 qualifying patients · 298 qualifying AE source records'

    def test_overview_100_patients_sidebar_intervals_and_scale_timings(self):
        p = self.page
        load_ms = []
        for _ in range(5):
            start = time.perf_counter()
            p.reload()
            expect(p.locator('.patient-line')).to_have_count(100)
            expect(p.locator('#event-selector')).to_be_enabled()
            p.locator('#tiers').select_option('2')
            load_ms.append((time.perf_counter()-start)*1000)
        state = p.request.get('http://127.0.0.1:%d/api/initial' % self.server.server_port).json()
        expect(p.locator('.mark')).to_have_count(len(state['marks']) + len(state['sentinels']))
        expected_intervals = sum(m['interval_status'] in ('complete','ongoing') for m in state['marks'])
        expect(p.locator('.interval-body')).to_have_count(expected_intervals)
        expect(p.locator('[data-domain="RS"] .interval-body')).to_have_count(0)
        # Every interval uses exact start/end coordinates; same-day stays zero-span.
        for record in ['AE-001-1','AE-002-1','CM-001-1','EX-004-1']:
            mark = next(m for m in state['marks'] if m['record_id']==record)
            geometry = p.locator('[data-record-id="'+record+'"]').evaluate('el=>({start:+el.dataset.x,end:+el.dataset.endX,caps:[...el.querySelectorAll(".interval-cap")].map(c=>+c.getAttribute("x1"))})')
            self.assertEqual(geometry['caps'], [geometry['start'],geometry['end']])
            self.assertEqual(geometry['end']==geometry['start'], mark['date']==mark['end_date'])
        expect(p.locator('aside #analysis-controls')).to_have_count(1)
        expect(p.locator('aside #view-controls')).to_have_count(1)
        side = p.locator('aside').bounding_box()
        summary = p.locator('.summary').bounding_box()
        assert side is not None and summary is not None
        self.assertLessEqual(side['x']+side['width'], summary['x'])
        colors = p.locator('fieldset').evaluate_all('els=>els.map(e=>getComputedStyle(e).backgroundColor)')
        self.assertNotEqual(colors[0],colors[1])
        baseline = self.spec()
        before_ids = sorted(p.locator('.mark').evaluate_all('els=>els.map(e=>e.dataset.displayId)'))
        counts = p.locator('#counts').text_content()
        zoom_ms = []
        for _ in range(5):
            start = time.perf_counter()
            p.locator('#zoom-in').click()
            expect(p.locator('#timeline')).to_have_attribute('data-animating','false')
            zoom_ms.append((time.perf_counter()-start)*1000)
            self.assertEqual(self.spec(), baseline)
            self.assertEqual(p.locator('#counts').text_content(), counts)
            p.locator('#reset-zoom').click()
            expect(p.locator('#timeline')).to_have_attribute('data-animating','false')
        self.assertEqual(sorted(p.locator('.mark').evaluate_all('els=>els.map(e=>e.dataset.displayId)')),before_ids)
        # Last patient's actual source is reachable, not just the first viewport rows.
        p.locator('#event-selector').select_option('RS-100-2')
        expect(p.locator('#selection')).to_contain_text('Selected RS-100-2')
        expect(p.locator('#sources > .source-card > summary')).to_contain_text('RS-100-2 · RS original row')
        self.select('sort','desc')
        self.assertEqual(p.locator('[data-patient]').first.text_content(),'SYN-100')
        self.assertEqual(p.locator('#counts').text_content(),counts)
        self.select('sort','asc')
        self.select('event-selector','')
        p.locator('.summary').scroll_into_view_if_needed()
        p.screenshot(path=str(EVIDENCE / 'feedback-100-overview.png'))
        report = {'browser':self.browser.version,'patients':100,'marks':len(state['marks']),
                  'complete_intervals':expected_intervals,'qualifying_ae_records':state['analysis']['qualifying_ae_record_count'],
                  'reload_to_ready_ms':load_ms,'reload_median_ms':statistics.median(load_ms),
                  'zoom_click_to_settled_ms':zoom_ms,'zoom_median_ms':statistics.median(zoom_ms),
                  'counts_and_spec_unchanged_by_zoom':True,'reset_restored_mark_ids':True,
                  'browser_errors':self.errors,'measurement_note':'Local Chromium, 1440x1100, five reloads and five zoom/reset cycles; timings include Playwright overhead and zoom animation. Not a general performance guarantee.'}
        (EVIDENCE/'scale-result.json').write_text(json.dumps(report,indent=2)+'\n')
        self.assertLess(max(load_ms),5000)
        self.assertLess(max(zoom_ms),5000)

    def test_scale_rs_selection_hide_zoom_and_clear(self):
        p = self.page
        self.select('event-selector','AE-002-1')
        expect(p.locator('#selection')).to_contain_text('Selected AE-002-1')
        self.select('event-selector','RS-002-1')
        expect(p.locator('#event-selector')).to_have_value('RS-002-1')
        expect(p.locator('#selection')).to_contain_text('Selected RS-002-1')
        expect(p.locator('#sources > .source-card > summary')).to_have_text('RS-002-1 · RS original row 2')
        self.check('RS',True)
        expect(p.locator('#event-selector')).to_have_value('RS-002-1')
        expect(p.locator('#selection')).to_contain_text('logical selection retained')
        p.locator('#open-source').click()
        expect(p.locator('#sources > .source-card > summary')).to_have_text('RS-002-1 · RS original row 2')
        self.select('population','[["SYN-SPIKE","SYN-001"]]')
        expect(p.locator('#selection')).to_have_text('No selected event.')
        expect(p.locator('#event-selector')).to_have_value('')
        expect(p.locator('#sources')).to_be_empty()


if __name__ == '__main__':
    unittest.main(verbosity=2)
