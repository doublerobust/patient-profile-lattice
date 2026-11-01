"""Real Chromium interaction checks for one-line semantic zoom (synthetic data only)."""
import unittest
from playwright.sync_api import expect
from test_browser import BrowserFixture, EVIDENCE


class TimelineChecks(BrowserFixture):
    def test_zoom_in_after_short_interval_focus_does_not_zoom_out(self):
        p = self.page
        self.select('event-selector', 'CM-001-2')
        self.settled()
        before = self.span()
        self.assertLess(before, 2*86400000)  # Short interval's exact focus fit.
        spec, counts = self.spec(), p.locator('#counts').text_content()
        p.locator('#zoom-in').click()
        self.settled()
        self.assertEqual(self.span(), before)  # At this focus floor, never enlarge.
        self.zoom_at_record('CM-001-2', -80)
        self.assertEqual(self.span(), before)
        p.locator('#zoom-out').click()
        self.settled()
        self.assertAlmostEqual(self.span(), before/0.65, delta=1)
        self.assertEqual(self.spec(), spec)
        self.assertEqual(p.locator('#counts').text_content(), counts)

    def test_one_line_and_cross_domain_same_day_offsets(self):
        p = self.page
        expect(p.locator('.patient-line')).to_have_count(2)
        expect(p.locator('.domain-row')).to_have_count(0)
        ids = ['AE-001-1', 'CM-001-1', 'CM-001-2']
        before = self.positions(ids)
        self.assertEqual(len({v['y'] for v in before}), 1)
        self.assertEqual(len({v['x'] for v in before}), 1)
        self.assertEqual({v['shape'] for v in before}, {'g'})  # AE and CM now use interval bars.
        self.assertEqual(len({v['color'] for v in before}), 2)
        expect(p.locator('.annotation')).to_have_count(0)
        self.zoom_at_record('AE-001-1', -1000)
        after = self.positions(ids)
        self.assertEqual(len({v['y'] for v in after}), 3)
        self.assertEqual(len({v['x'] for v in after}), 1)
        self.assertLessEqual(max(v['y'] for v in after) - min(v['y'] for v in after), 72)
        self.assertGreater(after[1]['opacity'], before[1]['opacity'])
        expect(p.locator('.annotation-layer')).to_have_attribute('data-annotation-level', '2')
        self.assertGreater(p.locator('.annotation').count(), 0)
        # Context mark is separately mouse-pickable at close zoom.
        p.locator('[data-record-id="CM-001-2"]').click()
        expect(p.locator('#sources')).to_contain_text('CM-001-2 · CM original row 2')
        self.settled()
        self.pixel_pick('AE-001-1')
        p.locator('#open-source').click()
        expect(p.locator('#sources')).to_contain_text('SUPPAE-001-1')
        p.locator('#reset-zoom').click()
        self.settled()
        self.assertEqual(len({v['y'] for v in self.positions(ids)}), 1)

    def positions(self, ids):
        return [self.page.locator('[data-record-id="' + rid + '"]').evaluate('''el => ({
            x: Number(el.dataset.x), y: Number(el.dataset.y), shape: el.tagName, color: el.getAttribute('fill'),
            opacity: Number(el.getAttribute('opacity'))
        })''') for rid in ids]

    def settled(self):
        super().settled()

    def span(self):
        return self.page.locator('#timeline').evaluate('el => Number(el.dataset.end)-Number(el.dataset.start)')

    def zoom_at_record(self, rid, delta):
        mark = self.page.locator('[data-record-id="' + rid + '"]')
        mark.scroll_into_view_if_needed()
        box = mark.bounding_box()
        assert box is not None
        # Wheel client coordinates are integer CSS pixels, not fractional SVG centers.
        client_x, client_y = round(box['x'] + box['width']/2), round(box['y'] + box['height']/2)
        anchor = self.page.locator('#timeline').evaluate('''(el, pos) => {
            const x = new DOMPoint(pos[0],pos[1]).matrixTransform(el.getScreenCTM().inverse()).x;
            return {x, time: Number(el.dataset.start)+(x-180)/760*(el.dataset.end-el.dataset.start)};
        }''', [client_x, client_y])
        self.page.mouse.move(client_x, client_y)
        self.page.mouse.wheel(0, delta)
        self.page.wait_for_timeout(60)  # Allow browser wheel delivery before checking animation.
        self.settled()
        return anchor

    def test_cursor_anchor_filters_sort_selection_and_reset(self):
        p = self.page
        before_spec = self.spec()
        signature = p.locator('#diagnostics').text_content()
        anchor = self.zoom_at_record('AE-001-1', -1000)
        x_after = p.locator('#timeline').evaluate('(el,time) => 180+(time-el.dataset.start)/(el.dataset.end-el.dataset.start)*760', anchor['time'])
        self.assertAlmostEqual(x_after, anchor['x'], delta=0.05)
        self.assertEqual(before_spec, self.spec())
        self.assertEqual(signature, p.locator('#diagnostics').text_content())
        bounds = p.locator('#timeline').get_attribute('data-start'), p.locator('#timeline').get_attribute('data-end')
        self.select('sort', 'desc')
        self.assertEqual(p.locator('[data-patient]').all_text_contents(), ['SYN-002', 'SYN-001'])
        self.check('CM', True)
        self.assertEqual(bounds, (p.locator('#timeline').get_attribute('data-start'), p.locator('#timeline').get_attribute('data-end')))
        self.pixel_pick('AE-001-1')
        self.select('severity', 'MILD')
        expect(p.locator('#selection')).to_have_text('No selected event.')
        expect(p.locator('#counts')).to_have_text('2 qualifying patients · 3 qualifying AE source records')
        expect(p.locator('#status')).to_contain_text('analysis_excluded')
        p.locator('#reset-zoom').click()
        self.settled()
        expect(p.locator('[data-record-id="AE-003-2"]')).to_have_attribute('data-x', '1055')
        expect(p.locator('#error')).to_be_empty()

    def test_overview_collision_chooser_and_trackpad_modes(self):
        p = self.page
        p.locator('[data-cluster="SYN-SPIKE/SYN-001/2025-01-10"]').click()
        expect(p.locator('#coincident-events')).to_contain_text('CM-001-2')
        p.get_by_role('button', name='Select CM-001-2', exact=True).click()
        expect(p.locator('#sources')).to_contain_text('CM-001-2 · CM original row 2')
        self.settled()
        p.locator('#reset-zoom').click()
        self.settled()  # Selection now focuses the interval before the wheel exercise.
        before = self.span()
        # Line-mode wheel and ctrl+wheel are normalized without browser page zoom.
        point = p.locator('#timeline').evaluate('el => {const p = new DOMPoint(500,110).matrixTransform(el.getScreenCTM()); return {clientX:p.x,clientY:p.y};}')
        p.locator('#timeline').dispatch_event('wheel', dict(point, deltaY=-3, deltaMode=1))
        self.settled()
        middle = self.span()
        self.assertLess(middle, before)
        p.locator('#timeline').dispatch_event('wheel', dict(point, deltaY=-20, ctrlKey=True))
        self.settled()
        after = self.span()
        self.assertLess(after, middle)
        p.locator('#reset-zoom').click()
        self.settled()
        self.assertEqual(p.evaluate('window.visualViewport.scale'), 1)
        p.locator('#timeline').screenshot(path=str(EVIDENCE / 'single-line-overview.png'))
        self.zoom_at_record('AE-001-1', -1000)
        p.locator('#timeline').screenshot(path=str(EVIDENCE / 'single-line-close.png'))

    def test_zoom_limits_buttons_replay_and_all_domains_hidden(self):
        p = self.page
        initial_span = self.span()
        before = self.spec()
        p.locator('#save').click()
        expect(p.locator('#replay-result')).to_contain_text('Saved exact normalized review')
        p.emulate_media(reduced_motion='reduce')
        for _ in range(9):
            p.locator('#zoom-in').click()
            self.settled()
        self.assertEqual(self.span(), 2*86400000)
        p.locator('#zoom-in').click()
        self.settled()
        self.assertEqual(self.span(), 2*86400000)
        self.assertEqual(self.spec(), before)
        p.locator('#replay').click()
        expect(p.locator('#replay-result')).to_contain_text('exact specification restored')
        self.assertEqual(self.span(), initial_span)
        self.assertEqual(self.spec(), before)
        p.locator('#zoom-out').click()
        self.settled()
        self.assertEqual(self.span(), initial_span)
        for domain in ['AE', 'CM', 'EX', 'RS']:
            self.check(domain, True)
        expect(p.locator('.patient-line')).to_have_count(2)
        expect(p.locator('.mark')).to_have_count(0)
        expect(p.locator('#counts')).to_have_text('2 qualifying patients · 3 qualifying AE source records')
        expect(p.locator('#selection')).to_contain_text('logical selection retained')
        p.locator('#open-source').click()
        expect(p.locator('#sources')).to_contain_text('AE-001-2 · AE original row 2')

    def test_moving_pointer_mid_animation_and_continuous_detail(self):
        p = self.page
        p.locator('#timeline').scroll_into_view_if_needed()
        # Two different cursor anchors in one wheel burst; the second must anchor
        # the displayed camera, not a stale target from the previous wheel event.
        result = p.locator('#timeline').evaluate('''el => {
            const wheel = x => {
                const point = new DOMPoint(x,110).matrixTransform(el.getScreenCTM());
                el.dispatchEvent(new WheelEvent('wheel',{clientX:Math.round(point.x),clientY:Math.round(point.y),deltaY:-200,bubbles:true,cancelable:true}));
                return new DOMPoint(Math.round(point.x),Math.round(point.y)).matrixTransform(el.getScreenCTM().inverse()).x;
            };
            wheel(420);
            const start = Number(el.dataset.start), end = Number(el.dataset.end);
            const x = wheel(700);
            return {x, time:start+(x-180)/760*(end-start)};
        }''')
        self.settled()
        x_after = p.locator('#timeline').evaluate('(el,time) => 180+(time-el.dataset.start)/(el.dataset.end-el.dataset.start)*760', result['time'])
        self.assertAlmostEqual(x_after, result['x'], delta=0.05)
        # Return to the January 10/12 records (the second anchor above pans them out).
        p.locator('#reset-zoom').click()
        self.settled()
        self.zoom_at_record('AE-001-1', -400)
        opacity = self.positions(['CM-001-1'])[0]['opacity']
        self.assertGreater(opacity, 0.22)
        self.assertLess(opacity, 1)
        # AE-001-2 shares its date with CM-001-3; hide context to make it a singleton.
        for domain in ['CM', 'EX', 'RS']:
            self.check(domain, True)
        mark_y = self.positions(['AE-001-2'])[0]['y']
        line_y = float(p.locator('.patient-line').first.get_attribute('y1') or 'nan')
        self.assertEqual(mark_y, line_y)


if __name__ == '__main__':
    unittest.main(verbosity=2)
