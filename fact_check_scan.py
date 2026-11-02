"""Bounded secret-pattern and fixture-integrity evidence; never prints matches."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parent
patterns = [re.compile(rb'sk-(?:proj-)?[A-Za-z0-9_-]{24,}'),
            re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}'),
            re.compile(rb'Bearer [A-Za-z0-9_=-]{24,}'),
            re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]

def git(*args):
    return subprocess.check_output(['git', *args], cwd=root)

# Scan every file blob reachable from the exact reviewed commit, including history.
objects = git('rev-list', '--objects', '0eb084b').splitlines()
hits = []
scanned = 0
for obj in objects:
    oid, _, path = obj.partition(b' ')
    if not path:
        continue
    if git('cat-file', '-t', oid.decode()).strip() != b'blob':
        continue
    blob = git('cat-file', '-p', oid.decode())
    scanned += 1
    matched = [index for index, pattern in enumerate(patterns) if pattern.search(blob)]
    if matched:
        hits.append({'object': oid.decode(), 'path': path.decode(errors='replace'), 'pattern_indices': matched})

fixtures = [p for directory in ('data', 'fixtures', 'test-fixtures') for p in (root / directory).rglob('*') if p.is_file()]
changed = git('diff', '--name-only', 'ca13cdf', '0eb084b', '--', 'data', 'fixtures', 'test-fixtures', 'cohort.py', 'scenario_adapter.py').decode().splitlines()
result = {
    'reviewed_commit': git('rev-parse', '0eb084b').decode().strip(),
    'reachable_history_blob_count': scanned,
    'high_confidence_token_pattern_findings': hits,
    'fixture_files_examined': len(fixtures),
    'fixture_code_or_data_changes_since_baseline': changed,
    'fixtures': [{'path': str(p.relative_to(root)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(fixtures)],
    'scope': 'Four token/private-key regexes over blobs reachable from the reviewed commit, not a proof that all possible secrets or real patient data are absent.'
}
(root / 'fact-check-scan.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k != 'fixtures'}, indent=2))
