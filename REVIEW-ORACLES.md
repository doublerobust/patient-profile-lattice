# PR #1: review-oracle follow-up

Base: `ad8084e748b7b46e09463aa22777acdb64c87137`.
This is a local follow-up for review; no runtime files, clinical fixtures, public branch or live services changed. The earlier TEST-RESULTS.txt describes its earlier run, not this follow-up.

## Frozen renderer counts

`test_3d.test_route_and_same_data` now checks literal counts for the fixed 100-patient fixture at each tier selection:

| Requested tier | Logical display marks |
|---|---:|
| 0 (including overview AE/CM) | 1135 |
| 1 | 1480 |
| 2 | 1577 |

These were inspected at the base commit, not computed by the helper during assertion. The independent submitted-geometry display-ID check remains. Counts refer to logical marks, not extra endpoint triangles.

A controlled in-memory mutation set every mark's tier to zero in `Engine.evaluate`, so both the renderer and its derived expectation consumed the same bad values. The original test passed (exit 0); the strengthened test failed with `1577 != 1135` (exit 1). No mutation was written into application source. This demonstrates the shared-oracle blind spot and the new assertion catching it.

## Authentic historical oracle recovered

The original bytes still exist in task t_a45a091e's `sentinel-viewer.zip`, not just in a reconstructed integration bundle. The ZIP hash and both extracted member hashes were checked against the existing integration provenance. `test-fixtures/baseline-provenance.json` records those hashes and member paths.

The sentinel browser test validates the archived generator hash before loading it, checks the archived measurements hash, and compares every patient's original-generator count, current all-tier count and current tier-0-only count against that frozen record. Historical tier-0 counts do not limit today's overview: AE/CM remain visible. No fake Git ref is introduced and no historical measurement is regenerated from current implementation code.

## Actual verification and limitations

Environment: macOS, Python 3.9.6, requirements-test.txt pinned Playwright 1.56.0, bundled Chromium installed with `python -m playwright install chromium`. Commands below ran in this isolated clone with its own `.venv`.

- `PYTHON=.venv/bin/python ./run_checks.sh test_3d.ThreeChecks.test_route_and_same_data test_sentinel_browser.SentinelBrowserChecks.test_actual_per_line_counts_before_after_and_unchanged_analysis`: **exit 0, two tests passed**. Real Chromium, no test skips.
- `.venv/bin/python app.py --verify-data`: **exit 0, PASS**.
- `git diff --check`: **exit 0**.
- `PYTHON=.venv/bin/python ./run_checks.sh test_3d test_sentinel_browser`: **exit 1, seven tests run with two errors**. Both changed tests passed; the two other 3D tests timed out waiting for animation completion.
- A separate detached worktree of unmodified base `ad8084e` reproduced both timeouts with `PYTHON=/Users/openclaw/research/hermes-specialist-team/workspaces/developer/patient-profile-viz/pr1-review-fixes/.venv/bin/python ../pr1-review-baseline/run_checks.sh test_3d.ThreeChecks.test_interrupt_idle_pick_and_end_semantics test_3d.ThreeChecks.test_short_interval_focus_zoom_direction`: **exit 1, two errors**. These failures are not caused by this test-only patch. Root cause has not been established and no assertion was relaxed to hide them.

The full 40-test suite was not rerun in this follow-up. Do not claim the current environment is fully green. Independent review and deciding how to address the reproduced baseline animation timeouts remain outstanding.

Logs (local evidence directory, supplied in handoff ZIP):
- shared-oracle-mutation-before.log (old test accepts deliberate drift)
- shared-oracle-mutation-after.log (new test rejects drift)
- review-oracles-targeted.log (seven-test run, two timeouts)
- review-baseline-3d.log (unchanged PR head reproduces both timeouts)
- review-oracles-green.log (two modified tests pass)
- review-oracles-data.log

Changed paths: test_3d.py, test_sentinel_browser.py, BROWSER-REGRESSION-RECONCILIATION.md, REVIEW-ORACLES.md, and three test-fixtures files. No approval, merge, deployment or new performance claim.
