"""Trusted Chromium touch input via CDP, not JS-dispatched pointer events.
An iPad viewport/hasTouch is emulation, NOT a physical Safari result.
"""
import json
from playwright.sync_api import expect
from test_browser import BrowserFixture


class TouchChecks(BrowserFixture):
    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1024, 'height': 1366},
                                                has_touch=True, is_mobile=True, device_scale_factor=2)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda err: self.errors.append(str(err)))
        self.cdp = self.context.new_cdp_session(self.page)

    def open(self, route):
        self.route = route
        self.page.goto('http://127.0.0.1:%d%s' % (self.server.server_port, route))
        expect(self.page.locator('#counts')).to_contain_text('2 qualifying patients')
        self.page.locator('#tiers').select_option('2')
        self.canvas = self.page.locator('#timeline' if route == '/' else '#scene')
        if route != '/':
            self.page.wait_for_function('() => window.clinical3d?.ready')
        self.canvas.scroll_into_view_if_needed()
        self.page.wait_for_timeout(100)
        self.baseline = self.invariants()

    def invariants(self):
        return self.page.evaluate('''() => ({counts:document.querySelector('#counts').textContent,
          diagnostics:document.querySelector('#diagnostics').textContent,
          pins:document.querySelector('#pins').textContent,
          analysis:JSON.parse(document.querySelector('#spec').textContent).analysis_state})''')

    def view(self):
        return self.page.evaluate('''() => window.clinical3d ? Object.fromEntries(
          Object.entries(window.clinical3d.stats().view).filter(([k])=>!k.startsWith('_'))) :
          {start:+document.querySelector('#timeline').dataset.start,
           span:document.querySelector('#timeline').dataset.end-document.querySelector('#timeline').dataset.start}''')

    def touch(self, kind, points):
        self.cdp.send('Input.dispatchTouchEvent', {'type': kind, 'touchPoints': [
            {'id': i + 1, 'x': x, 'y': y, 'radiusX': 1, 'radiusY': 1, 'force': 1}
            for i, (x, y) in enumerate(points)]})
        self.page.wait_for_timeout(35)

    def center(self):
        b = self.canvas.bounding_box()
        assert b is not None
        top=max(0, b['y'])
        bottom=min(self.page.viewport_size['height'], b['y']+b['height'])
        assert bottom>top, b
        return b['x'] + b['width']*.55, (top+bottom)/2

    def drag(self, points, dx, dy):
        self.touch('touchStart', points)
        for f in [.25, .5, .75, 1]:
            self.touch('touchMove', [(x+dx*f, y+dy*f) for x, y in points])
        self.touch('touchEnd', [])

    def test_one_finger_and_pan_toggle(self):
        for route in ['/', '/3d', '/lattice']:
            with self.subTest(route=route):
                self.open(route)
                x, y = self.center()
                before = self.view()
                self.drag([(x, y)], 55, 20)
                after = self.view()
                if route == '/':
                    self.assertNotEqual(before['start'], after['start'])
                else:
                    self.assertNotEqual(before['yaw'], after['yaw'])
                    self.assertEqual(before['x'], after['x'])
                    self.page.locator('#gesture-pan').click()
                    self.canvas.scroll_into_view_if_needed()
                    x, y = self.center()
                    before = self.view()
                    self.drag([(x, y)], 50, 10)
                    after = self.view()
                    self.assertEqual(before['yaw'], after['yaw'])
                    self.assertNotEqual(before['x'], after['x'])
                self.assertEqual(self.baseline, self.invariants())

    def test_two_finger_pan_and_membership_rebase(self):
        for route in ['/', '/3d', '/lattice']:
            with self.subTest(route=route):
                self.open(route)
                # The view-chat panel narrows the layout; the canvas can sit below
                # the fold, so scroll to it before deriving touch coordinates.
                self.canvas.scroll_into_view_if_needed()
                x, y = self.center()
                selection = self.page.locator('#selection').text_content()
                self.touch('touchStart', [(x-45, y)])
                before = self.view()
                self.touch('touchStart', [(x-45, y), (x+45, y)])
                self.assertEqual(before, self.view(), 'Adding a finger must not move camera')
                for f in [.25, .5, .75, 1]:
                    self.touch('touchMove', [(x-45+40*f, y+20*f), (x+45+40*f, y+20*f)])
                after = self.view()
                self.assertNotEqual(before.get('start', before.get('x')), after.get('start', after.get('x')))
                self.assertAlmostEqual(before['span'], after['span'], delta=before['span']*.001)
                if route != '/':
                    self.assertEqual(before['yaw'], after['yaw'])
                self.touch('touchEnd', [(x-5, y+20)])
                self.assertEqual(after, self.view(), 'Lifting a finger must not move camera')
                self.touch('touchEnd', [])
                self.assertEqual(selection, self.page.locator('#selection').text_content())
                self.assertEqual(self.baseline, self.invariants())

    def point(self, record):
        if self.route != '/':
            return self.page.evaluate('(id) => window.clinical3d.projectRecord(id)', record)
        return self.page.locator('[data-record-id="'+record+'"]').evaluate('''e => {
          const p=new DOMPoint(+e.dataset.x,+e.dataset.y).matrixTransform(e.ownerSVGElement.getScreenCTM());
          return {x:p.x,y:p.y};}''')

    def test_pinch_zoom_anchor(self):
        for route in ['/', '/3d', '/lattice']:
            with self.subTest(route=route):
                self.open(route)
                # Hold a front projection so tier/projection changes cannot move a glyph.
                self.page.emulate_media(reduced_motion='reduce')
                if route == '/lattice':
                    self.page.locator('#lattice-patient-time').click()
                self.canvas.scroll_into_view_if_needed()
                self.page.wait_for_timeout(100)
                anchor = self.point('AE-001-1')
                x, y = anchor['x'], anchor['y']
                before = self.view()
                self.touch('touchStart', [(x-35, y), (x+35, y)])
                for distance in [45, 55, 65, 75]:
                    self.touch('touchMove', [(x-distance, y), (x+distance, y)])
                self.touch('touchEnd', [])
                self.assertLess(self.view()['span'], before['span']*.6)
                after = self.point('AE-001-1')
                self.assertAlmostEqual(after['x'], x, delta=2)
                # Timeline semantic zoom changes row spacing; its anchor is the date, not a fixed row.
                if route != '/':
                    self.assertAlmostEqual(after['y'], y, delta=2)
                self.assertEqual(self.baseline, self.invariants())

    def test_tap_select_and_overlap_chooser(self):
        for route in ['/', '/3d', '/lattice']:
            with self.subTest(route=route):
                self.open(route)
                self.page.emulate_media(reduced_motion='reduce')
                if route == '/lattice':
                    self.page.locator('#lattice-patient-time').click()
                self.canvas.scroll_into_view_if_needed()
                self.page.wait_for_timeout(100)
                pt = self.point('AE-001-1')
                self.page.touchscreen.tap(pt['x'], pt['y'])
                chooser = self.page.locator('#lattice-contributors' if route == '/lattice' else '#coincident-events')
                expect(chooser).to_be_visible()
                expect(chooser).to_contain_text('AE-001-1')
                chooser.locator('button').filter(has_text='AE-001-1').first.tap()
                expect(self.page.locator('#selection')).to_contain_text('Selected AE-001-1')
                expect(self.page.locator('#sources')).to_contain_text('AE-001-1 · AE original row 1')
                self.page.locator('#reset-zoom').click()
                for lane in ['CM', 'EX', 'RS']:
                    self.page.locator('#hide-'+lane).check()
                    expect(self.page.locator('#hide-'+lane)).to_be_enabled()
                self.canvas.scroll_into_view_if_needed()
                self.page.wait_for_timeout(100)
                pt = self.point('AE-001-2')
                self.page.touchscreen.tap(pt['x'], pt['y'])
                expect(self.page.locator('#selection')).to_contain_text('Selected AE-001-2')
                expect(self.page.locator('#sources')).to_contain_text('AE-001-2 · AE original row 2')
                self.assertEqual(self.baseline, self.invariants())

    def test_gesture_cancels_focus_and_cancel_recovers(self):
        for route in ['/', '/3d', '/lattice']:
            with self.subTest(route=route):
                self.open(route)
                # Select via DOM while the canvas stays in the viewport.
                if route == '/':
                    # The SVG tween is only 180ms; freeze its clock so CDP transport
                    # latency cannot let focus finish/scroll before touch arrives.
                    self.page.clock.install()
                    self.page.clock.pause_at(self.page.evaluate('Date.now()'))
                self.page.locator('#event-selector').evaluate('''e => {
                    e.value='AE-001-2';e.dispatchEvent(new Event('change',{bubbles:true}));}''')
                self.page.wait_for_function('''() => window.clinical3d ? window.clinical3d.stats().animating :
                  document.querySelector('#timeline').dataset.animating==='true' ''')
                x, y = self.center()
                self.touch('touchStart', [(x, y)])
                frozen = self.view()
                self.assertFalse(self.page.evaluate('''() => window.clinical3d ? window.clinical3d.stats().animating :
                    document.querySelector('#timeline').dataset.animating==='true' '''))
                if route == '/':
                    self.page.clock.run_for(1000)
                self.page.wait_for_timeout(1000)
                self.assertEqual(frozen, self.view())
                self.touch('touchCancel', [])
                self.drag([(x, y)], 40, 0)
                self.assertNotEqual(frozen, self.view())
                self.assertEqual(self.baseline, self.invariants())
                if route == '/':
                    self.page.clock.resume()
