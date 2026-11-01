"""Deterministic synthetic scale fixture. No RNG, clock, files, or external inputs.

Retain the three golden patients verbatim; append 97 fictional patients with
three AEs, two treatment intervals, two medication intervals and two assessments.
This is a rendering stress fixture, not a simulated trial distribution.
"""
import copy
from datetime import date, timedelta


def scale_cohort(base):
    fixture = copy.deepcopy(base)
    fixture['snapshot_id'] = 'synthetic-scale-100-v1'
    fixture['generator_version'] = 'scale-100-v1'
    fixture['requests'] = []  # Golden oracles apply only to the unchanged small fixture.
    origin = date(2025, 1, 1)
    for number in range(4, 101):
        patient = {'STUDYID': 'SYN-SPIKE', 'USUBJID': f'SYN-{number:03d}'}
        fixture['population'].append(patient)
        base_day = (number * 17) % 180

        def add(domain, seq, start, end=None, **extra):
            values = dict(patient, DOMAIN=domain, **{domain + 'SEQ': seq}, **extra)
            values['RSDTC' if domain == 'RS' else domain + 'STDTC'] = (origin + timedelta(days=start)).isoformat()
            if end is not None:
                values[domain + 'ENDTC'] = (origin + timedelta(days=end)).isoformat()
            rows = fixture['datasets'][domain]
            rows.append({'dataset': domain, 'record_id': f'{domain}-{number:03d}-{seq}',
                         'row_number': len(rows) + 1, 'values': values})

        for seq, severity in enumerate(('SEVERE', 'MODERATE', 'MILD'), 1):
            start = base_day + seq * 10
            add('AE', seq, start, start + (number + seq) % 12,
                AESEV=severity, AETERM='SYNTHETIC EVENT', AEGRPID=f'EP{seq}')
        for seq in (1, 2):
            start = base_day + (seq - 1) * 35
            add('EX', seq, start, start + 27, EXTRT='SYNTHETIC TREATMENT')
            start = base_day + seq * 10
            add('CM', seq, start, start + 5 + number % 15,
                CMTRT='SYNTHETIC MEDICATION', CMGRPID=f'G{seq}')
            add('RS', seq, base_day + seq * 28, RSTESTCD='OVRLRESP', RSORRES='SYNTHETIC ASSESSMENT')
    return fixture
