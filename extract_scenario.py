"""Extract authorized synthetic outputs; never retain or run external inference code.
Network is used only when explicitly running this extraction utility, not by the app.
"""
import hashlib
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from urllib.request import urlopen

COMMIT = 'be3744cd7768373552e87201ea0efe90578c094f'
URL = f'https://raw.githubusercontent.com/pzhang724/patient-profile-linkage/{COMMIT}/src/cube/c0_data.js'
ROOT = Path(__file__).resolve().parent / 'fixtures/keynote189-synthetic'
SOURCE_SHA256 = 'a3fc77bc4f5c0244e4bef5cbe5dc45d0119e183debf535bd6547d268783efd0c'
RAW_SHA256 = '4dd5639d3b9799ee6c8b31615659d2433452fd6e077aca1ba8cb7d26064fbb54'


def extract():
    source = urlopen(URL, timeout=30).read()
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError('pinned_generator_hash_mismatch')
    boundary = '// ---------- Derived per-patient metrics + signal engine ----------'
    text = source.decode()
    if text.count(boundary) != 1:
        raise ValueError('unexpected generator boundary')
    # Inspect the pinned generator before running. Only its seeded generation and
    # planted-data section execute in a no-I/O VM context; no app/signal code runs.
    prefix = text.split(boundary)[0]
    runner = """const vm=require('node:vm'),fs=require('node:fs');
const input=fs.readFileSync(0,'utf8');
const data=vm.runInNewContext(input+'\\nJSON.stringify({CUTOFF,DOM,LABS,PTS})',Object.create(null),{timeout:5000});
process.stdout.write(data);
"""
    result = subprocess.run(['node', '-e', runner], input=prefix, text=True,
                            capture_output=True, check=True)
    data = json.loads(result.stdout)
    raw = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()
    if hashlib.sha256(raw).hexdigest() != RAW_SHA256:
        raise ValueError('pinned_output_hash_mismatch')
    metadata = {
        'synthetic_only': True, 'repository': 'https://github.com/pzhang724/patient-profile-linkage',
        'imported_at_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'commit': COMMIT, 'generator_path': 'src/cube/c0_data.js', 'source_url': URL,
        'source_sha256': hashlib.sha256(source).hexdigest(),
        'raw_sha256': hashlib.sha256(raw).hexdigest(), 'seed': 189,
        'entrypoint': 'PTS = Array.from({length:60},(_,i)=>makePatient(i)); then plant() IIFE',
        'extraction': 'Execute prefix before Derived per-patient metrics + signal engine in Node VM; serialize CUTOFF, DOM, LABS, PTS. Preserve raw outputs including planted anomalies. Do not execute derived metrics/signals or rewrite ds.eot.',
        'permission': 'Yue explicitly authorized synthetic data reuse for this demo. No source-code reuse license verified; generator source is not retained.',
        'warning': 'This dataset is synthetic. NOT real trial data. NOT a submission-ready dataset.',
        'counts': {'patients': len(data['PTS']), **{k: sum(len(p[k]) for p in data['PTS']) for k in ('ae','cm','ex','tr','lb')}}}
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / 'raw.json').write_bytes(raw)
    (ROOT / 'provenance.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    extract()
