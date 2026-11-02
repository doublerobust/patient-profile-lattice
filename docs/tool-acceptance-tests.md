# Validated tool acceptance tests

Run from the repository root. Node 18+ supplies node:test and structuredClone; no npm install is needed for these unit tests. Verified here with Node v26.12.1 and Python 3.11.15.

    npm test
    npm run test:tools
    python -m unittest test_tool_acceptance test_view_tools test_model_agent -v

Python dependencies use the existing requirements.txt. For full browser regression use requirements-test.txt plus Playwright Chromium:

    python -m pip install -r requirements-test.txt
    python -m playwright install chromium
    python -m unittest discover -v

Use the intended virtual environment's python rather than an unrelated pip. No provider credentials or external model calls are needed. Browser tests use loopback servers and mocked providers.

## Acceptance coverage

Explicit AC-numbered tests are in tool-registry.acceptance.test.cjs:

1. Registered names only and valid schemas: invalid-call subtests, non-JSON/accessor rejection, and the all-registered-tools execution test.
2. Analysis proposals include before/after consequences, do not commit until separate matching confirmation, and reject model confirmation, wrong/missing tokens, cancellation and dataset drift. test_tool_acceptance.py checks actual computed consequences.
3. Unsupported alignment names the requested anchor, denominator and missing-anchor policy without state/history changes. Python checks the actual resolver on both cohorts and preserves source records.
4. Ambiguous, unsupported and clinically inferential structured calls reject before resolver/commit; explicit refusal and clarification responses leave state/history unchanged. Python repeats this against the actual adapter.
5. Functions/accessors/cycles are rejected without invoking code. All tool paths run in a VM with document/window/element access trapped, eval/Function/timers trapped, and string code generation disabled. Code-like model text remains inert task/question data. Trusted module/test source is compiled by the harness, never model text. Native clone results are re-homed into the VM realm to avoid host-prototype false failures.
6. Both counting units return contributing IDs and preserve state; mismatched resolver counts/units/duplicate IDs reject. Python derives patient counts from actual contributing AE source records.
7. Development requests create uniquely identified local session ledger entries marked proposed/result_created:false. No external ticket or implementation is claimed; Undo/Reset retain tasks.
8. Each executed tool (including read-only tools) adds an entry with replayable validated diff, source IDs and Undo/Reset controls. Failed commits add nothing. Proposals/clarifications/refusals are not executed actions.
9. Reverse Undo restores each complete analysis/display snapshot, including alignment, camera and combined population/selection changes. Existing core/history tests cover further atomicity and reset cases.

## Execution evidence

- npm run test:tools: exit 0; 54 passed, zero failed/skipped (evidence-acceptance-node.log).
- npm test: exit 0; 54 passed, zero failed/skipped (evidence-acceptance-all-node.log).
- python -m unittest test_tool_acceptance test_view_tools test_model_agent -v: exit 0; 14 passed (evidence-acceptance-python.log).
- python -m unittest discover -v: exit 0; 81 passed in 111.209s, including existing browser regressions (evidence-acceptance-python-full.log).
- git diff --check: exit 0.
- Initial new Node run: exit 1; 30 passed, one VM cross-realm test-harness error. Fixed the harness, not production validation (evidence-acceptance-first.log).
- A combined final command containing python -c was blocked by command approval before execution; reran the Node/check commands without it, successfully. No approval configuration changed.

These tests do not prove arbitrary model prose classification, all possible DOM APIs or live provider behavior. Synthetic bridge responses are labeled test fixtures, not real cohort results; separate Python tests exercise real source resolution. No new production behavior or fixture data was changed by the acceptance-test commit. No independent review is claimed.

## Integration handoff

Worktree: /Users/openclaw/research/patient-profile-viz/work-base/.worktrees/t_0e8d45f4
Branch: wt/t_0e8d45f4

Baseline d509780 imports parent core/history/adapter/UI prerequisites. Commit 29934dd imports the parent's verified but uncommitted registry implementation from t_d0e758a1, read-only. The subsequent acceptance commit contains only new tests, npm scripts, this documentation and evidence. Integrators who already have the registry should take only that acceptance commit, rather than overwrite shared implementation files. Parent worktrees were not modified.
