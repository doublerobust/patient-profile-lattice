import json
from playwright.sync_api import expect
from test_browser import BrowserFixture
from waitfor import wait_for

class ChatChecks(BrowserFixture):
    interactions=[]

    @classmethod
    def tearDownClass(cls):
        from pathlib import Path
        Path('evidence-chat-interactions.json').write_text(json.dumps(cls.interactions,indent=2))
        super().tearDownClass()

    def snapshot(self):
        return self.page.evaluate('viewChatBridge.snapshot()')

    def invariants(self):
        return self.page.evaluate('({analysis:state.analysis, spec:state.spec.analysis_state,signature:state.analysis_signature})')

    def request(self, tool, args=None):
        text=json.dumps({'tool':tool,'args':args}) if args is not None else tool
        before=self.snapshot()
        self.page.locator('#chat-request').fill(text)
        self.page.get_by_role('button',name='Run local command',exact=True).click()
        expect(self.page.locator('#chat-tool-status')).not_to_contain_text('validating')
        self.interactions.append({'route':self.page.url.split(str(self.server.server_port))[-1], 'request':text,'before':before,'after':self.snapshot(),'result':self.page.locator('#chat-result').text_content(),'record_ids':self.page.locator('#chat-records').text_content(),'analysis':self.invariants()})

    def test_tools_all_routes(self):
        for route in ['/', '/3d', '/lattice']:
            with self.subTest(route=route):
                self.page.goto('http://127.0.0.1:%d%s' % (self.server.server_port,route))
                wait_for(self.page, 'window.viewChatBridge !== undefined')
                self.page.emulate_media(reduced_motion='reduce')
                self.page.locator('#tiers').select_option('2')
                expect(self.page.locator('#chat-body')).to_be_hidden()
                self.page.locator('#chat-toggle').click()
                baseline=self.snapshot(); counts=self.invariants()
                camera={'start':1735603200000,'end':1739491200000} if route=='/' else {'position':[500,500,4000],'target':[0,0,0],'span':900}
                self.request('set_view',{'sort':'desc','focus':'SYN-001','layers':['AE','EX'],'tier':'2','camera':camera})
                expect(self.page.locator('#chat-result')).to_contain_text('View changed')
                expect(self.page.locator('#chat-records')).to_contain_text('AE-001-1')
                self.assertNotEqual(baseline,self.snapshot());self.assertEqual(counts,self.invariants())
                self.page.locator('#chat-undo').click()
                expect(self.page.locator('#chat-result')).to_contain_text('Undo:')
                self.assertEqual(baseline,self.snapshot());self.assertEqual(counts,self.invariants())
                geometry=self.page.evaluate('window.clinical3d?.stats()')
                self.request('highlight_events',{'scope':'current_analysis','filters':{'term':'SYNTHETIC NAUSEA'}})
                if route=='/':
                    expect(self.page.locator('[data-highlight-record]')).to_have_count(2)
                else:
                    metric='lines' if route=='/lattice' else 'triangles'
                    wait_for(self.page, '(x)=>clinical3d.stats()[x.metric]>x.before',arg={'metric':metric,'before':geometry[metric]})
                self.assertEqual(self.snapshot()['highlights'],['AE-001-1','AE-001-2'])
                expect(self.page.locator('#chat-records')).to_have_text('AE-001-1\nAE-001-2')
                self.assertEqual(counts,self.invariants())
                self.page.locator('#chat-undo').click()
                expect(self.page.locator('#chat-result')).to_contain_text('Undo:')
                self.assertEqual(baseline,self.snapshot())
                for unit,n in [('AE records',2),('patients',1)]:
                    self.request('query_data',{'scope':'current_analysis','unit':unit,'filters':{'term':'SYNTHETIC NAUSEA'}})
                    expect(self.page.locator('#chat-result')).to_contain_text(f'{n} {unit}')
                    expect(self.page.locator('#chat-records')).to_have_text('AE-001-1\nAE-001-2')
                    self.assertEqual(baseline,self.snapshot());self.assertEqual(counts,self.invariants())
                    self.page.locator('#chat-undo').click()
                    expect(self.page.locator('#chat-result')).to_contain_text('Undo:')
                    self.assertEqual(baseline,self.snapshot())
                self.request('set_view',{'tier':'1'})
                self.page.locator('#chat-reset').click()
                expect(self.page.locator('#chat-result')).to_contain_text('Reset:')
                self.assertEqual(baseline,self.snapshot());self.assertEqual(counts,self.invariants())

    def test_refusal_keyboard_narrow_and_no_external_requests(self):
        self.page.set_viewport_size({'width':390,'height':844})
        outbound=[]
        self.page.on('request',lambda r: outbound.append(r.url) if not r.url.startswith('http://127.0.0.1:') else None)
        button=self.page.get_by_role('button',name='Ask about this view',exact=True)
        before=self.page.locator('#timeline').bounding_box()
        button.focus();self.page.keyboard.press('Enter')
        expect(self.page.locator('#chat-request')).to_be_focused()
        self.assertEqual(before,self.page.locator('#timeline').bounding_box())
        panel=self.page.locator('#chat-body').bounding_box()
        self.assertGreaterEqual(panel['x'],0);self.assertLessEqual(panel['x']+panel['width'],390)
        baseline=self.snapshot();counts=self.invariants()
        for text in ['grade 3 AEs','patients after treatment','count grade 3 AEs',json.dumps({'tool':'set_view','args':{'sort':'asc','analysis_state':{}}})]:
            self.request(text)
            expect(self.page.locator('#chat-tool-status')).to_contain_text('refused')
            self.assertEqual(baseline,self.snapshot());self.assertEqual(counts,self.invariants())
        self.page.keyboard.press('Escape');expect(button).to_be_focused()
        expect(self.page.locator('#chat-body')).to_be_hidden()
        self.assertEqual(outbound,[])
