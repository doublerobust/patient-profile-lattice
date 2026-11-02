"""Read-only, fail-closed AE query shared by highlight_events and query_data."""
from datetime import date


def query_records(engine, spec, args):
    if not isinstance(args, dict) or set(args) != {'scope', 'unit', 'filters'}:
        raise ValueError('Specify scope=current_analysis, unit (patients or AE records), and filters. Which counting unit?')
    if args['scope'] != 'current_analysis' or args['unit'] not in ('patients', 'AE records'):
        raise ValueError('Choose current_analysis scope and patients or AE records; no counting-unit inference.')
    filters = args['filters']
    if not isinstance(filters, dict) or set(filters) - {'term', 'grade', 'patient', 'date_window', 'linked_cm'}:
        raise ValueError('Unsupported filter. Which explicit date window and anchor do you intend?')
    if 'grade' in filters and (type(filters['grade']) is not int or not 1 <= filters['grade'] <= 5):
        raise ValueError('Grade must be an integer 1–5; severity is not toxicity grade.')
    for key in ('term', 'patient', 'linked_cm'):
        if key in filters and (not isinstance(filters[key], str) or not filters[key].strip()):
            raise ValueError(key + ' must be a nonempty exact source value.')
    window = filters.get('date_window')
    if 'date_window' in filters:
        if not isinstance(window, dict) or set(window) != {'anchor', 'start', 'end'} or window['anchor'] != 'AESTDTC':
            raise ValueError('Which window and anchor? Supply AESTDTC calendar start/end (inclusive). Relative windows unsupported.')
        try:
            for key in ('start', 'end'):
                if date.fromisoformat(window[key]).isoformat() != window[key]: raise ValueError()
            if window['start'] > window['end']: raise ValueError()
        except (ValueError, TypeError):
            raise ValueError('Use valid ordered YYYY-MM-DD window endpoints.')
    evaluated = engine.evaluate(spec)
    matches, patients, links, unknown_grade, incomplete_date = [], set(), set(), 0, 0
    for rid in evaluated['analysis']['qualifying_ae_record_ids']:
        v = engine.records[rid]['values']
        if 'term' in filters and v.get('AETERM', '').casefold() != filters['term'].casefold(): continue
        if 'patient' in filters and v['USUBJID'] != filters['patient']: continue
        if 'grade' in filters:
            if not v.get('AETOXGR'): unknown_grade += 1
            if str(v.get('AETOXGR', '')) != str(filters['grade']): continue
        if window:
            onset = v.get('AESTDTC', '')
            try:
                if date.fromisoformat(onset).isoformat() != onset: raise ValueError()
            except ValueError:
                incomplete_date += 1
                continue
            if not window['start'] <= onset <= window['end']: continue
        if 'linked_cm' in filters:
            related = {r['ref']['record_id'] for rel in engine.evidence(rid)['relationships']
                       for r in rel['source_records'] if r['values'].get('DOMAIN') == 'CM'
                       and r['values'].get('CMTRT', '').casefold() == filters['linked_cm'].casefold()}
            if not related: continue
            links.update(related)
        matches.append(rid)
        patients.add((v['STUDYID'], v['USUBJID']))
    return {'count': len(matches) if args['unit'] == 'AE records' else len(patients),
            'unit': args['unit'], 'record_ids': sorted(matches), 'patient_keys': sorted(patients),
            'linked_record_ids': sorted(links), 'scope': 'current_analysis',
            'note': 'Current qualifying analysis, independent of view; exact AE onset calendar window inclusive, or all dates when omitted. Linked CM means documented association, not causation.',
            'excluded_missing_grade': unknown_grade, 'excluded_incomplete_onset': incomplete_date}
