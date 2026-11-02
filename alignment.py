"""Display-only anchor resolution over immutable, dataset-specific source records.

An undated qualifying candidate makes the earliest date unresolved, even if other
candidates have dates: do not silently choose the earliest *complete* date.
No analysis window, response confirmation, dose or induction inference is made.
"""
from datetime import date
import re

ANCHORS = {
    'first_treatment': ('days since first documented treatment', 'Earliest documented exposure start (EXSTDTC); no numeric dose or induction predicate.'),
    'first_PR': ('days since first recorded PR', 'Earliest RSORRES=PR with RSTESTCD=OVRLRESP at RSDTC; recorded, not confirmed response.'),
    'first_PD': ('days since first recorded PD', 'Earliest RSORRES=PD with RSTESTCD=OVRLRESP at RSDTC; no inferred progression.'),
    'death': ('days since recorded death', 'Earliest DSDECOD=DEATH at DSSTDTC; fatal AE onset is not a death date.')
}
MISSING = ('All patients in the current visible roster remain visible. Patients without a resolved anchor stay in labeled unaligned groups: '
           'no qualifying event recorded, or event recorded but date unresolved. No partial or missing date is imputed. '
           'Relative bins use the resolved visible patient denominator; unaligned groups are counted separately. Analysis is unchanged.')


def complete(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def resolve_alignment(engine, anchor):
    anchor = 'first_treatment' if anchor == 'first_dose' else anchor
    if anchor == 'calendar':
        denominator = len(engine.fixtures['population'])
        missing = 'Calendar display: no relative anchor required; no patients excluded and no dates imputed.'
        return {'status': 'resolved', 'anchor': anchor, 'axis_label': 'Calendar date',
                'denominator': denominator, 'denominator_unit': 'loaded roster patients',
                'missing_anchor_handling': missing,
                'patients': [], 'record_ids': [],
                'note': f'Absolute calendar dates restored; {denominator} loaded roster patients. {missing} Analysis unchanged.'}
    if anchor not in ANCHORS:
        return {'status': 'unsupported', 'anchor': anchor, 'record_ids': [],
                'denominator': len(engine.fixtures['population']), 'denominator_unit': 'loaded roster patients (unchanged)',
                'missing_anchor_handling': 'Requested anchor is unsupported. No transform applied, no patients excluded and no dates imputed.',
                'note': 'Unsupported alignment; development task required. No randomization/DM anchor is established in this fixture. Supported display anchors: calendar, first_treatment (first_dose), first_PR, first_PD, death. No approximation was made.'}
    by_patient = {}
    for row in engine.records.values():
        v, domain = row['values'], row['dataset']
        field = None
        if anchor == 'first_treatment' and domain == 'EX':
            field = 'EXSTDTC'
        elif anchor in ('first_PR', 'first_PD') and domain == 'RS' and v.get('RSTESTCD') == 'OVRLRESP' and v.get('RSORRES') == anchor[6:]:
            field = 'RSDTC'
        elif anchor == 'death' and domain == 'DS' and v.get('DSDECOD') == 'DEATH':
            field = 'DSSTDTC'
        if field:
            by_patient.setdefault((v['STUDYID'], v['USUBJID']), []).append((row['record_id'], complete(v.get(field))))
    patients = []
    counts = dict(resolved=0, no_qualifying_event=0, event_date_unresolved=0)
    for p in engine.fixtures['population']:
        key = (p['STUDYID'], p['USUBJID'])
        candidates = by_patient.get(key, [])
        status = ('no_qualifying_event' if not candidates else
                  'event_date_unresolved' if any(d is None for _, d in candidates) else 'resolved')
        day = min(d for _, d in candidates) if status == 'resolved' else None
        ids = sorted(rid for rid, d in candidates if day is None or d == day)
        patients.append({'patient_key': list(key), 'status': status, 'date': day, 'record_ids': ids})
        counts[status] += 1
    label, definition = ANCHORS[anchor]
    return {'status': 'resolved', 'anchor': anchor, 'axis_label': label,
            'definition': definition, 'convention': 'Elapsed calendar days; anchor date = 0. Not an SDTM study-day convention.',
            'denominator': len(patients), 'denominator_unit': 'loaded roster patients', 'counts': counts,
            'patients': patients, 'record_ids': sorted({rid for p in patients for rid in p['record_ids']}),
            'missing_anchor_handling': MISSING,
            'note': label + '. ' + definition + ' Elapsed calendar days (anchor = 0, not SDTM study day). ' + MISSING}


def alignment_capabilities(engine):
    summaries = {}
    for anchor in ANCHORS:
        r = resolve_alignment(engine, anchor)
        summaries[anchor] = {k: r[k] for k in ('axis_label', 'definition', 'convention', 'denominator', 'denominator_unit', 'counts')}
    return {'supported_anchors': ['calendar', *ANCHORS], 'aliases': {'first_dose': 'first_treatment'},
            'renderer': '/lattice only; timeline and legacy /3d remain calendar-only',
            'anchors': summaries, 'missing_anchor_handling': MISSING,
            'unsupported': ['randomization', 'anchor-relative analytical windows (development task; no analysis execution)']}
