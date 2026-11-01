"""Source-backed display preparation, separate from pinned analytical rules.

Tier decisions are prepared here, never inferred by the SVG renderer. Synthetic
DS codes and follow-up extensions are demonstration mappings, not a protocol.
"""
from datetime import date
import json
from pathlib import Path

CONFIG = json.loads((Path(__file__).parent / 'display-priorities-v1.json').read_text())
TIERS = {kind: entry['tier'] for entry in CONFIG['tiers'] for kind in entry['kinds']}
DS_KINDS = {'WITHDRAWAL BY SUBJECT': 'trial_withdrawal',
            'TRIAL DISCONTINUATION': 'trial_withdrawal',
            'TREATMENT DISCONTINUATION': 'treatment_discontinuation',
            'SUBSEQUENT ANTICANCER THERAPY': 'subsequent_therapy', 'DEATH': 'death'}


ANNOTATION_FIELDS = {
    'AE': ('AETERM', 'AEDECOD', 'AESEV', 'AESER', 'AETOXGR'),
    'CM': ('CMTRT', 'CMDECOD', 'CMDOSE', 'CMDOSU', 'CMDOSFRQ'),
    'EX': ('EXTRT', 'EXDOSE', 'EXDOSU', 'EXDOSFRQ', 'EXADJ'),
    'RS': ('RSTEST', 'RSTESTCD', 'RSORRES'),
    'DS': ('DSTERM', 'DSDECOD', 'DSREAS'),
}


def annotation(row):
    """Read-only display projection; missing values remain absent, not inferred."""
    values, domain = row['values'], row['dataset']
    fields = {key: values[key] for key in ANNOTATION_FIELDS[domain]
              if key in values and values[key] not in ('', None)}
    terms = {'AE': ('AETERM', 'AEDECOD'), 'CM': ('CMTRT', 'CMDECOD'),
             'EX': ('EXTRT',), 'RS': ('RSTEST', 'RSTESTCD'), 'DS': ('DSTERM', 'DSDECOD')}
    return {'term': next((str(fields[f]) for f in terms[domain] if f in fields),
                         domain + ' term not recorded'), 'fields': fields}


def prepare(engine, marks):
    """Classify complete source series before view filters; preserve source identity."""
    sentinels, summaries = [], []
    for mark in marks:
        mark['annotation'] = annotation(engine.records[mark['record_id']])
    def classify(mark, kind):
        mark.update(display_kind=kind, tier=TIERS[kind], display_id=mark['mark_id'])
    def point(mark, kind, day, extra=False):
        result = dict(mark)
        classify(result, kind)
        result.update(date=day, raw_date=day or '', end_date=None, raw_end_date='',
                      is_interval=False, interval_status='point', end_state='point',
                      end_source=None)
        if extra:
            result['display_id'] += ':' + kind
            result['sentinel_copy'] = True
        return result
    for patient in engine.fixtures['population']:
        key = [patient['STUDYID'], patient['USUBJID']]
        rows = [m for m in marks if m['patient_key']==key]
        by_lane = {d: [m for m in rows if m['lane']==d] for d in ('AE','CM','EX','RS','DS')}
        for mark in rows:
            v = engine.records[mark['record_id']]['values']
            lane = mark['lane']
            if lane == 'AE':
                grade = int(v.get('AETOXGR') or 0)
                kind = 'serious_or_grade3_ae' if v.get('AESER')=='Y' or grade>=3 else 'routine_ae'
                classify(mark, kind)
                if v.get('AESEV')=='SEVERE':
                    mark['tier'] = min(mark['tier'], TIERS['routine_ae'] - CONFIG['overrides'][1]['escalate_tiers'])
                if grade == 5:
                    # Fatal AE onset is not a death date. Keep unknown if neither date is recorded.
                    death_date = next((v[f] for f in CONFIG['overrides'][0]['date_priority'] if engine.ref.complete_date(v.get(f,''))), None)
                    mark.update(point(mark, 'death', death_date))
            elif lane == 'CM': classify(mark, 'concomitant_medication')
            elif lane == 'EX':
                classify(mark, {'INTERRUPTION':'dose_interruption','REDUCTION':'dose_reduction'}.get(v.get('EXADJ'),'exposure'))
            elif lane == 'RS':
                classify(mark, 'response' if v.get('RSTESTCD')=='OVRLRESP' else 'assessment')
            elif lane == 'DS':
                classify(mark, DS_KINDS.get(v.get('DSDECOD'), 'assessment'))
        ex = [m for m in by_lane['EX'] if m['date']]
        starts = sorted(ex, key=lambda m:(m['date'],m['record_id']))
        ends = sorted([m for m in ex if m['interval_status']=='complete'], key=lambda m:(m['end_date'],m['record_id']))
        start = starts[0]['date'] if starts else None
        end = ends[-1]['end_date'] if ends else None
        if starts: sentinels.append(point(starts[0],'treatment_start',start,True))
        if ends: sentinels.append(point(ends[-1],'last_dose',end,True))
        responses = sorted([m for m in by_lane['RS'] if m['date'] and engine.records[m['record_id']]['values'].get('RSTESTCD')=='OVRLRESP'],key=lambda m:(m['date'],m['record_id']))
        response_values = [engine.records[m['record_id']]['values'].get('RSORRES') for m in responses]
        first_pd = None
        first_response = False
        for mark, value in zip(responses,response_values):
            if value in ('CR','PR') and not first_response:
                classify(mark,'first_response'); first_response=True
            if value=='PD' and first_pd is None:
                classify(mark,'first_pd'); first_pd=mark['date']
        ranks = CONFIG['response_order']
        best = min((v for v in response_values if v in ranks), key=ranks.index, default=None)
        reasons = [engine.records[m['record_id']]['values'].get('DSREAS') or engine.records[m['record_id']]['values'].get('DSDECOD') for m in by_lane['DS'] if m['display_kind'] in ('trial_withdrawal','treatment_discontinuation')]
        # If death is documented in both AE and DS, paint one sentinel with both sources available.
        deaths = [m for m in rows if m['display_kind']=='death']
        if len(deaths)>1:
            keep = next((m for m in deaths if m['date']), deaths[0])
            keep['related_death_record_ids'] = [m['record_id'] for m in deaths]
            for m in deaths:
                if m is not keep: m['display_suppressed']=True
        summaries.append({'patient_key':key, 'best_response':best,
                          'time_to_pd':(date.fromisoformat(first_pd)-date.fromisoformat(start)).days if first_pd and start else None,
                          'treatment_duration':(date.fromisoformat(end)-date.fromisoformat(start)).days if start and end else None,
                          'discontinuation_reason':'; '.join(sorted(set(reasons))) or None})
    return sentinels, summaries
