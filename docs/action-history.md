Action history v1 (t_efdcbff1)

Files and integration boundary
  static/action-history.js exports ViewActionHistory in browsers and CommonJS in Node.
  Load static/state-core.js first. No dependencies or external requests.
  static/history-demo.html is a runnable synthetic component exercise. It does NOT
  replace the patient app's legacy chat/history. Registry task t_d0e758a1 owns
  wiring this component to validated dispatch and the atomic renderer bridge.
  This separation avoids overwriting sibling changes in static/view-chat.js/app.py.

API
  const history = ViewActionHistory.createHistory({initial, commit});
  const unmount = ViewActionHistory.mountHistory(container, history);

  initial: complete core-compatible {analysis,display} state captured at session
    start, detached/frozen. Reset always uses this baseline, even after all Undos.
  commit(next, {operation, previous}): trusted async bridge, operation is execute,
    undo, or reset. Default is an in-memory no-op for pure tests. MUST atomically
    apply/evaluate/render next, or restore previous itself before rejecting.
    History cannot roll back arbitrary external side effects or partial DOM writes.
    It publishes state and appends/removes entries only after commit resolves.
    Do not dispatch or await another history transition inside commit (busy gate).

  await history.execute({action:{tool,args}, diff, record_ids:[], linked_record_ids:[]})
    Apply through core.applyDiff; validate JSON metadata and diff before commit.
    Return the immutable history entry on success. Include source IDs returned by
    the tool exactly (do not normalize or append presentation labels to them).
    The two ID arrays default to [] when absent; provided values must be unique
    nonempty strings. Overlap between primary and linked lists is preserved.
    Include {} diff for reads/no-op tools: they still receive an undoable entry.
    Arguments must be a plain JSON object; executable metadata/accessors rejected.
    Unknown tool names are NOT validated here: the registry owns registration,
    argument/source-membership validation, permission and analysis confirmation.
    Only call execute for an authorized executed action, not refused/proposed work.

  history.snapshot() -> frozen {state, entries, busy}
  history.subscribe(fn) -> unsubscribe; immediately receives current snapshot.
    Observers cannot invalidate an accepted transition; observer exceptions are
    isolated. Snapshot changes on busy start and completion/failure.
  await history.undo(optionalEntryId)
    core.revertDiff on latest entry, then remove it after successful commit.
    Explicit IDs must match the latest action. No selective replay or redo.
    A read-only action has a no-op Undo, preserving chronological semantics.
  await history.reset()
    core.resetState(current,initial), then clears ALL entries, including query
    entries. No stale reset/action row is appended. Buttons remain in the panel.
  history.replaceSession(newInitial)
    Synchronous, clears old history and baseline, captures an already-loaded new
    dataset/session. Does not commit to renderer. IDs remain monotonic to avoid
    aliasing old UI references. Rejected while a transition is in flight.
  unmount() removes only this component and its subscription.

Entry schema (all data detached and deeply frozen)
  {schema_version:1, id:'action-N', action:{tool,args}, diff,
   record_ids:[], linked_record_ids:[],
   controls:{undo:{entry_id:'action-N'}, reset:{target:'initial'}}}
  IDs are unique within one controller; failed attempts can leave sequence gaps.
  No timestamps, guessed counts or fabricated source results are generated.
  Each entry exposes raw JSON including action/diff/source IDs plus Undo/Reset
  controls; older Undo controls are disabled until newer entries are undone.
  Rendering uses textContent, never tool-supplied HTML or eval. Full-domain diffs
  can be large; entries are collapsed by default but never silently truncated.

Required registry/renderer integration
  1. Mount in the existing panel; remove the legacy duplicate history owner.
  2. Capture complete initial state after renderer readiness. Convert flat legacy
     snapshots into the core schema; never conflate focus with analysis population.
  3. Resolve/validate/confirm the tool first. Compute core.stateDiff(current,next).
     Pass its executed action and exact source IDs to execute. Do not apply next
     separately and then record: history owns apply/commit/publication.
  4. Serialize renderer controls, dataset replacement and asynchronous requests
     with history transitions. Concurrent execute/undo/reset fails busy, not queued.
     A request planned against old state must be invalidated or fail core conflict.
     {} no-op requests still need a dataset/version guard in the registry.
  5. For manual controls, record their transitions or start a fresh session from
     the loaded state; do not let renderer drift silently from snapshot().state.
  6. Analysis diffs require explicit user confirmation upstream. This controller
     does not itself authorize changes and must not be exposed as a model tool.
  7. A real development task creation is an external side effect, NOT undone by
     resetting view state. UI states this limitation. Preserve the task's returned
     ID in validated action metadata; do not claim it was deleted by Undo.

Verification
  node --test action-history.test.cjs state-core.test.cjs state-core.integration.test.cjs
  .venv/bin/python -m unittest test_action_history -v
  (Python venv with playwright==1.56.0, Chromium installed.)
  python3.11 -m venv .venv
  .venv/bin/python -m pip install playwright==1.56.0
  .venv/bin/python -m playwright install chromium  # only if browser is missing

Manual exercise (loopback only, no deployment)
  .venv/bin/python -m http.server 8765 --bind 127.0.0.1 --directory static
  Open http://127.0.0.1:8765/history-demo.html
  Execute combined action, inspect JSON, execute query, Undo twice; execute again
  and Reset. Current-state display must equal the original, history must be empty.

Evidence: evidence-history-red.log (module absent before implementation),
  evidence-history-green.log (focused Node suite), evidence-history-browser.log
  (real Chromium on loopback synthetic page). No screenshots/private image egress.
  These are component checks, not patient renderer/full app integration or an
  independent review; downstream registry and acceptance cards own those checks.
