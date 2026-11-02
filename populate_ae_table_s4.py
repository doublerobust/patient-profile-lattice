"""Generate a LOCAL SYNTHETIC derivative; never overwrite the imported raw.json.

Literal terms and approximate display SOC mapping: evidence task t_d2fb3039.
Assignment is ours: unweighted source-order round-robin, independent of arm.
No Table S4 incidence, grade distribution, timing or causality is reproduced.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent / 'fixtures/keynote189-synthetic'
UPSTREAM_SHA256 = '4dd5639d3b9799ee6c8b31615659d2433452fd6e077aca1ba8cb7d26064fbb54'
DERIVATIVE_SHA256 = '4cd25aba56fd5163b99f6fee0ef76796dac53b03cc93b89c55284f3d87b11557'
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


def populate(raw):
    result = copy.deepcopy(raw)
    index = 0
    for patient in result['PTS']:
        for row in patient['ae']:
            row['term'], row['soc'], row['ir'] = TABLE_S4[index % len(TABLE_S4)]
            index += 1
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
    print('40 terms; unweighted assignment; not trial data or trial prevalence')


if __name__ == '__main__':
    main()
