# Patient profile lattice

A local, synthetic-only prototype for reading oncology patient timelines three ways from one record model: a 2D lane chart, a patient x time x visual layer lattice, and a GPU 3D study.

The question it explores is a reading question, not an analysis question: with one patient roster on screen, can you move between overview, mid and close zoom, and between four projections of the same records, without the display quietly changing what is counted?

This is a feasibility spike. It is not clinical evidence, it is not a regulatory or SDTM conformance tool, and it is not a product.

## Run it

Python 3.9 or newer. The viewer itself uses only the standard library.

```sh
python3 app.py                                  # default 100-patient synthetic snapshot
python3 app.py --cohort keynote189              # KEYNOTE-189-style synthetic fixture (60 patients)
python3 app.py --port 8800 --cohort keynote189  # pick a port
```

Then open one of:

| URL | View |
|---|---|
| `http://127.0.0.1:8765/` | 2D lane view, one line per patient, zoom dependent detail |
| `http://127.0.0.1:8765/lattice` | Patient x time x visual layer lattice, four free-rotating projections |
| `http://127.0.0.1:8765/3d` | GPU prototype of the same records and the same pinned engine |

The server binds loopback only. There are no uploads, no outbound service calls from the viewer, no chat interface, no agent panel and no telemetry.

Two read-only integrity checks:

```sh
python3 app.py --verify-data     # pinned file hashes, normalized spec, synthetic-only flag, SUPPAE parent links
python3 data/validate.py         # 18 golden contract checks
```

Both were run against this release: `--verify-data` printed PASS, and `data/validate.py` ran 18 tests with all OK.

## The two synthetic cohorts

| Cohort | Source | Size | Status |
|---|---|---|---|
| `--cohort 100` (default) | `data/`, hand-authored spike snapshot `synthetic-spike-v1`, seed 82087039 | 100 patients, 298 qualifying AE source records | Invented feasibility records. No real patient or trial data. |
| `--cohort keynote189` | `fixtures/keynote189-synthetic/`, imported generated output | 60 patients, 260 AE / 80 CM / 1771 EX / 391 TR / 4962 LB source rows | Synthetic. Not real trial data. Not a submission-ready dataset. |

The fixture is pinned by hash. `fixtures/keynote189-synthetic/provenance.json` records the upstream URL, commit, generator entry point, import time, both SHA-256 values, the vendored generator hash and the recomputed row counts. `extract_scenario.py` re-verifies the pinned generator hash before regenerating and re-verifies the raw output hash before writing (it needs Node; the viewer does not).

## Acknowledgement: the reference repository and the KN189-style synthetic data

