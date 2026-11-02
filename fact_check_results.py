"""Summarize actual captured runs, never infer missing checks as passes."""
import json
from pathlib import Path
import re
root = Path(__file__).resolve().parent
runs = {}
for label, filename in [('full_python', 'fact-check-regression.log'), ('isolated_legacy_3d', 'fact-check-3d-rerun.log'), ('focused_acceptance', 'fact-check-acceptance.log'), ('independent_probes', 'fact-check-probes-verified.log')]:
    text = (root / filename).read_text()
    m = re.search(r'Ran (\d+) tests? in ([0-9.]+)s', text)
    if not m:
        raise RuntimeError('Missing test-run summary: ' + filename)
    count, seconds = int(m[1]), float(m[2])
    fail = re.search(r'FAILED \((.*?)\)', text)
    failures = int(re.search(r'failures=(\d+)', fail[1])[1]) if fail and 'failures=' in fail[1] else 0
    errors = int(re.search(r'errors=(\d+)', fail[1])[1]) if fail and 'errors=' in fail[1] else 0
    runs[label] = {'file': filename, 'tests': count, 'passed': count - failures - errors,
                   'failures': failures, 'errors': errors, 'seconds': seconds,
                   'exit_code': 1 if fail else 0}
for label, filename in [('node', 'fact-check-node.log'), ('alignment_geometry', 'fact-check-geometry.log')]:
    text = (root / filename).read_text()
    runs[label] = {key: int(re.search(r'\b' + key + r' (\d+)', text)[1]) for key in ['tests', 'pass', 'fail']}
    runs[label]['file'] = filename
result = {'reviewed_commit': '0eb084bbcee7eebfed0f9115a821ec1780263037', 'overall': 'CHANGES_REQUIRED', 'runs': runs}
(root / 'fact-check-results.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
