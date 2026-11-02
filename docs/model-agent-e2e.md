Local-mock model agent acceptance
=================================

Run from the repository root:
  python -m pip install -r requirements-test.txt
  python -m playwright install chromium
  npm ci
  npm run build
  python -m unittest test_agent_e2e test_alignment_browser test_model_agent -v

CI: .github/workflows/model-agent-tests.yml installs Chromium with Linux dependencies,
runs that acceptance command twice, then the full Python regression, Node tests,
alignment geometry tests, build and reproducible-bundle/diff checks. It needs no
provider account or secrets. The workflow has not been published or run on hosted
CI in this task; the corresponding commands were exercised locally on macOS.

Coverage map
------------
1. test_01: browser -> HTTP adapter -> scripted local OpenAI-compatible endpoint ->
   capability call -> validated set_view -> matching action/diff/source IDs in the
   in-page history. Checks assistant/tool roles and call IDs across turns. An
   attempted analysis_state injection is rejected without changing state/history.
2. test_02: randomization is unsupported, leaves alignment/state unchanged, gives a
   development-task limitation, exposes propose_development_task in the catalogue,
   and records a separately requested local proposal without a fabricated result.
3. test_03: analysis subset previews exact before/after counts; cancel is inert;
   only explicit UI confirmation executes; the model has no confirmation tool.
   Undo restores analysis, display, qualifying IDs and pre-existing highlights.
4. test_04: scripted clarification leaves both domains/history unchanged; model
   attempts to call a confirmation tool are refused.
5. test_05: replacing a nonempty highlight set and Undo restores exact source IDs,
   state, prior history and the visible matched-ID list (not merely an empty state).
6. Existing test_alignment_browser.AlignmentBrowserChecks exercises KN189 through
   the real adapter/local mock. First PR is 23/60; 37 missing-anchor patients remain
   visible with null time in labeled unaligned groups. Source dates, marks and
   analysis are unchanged. It checks axis convention, projection denominators,
   source-ID coverage, geometry Undo, treatment/PD/death and unsupported renderers.
   alignment-model.test.mjs adds pure geometry and missing-group checks.
7. test_07 plus every new test's teardown: ephemeral random credential, actual
   save/download/import replay, localStorage/sessionStorage, DOM/history, replayed
   state, server stderr, browser console and model request bodies. Provider echo is
   redacted. Fixtures are byte-scanned and hashed before/after. Reload disconnects.
   Authorization is checked by the mock in memory, never stored in transcripts.
8. test_08: real adapter HTTP rejection before socket creation for non-HTTPS,
   unallowlisted loopback, URL credentials/query/fragment, nonstandard port, private,
   link-local, IPv6, mapped loopback, mixed public/private and empty DNS results.
   DNS is stubbed; no public lookup/network is necessary. Exact allowlisted loopback
   succeeds. Existing test_model_agent checks public HTTPS validation and consent.
9. test_09/test_09b: before consent there are zero model requests; a gated real
   response keeps the UI disconnected while testing; only success changes status.
   HTTP 401 cannot connect or leak the remote credential echo. Config changes revoke
   connection status. Existing UI tests add stale responses and consent cancellation.

Harness boundaries
------------------
The new endpoint uses server-local queues, fails on unexpected requests, asserts
all scripted replies were consumed, validates path/model/auth/streaming, uses fresh
browser contexts and ephemeral ports, and blocks direct browser provider traffic.
Synchronization uses UI readiness and threading Events, never arbitrary sleeps.
No source fixtures or production implementation files were changed.

Scripts test tool execution and honest UI handling, not arbitrary LLM comprehension:
a scripted clarify_request does not prove a real model always detects ambiguity.
The credential scan proves absence of this run's sentinel on the exercised surfaces,
not absence of every possible secret on every filesystem/process/browser surface.
Source IDs are intentionally visible locally and in supported review packages;
default model egress withholds them. Do not confuse this with prohibiting all local
source evidence. No real provider, real credential, physical iPad, hosted CI,
deployment, publication, or independent approval is claimed.
