State core v1 — t_b42b5216

Module: static/state-core.js (CommonJS export or browser global ViewStateCore).
No dependencies, DOM access, networking, text execution, or hidden mutable store.
Run: node --test state-core.test.cjs state-core.integration.test.cjs

State contract

State is exactly {analysis, display}. createState(state) validates, detaches and
recursively freezes a snapshot. Inputs are never mutated. Consumers own which
snapshot is current. Every transition returns a new deeply frozen snapshot.

analysis exactly matches data/schemas.json analysis_state:
  population: unique [STUDYID, USUBJID] tuples; [] is an empty population.
  ae_predicate: null or {variable:'AESEV', operator:'eq', value:MILD|MODERATE|SEVERE}.
  temporal_window: null or the exact pinned EXSTDTC/AESTDTC 0–30-day rule in
    data/schemas.json. Unsupported temporal semantics are rejected, not inferred.

Display is exactly:
  view: the full data/schemas.json view_state (patient_sort, hidden_lanes,
    focus_patient_keys, display_date_window, selection).
  sort: duration | asc | desc | response | pd | reason.
  tier: 'auto' | '0' | '1' | '2'.
  renderer: 'timeline' | '3d' | 'lattice'.
  camera: null before initialization; timeline {start,end} finite epoch numbers
    in increasing order; spatial {x,y,z,yaw,pitch,distance,span}, finite numbers,
    positive distance/span. Legacy 3d also allows numeric peel. These are native
    chatSnapshot coordinates, NOT the model tool's position/target schema.
  alignment: null for calendar or the resolved alignment.py result described below.
  highlights: unique nonempty source record ID strings.

Display focus/subset lives only in view.focus_patient_keys. Empty focus means all
visible roster patients, NOT an empty analysis population. Hidden layers, camera,
selection and alignment never remove patients from analysis. Do not derive the
analysis population from these display fields. Identifiers/dates/order are copied
without normalization, sorting or imputation. Fields not documented above fail.

Diff contract and APIs

A StateDiff is an object with optional analysis and display keys, and no other
keys. Each present key is {before: complete domain snapshot, after: complete
domain snapshot}. {} is a valid read-only/no-op diff. Full-domain replacements
make deletion/null values explicit and keep undo deterministic.

  validateState(state), validateDiff(diff)
    Validate and return the original input. These do not freeze or copy it.
    TypeError on malformed/unknown fields or non-finite/non-JSON values.
  createState(state)
    Validate then return a detached immutable snapshot.
  stateDiff(before, after)
    Validate both states, return detached immutable diff of changed domains only.
    Object field order is ignored for equality; array order is preserved.
  applyDiff(current, diff)
    Require current to match every touched domain's before value, then replace
    touched domains with after. Validate before any result is returned.
  revertDiff(current, diff)
    Require touched domains to match after, then replace only those with before.
  resetState(current, initial)
    Validate both and restore the complete supplied initial snapshot exactly.
    Caller must retain an immutable initial snapshot per dataset/session.

A conflict throws TypeError and leaves every input untouched. Display-only undo
preserves a later, independent analysis change. Same-domain stale undo fails
rather than silently overwriting unrelated edits. There is deliberately no
cross-domain check on untouched domains: renderer reconciliation must not
silently change analysis. Null selection, hidden selection, and absent highlights
are preserved, not reconstructed from currently visible marks.

Tool/history integration

  const initial = ViewStateCore.createState(bridge.snapshot());
  const diff = ViewStateCore.stateDiff(current, proposed);
  // Handler validates capability/source membership and obtains explicit human
  // confirmation if diff.analysis exists. This core is NOT an authorization gate.
  const next = ViewStateCore.applyDiff(current, diff);
  await bridge.apply(next); // external renderer/evaluator commit may fail
  // Only after successful commit publish current=next and append history entry.
  // Undo: bridge.apply(ViewStateCore.revertDiff(current, entry.diff)).
  // Reset: bridge.apply(ViewStateCore.resetState(current, initial)).

Do not expose applyDiff/resetState as model-callable tools. History/UI owns undo
and reset. An analysis diff is data, NOT evidence of user consent. Confirmation,
dataset identity, async race checks, history stack, actual browser commit/rollback,
and source membership checks remain responsibilities of dependent cards.
Full baseline replacement after switching datasets is unsafe; invalidate old
history/proposals and capture a new initial snapshot at the integration boundary.

Compatibility/evidence

Inspected data/schemas.json, data/normalized_spec.json, renderer3d.js and lattice.js
chatSnapshot implementations. Read the saved parent t_ac9c93cd static/app.js,
static/tool-registry.js and alignment.py without modifying that worktree. This
core's diff format matches that registry's existing stateDiff envelope. The
parent's simplified unit fixture omits required pinned view/analysis fields; use
a complete spec-backed snapshot (as these tests do) rather than weaken validation.

Alignment accepts the saved resolver's full fields: status (resolved/executed),
anchor, axis_label, definition, convention, denominator, denominator_unit, counts,
patients, record_ids, missing_anchor_handling, note. Only lattice allows non-null
alignment; supported anchors are first_treatment, first_PR, first_PD, death.
Resolved dates must be complete calendar dates and missing dates remain null;
patient totals, status counts and source-ID union must agree. Calendar resolves
to null upstream. This validates result structure, NOT source truth: tool handlers
must use trusted fixture resolution and reject fabricated/unsupported anchors.
No fixture dates or anchor counts were changed or inferred. The alignment test
uses explicitly synthetic result shapes, not claimed cohort observations.

This card adds only the core and focused checks. It does not replace the parent's
ToolSession, serve a new HTTP route or wire the UI. Dependent history/registry/QA
cards implement those integration concerns. No independent review or full browser
suite is claimed; the browser-export smoke runs in Node vm with no DOM/network.
