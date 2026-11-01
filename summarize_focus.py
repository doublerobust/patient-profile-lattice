import json
from pathlib import Path
from app import Engine
s=Engine(Path('data'),cohort='100').evaluate(Engine(Path('data'),cohort='100').default_spec())
for m in s['marks']:
    if m['patient_key'][1] in ('SYN-004','SYN-001'):
        print(m['record_id'], m['display_kind'],m['date'],m['end_date'],m['interval_status'],m.get('display_suppressed'))
for phase in ('before','after'):
    report=json.loads(Path(f'evidence/focus-vsets-{phase}.json').read_text())
    print(phase)
    for route,rows in report.items():
        for r in rows:
            if r['mode']=='auto':print(route, r['state'],r['tier'],r['counts'],'V',r['pass'],'missing',len(r['missing']),'extra',len(r['unexpected']))