The lattice prototype takes selected interaction ideas from **[pzhang724/patient-profile-linkage](https://github.com/pzhang724/patient-profile-linkage)** at pinned commit `be3744cd7768373552e87201ea0efe90578c094f` ("Add patient lanes and patient x domain x time event cube on synthetic KN189-style data", 2026-10-31). Credit for that design direction belongs to its author.

What travelled across the boundary, and what did not:

- **Synthetic data only.** The KN189-style fixture in `fixtures/keynote189-synthetic/raw.json` is that repository's own generated, seeded output (seed 189, 60 patients), copied with the project owner's explicit data-only authorization. It is synthetic, it is not real KEYNOTE-189 data, and it is not a submission-ready dataset.
- **No source code, no generator, no agent panel, no signal rules.** Nothing in this repository is copied from that project's source. The generator, the Claude-backed agent panel, the rule-based signal engine and the derived-metrics code are all out of scope and are not retained here. The local interaction model, the projections, the sentinel tiers and the analysis safeguards are an independent implementation written against requirements and observed behavior.
- **No license was present upstream at the pinned commit.** The tree contains no `LICENSE`, `COPYING` or `NOTICE` file and the repository API reported `license: null` when inspected. That is a data-only courtesy arrangement for a demonstration fixture, not a source-code license, and nothing here should be read as granting rights in that project's code.

The full comparison, the adopted and rejected concepts and the licensing reasoning are in `README-COMPARISON-PROVENANCE.md`, `AUDIT-EXTERNAL-REPO.md`, `AUDIT-SOURCES.md` and `COMPARISON-LATTICE.txt`.

## Deliberate boundaries

These are rejections, not missing features pending a sprint:

- No agent panel and no third-party model calls from the viewer.
- No signal inference or alert rules. Sentinel markers are display annotations, not clinical judgments.
- No event-based alignment that drops patients without an anchor event, because it changes the displayed population.
- No confirmed-response redefinition, and no arm-percentage comparison rows. The cohort view is a display summary, not an endpoint.
- Filters marked "review" change the patient set; counts under "analysis" are kept separate and are not silently rewritten by a view change.

## Test status

Verified locally on 1 November 2026 with Python 3.9.6, Playwright 1.56.0 and its bundled Chromium 141.0.7390.37 on macOS:

- **Engine and contract modules pass.** `test_app` (5), `test_cohort` (4), `test_addresses` (3), `test_sentinel` (3), `test_grammar` (2): 17 tests, all OK. `data/validate.py`: 18 tests, all OK.
- **Browser modules pass.** `test_browser` (3), `test_3d` (3), `test_zoom` (6), `test_focus` (1), `test_feedback` (4), `test_sentinel_browser` (4), `test_grammar_browser` (2): 23 tests, all OK. Aggregate `./run_checks.sh`: `Ran 40 tests in 97.475s`, `OK`, exit 0. No skipped tests or failing exceptions.
- The earlier red suite has been adjudicated per test in [BROWSER-REGRESSION-RECONCILIATION.md](BROWSER-REGRESSION-RECONCILIATION.md). Expectations now enforce the AE/CM overview visibility rule, state-specific endpoints, collision-aware selection, click-focus timing and pixel-capped geometry. A real short-interval focus bug that made Zoom in zoom out was fixed in both 2D and 3D, with red/green regression tests. Analytical counts and pinned data are unchanged.
- [TEST-RESULTS.txt](TEST-RESULTS.txt) records exact commands, exit codes and Ran/OK lines for each module and the aggregate, plus the 18-test validator and `--verify-data` PASS. This is local implementer verification on the pinned Playwright 1.56 / Chromium 141 environment, not independent review. Frame-timing figures are tagged with the browser that produced them and are not compared across browser versions.

What was verified interactively for this release, in Chromium, against a live server: all three routes return 200 with no page errors; the default cohort reports 100 qualifying patients and 298 qualifying AE source records; the KN189 cohort reports 60 qualifying patients and 260 qualifying AE source records; the lattice renderer reports `ready: true`, 291 marks, 3 draw calls and 60 ordered patients, and all four projection controls are present and operable.

To run the browser modules yourself you need Playwright and Chromium:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-test.txt
python3 -m playwright install chromium
./run_checks.sh
```

## Files

| Path | Purpose |
|---|---|
| `app.py` | Loopback HTTP server, engine, routes, review/analysis endpoints |
| `cohort.py` | Cohort scaling over the pinned snapshot |
| `display.py` | Display config, zoom tiers, interval end states |
| `scenario_adapter.py` | Adapter for the imported KN189-style fixture |
| `extract_scenario.py` | Hash-verified fixture regeneration (needs Node) |
| `static/` | Served UI: HTML, CSS, lane app, grammar, prebuilt 3D bundle |
| `static/lattice.js`, `lattice.js`, `lattice-model.mjs` | Lattice projection model and renderer |
| `renderer3d.js` | 3D renderer source, bundled into `static/renderer3d.js` |
| `data/` | Pinned generic synthetic snapshot, contract, schemas, golden results, validator |
| `fixtures/keynote189-synthetic/` | Imported synthetic fixture, provenance and row counts |
| `test_*.py` | Engine and browser checks |
| `AUDIT-*.md`, `README-COMPARISON-PROVENANCE.md`, `COMPARISON-LATTICE.txt` | External audit, provenance, reuse boundary, comparison |

Internal handoff notes, captured local evidence directories, patch bundles and scratch backups from the build are not part of this release.

## Licensing

No license file is included, and no license is granted by this repository. If you want to reuse the code, ask first. The KN189-style fixture is generated output from an upstream repository that carried no license at the pinned commit; it is here under a data-only authorization for demonstration and carries no redistribution rights of its own.

Nothing in this repository is medical advice, a validated analysis, or a substitute for a statistician and a qualified reviewer working from real source data.
