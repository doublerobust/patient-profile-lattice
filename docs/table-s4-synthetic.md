# Table S4 vocabulary in a local synthetic derivative

All patients and event records remain synthetic. They are not trial data, not clinical evidence, and not a submission-ready dataset. Counts shown by highlight/query tools describe this fixture only, not source-trial prevalence.

## Source, scope and retrieval

Gandhi L, Rodríguez-Abreu D, Gadgeel S, et al. *Pembrolizumab plus Chemotherapy in Metastatic Non–Small-Cell Lung Cancer.* N Engl J Med 2018;378:2078–92. DOI: 10.1056/NEJMoa1801005.

Supplementary Appendix, Table S4, “Adverse Events in the As-Treated Population of Patients Who Received Carboplatin,” printed pages 25–28.

- Supplied URL: https://www.nejm.org/doi/suppl/10.1056/NEJMoa1801005/suppl_file/nejmoa1801005_appendix.pdf
- Retrieved copy: https://web.archive.org/web/20220108182644if_/https://www.nejm.org/doi/suppl/10.1056/NEJMoa1801005/suppl_file/nejmoa1801005_appendix.pdf
- This is the archived 2022-01-08 appendix. Live NEJM retrieval was Cloudflare-blocked; a current revision has not been verified.
- Download independently re-fetched during integration: 827,631 bytes, 35 pages, SHA-256 `00a40a9743009677eda784fa52386f9efd4d7d83baed9afb3aceb0a68de44469`.
- The evidence brief's PDF hash agrees with the retrieved bytes. The parent task's summary metadata had a different hash; it is not used as a pin.
- Table population: carboplatin as-treated subgroup, pembrolizumab–pemetrexed–carboplatin N=294 vs placebo–pemetrexed–carboplatin N=145, not the whole trial.
- Source AE window: during allocated treatment or within 30 days thereafter (90 for serious events), regardless of investigator attribution; crossover excluded. These clinical windows are not imposed on the synthetic records.

## Literal vocabulary versus local mapping

The evidence handoff explicitly supplied these 40 literal strings, in source order:

Any-cause rows (28): Nausea; Anemia; Fatigue; Constipation; Diarrhea; Neutropenia; Decreased appetite; Vomiting; Cough; Rash; Edema peripheral; Dyspnea; Thrombocytopenia; Lacrimation increased; Asthenia; Pyrexia; Headache; Back pain; Dizziness; Blood creatinine increased; Alanine aminotransferase increased; Dysgeusia; Pruritus; Hypokalemia; Pneumonia; Stomatitis; Upper respiratory tract infection; Urinary tract infection.

Immune-related events-of-interest rows (12): Hypothyroidism; Hyperthyroidism; Pneumonitis; Colitis; Infusion reactions; Nephritis; Severe skin reactions; Hepatitis; Pancreatitis; Hypophysitis; Myositis; Adrenal insufficiency.

The source footnote says that related terms are included in addition to the listed specific preferred terms. The 12 events-of-interest rows are therefore treated as event categories including related terms, not as 12 individual MedDRA preferred terms. Summary rows such as “Any,” discontinuations and events leading to death are excluded: they are not vocabulary terms. No unmapped terms are invented.

`populate_ae_table_s4.py::TABLE_S4` is the machine-readable map. Literal strings are from the source; approximate SOC assignments are local display mappings, not supplied by Table S4 and not a validated MedDRA coding exercise. The local `ir` flag identifies the 12 events-of-interest rows, not patient-level immune-related adjudication. Term-level provenance states this distinction for each adapted AE record.

## Assignment: explicitly ours, without incidence weighting

Uniform per-arm term dealing to ensure vocabulary coverage in both arms; arm is used as a balancing key, with no source incidence weights. Patient-level and arm-level patterns remain synthetic.

For each arm separately, cycle the full 40-term source-order deck across that arm's AE row count, starting at index zero. Shuffle the entire finished assignment list, not just the deck, using Python `random.Random(20261102)` with arms processed in sorted order (B, P). Then assign to that arm's existing rows in patient/row order without moving any rows. This removes the repeated deck's positional structure and guarantees all 40 terms in both arms: 4–5 occurrences per term in P (179 rows), 2–3 in B (81 rows). The fixed seed is not selected by a statistical test. Coverage is the demo constraint, not a guarantee against term–arm association generally or a clinically plausible event mix. No source incidence inputs are used.

This replaces the previous global round-robin derivative from `fe42e74` (SHA-256 `4cd25aba56fd5163b99f6fee0ef76796dac53b03cc93b89c55284f3d87b11557`), whose positional assignment left nine terms exclusive to P. Tests compare all non-target fields directly against those previous published bytes.

Only `ae.term`, `ae.soc`, and `ae.ir` change. All 60 synthetic patients, their IDs, order, 260 AE rows, event dates, grades, seriousness flags, other domains and planted anomalies remain unchanged. The renamed terms do not establish causal links to drugs, diagnoses, outcomes or concomitant medication indications. Existing CM text is not rewritten to manufacture consistency. No trial incidence, severity distribution, timing or subject-level events are reproduced.

## Two files, two identities

- `fixtures/keynote189-synthetic/raw.json` remains the imported generated output, byte-for-byte, SHA-256 `4dd5639d3b9799ee6c8b31615659d2433452fd6e077aca1ba8cb7d26064fbb54`.
- `fixtures/keynote189-synthetic/table-s4-synthetic.json` is a LOCAL synthetic derivative, SHA-256 `1931f79eb754cc569d4cb2539fec1d2c3071e6daf18820ccc8f9dee6a251304e`.
- `provenance.json` retains the original import metadata and pins both identities, citation and qualifications. The upstream repository supplied generated synthetic data, not this term assignment. Upstream permission status remains as documented in `DATA.md`; no new license claim is made.
- `--cohort keynote189` now loads the derivative as snapshot `synthetic-keynote189-table-s4-v3`; old reviews are not silently replayed against the changed snapshot. Patient and record IDs are unchanged; only the snapshot version is advanced for the changed fixture identity.
- Each adapted record identifies the derivative file/hash and upstream file/hash. Each AE also carries its original upstream row, derivative row, exact JSON pointer and term provenance. Export/replay retain these local synthetic source details. This is separate from model egress, which excludes source IDs/rows by default.

Reproduce and verify from the repository root:

```sh
.venv/bin/python populate_ae_table_s4.py          # writes only the derivative
.venv/bin/python populate_ae_table_s4.py --check  # read-only regeneration comparison
.venv/bin/python -m unittest test_table_s4_dealing test_table_s4 test_table_s4_browser -v
```

Try “Highlight exact term Lacrimation increased” and approve the displayed scope proposal. Query with `query_data`, scope `current_analysis`, filters `{"term":"Lacrimation increased"}`, and explicit unit `AE records` or `patients`. In this deterministic fixture the term has 7 AE records; that is a synthetic test result, not a trial rate. Local source IDs remain inspectable; no real external provider was used to verify this flow.
