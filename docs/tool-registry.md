# Validated tool registry and application integration

The browser loads state-core.js, action-history.js, tool-registry.js, then view-chat.js. The CommonJS/browser registry exports ToolSession, validateCall, planView, stateDiff and the frozen registered names. Both local JSON commands and adapter-provided model calls use the same dispatch path. Model prose is inert, labeled unverified, and never evaluated as code. The registry has no DOM access; only trusted UI/renderer code renders validated data.

## Tools and source meaning

- get_capabilities: fixture-grounded alignment catalogue and tool limitations.
- get_view_state: separate analysis and display snapshots, not a claim that displayed records define the analysis.
- set_view: sort, focus or explicit nonempty subset, visible AE/CM/EX/RS layers, tier and renderer-specific camera. focus:null restores all display patients; subset and focus cannot be combined. Analysis is unchanged. History record_ids are the prior affected rendered source set returned by bridge.records(), not a post-change analytical count.
- set_alignment: calendar or source-backed first_treatment (alias first_dose), first_PR, first_PD and death on /lattice, only when the loaded catalogue exposes the required mapping. Death is unavailable in small/100 and supported in keynote189; see [the snapshot-pinned capability audit](lattice-agent-capabilities.md) for all three cohorts and reproduction commands. Relative alignment preserves original source dates, uses elapsed calendar days (anchor=0, not SDTM study-day numbering), and keeps missing anchors visible in separate no-event/date-unresolved groups. Resolver denominator is the loaded roster; the renderer separately displays visible resolved/missing denominators. Calendar reset states its denominator and that no relative anchor is required. Randomization is unsupported; no fallback anchor or imputation is used. Timeline and legacy /3d refuse relative alignment.
- highlight_events: explicit current_analysis filters only, with source-keyed AE result IDs. term, grade, patient, linked_cm, inclusive AESTDTC date_window and exact record_ids are supported. Exact IDs must identify existing AE records and are intersected with qualifying analysis; they cannot expand it. Highlights are not filters on analysis.
- query_data: requires scope=current_analysis, explicit unit (patients or AE records), and filters. Returns contributing AE record IDs and separate linked CM evidence IDs, plus count/unit. It counts the current qualifying analysis, not the visible display subset. Raw record content is not sent to the model without separate per-request egress permission.
- propose_analysis_subset: returns computed before/after patient and AE-record consequences and a pending proposal, without changing live state or history. Only a separate human Confirm action with the matching proposal ID commits it. The model cannot call confirmation. Cancel, stale state/dataset and unsupported values fail closed.
- propose_development_task: creates a uniquely identified entry in the LOCAL SESSION task ledger, marked proposed and result_created:false. This is not an external kanban/GitHub ticket or implemented result. Tasks survive view Undo/Reset but not page reload; there is no durable task backend in this implementation.
- clarify_request: returns a question without state/history mutation. Unsupported and clinically inferential structured arguments are rejected rather than reinterpreted.

## State and history

ToolSession receives a trusted bridge with snapshot, roster, records, dataset, resolve and atomic apply callbacks. snapshot contains {analysis,display}. A validated display operation cannot write analysis. Core validation rejects unknown fields, malformed cameras, invalid dates, nonfinite values, executable values/accessors, cycles and prototype payloads.

Resolved changes become validated before/after diffs. The app evaluates the proposed combined specification before committing, rejects unexpected normalization or detected state drift, and restores previous state on a rendering error. History publishes only after commit succeeds. Each executed tool, including reads, has action/args, diff, record_ids, linked_record_ids and Undo/Reset metadata in inspectable in-page JSON. Refusals, clarification and unconfirmed proposals are not executed actions.

Undo reverses the latest entry exactly, including analysis population, display selection, highlights, alignment and camera. Reads have a no-op Undo. Reset restores the session baseline and clears action rows; task ledger entries remain explicitly visible. Manual changes start a fresh history session on the next tool action. Concurrent tool requests are rejected, not queued. Dataset/state drift invalidates pending work.

## Verification and boundaries

See tool-acceptance-tests.md for AC1–AC9 coverage. Integration evidence in evidence-registry-integration-*.log includes all 54 Node tests, two alignment geometry tests and all 84 Python-discovery tests, including Chromium/local mock model integration. The KN189 browser test verifies first-PR 23/60, missing groups, source preservation, projections, Undo and unsupported randomization. Source tests verify generic first-treatment=100/PR=25 and KN189 treatment=60/PR=23/PD=45/death=36 without editing fixtures.

Run:

    npm test
    node --test alignment-model.test.mjs
    python -m unittest discover -v
    npm run build
    git diff --check

No external provider, physical iPad, deployment or independent approval is claimed. Arbitrary natural-language intent classification is not proven by schema validation: ambiguity tests cover structured calls and explicit refusal/clarification, not every possible model interpretation. Canvas gestures are not comprehensively serialized during asynchronous requests; detected snapshot drift rejects the request instead of overwriting that change. Downstream QA/fact-check cards own further end-to-end and independent review.
