"""Chromium evidence for sentinel tiers, all sorts and end-state glyphs."""
import csv
import json
import statistics
from playwright.sync_api import expect
from test_browser import BrowserFixture, EVIDENCE


class SentinelBrowserChecks(BrowserFixture):
    cohort = '100'
    initial_counts = '100 qualifying patients · 298 qualifying AE source records'
    default_overview = True

    def initial(self):
        return self.page.request.get('http://127.0.0.1:%d/api/initial' % self.server.server_port).json()

    def line_counts(self):
        return self.page.locator('[data-patient]').evaluate_all('''els=>Object.fromEntries(els.map(e=>[e.dataset.patient,
          document.querySelectorAll('.mark[data-patient-key="'+e.dataset.patient+'"]').length]))''')

    def assert_visible_marks(self, state, tier):
        start,end=self.page.locator('#timeline').evaluate('e=>[+e.dataset.start,+e.dataset.end]')
        from test_focus import stamp
        expected=[m for m in state['marks']+state['sentinels']
                  if not m.get('display_suppressed') and (m['tier']<=tier or m['lane'] in ('AE','CM'))
                  and (not m['date'] or (stamp(m['date'])<=end and stamp(m['end_date'] if m['interval_status'] in ('complete','ongoing') else m['date'])>=start))]
        self.assertEqual(self.page.locator('.mark').evaluate_all('es=>es.map(e=>e.dataset.displayId).sort()'),sorted(m['display_id'] for m in expected))
        return expected

    def test_actual_per_line_counts_before_after_and_unchanged_analysis(self):
        p=self.page
        state=self.initial()
        expect(p.locator('#timeline')).to_have_attribute('data-max-tier','0')
        after=self.line_counts()
        self.assertEqual(len(after),100)
        expected_overview=self.assert_visible_marks(state,0)
        for key,n in after.items():
            self.assertEqual(n,sum('/'.join(m['patient_key'])==key for m in expected_overview))
        # Eight is a sentinel-only budget, not a cap on AE/CM context geometry.
        sentinel_counts={key:sum('/'.join(m['patient_key'])==key and m['tier']==0 for m in expected_overview) for key in after}
        self.assertLessEqual(max(sentinel_counts.values()),8)
        counts=p.locator('#counts').text_content()
        spec=self.spec()
        signature=p.locator('#diagnostics').text_content()
        p.locator('#tiers').select_option('2')
        before=self.line_counts()
        self.assert_visible_marks(state,2)
        expected=state['marks']+state['sentinels']
        for key,n in before.items():
            self.assertEqual(n,sum('/'.join(m['patient_key'])==key and not m.get('display_suppressed') for m in expected))
        for mode in ['0','1','2','auto']:
            p.locator('#tiers').select_option(mode)
            self.assertEqual(p.locator('#counts').text_content(),counts)
            self.assertEqual(self.spec(),spec)
            self.assertEqual(p.locator('#diagnostics').text_content(),signature)
        self.assertEqual(self.line_counts(),after)
        # Compare two measured views of this fixture. The historical private
        # reviewed-baseline git ref is not shipped in the public repository.
        def summary(values):
            return dict(total=sum(values),min=min(values),max=max(values),mean=statistics.mean(values),median=statistics.median(values))
        report={'browser':self.browser.version,'patients':100,
                'current_fixture_all_tiers':summary(list(before.values())), 'current_fixture_overview':summary(list(after.values())),
                'analysis_unchanged':True,'qualifying_ae_records':298,'browser_errors':self.errors,
                'count_definition':'One logical event/interval .mark, including coincident events separately; caps, labels and +N chooser badges are not additional events.',
                'per_line':[dict(patient=k,all_tiers=before[k],overview=after[k],sentinels=sentinel_counts[k]) for k in sorted(after)]}
        (EVIDENCE/'mark-counts.json').write_text(json.dumps(report,indent=2)+'\n')
        with (EVIDENCE/'mark-counts.csv').open('w') as f:
            writer=csv.DictWriter(f,fieldnames=['patient','all_tiers','overview','sentinels'])
            writer.writeheader();writer.writerows(report['per_line'])
        p.locator('#timeline').screenshot(path=str(EVIDENCE/'sentinel-overview.png'))

    def test_sorting_staircase_and_all_five_choices(self):
        p=self.page
        state=self.initial()
        summaries={s['patient_key'][1]:s for s in state['patient_summaries']}
        def order(): return p.locator('[data-patient]').all_text_contents()
        self.assertEqual(order()[0],'SYN-100')
        durations=[summaries[x]['treatment_duration'] for x in order()]
        known=[x for x in durations if x is not None]
        self.assertEqual(known,sorted(known,reverse=True))
        # Last-dose x coordinates form a staircase for the 97 appended aligned patients.
        xs=p.locator('[data-kind="last_dose"]').evaluate_all('els=>els.filter(e=>Number(e.dataset.patientKey.split("-").pop())>=4).map(e=>+e.dataset.x)')
        self.assertEqual(xs,sorted(xs,reverse=True))
        counts=p.locator('#counts').text_content()
        for mode,field in [('response','best_response'),('pd','time_to_pd'),('reason','discontinuation_reason')]:
            p.locator('#sort').select_option(mode)
            values=[summaries[x][field] for x in order()]
            known=[v for v in values if v is not None]
            self.assertEqual(values[len(known):],[None]*(len(values)-len(known)))
            if mode=='response': known=[state['display_config']['response_order'].index(v) for v in known]
            self.assertEqual(known,sorted(known))
        p.locator('#sort').select_option('asc');self.assertEqual(order(),sorted(order()))
        p.locator('#sort').select_option('desc');self.assertEqual(order(),sorted(order(),reverse=True))
        self.assertEqual(p.locator('#counts').text_content(),counts)

    def test_interval_glyphs_death_and_source_selection(self):
        p=self.page
        p.locator('#tiers').select_option('2')
        for record in ('AE-004-1','CM-005-2'):
            m=p.locator('[data-record-id="'+record+'"]')
            expect(m.locator('.interval-body')).to_have_count(1)
            expect(m.locator('.domain-symbol')).to_have_count(1)
            expect(m.locator('.end-terminus')).to_have_count(1)
            expect(m.locator('.end-terminus')).to_have_attribute('data-end-state','recorded')
            expect(m.locator('.end-terminus')).to_have_attribute('d','M -1.5 -6 H 1.5 V 6 H -1.5 Z')
        for record,field,date in [('AE-004-2','AEFUDTC','2025-02-05'),('CM-004-1','CMFUDTC','2025-02-15')]:
            m=p.locator('[data-record-id="'+record+'"]')
            expect(m.locator('.interval-body')).to_have_count(1)
            expect(m.locator('.end-terminus')).to_have_count(1)
            expect(m.locator('.end-terminus')).to_have_attribute('data-end-state','ongoing')
            expect(m.locator('.end-terminus')).to_have_attribute('d','M -5 -6 L 1 0 L -5 6')
            expect(m.locator('.end-terminus')).to_have_attribute('fill','none')
            expect(m).to_have_attribute('aria-label',__import__('re').compile('ongoing at last observed '+date+' \\('+field+'\\)'))
            expect(m.locator('.followup-label')).to_have_count(0)  # overview is label-free
        for record in ('AE-004-3','CM-004-2'):
            m=p.locator('[data-record-id="'+record+'"]')
            expect(m.locator('.interval-body')).to_have_count(0)
            expect(m.locator('.end-terminus')).to_have_count(1)
            expect(m.locator('.end-terminus')).to_have_attribute('data-end-state','unknown')
            expect(m.locator('.end-terminus')).to_have_attribute('d','M -6 2 Q -3 -5 0 0 Q 3 5 6 -2')
            expect(m).to_have_attribute('aria-label',__import__('re').compile('end unknown'))
            self.assertEqual(m.get_attribute('data-x'),m.get_attribute('data-end-x'))
        death=p.locator('[data-record-id="AE-010-1"]')
        expect(death).to_have_count(1)
        expect(death).to_have_attribute('data-kind','death')
        expect(death.locator('.interval-body')).to_have_count(0)
        p.locator('#event-selector').select_option('DS-004-2')
        expect(p.locator('#sources > .source-card > summary')).to_contain_text('DS-004-2 · DS original row')
        expect(p.locator('#sources')).to_contain_text('TRIAL DISCONTINUATION')
        expect(p.locator('#sources')).not_to_contain_text('censor')
        p.locator('#event-selector').select_option('AE-004-2')
        expect(p.locator('#sources')).to_contain_text('AEFUDTC')
        p.locator('#tiers').select_option('0')
        self.settled()
        expect(p.locator('#selection')).to_have_text('Selected AE-004-2 · visible')
        expect(p.locator('[data-record-id="AE-004-2"]')).to_have_count(1)
        expect(p.locator('#event-selector')).to_have_value('AE-004-2')
        p.locator('#open-source').click()
        expect(p.locator('#sources')).to_contain_text('2025-02-05')

    def test_auto_zoom_tiers_and_replay_defaults(self):
        p=self.page
        signature=p.locator('#diagnostics').text_content()
        p.emulate_media(reduced_motion='reduce')
        for _ in range(3):
            p.locator('#zoom-in').click()
            expect(p.locator('#timeline')).to_have_attribute('data-animating','false')
        expect(p.locator('#timeline')).to_have_attribute('data-max-tier','1')
        self.assert_visible_marks(self.initial(),1)
        for _ in range(3):
            p.locator('#zoom-in').click()
            expect(p.locator('#timeline')).to_have_attribute('data-animating','false')
        expect(p.locator('#timeline')).to_have_attribute('data-max-tier','2')
        self.assert_visible_marks(self.initial(),2)
        self.assertGreater(p.locator('.mark[data-tier="0"]').count(),0)
        p.locator('#save').click()
        expect(p.locator('#replay-result')).to_contain_text('Saved exact normalized review')
        p.locator('#sort').select_option('pd')
        p.locator('#tiers').select_option('2')
        p.locator('#replay').click()
        expect(p.locator('#replay-result')).to_contain_text('exact specification restored')
        expect(p.locator('#timeline')).to_have_attribute('data-max-tier','0')
        expect(p.locator('#sort')).to_have_value('duration')
        expect(p.locator('#tiers')).to_have_value('auto')
        self.assertEqual(p.locator('#diagnostics').text_content(),signature)
        expect(p.locator('#priority-wording')).to_have_text('Overview priorities chosen for clinical review; endpoint and censoring annotations follow the protocol/SAP.')
