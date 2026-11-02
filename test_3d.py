"""3D route and shared-engine regressions, exercised in actual Chromium."""
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from app import Engine, make_handler
from waitfor import wait_for
ROOT=Path(__file__).parent

class ThreeChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(Engine(ROOT/'data',cohort='100')))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.pw=sync_playwright().start();cls.browser=cls.pw.chromium.launch()
    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.pw.stop();cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def setUp(self):
        self.p=self.browser.new_page(viewport={'width':1440,'height':1100})
        self.errors=[];self.p.on('pageerror',lambda e:self.errors.append(str(e)))
        self.base='http://127.0.0.1:%s'%self.server.server_port
    def tearDown(self):
        self.p.close();self.assertEqual(self.errors,[])
    def load(self):
        response=self.p.goto(self.base+'/3d');self.assertEqual(response.status,200)
        wait_for(self.p, 'window.clinical3d?.ready')
        expect(self.p.locator('#counts')).to_have_text('100 qualifying patients · 298 qualifying AE source records')
    def test_route_and_same_data(self):
        self.load()
        self.assertEqual(self.p.request.get(self.base+'/').status,200)
        self.assertEqual(self.p.locator('#sort option').count(),6)
        data=self.p.request.get(self.base+'/api/initial').json()
        # stats().marks counts logical display marks, not endpoint primitives.
        def expected(tier):
            return [m for m in data['marks']+data['sentinels'] if not m.get('display_suppressed') and (m['tier']<=tier or m['lane'] in ('AE','CM'))]
        self.assertEqual(self.p.evaluate('clinical3d.stats().marks'),len(expected(0)))
        baseline=self.p.locator('#spec').text_content()
        signature=self.p.locator('#diagnostics').text_content()
        for sort in ['asc','desc','duration','response','pd','reason']:
            self.p.select_option('#sort',sort)
            self.assertEqual(self.p.locator('#spec').text_content(),baseline)
        # Frozen review counts for the 100-patient fixture (see REVIEW-ORACLES.md).
        # Do not derive these literals from the same eligibility rule as the renderer.
        for tier, count in ((0, 1135), (1, 1480), (2, 1577)):
            self.p.select_option('#tiers',str(tier))
            self.assertEqual(self.p.evaluate('clinical3d.stats().marks'),count)
            self.assertEqual(len(expected(tier)),count)
            submitted=self.p.evaluate('clinical3d.auditGeometry().marks.map(m=>m.display_id).sort()')
            self.assertEqual(len(submitted),count)
            self.assertEqual(submitted,sorted(m['display_id'] for m in expected(tier)))
        self.p.click('#peel');self.p.wait_for_timeout(1100)
        self.p.click('#oblique');self.p.wait_for_timeout(1100)
        self.assertEqual(self.p.locator('#diagnostics').text_content(),signature)
        self.assertEqual(self.p.locator('#spec').text_content(),baseline)
        self.assertLessEqual(self.p.evaluate('clinical3d.stats().drawCalls'),6)
    def test_interrupt_idle_pick_and_end_semantics(self):
        self.load();p=self.p
        p.select_option('#tiers','2')
        p.locator('#scene').scroll_into_view_if_needed()
        p.click('#oblique');p.wait_for_timeout(150)
        p.locator('#scene').scroll_into_view_if_needed()
        box=p.locator('#scene').bounding_box();assert box is not None
        x=box['x']+box['width']/2;y=box['y']+box['height']/2
        p.mouse.move(x,y);p.mouse.down()
        self.assertFalse(p.evaluate('clinical3d.stats().animating'))
        p.mouse.move(x+25,y+10,steps=8);p.mouse.up()
        p.mouse.wheel(0,-80);p.wait_for_timeout(200)
        self.assertFalse(p.evaluate('clinical3d.stats().animating'))
        p.click('#peel');p.wait_for_timeout(1100)
        # Raycast a screen-projected source glyph after zoom/pan/rotate/peel.
        point=p.evaluate("clinical3d.projectRecord('AE-010-1')")
        p.mouse.click(point['x'],point['y'])
        expect(p.locator('#sources')).to_contain_text('AE-010-1')
        for record,text in [('AE-004-1','AEENDTC'),('AE-004-2','AEFUDTC'),('AE-004-3','AE-004-3')]:
            p.select_option('#event-selector',record)
            expect(p.locator('#sources')).to_contain_text(text)
        semantics=p.evaluate('clinical3d.stats().endStates')
        self.assertGreater(semantics['recorded'],0);self.assertGreater(semantics['ongoing'],0);self.assertGreater(semantics['unknown'],0)
        # Selection now starts a 900ms focus tween; source evidence arrives first.
        wait_for(p, '() => !busy && !clinical3d.stats().animating')
        p.evaluate('() => new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
        frames=p.evaluate('clinical3d.stats().frames');p.wait_for_timeout(300)
        self.assertEqual(p.evaluate('clinical3d.stats().frames'),frames)
        p.click('#open-source');expect(p.locator('#sources')).to_contain_text('AE-004-3')
        expect(p.locator('#error')).to_be_empty()

    def test_short_interval_focus_zoom_direction(self):
        self.load();p=self.p
        p.select_option('#event-selector','AE-004-1')
        expect(p.locator('#selection')).to_contain_text('Selected AE-004-1')
        wait_for(p, '() => !busy && !clinical3d.stats().animating')
        before=p.evaluate('clinical3d.stats().view.span')
        self.assertLess(before,35)
        spec=p.locator('#spec').text_content()
        counts=p.locator('#counts').text_content()
        p.click('#zoom-in')
        wait_for(p, '() => !clinical3d.stats().animating')
        self.assertEqual(p.evaluate('clinical3d.stats().view.span'),before)
        p.locator('#scene').hover()
        p.mouse.wheel(0,-80)
        p.wait_for_timeout(100)
        self.assertEqual(p.evaluate('clinical3d.stats().view.span'),before)
        p.click('#zoom-out')
        wait_for(p, '() => !clinical3d.stats().animating')
        # GSAP rounds interpolated property values to six decimal places.
        self.assertAlmostEqual(p.evaluate('clinical3d.stats().view.span'),before/0.65,delta=1e-6)
        self.assertEqual(p.locator('#spec').text_content(),spec)
        self.assertEqual(p.locator('#counts').text_content(),counts)

if __name__=='__main__':unittest.main()
