#!/usr/bin/env python3
"""Loopback-only synthetic lane-view spike. No uploads, chat, or external services."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import sys
from typing import cast
from urllib.parse import urlparse
from cohort import scale_cohort
from scenario_adapter import load_scenario
from display import CONFIG, prepare

ROOT = Path(__file__).resolve().parent
LANES = ['AE', 'CM', 'EX', 'RS']  # Fixed by this UI; not a configurable spec field.
LOCKED = {'contract.json', 'fixtures.json', 'expected_results.json', 'schemas.json',
          'evidence.json', 'README.txt', 'validate.py', 'normalized_spec.json'}


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


class Engine:
    def __init__(self, data, cohort='small'):
        self.data = Path(data).resolve()
        manifest = load_json(self.data / 'manifest.json')
        if set(manifest['file_sha256']) != LOCKED:
            raise ValueError('manifest_file_set_mismatch')
        for name, expected in manifest['file_sha256'].items():
            if hashlib.sha256((self.data / name).read_bytes()).hexdigest() != expected:
                raise ValueError('file_hash_mismatch: ' + name)
        # Reuse the pinned, unchanged reference semantics rather than fork the rules.
        definition = importlib.util.spec_from_file_location('lane_reference', self.data / 'validate.py')
        if definition is None or definition.loader is None:
            raise ValueError('reference_module_unavailable')
        self.ref = importlib.util.module_from_spec(definition)
        definition.loader.exec_module(self.ref)
        self.fixtures = self.ref.load('fixtures.json')
        if self.fixtures['synthetic_only'] is not True or manifest['synthetic_only'] is not True:
            raise ValueError('synthetic_data_required')
        if cohort not in ('small', '100', 'keynote189'):
            raise ValueError('unknown_cohort')
        self.cohort = cohort
        self.original_sources, self.scenario = {}, None
        if cohort == '100':
            self.fixtures = scale_cohort(self.fixtures)
        elif cohort == 'keynote189':
            self.fixtures, self.original_sources, self.scenario = load_scenario(self.fixtures)
        self.snapshot_sha256 = (digest(self.fixtures) if cohort != 'small'
                                else manifest['snapshot_sha256'])
        self.records = {r['record_id']: r for rows in self.fixtures['datasets'].values() for r in rows}
        if len(self.records) != sum(len(rows) for rows in self.fixtures['datasets'].values()):
            raise ValueError('duplicate_record_id')
        self.display_marks = []
        for domain in LANES + ['DS']:
            for row in self.fixtures['datasets'].get(domain, []):
                self.display_marks.append({'mark_id': 'mark:' + self.fixtures['snapshot_id'] + ':' + row['record_id'],
                    'record_id': row['record_id'], 'patient_key': list(self.ref.patient_key(row)), 'lane': domain,
                    **self.interval(row), 'selectable': True, 'source_ref': self.source_ref(row)})
        self.sentinels, self.patient_summaries = prepare(self, self.display_marks)
        self.normalize(self.default_spec())
        for row in self.fixtures['datasets']['SUPPAE']:
            if len(self.ref.resolve_selector(self.fixtures, row['values'])) != 1:
                raise ValueError('supplement_parent_link_mismatch')

    def default_spec(self):
        spec = self.ref.load('normalized_spec.json')
        spec['snapshot_id'] = self.fixtures['snapshot_id']
        spec['snapshot_sha256'] = self.snapshot_sha256
        if self.cohort != 'small':
            spec['analysis_state']['population'] = sorted(
                [[p['STUDYID'], p['USUBJID']] for p in self.fixtures['population']])
            spec['analysis_state']['ae_predicate'] = None
            spec['view_state']['selection'] = None
        return spec

    def check_pins(self, spec):
        expected = self.default_spec()
        for key in ('snapshot_id', 'snapshot_sha256'):
            if spec[key] != expected[key]:
                raise ValueError('snapshot_mismatch')
        for key in ('rule_bundle_id', 'rule_bundle_version', 'rule_bundle_sha256'):
            if spec[key] != expected[key]:
                raise ValueError('rule_bundle_mismatch')

    def eligible_ids(self, analysis):
        patients = set(map(tuple, analysis['qualifying_patient_keys']))
        return set(analysis['qualifying_ae_record_ids']) | {
            row['record_id'] for domain in ('CM', 'EX', 'RS', 'DS')
            for row in self.fixtures['datasets'].get(domain, [])
            if self.ref.patient_key(row) in patients}

    def normalize(self, spec):
        # Check pins before schema constants so mismatch errors remain useful to reviewers.
        self.check_pins(spec)
        self.ref.schema_check('normalized_spec', spec)
        result = copy.deepcopy(spec)
        result['analysis_state']['population'].sort()
        view = result['view_state']
        view['hidden_lanes'].sort()
        view['focus_patient_keys'].sort()
        roster = {self.ref.patient_key(p) for p in self.fixtures['population']}
        if not set(map(tuple, view['focus_patient_keys'])) <= roster:
            raise ValueError('unknown_focus_patient')
        analysis = self.ref.analyze(self.fixtures, result['analysis_state'])
        selection = view['selection']
        if selection:
            ids = selection['source_record_ids']
            if len(ids) != 1 or selection['mark_id'] != 'mark:' + spec['snapshot_id'] + ':' + ids[0]:
                raise ValueError('invalid_mark_identity')
            if ids[0] not in self.eligible_ids(analysis):
                raise ValueError('selection_not_eligible')
        window = view['display_date_window']
        if window and window['start'] > window['end']:
            raise ValueError('invalid_display_date_window')
        return result

    def interval(self, row):
        domain, values = row['dataset'], row['values']
        start = values.get('RSDTC' if domain == 'RS' else domain + 'STDTC', '')
        end = values.get(domain + 'ENDTC', '')
        is_interval = domain not in ('RS', 'DS') or domain + 'ENDTC' in values
        complete_start, complete_end = self.ref.complete_date(start), self.ref.complete_date(end)
        status, end_state, end_source = 'point', 'point', None
        if is_interval:
            status = ('incomplete_start' if not complete_start else
                      'missing_end' if not end else 'incomplete_end' if not complete_end else
                      'reversed' if complete_end < complete_start else 'complete')
            end_state = 'recorded' if status == 'complete' else 'unknown'
            end_source = domain + 'ENDTC' if status == 'complete' else None
            followup = CONFIG['interval_followup_fields'].get(domain)
            if followup and not end and complete_start and values.get(followup['ongoing']) == 'Y':
                documented = values.get(followup['date'], '')
                complete_followup = self.ref.complete_date(documented)
                if complete_followup and complete_followup >= complete_start:
                    end = documented
                    complete_end = complete_followup
                    status, end_state, end_source = 'ongoing', 'ongoing', followup['date']
        return {'date': start if complete_start else None, 'raw_date': start,
                'end_date': end if status in ('complete', 'ongoing') else None,
                'raw_end_date': values.get(domain + 'ENDTC', ''),
                'is_interval': is_interval, 'interval_status': status,
                'end_state': end_state, 'end_source': end_source}

    def source_ref(self, row):
        if row['dataset'] == 'DS':
            return {'snapshot_id': self.fixtures['snapshot_id'], 'record_id': row['record_id'],
                    'dataset': 'DS', 'row_number': row['row_number'],
                    'source_key': {k: row['values'][k] for k in ('STUDYID', 'USUBJID', 'DSSEQ')}}
        return self.ref.source_ref(self.fixtures, row)

    def source(self, record_id):
        row = self.records[record_id]
        result = {'ref': self.source_ref(row), 'values': copy.deepcopy(row['values'])}
        if record_id in self.original_sources:
            result['original_source'] = copy.deepcopy(self.original_sources[record_id])
        return result

    def evidence(self, record_id):
        row = self.records[record_id]
        relationships = []
        seen = set()
        for relrow in self.fixtures['datasets']['RELREC']:
            v = relrow['values']
            key = (v['STUDYID'], v['USUBJID'], v['RELID'])
            if key in seen:
                continue
            seen.add(key)
            rel = self.ref.resolve_relationship(self.fixtures, dict(zip(('STUDYID', 'USUBJID', 'RELID'), key)))
            members = {rid for ep in rel.get('endpoints', []) for rid in ep['resolved_source_record_ids']}
            if record_id not in members:
                continue
            source_ids = sorted(members | set(rel['relrec_source_record_ids']))
            refs = rel['semantics_evidence_refs']
            docs = [d for d in self.fixtures['synthetic_relationship_documentation']
                    if 'fixtures.json#synthetic_relationship_documentation/' + d['document_id'] in refs]
            text = 'Relationship evidence supports an association. It does not establish cause.'
            if any(ep['raw_reltype'] == '' for ep in rel['endpoints']):
                text += ' The source relationship type is blank. No relationship type is inferred.'
            if rel['clinical_meaning'] == 'unknown':
                text += ' Clinical meaning: not documented in source.'
            else:
                text += ' Separate synthetic documentation states medication used to treat AE; this is not evidence of causation.'
            relationships.append({'evidence': rel, 'explanation': text,
                                  'source_records': [self.source(rid) for rid in source_ids],
                                  'semantics_documents': docs})
        supplements = []
        for supplement in self.fixtures['datasets']['SUPPAE']:
            parents = self.ref.resolve_selector(self.fixtures, supplement['values'])
            if record_id in parents:
                supplements.append({'parent_source_record_ids': parents,
                                    'source_record': self.source(supplement['record_id'])})
        return {'mark_id': 'mark:' + self.fixtures['snapshot_id'] + ':' + record_id,
                'derivation_rule_id': 'provenance-v1', 'source_records': [self.source(row['record_id'])],
                'relationships': relationships, 'supplements': supplements}

    def evaluate(self, spec, analysis_change=False):
        spec = copy.deepcopy(spec)
        reason = None
        # Only an explicit analytical action may clear excluded selections. Replay must reject them.
        if analysis_change:
            self.ref.schema_check('normalized_spec', spec)
            self.check_pins(spec)
            ids = self.eligible_ids(self.ref.analyze(self.fixtures, spec['analysis_state']))
            selection = spec['view_state']['selection']
            if selection and not set(selection['source_record_ids']) <= set(ids):
                spec['view_state']['selection'] = None
                reason = 'analysis_excluded'
        spec = self.normalize(spec)
        analysis = self.ref.analyze(self.fixtures, spec['analysis_state'])
        patients = self.ref.visible_patients(self.fixtures, spec)
        lanes = [d for d in LANES if d not in spec['view_state']['hidden_lanes']]
        if self.fixtures['datasets'].get('DS'): lanes.append('DS')
        window = spec['view_state']['display_date_window']
        def visible(mark):
            if mark['patient_key'] not in patients or mark['lane'] not in lanes:
                return False
            if mark['lane']=='AE' and mark['record_id'] not in analysis['qualifying_ae_record_ids']:
                return False
            end = mark['end_date'] or mark['date']
            return not window or (mark['date'] is not None and mark['date'] <= window['end'] and end >= window['start'])
        marks = [m for m in self.display_marks if visible(m)]
        sentinels = [m for m in self.sentinels if visible(m)]
        selection = spec['view_state']['selection']
        return {'spec': spec, 'analysis': analysis,
                'analysis_signature': digest({k: v for k, v in spec.items() if k != 'view_state'}),
                'visible_patient_keys': patients, 'lane_order': lanes, 'marks': marks,
                'sentinels': sentinels, 'display_config': CONFIG, 'patient_summaries': self.patient_summaries,
                'selection_visible': bool(selection and any(m['mark_id'] == selection['mark_id'] for m in marks)),
                'selection_cleared_reason': reason,
                'roster': [[p['STUDYID'], p['USUBJID']] for p in self.fixtures['population']],
                'scenario': self.scenario}

    def pick(self, spec, mark_id):
        state = self.evaluate(spec)
        mark = next((m for m in state['marks'] if m['mark_id'] == mark_id), None)
        if mark is None:
            raise ValueError('mark_not_pickable')
        return self.evidence(mark['record_id'])

    def export_review(self, spec):
        state = self.evaluate(spec)
        selection = state['spec']['view_state']['selection']
        evidence = self.evidence(selection['source_record_ids'][0]) if selection else None
        package = {'format': 'lane-review-v1', 'synthetic_only': True, 'question': None,
                   'exported_at_utc': datetime.now(timezone.utc).isoformat(),
                   'spec': state['spec'], 'analysis': state['analysis'],
                   'analysis_signature': state['analysis_signature'],
                   'source_records': evidence['source_records'] if evidence else [],
                   'selection_evidence': evidence}
        return dict(package, content_sha256=digest(package))

    def replay(self, package):
        required = {'format', 'synthetic_only', 'question', 'exported_at_utc', 'spec', 'analysis',
                    'analysis_signature', 'source_records', 'selection_evidence', 'content_sha256'}
        if set(package) != required or package['format'] != 'lane-review-v1' or package['synthetic_only'] is not True or package['question'] is not None:
            raise ValueError('invalid_review_package')
        body = {k: v for k, v in package.items() if k != 'content_sha256'}
        if digest(body) != package['content_sha256']:
            raise ValueError('content_hash_mismatch')
        state = self.evaluate(package['spec'])
        if canonical(state['spec']) != canonical(package['spec']):
            raise ValueError('spec_not_normalized')
        if state['analysis'] != package['analysis'] or state['analysis_signature'] != package['analysis_signature']:
            raise ValueError('analysis_reproduction_mismatch')
        reconstructed = self.export_review(state['spec'])
        if reconstructed['source_records'] != package['source_records'] or reconstructed['selection_evidence'] != package['selection_evidence']:
            raise ValueError('provenance_mismatch')
        state['replay_checks'] = {'exact_spec_restoration': True, 'analysis_reproduction': True, 'provenance_verified': True}
        return state


class Server(ThreadingHTTPServer):
    # Chromium opens one upstream connection per HTTP/2 stream; the socketserver
    # default listen backlog of 5 gets overflowed, and macOS RSTs the excess, which
    # the Tailscale proxy reports to the browser as 502 on random assets.
    request_queue_size = 128
    daemon_threads = True


def make_handler(engine):
    class Handler(BaseHTTPRequestHandler):

        def reply(self, status, body, content_type='application/json'):
            encoded = canonical(body) if content_type == 'application/json' else body
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(encoded)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(encoded)

        def local_request(self):
            host = self.headers.get('Host', '')
            # Exact authorities prevent lookalike hosts bypassing the rebinding guard.
            local_names = ('127.0.0.1', 'localhost', '[::1]')
            allowed: set[str] = set(local_names)
            allowed.update(name + ':' + str(cast(ThreadingHTTPServer, self.server).server_port) for name in local_names)
            allowed.update(('yues-mac-studio.tail8e98a8.ts.net',
                            'yues-mac-studio.tail8e98a8.ts.net:9143',
                            'yues-mac-studio.tail8e98a8.ts.net:9144',
                            'yues-mac-studio.tail8e98a8.ts.net:9145'))
            origin = self.headers.get('Origin')
            return host in allowed and (origin is None or origin in
                                        ('http://' + host, 'https://' + host))

        def refuse_page(self):
            url = 'http://127.0.0.1:' + str(cast(ThreadingHTTPServer, self.server).server_port) + '/'
            body = ('<!doctype html><meta charset="utf-8"><title>Open this URL</title>'
                    '<h1>Open the viewer at its local address</h1>'
                    '<p>On the Mac, open <a href="' + url + '">' + url + '</a>.</p>'
                    '<p>From another machine, use the configured tailnet URL.</p>')
            return self.reply(403, body.encode('utf-8'), 'text/html; charset=utf-8')

        def do_GET(self):
            if not self.local_request():
                return self.refuse_page()
            path = urlparse(self.path).path
            if path == '/api/initial':
                return self.reply(200, engine.evaluate(engine.default_spec()))
            if path in ('/3d', '/3d/', '/lattice', '/lattice/'):
                adapter = 'lattice' if path.startswith('/lattice') else 'renderer3d'
                extra_css = '<link rel="stylesheet" href="/lattice.css">' if adapter == 'lattice' else ''
                page = (ROOT / 'static' / 'index.html').read_text()
                page = page.replace('<script src="/app.js" defer></script>',
                    '<link rel="stylesheet" href="/3d.css">' + extra_css +
                    '<script src="/' + adapter + '.js" defer></script><script src="/app.js" defer></script>')
                return self.reply(200, page.encode(), 'text/html; charset=utf-8')
            files = {'/': ('index.html', 'text/html; charset=utf-8'),
                     '/renderer3d.js': ('renderer3d.js', 'text/javascript; charset=utf-8'),
                     '/3d.css': ('3d.css', 'text/css; charset=utf-8'),
                     '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                     '/grammar.js': ('grammar.js', 'text/javascript; charset=utf-8'),
                     '/gestures.js': ('gestures.js', 'text/javascript; charset=utf-8'),
                     '/view-chat.js': ('view-chat.js', 'text/javascript; charset=utf-8'),
                     '/view-chat.css': ('view-chat.css', 'text/css; charset=utf-8'),
                     '/lattice.js': ('lattice.js', 'text/javascript; charset=utf-8'),
                     '/lattice.css': ('lattice.css', 'text/css; charset=utf-8'),
                     '/style.css': ('style.css', 'text/css; charset=utf-8')}
            if path not in files:
                return self.reply(404, {'error': 'not_found'})
            name, mime = files[path]
            self.reply(200, (ROOT / 'static' / name).read_bytes(), mime)

        def do_POST(self):
            if not self.local_request():
                return self.refuse_page()
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length < 1 or length > 1_000_000:
                    raise ValueError('invalid_request_size')
                body = json.loads(self.rfile.read(length))
                path = urlparse(self.path).path
                if path == '/api/evaluate':
                    result = engine.evaluate(body['spec'], analysis_change=body.get('analysis_change') is True)
                elif path == '/api/view-query':
                    from view_tools import query_records
                    result = query_records(engine, body['spec'], body['args'])
                elif path == '/api/pick':
                    result = engine.pick(body['spec'], body['mark_id'])
                elif path == '/api/source':
                    result = engine.source(body['record_id'])
                elif path == '/api/export':
                    result = engine.export_review(body['spec'])
                elif path == '/api/replay':
                    result = engine.replay(body['package'])
                else:
                    return self.reply(404, {'error': 'not_found'})
                self.reply(200, result)
            except Exception as exc:
                self.reply(400, {'error': str(exc)})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=ROOT / 'data')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--cohort', choices=('100', 'small', 'keynote189'), default='100',
                        help='100-patient demo (default); keynote189 is the authorized imported synthetic scenario; small preserves golden fixture')
    parser.add_argument('--verify', type=Path, help='Read-only saved-review verification; never repairs or rewrites')
    parser.add_argument('--verify-data', action='store_true', help='Read-only input hash and SUPPAE parent-link verification')
    args = parser.parse_args()
    try:
        engine = Engine(args.data, cohort=args.cohort)
        if args.verify:
            state = engine.replay(load_json(args.verify))
            print(json.dumps(state['replay_checks'], sort_keys=True))
        elif args.verify_data:
            print('PASS: pinned file hashes, normalized spec, synthetic-only flag and SUPPAE parent links')
        else:
            server = Server(('127.0.0.1', args.port), make_handler(engine))
            print('Synthetic-only lane viewer: http://127.0.0.1:%d' % server.server_port, flush=True)
            server.serve_forever()
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
