# Integration verification (implementer, not independent review)

Starting point: accepted model-agent commit 876835b. Integration branch: feature/model-agent-nejm-s4. Workflow change excluded; no token scope expansion, merge or deployment.

Source/data details and exact hashes: docs/table-s4-synthetic.md. All 40 literal terms mapped; 28 any-cause and 12 immune-related categories including related terms. Local unweighted assignment, not trial rates. Upstream raw.json unchanged. Archived PDF independently downloaded and hashed; parent metadata hash discrepancy resolved against bytes and attached brief.

Commands executed from this isolated worktree, Python 3.11.15, Playwright 1.56.0, jsonschema 4.25.1:

- uv venv .venv --python 3.11; uv pip install --python .venv/bin/python -r requirements-test.txt; npm ci: exit 0.
- .venv/bin/python -m playwright install chromium: exit 0.
- .venv/bin/python -m unittest test_table_s4 -v: initial RED, exit 1 (3 failures, 2 errors); later all 5 passed before additional extraction test.
- .venv/bin/python -m unittest test_table_s4.TableS4Checks.test_term_query_and_highlight_retain_units_and_derivative_provenance -v: label regression RED, exit 1, fixed by synthetic result labels.
- .venv/bin/python -m unittest test_table_s4.TableS4Checks.test_reextract_does_not_erase_derivative_manifest -v: RED exit 1; fixed extraction preserving derivative provenance and import time.
- .venv/bin/python -m unittest test_table_s4 test_table_s4_browser -v: final targeted verification exit 0, 7 tests. Actual browser, local scripted endpoint, approved highlight, both counting units, local IDs, source-bearing save/download/import/replay, credential absence, and empty endpoint/model/key after reload.
- npm run build: exit 0.
- npm test: exit 0, 58 passed, 0 failed/skipped.
- node --test *.test.mjs: exit 0, 2 passed, 0 failed/skipped.
- .venv/bin/python app.py --verify-data: exit 0, PASS.
- .venv/bin/python app.py --cohort keynote189 --verify-data: exit 0, PASS.
- .venv/bin/python data/validate.py: exit 0, 18 tests OK. Generated timing reports restored, not shipped as data changes.
- .venv/bin/python populate_ae_table_s4.py --check: exit 0; upstream and derivative byte/hash pins pass.
- .venv/bin/python extract_scenario.py: exit 0, real pinned upstream fetch and Node extraction; derivative manifest retained; subsequent derivative --check exit 0.
- .venv/bin/python audit_alignment.py: exit 0; evidence-s4-anchor-audit.json includes both fixture hashes.
- git diff --check; git diff --cached --check: exit 0.

IMPORTANT: full regression is NOT green. `.venv/bin/python -m unittest discover -v` ran 115 tests in 265.729s, exit 1 (1 failure, 2 errors). It started before the final test edits. It encountered the previously documented 3D animation wait timeout in test_short_interval_focus_zoom_direction, and the original new browser test's post-reload wait_for_function hit CSP unsafe-eval (also reported by teardown). The new test now waits for visible loaded cohort counts instead of evaluating a polling string; no CSP or application security was weakened. Final targeted rerun passed all 7. A fresh full regression on the final tree remains REQUIRED. The 3D failure was not fixed or rerun in this time budget.

Logs: evidence-s4-full.log, evidence-s4-targeted-verified.log, evidence-s4-node.log, evidence-s4-geometry.log, evidence-s4-build.log, evidence-s4-data.log, evidence-s4-source.log, evidence-s4-extraction-real.log, and red test logs. Historical evidence from 876835b is not evidence of this integration passing.

No external provider, real credential, public model TLS handshake, physical iPad, hosted CI, merge or deployment was tested/performed. Model credentials remain session-only; record-level egress requires separate explicit confirmation. Local export deliberately retains synthetic source data. Upstream dataset permission remains pending as documented in DATA.md.
