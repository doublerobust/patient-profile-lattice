"""Generate a LOCAL SYNTHETIC derivative; never overwrite the imported raw.json.

Literal terms and approximate display SOC mapping: evidence task t_d2fb3039.
Uniform per-arm term dealing to ensure vocabulary coverage in both arms; arm is used as a balancing key, with no source incidence weights. Patient-level and arm-level patterns remain synthetic.
No Table S4 incidence, grade distribution, timing or causality is reproduced.
"""
import argparse
import copy
import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent / 'fixtures/keynote189-synthetic'
UPSTREAM_SHA256 = '4dd5639d3b9799ee6c8b31615659d2433452fd6e077aca1ba8cb7d26064fbb54'
DERIVATIVE_SHA256 = '1931f79eb754cc569d4cb2539fec1d2c3071e6daf18820ccc8f9dee6a251304e'
# Literal term, LOCAL approximate SOC, LOCAL event-of-interest flag.
TABLE_S4 = [
    ('Nausea', 'Gastrointestinal disorders', False),
    ('Anemia', 'Blood and lymphatic system disorders', False),
    ('Fatigue', 'General disorders and administration site conditions', False),
    ('Constipation', 'Gastrointestinal disorders', False),
    ('Diarrhea', 'Gastrointestinal disorders', False),
    ('Neutropenia', 'Blood and lymphatic system disorders', False),
    ('Decreased appetite', 'Metabolism and nutrition disorders', False),
    ('Vomiting', 'Gastrointestinal disorders', False),
    ('Cough', 'Respiratory, thoracic and mediastinal disorders', False),
    ('Rash', 'Skin and subcutaneous tissue disorders', False),
    ('Edema peripheral', 'General disorders and administration site conditions', False),
    ('Dyspnea', 'Respiratory, thoracic and mediastinal disorders', False),
    ('Thrombocytopenia', 'Blood and lymphatic system disorders', False),
    ('Lacrimation increased', 'Eye disorders', False),
    ('Asthenia', 'General disorders and administration site conditions', False),
    ('Pyrexia', 'General disorders and administration site conditions', False),
    ('Headache', 'Nervous system disorders', False),
    ('Back pain', 'Musculoskeletal and connective tissue disorders', False),
    ('Dizziness', 'Nervous system disorders', False),
    ('Blood creatinine increased', 'Renal and urinary disorders', False),
    ('Alanine aminotransferase increased', 'Hepatobiliary disorders', False),
    ('Dysgeusia', 'Nervous system disorders', False),
    ('Pruritus', 'Skin and subcutaneous tissue disorders', False),
    ('Hypokalemia', 'Metabolism and nutrition disorders', False),
    ('Pneumonia', 'Infections and infestations', False),
    ('Stomatitis', 'Gastrointestinal disorders', False),
    ('Upper respiratory tract infection', 'Infections and infestations', False),
    ('Urinary tract infection', 'Infections and infestations', False),
    ('Hypothyroidism', 'Endocrine disorders', True),
    ('Hyperthyroidism', 'Endocrine disorders', True),
    ('Pneumonitis', 'Respiratory, thoracic and mediastinal disorders', True),
    ('Colitis', 'Gastrointestinal disorders', True),
    ('Infusion reactions', 'General disorders and administration site conditions', True),
    ('Nephritis', 'Renal and urinary disorders', True),
    ('Severe skin reactions', 'Skin and subcutaneous tissue disorders', True),
    ('Hepatitis', 'Hepatobiliary disorders', True),
    ('Pancreatitis', 'Gastrointestinal disorders', True),
    ('Hypophysitis', 'Endocrine disorders', True),
    ('Myositis', 'Musculoskeletal and connective tissue disorders', True),
    ('Adrenal insufficiency', 'Endocrine disorders', True),
]


def populate(raw, seed=20261102):
    result = copy.deepcopy(raw)
    rows_by_arm = {}
    for patient in result['PTS']:
        rows_by_arm.setdefault(patient['arm'], [])
        rows_by_arm[patient['arm']].extend(patient['ae'])
    rng = random.Random(seed)
    for arm in sorted(rows_by_arm):
        rows = rows_by_arm[arm]
        # Restart the full deck for each arm, then shuffle ALL dealt assignments.
        # Cycling a once-shuffled deck would retain a 40-row positional pattern.
        assignments = [TABLE_S4[index % len(TABLE_S4)] for index in range(len(rows))]
        rng.shuffle(assignments)
        for row, assignment in zip(rows, assignments):
            row['term'], row['soc'], row['ir'] = assignment
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='verify without writing')
    args = parser.parse_args()
    upstream = (ROOT / 'raw.json').read_bytes()
    if hashlib.sha256(upstream).hexdigest() != UPSTREAM_SHA256:
        raise ValueError('upstream_hash_mismatch')
    output = (json.dumps(populate(json.loads(upstream)), ensure_ascii=False, separators=(',', ':')) + '\n').encode()
    sha = hashlib.sha256(output).hexdigest()
    if DERIVATIVE_SHA256 and sha != DERIVATIVE_SHA256:
        raise ValueError('derivative_generation_hash_mismatch')
    target = ROOT / 'table-s4-synthetic.json'
    if args.check:
        if target.read_bytes() != output:
            raise ValueError('derivative_file_mismatch')
    else:
        target.write_bytes(output)
    print('PASS: upstream sha256=' + UPSTREAM_SHA256)
    print('PASS: local synthetic derivative sha256=' + sha)
    print('40 terms; uniform per-arm dealing; not trial data or trial prevalence')


if __name__ == '__main__':
    main()
