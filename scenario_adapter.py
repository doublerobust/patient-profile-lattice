"""Independent adapter for synthetic fixtures from pzhang724/patient-profile-linkage.
Pinned commit: be3744cd7768373552e87201ea0efe90578c094f.
This dataset is synthetic. NOT real trial data. NOT a submission-ready dataset.
This is NOT an SDTM conversion or new analytical/clinical inference rule bundle.
"""
import copy
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
from populate_ae_table_s4 import DERIVATIVE_SHA256

ROOT = Path(__file__).parent / 'fixtures/keynote189-synthetic'
RAW_SHA256 = '4dd5639d3b9799ee6c8b31615659d2433452fd6e077aca1ba8cb7d26064fbb54'
COMMIT = 'be3744cd7768373552e87201ea0efe90578c094f'
WARNING = 'This dataset is synthetic. NOT real trial data. NOT a submission-ready dataset.'


def load_scenario(base):
    content = (ROOT/'raw.json').read_bytes()
    if hashlib.sha256(content).hexdigest() != RAW_SHA256:
        raise ValueError('scenario_raw_hash_mismatch')
    raw = json.loads(content)
    metadata = json.loads((ROOT/'provenance.json').read_text())
    counts = {'patients': len(raw['PTS']), **{
        k: sum(len(p[k]) for p in raw['PTS']) for k in ('ae', 'cm', 'ex', 'tr', 'lb')}}
    if (metadata.get('synthetic_only') is not True or metadata.get('warning') != WARNING
            or metadata.get('commit') != COMMIT or metadata.get('raw_sha256') != RAW_SHA256
            or metadata.get('counts') != counts or not metadata.get('imported_at_utc')):
        raise ValueError('scenario_provenance_mismatch')
    derivative = metadata.get('local_derivative', {})
    if (derivative.get('file') != 'table-s4-synthetic.json'
            or derivative.get('sha256') != DERIVATIVE_SHA256
            or derivative.get('upstream_sha256') != RAW_SHA256):
        raise ValueError('scenario_derivative_provenance_mismatch')
    content = (ROOT/'table-s4-synthetic.json').read_bytes()
    if hashlib.sha256(content).hexdigest() != DERIVATIVE_SHA256:
        raise ValueError('scenario_derivative_hash_mismatch')
    upstream = raw
    raw = json.loads(content)
    fixture = copy.deepcopy(base)
    fixture.update(snapshot_id='synthetic-keynote189-table-s4-v2', synthetic_only=True,
                   population=[], requests=[], synthetic_relationship_documentation=[])
    fixture['datasets'] = {d: [] for d in ('AE','CM','EX','RS','DS','RELREC','SUPPAE')}
    originals = {}
    for i, p in enumerate(raw['PTS']):
        patient = {'STUDYID':'SYNTHETIC-KEYNOTE189', 'USUBJID':p['id']}
        fixture['population'].append(patient)
        def day(n):
            return (date(2025,1,1)+timedelta(days=p['enr']+n)).isoformat()
        def add(domain, group, index, original, **fields):
            rows = fixture['datasets'][domain]
            seq = sum(r['values']['USUBJID']==p['id'] for r in rows)+1
            rid = f'{domain}:{p["id"]}:{seq}'
            values = dict(patient, DOMAIN=domain, **{domain+'SEQ':seq}, **fields)
            rows.append({'dataset':domain,'record_id':rid,'row_number':len(rows)+1,'values':values})
            originals[rid] = {'repository':'https://github.com/pzhang724/patient-profile-linkage',
                'commit':COMMIT,'fixture':'fixtures/keynote189-synthetic/table-s4-synthetic.json','raw_sha256':DERIVATIVE_SHA256,
                'upstream_fixture':'fixtures/keynote189-synthetic/raw.json','upstream_raw_sha256':RAW_SHA256,
                'synthetic_only':True, 'warning':WARNING,
                'patient_id':p['id'],'patient_index':i,'group':group,'row_index':index,
                'pointer':f'/PTS/{i}/{group}'+(f'/{index}' if index is not None else ''),
                'row':copy.deepcopy(original), 'enrollment_offset':p['enr'],
                'calendar_mapping':'2025-01-01 + enrollment offset + source day; fictional calendar, not trial dates'}
        for j,a in enumerate(p['ae']):
            add('AE','ae',j,a,AESTDTC=day(a['s']),AEENDTC=day(a['e']),
                AETERM=a['term'],AEBODSYS=a['soc'],AETOXGR=str(a['g']),AESER='Y' if a['ser'] else 'N')
            original = originals[f'AE:{p["id"]}:{j+1}']
            original['upstream_row'] = copy.deepcopy(upstream['PTS'][i]['ae'][j])
            original['term_provenance'] = {
                'literal_term': a['term'],
                'kind': 'event category including related terms' if a['ir'] else 'reported any-cause AE term',
                **{key: derivative[key] for key in ('citation', 'archive_url', 'pdf_sha256',
                    'source_population', 'assignment', 'local_mapping_note', 'warning')},
            }
        for j,c in enumerate(p['cm']):
            add('CM','cm',j,c,CMSTDTC=day(c['s']),CMENDTC=day(c['e']),CMTRT=c['name'],CMINDC=c['why'])
        for j,e in enumerate(p['ex']):
            # A source row is a single administration day, not a 21-day exposure.
            add('EX','ex',j,e,EXSTDTC=day(e['d']),EXENDTC=day(e['d']),EXTRT=e['drug'],EXDOSE_TEXT=e['dose'])
        for j,t in enumerate(p['tr']):
            add('RS','tr',j,t,RSDTC=day(t['d']),RSTESTCD='OVRLRESP',RSORRES=t['resp'],
                SYN_SLD=t['sld'],SYN_PCT=t['pct'])
        ds = p['ds']
        if ds['death'] is not None:
            add('DS','ds',None,ds,DSSTDTC=day(ds['death']),DSDECOD='DEATH')
        # Retain recorded reason and eot as given, even when anomalies disagree.
        if ds['reason'] != 'Ongoing':
            add('DS','ds',None,ds,DSSTDTC=day(ds['eot']),DSDECOD='TREATMENT DISCONTINUATION',DSREAS=ds['reason'])
        if ds['xo'] is not None:
            add('DS','ds',None,ds,DSSTDTC=day(ds['xo']),DSDECOD='SUBSEQUENT ANTICANCER THERAPY',DSREAS='Recorded crossover')
    metadata['adapter'] = 'synthetic-keynote189-table-s4-v2; local synthetic derivative; TR → RS; raw LB retained but not rendered by unchanged clinical engine'
    metadata['calendar_origin'] = '2025-01-01 (fictional display origin)'
    metadata['severity_note'] = 'Source provides toxicity grade and seriousness, not AESEV; severity predicates therefore match no rows. No grade-to-severity inference.'
    return fixture, originals, metadata
