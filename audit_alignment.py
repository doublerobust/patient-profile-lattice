"""Reproduce the capability matrix from immutable loaded fixtures (no network)."""
import hashlib
import json
from pathlib import Path
from app import Engine
from alignment import ANCHORS, alignment_capabilities, resolve_alignment

ROOT = Path(__file__).resolve().parent


def audit():
    result = {}
    for cohort in ('small', '100', 'keynote189'):
        engine = Engine(ROOT / 'data', cohort)
        rs = engine.fixtures['datasets']['RS']
        anchors = {}
        for anchor in (*ANCHORS, 'randomization'):
            resolved = resolve_alignment(engine, anchor)
            anchors[anchor] = {
                'status': resolved['status'],
                'resolved_patients': sum(p['status'] == 'resolved' for p in resolved.get('patients', [])),
                'counts': resolved.get('counts'),
                'limitation': resolved.get('limitation'),
            }
        result[cohort] = {
            'snapshot_id': engine.fixtures['snapshot_id'],
            'snapshot_sha256': engine.snapshot_sha256,
            'loaded_roster': len(engine.fixtures['population']),
            'RS_rows': len(rs),
            'RSSTRESC_populated_rows': sum(bool(r['values'].get('RSSTRESC')) for r in rs),
            'catalogue': alignment_capabilities(engine),
            'resolver': anchors,
        }
    return {
        'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
            'data/fixtures.json', 'data/manifest.json', 'cohort.py', 'scenario_adapter.py',
            'fixtures/keynote189-synthetic/raw.json')},
        'cohorts': result,
    }


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2, sort_keys=True))
