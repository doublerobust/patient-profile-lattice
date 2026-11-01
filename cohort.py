"""Deterministic, fictional 100-patient display fixture; never a trial distribution.

Original three golden patients remain verbatim. The other 97 share a treatment
start for a readable duration staircase and explicitly demonstrate review events.
AEONGO/AEFUDTC and CMONGO/CMFUDTC are synthetic source extensions documenting
ongoing status at a domain-specific follow-up, not RFENDTC or inferred collection.
"""
import copy
from datetime import date, timedelta


def scale_cohort(base):
    fixture = copy.deepcopy(base)
    fixture['snapshot_id'] = 'synthetic-scale-100-v2-sentinel'
    fixture['generator_version'] = 'scale-100-v2-sentinel'
    fixture['requests'] = []
    fixture['datasets']['DS'] = []
    origin = date(2025, 1, 1)
    for number in range(4, 101):
        patient = {'STUDYID': 'SYN-SPIKE', 'USUBJID': f'SYN-{number:03d}'}
        fixture['population'].append(patient)
        duration = 50 + number * 2

        def day(offset): return (origin + timedelta(days=offset)).isoformat()

        def add(domain, seq, start, end=None, **extra):
            values = dict(patient, DOMAIN=domain, **{domain + 'SEQ': seq}, **extra)
            values['RSDTC' if domain == 'RS' else domain + 'STDTC'] = day(start)
            if end is not None: values[domain + 'ENDTC'] = day(end)
            rows = fixture['datasets'][domain]
            rows.append({'dataset': domain, 'record_id': f'{domain}-{number:03d}-{seq}',
                         'row_number': len(rows) + 1, 'values': values})

        for seq, severity in enumerate(('SEVERE', 'MODERATE', 'MILD'), 1):
            start = seq * 10
            grade = 5 if number % 10 == 0 and seq == 1 else (3 if seq == 1 else 1)
            extra = dict(AESEV=severity, AETERM='SYNTHETIC EVENT', AEGRPID=f'EP{seq}',
                         AETOXGR=str(grade), AESER='Y' if grade >= 3 else 'N')
            if grade == 5:
                add('AE',seq,start,duration+10,**extra, DTHDTC=day(duration+10))
            elif seq == 2:
                add('AE',seq,start,**extra, AEONGO='Y', AEFUDTC=day(start+15))
            elif seq == 3:
                add('AE',seq,start,**extra)
            else:
                add('AE',seq,start,start+number%12,**extra)
        add('EX',1,0,27,EXTRT='SYNTHETIC TREATMENT')
        add('EX',2,35,duration,EXTRT='SYNTHETIC TREATMENT',EXADJ='REDUCTION' if number%2 else 'INTERRUPTION')
        add('CM',1,10,**{'CMTRT':'SYNTHETIC MEDICATION','CMGRPID':'G1','CMONGO':'Y','CMFUDTC':day(45)})
        add('CM',2,20,25 if number%2 else None, CMTRT='SYNTHETIC MEDICATION',CMGRPID='G2')
        best = ('CR','PR','SD','NE')[number%4]
        for seq, offset, response in [(1,28,best),(2,42,best),(3,duration-5,'PD')]:
            add('RS',seq,offset,RSTESTCD='OVRLRESP',RSORRES=response)
        add('RS',4,35,RSTESTCD='LESION',RSORRES='SYNTHETIC ASSESSMENT')
        reason = ('ADVERSE EVENT','PROGRESSIVE DISEASE','WITHDRAWAL BY SUBJECT')[number%3]
        add('DS',1,duration,DSDECOD='TREATMENT DISCONTINUATION',DSREAS=reason)
        add('DS',2,duration+2,DSDECOD='WITHDRAWAL BY SUBJECT' if number%3==2 else 'TRIAL DISCONTINUATION')
        add('DS',3,duration+5,DSDECOD='SUBSEQUENT ANTICANCER THERAPY')
    return fixture
