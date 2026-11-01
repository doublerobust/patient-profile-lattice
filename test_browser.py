"""Real Chromium mouse picking and ordinary saved-review flows; no screenshot analysis."""
import json
from pathlib import Path
from http.server import ThreadingHTTPServer
import threading
import unittest
from playwright.sync_api import sync_playwright, expect
from app import Engine, canonical, make_handler

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / 'evidence'


class BrowserFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(Engine(ROOT / 'data', cohort=getattr(cls, 'cohort', 'small'))))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()
        EVIDENCE.mkdir(exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1440, 'height': 1100}, accept_downloads=True)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda err: self.errors.append(str(err)))
        self.page.goto('http://127.0.0.1:%d' % self.server.server_port)
        expect(self.page.locator('#counts')).to_have_text(getattr(self, 'initial_counts', '2 qualifying patients · 3 qualifying AE source records'))
        # Legacy geometry/picking regressions explicitly request all display tiers.
        # Default sentinel behavior is verified separately in test_sentinel_browser.
        if not getattr(self, 'default_overview', False):
            self.page.locator('#tiers').select_option('2')

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [])

    def spec(self):
        return json.loads(self.page.locator('#spec').text_content())

    def select(self, element, value):
        self.page.locator('#' + element).select_option(value)
        expect(self.page.locator('#' + element)).to_be_enabled()
        expect(self.page.locator('#error')).to_be_empty()

    def check(self, lane, checked):
        self.page.locator('#hide-' + lane).set_checked(checked)
        expect(self.page.locator('#hide-' + lane)).to_be_enabled()

    def pixel_pick(self, record):
        mark = self.page.locator('[data-record-id="' + record + '"]')
        mark.scroll_into_view_if_needed()
        box = mark.bounding_box()
        self.assertIsNotNone(box)
        self.page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
        expect(self.page.locator('#selection')).to_contain_text('Selected ' + record)
        expect(self.page.locator('#sort')).to_be_enabled()

class BrowserChecks(BrowserFixture):
    def test_ordinary_sort_filter_peel_pick_source_export_replay(self):
        p = self.page
        self.select('severity', 'all')
        expect(p.locator('#counts')).to_have_text('3 qualifying patients · 7 qualifying AE source records')
        self.select('severity', 'SEVERE')
        baseline_signature = json.loads(p.locator('#diagnostics').text_content())['analysis_signature']
        self.select('sort', 'desc')
        self.assertEqual(p.locator('[data-patient]').all_text_contents(), ['SYN-002', 'SYN-001'])
        self.check('CM', True)
        self.select('focus', '[[' + '"SYN-SPIKE","SYN-001"' + ']]')
        expect(p.locator('#counts')).to_have_text('2 qualifying patients · 3 qualifying AE source records')
        self.assertEqual(json.loads(p.locator('#diagnostics').text_content())['analysis_signature'], baseline_signature)
        self.pixel_pick('AE-001-2')
        p.locator('#open-source').click()
        expect(p.locator('#sources')).to_be_visible()
        expect(p.locator('#sources')).to_contain_text('AE-001-2 · AE original row 2')
        expect(p.locator('#sources')).to_contain_text('"AESEQ": 2')
        relationship = p.locator('#sources .evidence-card')
        relationship.locator('summary').first.click()
        expect(relationship).to_contain_text('No relationship type is inferred')
        expect(relationship).to_contain_text('REL-3')
        expect(relationship).to_contain_text('CM-001-3')
        p.locator('#save').click()
        expect(p.locator('#replay-result')).to_contain_text('Saved exact normalized review')
        saved = self.spec()
        with p.expect_download() as downloaded:
            p.locator('#download').click()
        download = downloaded.value
        path = EVIDENCE / 'browser-export.json'
        download.save_as(path)
        package = json.loads(path.read_text())
        self.assertEqual(canonical(package['spec']), canonical(saved))
        self.check('AE', True)
        expect(p.locator('[data-record-id="AE-001-2"]')).to_have_count(0)
        expect(p.locator('#selection')).to_contain_text('logical selection retained')
        self.select('population', '[["SYN-SPIKE","SYN-002"]]')
        expect(p.locator('#status')).to_contain_text('analysis_excluded')
        expect(p.locator('#selection')).to_have_text('No selected event.')
        expect(p.locator('#counts')).to_have_text('1 qualifying patients · 1 qualifying AE source records')
        self.check('AE', False)
        self.select('focus', 'all')
        self.pixel_pick('AE-002-1')
        p.locator('#open-source').click()
        expect(p.locator('#sources')).to_contain_text('AE-002-1 · AE original row 4')
        p.locator('#replay').click()
        expect(p.locator('#replay-result')).to_contain_text('exact specification restored')
        self.assertEqual(canonical(self.spec()), canonical(saved))
        expect(p.locator('#counts')).to_have_text('2 qualifying patients · 3 qualifying AE source records')
        # File replay uses the same strict verifier, not a screenshot approximation.
        self.select('sort', 'asc')
        p.locator('#import').set_input_files(str(path))
        expect(p.locator('#replay-result')).to_contain_text('exact specification restored')
        self.assertEqual(canonical(self.spec()), canonical(saved))
        p.locator('#open-source').click()
        expect(p.locator('#sources')).to_be_visible()
        p.screenshot(path=str(EVIDENCE / 'reviewer-path.png'), full_page=True)

    def test_group_evidence_supplement_and_temporal_counts(self):
        p = self.page
        self.pixel_pick('AE-001-1')
        p.locator('#open-source').click()
        expect(p.locator('#sources')).to_contain_text('SUPPAE-001-1')
        relationship = p.locator('#sources .evidence-card')
        relationship.locator('summary').first.click()
        expect(relationship).to_contain_text('CM-001-1')
        expect(relationship).to_contain_text('CM-001-2')
        expect(relationship).to_contain_text('"endpoint_kind": "group"')
        expect(relationship).to_contain_text('It does not establish cause.')
        self.select('severity', 'all')
        self.select('temporal', 'explicit')
        expect(p.locator('#counts')).to_have_text('3 qualifying patients · 5 qualifying AE source records')
        expect(p.locator('[data-record-id="AE-002-1"]')).to_have_count(1)
        expect(p.locator('[data-record-id="AE-002-2"]')).to_have_count(0)
        expect(p.locator('[data-record-id="AE-003-1"]')).to_have_count(1)
        expect(p.locator('#diagnostics')).to_contain_text('incomplete_event_date')
        expect(p.locator('#diagnostics')).to_contain_text('AE-003-2')
        self.select('temporal', 'none')
        partial = p.locator('[data-record-id="AE-003-2"]')
        expect(partial).to_have_attribute('cx', '1055')

    def test_replay_hash_error_does_not_replace_current_view(self):
        p = self.page
        before = self.spec()
        p.locator('#save').click()
        expect(p.locator('#replay-result')).to_contain_text('Saved exact normalized review')
        package = json.loads(p.evaluate("localStorage.getItem('synthetic-lane-review-v1')"))
        package['content_sha256'] = '0' * 64
        p.locator('#import').set_input_files({'name':'tampered.json', 'mimeType':'application/json', 'buffer':canonical(package)})
        expect(p.locator('#error')).to_have_text('content_hash_mismatch')
        self.assertEqual(self.spec(), before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
