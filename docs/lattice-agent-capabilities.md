# Lattice agent capability audit — loaded-source snapshot

Scope: F2/F3 correction in task `t_7d23a19e`, based on implementation commit
`0eb084bbcee7eebfed0f9115a821ec1780263037`. The source fixtures, generator and
scenario adapter are unchanged from that commit. The resolver/catalogue correction
is in `alignment.py`; executable evidence is `evidence-anchor-audit.json`.
This document supersedes the archived audit comment claiming generic-cohort PR=1.
That number was wrong for this snapshot: **generic first recorded PR is 25**.
No fixture was modified to meet any count.

All cohorts are synthetic demonstrations, not real trial data, clinical results,
or submission-ready datasets. “keynote189” is the application's cohort selector,
not a claim that these are actual KEYNOTE-189 patient records.

## Snapshot pins and reproduction

Run from the repository root with Python 3.11 and the pinned requirements:

```sh
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements-test.txt
.venv/bin/python audit_alignment.py
.venv/bin/python -m unittest test_alignment_capabilities test_tool_acceptance test_model_agent -v
.venv/bin/python -m unittest test_alignment_mapping_browser test_alignment_browser test_agent_e2e -v
```

`audit_alignment.py` constructs `Engine('data', cohort)` for **small, 100 and
keynote189**, calls the actual `resolve_alignment` for each anchor and
`alignment_capabilities`, and emits JSON (no network and no fixture writes).
The JSON includes resolved-patient totals, missing-event/date counts, unsupported
statuses, catalogue details, source hashes and loaded snapshot hashes. It also
counts populated `RSSTRESC` keys directly in the loaded RS rows. Browser checks
require the Playwright Chromium installation (`.venv/bin/python -m playwright
install chromium` if not installed). All matrix counts below are in that output;
there are no manually substituted resolver responses.

| Cohort | Loaded roster | Snapshot ID | Engine snapshot SHA-256 |
| --- | ---: | --- | --- |
| small | 3 | synthetic-spike-v1 | `86da855baf7f7139424aae61d6fbb9874f6403b89dab21540f1a9bc3b63c7737` |
| 100 | 100 | synthetic-scale-100-v2-sentinel | `9fcf5b2759edd4330486d05f390642e0b96b898a46b788166ac573934e61e303` |
| keynote189 | 60 | synthetic-keynote189-be3744cd-v1 | `b9d9600d018e472ce1dd5e23417c48844c908d20ec1f15ba28d8d78d5769e2d2` |

Additional source SHA-256 pins (also emitted by the audit):

- `data/fixtures.json`: `86da855baf7f7139424aae61d6fbb9874f6403b89dab21540f1a9bc3b63c7737`
- `data/manifest.json`: `f1729e2c35d5bc665f45034f40172528f9cdc5aa3fca0445e26bf64c6f4e39c3`
- `cohort.py`: `d52921eb0c16829f0c0436f9cc31280ae437de7c213a04a11a012950c8b9cffb`
- `scenario_adapter.py`: `f4b49e4cf287707cd61fe5a3a7fdcc0d458782521713152cf751e959ffd59ec2`
- `fixtures/keynote189-synthetic/raw.json`: `4dd5639d3b9799ee6c8b31615659d2433452fd6e077aca1ba8cb7d26064fbb54`

The raw scenario is pinned to upstream commit
`be3744cd7768373552e87201ea0efe90578c094f` by `scenario_adapter.py`. Its dates use
`2025-01-01 + enrollment offset + source day`: fictional display dates, not trial
dates. The Engine validates the base manifest, and the scenario adapter validates
its raw-file hash and provenance before loading.

## Availability is not the same as resolution

The supported catalogue is computed from loaded records and field mappings, not
from the global candidate-anchor list, cohort name, UI command examples, patient
count, or presence of complete dates:

- Treatment mapping requires an EX record exposing `EXSTDTC`.
- Response mapping requires an RS row with `RSTESTCD=OVRLRESP` exposing both
  `RSORRES` and `RSDTC`. It supports both PR and PD even when **no patient** has
  that response. `RSSTRESC` is not used or substituted.
- Death mapping requires a DS row coded `DSDECOD=DEATH` exposing `DSSTDTC`.
  DS is a heterogeneous disposition domain: discontinuation/withdrawal rows
  alone do not establish a death mapping. A fatal AE, its onset, or AE `DTHDTC`
  is not substituted. Without a declarative death-source contract in these
  fixtures, a loaded death-coded row is the conservative mapping evidence.
