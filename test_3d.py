"""3D route and shared-engine regressions, exercised in actual Chromium."""
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from app import Engine, make_handler
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
        self.p.wait_for_function('window.clinical3d?.ready')
        expect(self.p.locator('#counts')).to_have_text('100 qualifying patients · 298 qualifying AE source records')
    def test_route_and_same_data(self):
        self.load()
        self.assertEqual(self.p.request.get(self.base+'/').status,200)
        self.assertEqual(self.p.locator('#sort option').count(),6)
        self.assertEqual(self.p.evaluate('clinical3d.stats().marks'),648)
        baseline=self.p.locator('#spec').text_content()
        signature=self.p.locator('#diagnostics').text_content()
        for sort in ['asc','desc','duration','response','pd','reason']:
            self.p.select_option('#sort',sort)
            self.assertEqual(self.p.locator('#spec').text_content(),baseline)
        self.p.select_option('#tiers','2')
        self.assertEqual(self.p.evaluate('clinical3d.stats().marks'),1577)
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
        p.wait_for_timeout(600)
        frames=p.evaluate('clinical3d.stats().frames');p.wait_for_timeout(300)
        self.assertEqual(p.evaluate('clinical3d.stats().frames'),frames)
        p.click('#open-source');expect(p.locator('#sources')).to_contain_text('AE-004-3')
        expect(p.locator('#error')).to_be_empty()

if __name__=='__main__':unittest.main()
