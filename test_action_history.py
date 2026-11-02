"""Real Chromium component exercise; synthetic state, no external service or images."""
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import unittest
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parent

class HistoryBrowserChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = functools.partial(SimpleHTTPRequestHandler, directory=str(ROOT / 'static'))
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.page = self.browser.new_page(viewport={'width': 390, 'height': 844})
        self.errors = []
        self.page.on('pageerror', lambda e: self.errors.append(str(e)))
        self.page.goto(f'http://127.0.0.1:{self.server.server_port}/history-demo.html')
        self.page.wait_for_function('window.demoHistory !== undefined')

    def tearDown(self):
        self.page.close()
        self.assertEqual(self.errors, [])

    def state(self):
        return self.page.evaluate('demoHistory.snapshot().state')

    def test_combined_state_read_only_history_undo_and_reset(self):
        initial = self.state()
        self.page.locator('#synthetic-action').click()
        changed = self.state()
        self.assertNotEqual(changed['analysis'], initial['analysis'])
        self.assertNotEqual(changed['display'], initial['display'])
        self.page.locator('.action-history summary').click()
        expect(self.page.locator('.action-history pre')).to_contain_text('SYN-AE-1')
        entry = self.page.evaluate('demoHistory.snapshot().entries[0]')
        self.assertEqual(set(entry['diff']), {'analysis', 'display'})
        self.assertEqual(entry['controls']['undo']['entry_id'], entry['id'])
        self.page.locator('#synthetic-query').click()
        expect(self.page.locator('.action-history-entries > li')).to_have_count(2)
        expect(self.page.get_by_role('button', name='Undo this action', exact=True).first).to_be_disabled()
        self.page.get_by_role('button', name='Undo', exact=True).click()
        self.assertEqual(self.state(), changed)
        self.page.get_by_role('button', name='Undo this action', exact=True).click()
        self.assertEqual(self.state(), initial)
        self.page.locator('#synthetic-action').click()
        self.page.locator('#synthetic-query').click()
        self.page.get_by_role('button', name='Reset to initial state', exact=True).first.click()
        self.assertEqual(self.state(), initial)
        self.assertEqual(self.page.evaluate('demoHistory.snapshot().entries'), [])
        expect(self.page.locator('.action-history')).to_contain_text('No actions in this session.')
        expect(self.page.get_by_role('button', name='Undo', exact=True)).to_be_disabled()
        self.assertEqual(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth'), True)

    def test_text_is_inert_and_failed_commit_is_honest(self):
        self.page.evaluate("""async () => {
          await demoHistory.execute({action:{tool:'<img src=x onerror="window.bad=true">',args:{code:'window.bad=true'}},diff:{},record_ids:['<script>window.bad=true</script>']});
        }""")
        self.page.locator('.action-history summary').click()
        expect(self.page.locator('.action-history pre')).to_contain_text('window.bad=true')
        self.assertEqual(self.page.locator('.action-history img, .action-history script').count(), 0)
        self.assertIsNone(self.page.evaluate('window.bad'))
        self.page.evaluate("""async () => {
          const h=ViewActionHistory.createHistory({initial:demoHistory.snapshot().state,commit:async()=>{throw Error('synthetic commit failure');}});
          const root=document.createElement('div');root.id='failing-history';document.body.append(root);
          ViewActionHistory.mountHistory(root,h);
        }""")
        self.page.locator('#failing-history').get_by_role('button', name='Reset', exact=True).click()
        expect(self.page.locator('#failing-history [role=status]')).to_contain_text('Not applied: synthetic commit failure')

if __name__ == '__main__':
    unittest.main()
