KEYNOTE-189-style synthetic demo fixtures

This dataset is synthetic. NOT real trial data. NOT a submission-ready dataset.

Source: https://github.com/pzhang724/patient-profile-linkage
Pinned commit: be3744cd7768373552e87201ea0efe90578c094f
Imported at (UTC): 2026-10-31T18:38:32Z

Yue explicitly authorized copying generated synthetic data from this public repository for demo fixtures only. No LICENSE file was present in the inspected commit; this is not permission to reuse external source code. No generator, application, agent-panel or signal-inference source code is retained here.

raw.json preserves generated CUTOFF, DOM, LABS and PTS, including original patient IDs, array order, fields and planted anomalies. It is generated output, not a committed upstream JSON dataset. The independently written ../../extract_scenario.py verifies the pinned source hash before executing the seed-189 generation/planted-data prefix in memory, stopping before derived metrics and the signal engine; it verifies the raw-output hash before writing. provenance.json records the full URL, both hashes, entrypoint, extraction boundary, import timestamp, warning and recomputed counts. The source structure and outputs are unchanged by the directory relocation.

Synthetic counts: 60 patients; 260 AE, 80 CM, 1771 EX, 391 TR and 4962 LB rows. These are not published trial results. No tuning to published endpoints or anomaly cleanup was performed.

The independent ../../scenario_adapter.py uses the existing clinical engine. TR is mapped to RS; LB is preserved but not rendered. Display dates use fictional 2025-01-01 plus enrollment offset plus source day. AE toxicity grade is not converted to AESEV. Raw provenance accompanies each adapted record, including exact original rows and JSON pointers. See ../../README.md for limitations.

The default generic synthetic cohort is unchanged. `--cohort keynote189` loads `table-s4-synthetic.json`, a separately pinned LOCAL synthetic derivative; it does not load or modify the original `raw.json`.

The derivative replaces only AE term, approximate display SOC and the local event-of-interest flag, using the 40 mapped literal terms from Table S4 of the archived 2022-01-08 NEJM appendix (DOI 10.1056/NEJMoa1801005). Table S4 describes the carboplatin as-treated subgroup (N=294 vs 145), not the whole trial. Its 12 immune-related rows are event categories including related terms, not single preferred terms. Term assignment is our unweighted source-order round-robin across existing AE rows, independent of arm; no incidence weighting or source-trial rates are reproduced. SOC and flag mappings are ours, not source coding. All dates, grades, seriousness flags, IDs, row counts, other domains and planted anomalies are untouched. See ../../docs/table-s4-synthetic.md for the exact vocabulary, citation, qualifications and both hashes.

Run `python populate_ae_table_s4.py --check` from the repository root to verify the derivative. The adapter pins both files and carries the derivative row, original upstream AE row, JSON pointer, both file/hash identities and term provenance into local inspection/export/replay. Deterministic modified bytes are not the original upstream data.