- Identity fields `STUDYID` and `USUBJID` must accompany those source fields.
  A present but blank/partial date establishes a field mapping, not a date.

The API preserves these separate outcomes:

1. **Supported, patient resolved:** top-level `status=resolved`, patient
   `status=resolved`, earliest complete qualifying date and contributing IDs.
2. **Supported, no qualifying event for a patient:** top-level `status=resolved`,
   patient `status=no_qualifying_event`, `date=null`, empty evidence IDs. This is
   not proof that the event never occurred. Small-cohort PD demonstrates a valid
   response mapping with no qualifying PD for any patient.
3. **Unsupported mapping:** top-level `status=unsupported`,
   `limitation=source_mapping_unavailable`, explicit development-task note, empty
   `record_ids`, and **no patient list or missing-event counts**. The catalogue
   omits it from `supported_anchors` and explains it in `unavailable_anchors` and
   `unsupported`. No transform, exclusion, imputation or analysis change occurs.

Within a supported mapping, a qualifying candidate with a blank, partial or invalid
calendar date yields `event_date_unresolved` and `date=null`. If any qualifying
candidate's date is unresolved, the resolver does not choose a later complete
candidate and call it “first.” These states are tested with isolated in-memory
copies; source fixtures are never rewritten.

## Source-field matrices

“Resolved” counts patients with resolved dates, not source rows or confirmed
responses. “No event” counts patients without a qualifying recorded event **only
for supported mappings**. All supported matrix rows have 0 date-unresolved
patients in this exact snapshot. For unsupported mappings, resolved=0 means no
resolved anchors are returned; the missing-event denominator is **N/A**, not the
entire cohort mislabeled as missing. Every mode supports calendar reset without
requiring a relative anchor. `first_dose` aliases `first_treatment` only when the
latter mapping is available; it does not test numeric dose or induction status.

### Small fixture — 3 patients

| Anchor | Source fields / selection | Mapping | Resolved | No event |
| --- | --- | --- | ---: | ---: |
| first_treatment | EX: earliest `EXSTDTC` | supported | 3 | 0 |
| first_PR | RS: `RSTESTCD=OVRLRESP`, `RSORRES=PR`, earliest `RSDTC` | supported | 1 | 2 |
| first_PD | RS: `RSTESTCD=OVRLRESP`, `RSORRES=PD`, earliest `RSDTC` | supported | 0 | 3 |
| death | No DS records exposing a death-code/date mapping | unsupported | 0 | N/A |
| randomization | No mapped randomization date/DM anchor | unsupported | 0 | N/A |

Source: `data/fixtures.json`. Death and randomization have **no source mapping**.
PD has a response mapping but no PD events; those are different states.

### Generic 100-patient fixture

| Anchor | Source fields / selection | Mapping | Resolved | No event |
| --- | --- | --- | ---: | ---: |
| first_treatment | EX: earliest `EXSTDTC` | supported | 100 | 0 |
| first_PR | RS: `RSTESTCD=OVRLRESP`, `RSORRES=PR`, earliest `RSDTC` | supported | 25 | 75 |
| first_PD | RS: `RSTESTCD=OVRLRESP`, `RSORRES=PD`, earliest `RSDTC` | supported | 97 | 3 |
| death | DS rows exist but none map `DSDECOD=DEATH`; no death-alignment mapping | unsupported | 0 | N/A |
| randomization | No mapped randomization date/DM anchor | unsupported | 0 | N/A |

Source: `cohort.py::scale_cohort` applied to the small fixture. RS contains **391
rows**, of which **3** have populated `RSSTRESC`; using that field would discard
recorded responses in generated rows. The resolver uses **RSORRES**, not RSSTRESC,
for both PR and PD. The generated disposition records describe discontinuation,
withdrawal or subsequent therapy, not death. Fatal-AE visual sentinels elsewhere
in the app do not authorize death alignment. Thus death=0 is an unavailable mapping,
not “100 patients with no qualifying death event in an available mapping.”

### keynote189 synthetic scenario — 60 patients

