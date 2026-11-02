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

The server binds loopback only. The "Ask about this view" panel starts disconnected, with explicitly labeled local rule/parser commands. An optional user-configured model connection sends requests through the loopback adapter only after endpoint/model testing and explicit egress consent; it is not enabled by default. Credentials are session-only. See [the tool registry contract](docs/tool-registry.md) for validation, analysis confirmation, source IDs, Undo/Reset and limitations. Touch devices get a shared pointer controller: one-finger rotate (or pan by toggle), two-finger translate, centred pinch zoom, with desktop drag conventions retained.

### Optional model-driven panel (local, not deployed)

For the model adapter, install the pinned JSON-schema dependency in a virtualenv
(the test requirements also install it):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install jsonschema==4.25.1
.venv/bin/python app.py --cohort keynote189
```

Open `http://127.0.0.1:8765/lattice`, expand **Ask about this view**, then the model
configuration. Enter the complete OpenAI-compatible `https://…/chat/completions`
URL (not just a base URL), exact model ID and session credential. Test the
connection and acknowledge the displayed endpoint/model/dataset egress dialog.
Only a successful test changes the label to **Model-driven agent**. Local parser
commands remain explicitly separate. External endpoints must resolve exclusively
to public addresses and use HTTPS port 443; redirects and URL credentials/query
parameters are refused. No external provider was used in verification.

Model prompts leave this machine after consent. Default tool follow-ups send
aggregate context, not source IDs or rows; text you type can itself contain
identifiers. Record-level results require the separate per-request egress control
and confirmation. Credentials stay in session memory, are cleared from the input
before connection testing, and must not be saved in review/export/history files.
Disconnect clears the configured connection.

Try `Sort descending; show AE and EX at tier 2`, or request alignment to first
recorded PR on the KN189 fixture. Patient/event selections use a separate one-shot
scope approval; see [supported wording](docs/tool-registry.md#model-display-scope-approval).
Analysis-population proposals have their own consequence preview and confirmation.
Use in-panel Undo/Reset to reverse executed actions. Randomization and
anchor-relative analytical windows remain unsupported, not approximated.

For a development-only loopback model, pass an exact endpoint allowlist at startup,
for example `--agent-dev-endpoint http://127.0.0.1:9000/v1/chat/completions`, and
configure that identical URL in the panel. This does not start a model server.
Automated tests start their own scripted local endpoint and use no external
credentials. See [capability audit](docs/lattice-agent-capabilities.md) and
[local-mock acceptance](docs/model-agent-e2e.md).

Two integrity checks (the validator refreshes its local verification report):

```sh
python3 app.py --verify-data     # pinned file hashes, normalized spec, synthetic-only flag, SUPPAE parent links
python3 data/validate.py         # 18 golden contract checks
```

Both were run against this release: `--verify-data` printed PASS, and `data/validate.py` ran 18 tests with all OK.

## The two synthetic cohorts

| Cohort | Source | Size | Status |
|---|---|---|---|
| `--cohort 100` (default) | `data/`, hand-authored spike snapshot `synthetic-spike-v1`, seed 82087039 | 100 patients, 298 qualifying AE source records | Invented feasibility records. No real patient or trial data. |
| `--cohort keynote189` | `fixtures/keynote189-synthetic/table-s4-synthetic.json`, local derivative of imported generated output | 60 patients, 260 AE / 80 CM / 1771 EX / 391 TR / 4962 LB source rows | Synthetic. Not real trial data. Not a submission-ready dataset. |

Both fixture files are pinned by hash. `fixtures/keynote189-synthetic/provenance.json` retains the upstream URL, commit, generator entry point, import time, source/raw hashes and row counts, plus a separately identified local derivative. No generator source is vendored. `extract_scenario.py` regenerates only the unchanged upstream `raw.json` (needs Node). `populate_ae_table_s4.py --check` verifies the local derivative without writing.

The derivative uses 40 literal AE terms from Table S4 of the archived 2022-01-08 NEJM appendix (DOI 10.1056/NEJMoa1801005), carboplatin as-treated subgroup N=294 vs 145, not the whole trial. The 12 immune-related rows are event categories including related terms, not single preferred terms. Assignment is our unweighted round-robin across existing synthetic AE rows, independent of arm; approximate SOC and `ir` mappings are also ours. No incidence weighting, trial prevalence, severity distribution, causality or actual patient events are reproduced. Imported `raw.json` remains byte-for-byte unchanged. See [exact vocabulary, source citation, mapping and hashes](docs/table-s4-synthetic.md).

## Acknowledgement: the reference repository and the KN189-style synthetic data

The lattice prototype takes selected interaction ideas from **[pzhang724/patient-profile-linkage](https://github.com/pzhang724/patient-profile-linkage)** at pinned commit `be3744cd7768373552e87201ea0efe90578c094f` ("Add patient lanes and patient x domain x time event cube on synthetic KN189-style data", 2026-10-31). Credit for that design direction belongs to its author.

What travelled across the boundary, and what did not:

- **Synthetic data only.** The KN189-style fixture in `fixtures/keynote189-synthetic/raw.json` is that repository's own generated, seeded output (seed 189, 60 patients), copied with the project owner's explicit data-only authorization. It is synthetic, it is not real KEYNOTE-189 data, and it is not a submission-ready dataset.
- **No source code, no generator, no agent panel, no signal rules.** Nothing in this repository is copied from that project's source. The generator, the Claude-backed agent panel, the rule-based signal engine and the derived-metrics code are all out of scope and are not retained here. The local interaction model, the projections, the sentinel tiers and the analysis safeguards are an independent implementation written against requirements and observed behavior.
- **No license was present upstream at the pinned commit.** The tree contains no `LICENSE`, `COPYING` or `NOTICE` file and the repository API reported `license: null` when inspected. That is a data-only courtesy arrangement for a demonstration fixture, not a source-code license, and nothing here should be read as granting rights in that project's code.

The full comparison, the adopted and rejected concepts and the licensing reasoning are in `README-COMPARISON-PROVENANCE.md`, `AUDIT-EXTERNAL-REPO.md`, `AUDIT-SOURCES.md` and `COMPARISON-LATTICE.txt`.

## Deliberate boundaries

These are rejections, not missing features pending a sprint:

- No automatic model egress. Optional model calls require explicit configuration and consent; local parser commands do not call a model.
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

No license file is included and no license is granted for this repository's own source code. If you want to reuse it, ask first.

That statement covers our code only. Bundled third-party components keep their own terms and are unaffected by it: three.js is MIT, GSAP ships under its own standard license, and both are bundled into `static/`. See `THIRD-PARTY.md`.

The KN189-style fixture under `fixtures/keynote189-synthetic/` is generated output from an upstream repository that carried no license at the pinned commit. It is here under a data-use authorization for demonstration only, carries no redistribution rights of its own, and is not covered by anything stated about this project's code. See `DATA.md` and `NOTICE.md`.

Nothing in this repository is medical advice, a validated analysis, or a substitute for a statistician and a qualified reviewer working from real source data.
