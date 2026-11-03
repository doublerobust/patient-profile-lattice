# Per-arm Table S4 derivative verification

Base: `fe42e74`. Branch: `fix/s4-per-arm-dealing`. Task: `t_c3d7e0bf`.

Uniform per-arm term dealing to ensure vocabulary coverage in both arms; arm is used as a balancing key, with no source incidence weights. Patient-level and arm-level patterns remain synthetic.

## Construction and scope

Restart the unchanged 40-term deck for each arm. Shuffle the entire completed assignment list with a local `random.Random(20261102)`, processing arms in sorted order (B, P); then assign to existing rows without moving rows. This seed was fixed before generation and was not searched or changed. There is no significance threshold or seed-selection loop.

Actual output: P has 179 AE rows, all 40 terms, 4–5 rows per term; B has 81 AE rows, all 40 terms, 2–3 rows per term. Zero term exclusivity is an asserted construction property for this fixture, not a claim about a fair arm-blind shuffle. The shuffle removes the repeated-deck positional pattern; this is not a general guarantee against term–arm association.

The generator's input API, three-field term/SOC/boolean map, data reads, and called functions are inspected by regression tests to exclude source-incidence inputs. A minimal structural input (arm and empty AE row slots) produces the same assignments as the complete upstream input. No trial-incidence fields or source tables are read.

Vocabulary, SOC mapping and `ir` mapping are unchanged. Direct comparison against the hash-pinned derivative in `fe42e74`, after removing only AE term/SOC/ir, proves equality of all other fields, including dates, grades, seriousness, IDs, order, row counts, other domains and anomalies. Upstream bytes are unchanged. Adapter snapshot identity advances from `synthetic-keynote189-table-s4-v2` to `synthetic-keynote189-table-s4-v3` for replay safety; patient and record IDs are unchanged.

## Hash pair

- Unchanged upstream `fixtures/keynote189-synthetic/raw.json`: `4dd5639d3b9799ee6c8b31615659d2433452fd6e077aca1ba8cb7d26064fbb54`
- New local derivative `fixtures/keynote189-synthetic/table-s4-synthetic.json`: `1931f79eb754cc569d4cb2539fec1d2c3071e6daf18820ccc8f9dee6a251304e`
- Previous derivative: `4cd25aba56fd5163b99f6fee0ef76796dac53b03cc93b89c55284f3d87b11557`

Both current hashes are pinned in `provenance.json` and the generator. Prior `evidence-s4-*` files are historical evidence for the previous integration, not fresh verification of this derivative.

## Executed checks

Environment: Python 3.11.15, Playwright 1.56.0 with task-local Chromium build 1194. No application CSP changes. Setup commands `uv venv .venv --python 3.11`, `uv pip install --python .venv/bin/python -r requirements-test.txt`, `npm ci`, and `.venv/bin/python -m playwright install chromium` all exited 0. Browser installation used `PLAYWRIGHT_BROWSERS_PATH="$HERMES_KANBAN_WORKSPACE/browsers"`; use that environment for browser reruns in this workspace.

| Exact command | Result | Exit |
| --- | --- | --- |
| `python -m unittest test_table_s4_dealing -v` before fix | 6 tests: 4 failures, 1 error, 1 pass (expected RED) | 1 |
| `.venv/bin/python populate_ae_table_s4.py` | derivative written; both hash checks PASS | 0 |
| `.venv/bin/python -m unittest test_table_s4_dealing test_table_s4 test_table_s4_browser -v` initial | 12 passed; browser setup errored because Chromium was absent | 1 |
| `.venv/bin/python -m unittest discover -v` after browser installation | 122 tests OK, 249.424s | 0 |
| `.venv/bin/python -m unittest test_table_s4_dealing test_table_s4 test_table_s4_browser -v` final | 13 tests OK, 5.479s | 0 |
| `npm test` | 58 passed, 0 failed | 0 |
| `node --test *.test.mjs` | 2 passed, 0 failed | 0 |
| `npm run build` | build succeeded; tracked bundles unchanged | 0 |
| `.venv/bin/python data/validate.py` | 18 tests OK | 0 |
| `.venv/bin/python populate_ae_table_s4.py --check` | byte-identical regeneration, both pins PASS | 0 |
| `.venv/bin/python app.py --verify-data` | PASS | 0 |
| `.venv/bin/python app.py --cohort keynote189 --verify-data` | PASS | 0 |
| `git diff --check` | clean | 0 |
| `git diff --exit-code fe42e74 -- fixtures/keynote189-synthetic/raw.json` | no differences | 0 |
| `shasum -a 256 fixtures/keynote189-synthetic/raw.json fixtures/keynote189-synthetic/table-s4-synthetic.json` | hash pair above | 0 |

The existing Chromium test exercised highlight/query and saved/downloaded/replayed source-bearing packages against a local scripted model endpoint; it checked credential exclusion and an unconfigured endpoint after reload. `Lacrimation increased` still has 7 synthetic AE records, not a trial rate. The six new construction guards include same-seed byte identity, per-arm coverage and uniform dealing, full-assignment shuffle inspection (81 and 179 entries, not a 40-entry deck), input inspection, preservation against the previous derivative, and manifest wording/seed.

Logs are retained with the task in `evidence-dealing-*.log` and its evidence archive. Validator-generated changes to `data/verification.json` and `data/verification.txt` were restored after recording test output to keep this patch scoped.

## Limits and review

No merge, deployment, live-service changes, quarantine changes, CSP edits, source-term edits, or workflow/token-scope expansion. No real external model provider, public provider TLS handshake, or physical iPad Safari test. Hosted CI is not claimed. Independent review is still required. Source citation/retrieval qualifications and pending upstream permission in `DATA.md` are unchanged; this update does not re-retrieve or reinterpret the source appendix.