| Anchor | Loaded source fields / original source | Mapping | Resolved | No event |
| --- | --- | --- | ---: | ---: |
| first_treatment | EX `EXSTDTC` from `ex[].d` | supported | 60 | 0 |
| first_PR | RS `RSTESTCD=OVRLRESP`, `RSORRES=PR`, `RSDTC` from `tr[].resp` / `tr[].d` | supported | 23 | 37 |
| first_PD | RS `RSTESTCD=OVRLRESP`, `RSORRES=PD`, `RSDTC` from `tr[].resp` / `tr[].d` | supported | 45 | 15 |
| death | DS `DSDECOD=DEATH`, `DSSTDTC` from non-null `ds.death` | supported | 36 | 24 |
| randomization | No mapped randomization date/DM anchor; enrollment offset is not randomization | unsupported | 0 | N/A |

Source: `scenario_adapter.py::load_scenario` and pinned `raw.json`. First PR is
**first recorded PR**, not confirmed response. PD is recorded PD, not inferred
progression. Death is a recorded death date, not a fatal-AE onset or disposition
end-of-treatment date.

## Implemented capabilities and boundaries

- `get_capabilities`: loaded-source alignment catalogue above, tool schemas and
  limitations. Global tool descriptions/command examples list candidate names;
  only the loaded catalogue says which mappings are supported.
- `set_alignment`: display-only on `/lattice`; elapsed calendar days, anchor=0,
  not SDTM study-day numbering. Original source dates and analytical counts are
  unchanged. Missing-event and unresolved-date patients stay in separate labeled
  groups. Resolver denominator is the loaded roster; displayed relative-bin
  denominators use resolved visible patients, with unaligned groups separate.
- `set_view`: explicit display sort/focus/subset, layers, tier and renderer-specific
  camera. `highlight_events`: source-keyed AE outlines. Neither changes analysis.
- `query_data`: explicit current-analysis scope and patients versus AE-record units,
  contributing source IDs, exact supported AE filters and absolute onset windows.
  Linked CM evidence uses the source relationship rules, not inferred causality.
- `propose_analysis_subset`: proposal with computed count consequences; a separate
  local human confirmation is required to change analysis. Undo/Reset and in-page
  action history preserve before/after analysis/display state and source IDs.
- `clarify_request`: non-mutating clarification. `propose_development_task`: local
  session suggestion only, not an external ticket, completed implementation, or
  clinical result. Its ledger survives view Undo/Reset but not reload.
- Model status becomes connected/model-driven only after the configured endpoint's
  successful self-test. The local rule parser is not a model. Model calls use the
  loopback adapter and explicit egress acknowledgement; default tool context is
  minimized, with separate per-request permission for record-level content.
  Synthetic source rows intentionally remain available in local provenance/export
  workflows. Do not claim “no raw records anywhere.” Credentials are session-only;
  tested persistence/egress checks are bounded checks, not universal proof.

Implementation references: `alignment.py`, `model_agent.py`, `view_tools.py`,
`static/tool-registry.js`, `static/view-chat.js`, `static/state-core.js`,
`static/action-history.js`, and the renderer's alignment model. See also
[tool-registry.md](tool-registry.md) and [model-agent-e2e.md](model-agent-e2e.md).

## Remaining development work / nonclaims

- Randomization in every cohort; death mapping for small and generic 100; any new
  anchor requires an explicit validated source mapping, not a surrogate date.
  Declarative schemas that can attest to an empty death source are not implemented;
  this catalogue conservatively relies on exposed loaded mapping evidence.
- Anchor-relative **analytical** windows, response confirmation, induction/dose
  inference, causal attribution, clinical interpretation and treatment advice.
  Display alignment is not support for those analyses.
- Relative alignment on timeline and legacy `/3d`; persistence/replay of relative
  alignment (currently session-only), and durable external development tickets.
- Arbitrary natural-language semantic grounding: the fact-check's F1 demonstrates
  that schema-valid inferred patient selections can evade prompt-only ambiguity/
  clinical-inference safeguards in the base snapshot. F2/F3 do not fix or approve
  that separate defect. Structured schema refusal is not proof of intent safety.
- Comprehensive canvas-gesture concurrency serialization, physical-device checks,
  live external-provider/TLS testing, hosted CI execution, deployment and
  independent approval are not established by this audit. Browser verification
  uses local Chromium and a scripted local mock, not fabricated provider results.

Evidence for this correction is saved in `evidence-anchor-*.log` and
`evidence-anchor-audit.json`. The pre-fix regression log is intentionally failing;
subsequent passing runs do not erase it. The audit describes this source snapshot,
not all hypothetical future datasets or all possible model behavior.
