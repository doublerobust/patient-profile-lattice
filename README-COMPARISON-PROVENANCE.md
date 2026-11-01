# Lattice prototype: comparison, provenance, and reuse boundary

This prototype takes selected interaction ideas from `pzhang724/patient-profile-linkage` at commit `be3744cd7768373552e87201ea0efe90578c094f`. It does not copy that repository's source code. The only authorized reuse is the generated synthetic KEYNOTE-189-style fixture described below.

The external repository was inspected as source at the pinned commit. It was not executed interactively. Statements about the external interface therefore describe the source and README, not a runtime validation of that application. The detailed audit and source record are `AUDIT-EXTERNAL-REPO.md` and `AUDIT-SOURCES.md`.

## What is different

| Area | Current patient-profile visualizer and lattice prototype | External repository at the pinned commit |
|---|---|---|
| Data | The established generic synthetic cohort remains available. The prototype also documents an imported 60-patient synthetic KEYNOTE-189-style fixture under the data-only authorization below. | A seeded, synthetic KEYNOTE-189-style generator with 60 patients. |
| Visual model | The additive `/lattice` route uses one patient × time × visual-layer spatial model and one orthographic scene. The existing clinical engine, sentinel tiers, interval end states, selection provenance, and analytical-count safeguards remain authoritative. | An event cube with patient × domain × time views, rendered as four discrete canvas modes. Its separate lanes page has a layered three.js scene. |
| Collapsed views | Collapse is a projection of the same lattice model. Free rotation remains available. | The full cube, patient × time, patient × domain, and domain × time views are selected as separate modes rather than geometric projections of one lattice. |
| Time and counts | Records use fixed display dates and pinned local analysis rules. Display summaries keep explicit denominators separate from analytical counts. | Event alignment supports seven anchors and removes patients who do not have the selected anchor event. Its cohort view includes per-window measures and arm-percentage rows. |
| Selection provenance | Selection can retain the local `original_source` chain to source rows and local derivation/replay evidence. | Marks and aggregates support display detail and contributor lists, but the inspected external source has no source-row lineage or analysis-spec/replay concept. |
| Agents and signals | No agent panel or signal-inference rules are part of this prototype. | The source includes a rule-based signal engine and an agent panel with Claude tools and bilingual regex fallback commands. |

## Concepts adopted at the concept level

The following are reimplemented locally from requirements and behavioral observations. They are not source-code reuse.

- Lattice and rotation. The useful framing is a patient × domain/layer × time structure. The prototype keeps four canonical views in one lattice: the full lattice; patient × time with layers collapsed; patient × layer with time collapsed; and layer × time with patients collapsed into a cohort view. Free rotation is preserved, so the named views are not separate tabs.

- Layer collapse. A shared record model can be shown as peeled layers, one merged line per patient, a patient-by-layer summary, or a cohort-by-time summary. This supports comparable views without changing the underlying analytical model.

- Camera transitions. Smooth moves to named views and semantic detail are useful. The local requirement extends the inspected external behavior: drag or wheel input interrupts a focus move immediately. The audit found that the external tween was not input-interruptible.

- Selection and contributor drill-down. An aggregate can enumerate its contributing patients or records before a user chooses a specific record. Local source-record provenance remains authoritative because the external repository does not supply source-row lineage.

- Cohort-summary discipline, in part. The implemented cohort projection reports unique visible patients with a displayed source start in each fixed 30-calendar-day bin, divided by the current visible-patient count. These are display summaries, not incidence, prevalence or new clinical endpoints. The analytical roster is unchanged.

- Existing sorting is retained: treatment duration, ascending patient ID, descending patient ID, best response, first PD, and discontinuation reason. These six sorts are view-only.

## Audit recommendations, not implemented

The audit recommends considering header-driven sorting and additional keys (peak laboratory value, best percent change, anchor day, longest dosing gap). These are not shipped capabilities. The external observed-patients row, assessed/observed per-window denominators, and small-n thinning are also not implemented. The audit's ADOPT-CONCEPT verdicts are recommendations, not implementation evidence.

## Concepts not adopted

The following boundaries are deliberate.

- Agent-panel behavior is rejected pending separate review. This includes Claude-based page tools and the bilingual regex fallback commands. It would introduce a privacy and service-behavior change, including possible third-party model calls.

- Signal-inference rules are rejected pending separate review. The external rules, including rules for potential Hy's law, an AE after death, missing steroid treatment, and dosing gaps, are not authoritative in the local clinical engine. Adopting them would change interpretation and counts.

- Event-based alignment that removes patients without an anchor event is rejected. It would alter the population displayed and conflict with local analytical-count safeguards.

- The external confirmed-response rule, which requires a later scan at least 28 days later, is rejected because it would change response interpretation.

- Arm-specific percentage rows are rejected. The local cohort view is not an arm comparison.

- Matrix threshold highlighting and flat SDTM-like query tables need separate review. Threshold highlighting borders the rejected signal-inference scope, and the tables are currently entangled with the rejected agent panel.

- The external semantic-zoom approach is not adopted as a new feature because the local visualizer already has zoom-dependent annotations and sentinel tiers. The external planted anomalies are retained only as part of the authorized synthetic fixture; the detection rules remain out of scope.

## Synthetic fixture provenance

Source repository: https://github.com/pzhang724/patient-profile-linkage

Pinned source commit: `be3744cd7768373552e87201ea0efe90578c094f`

Yue explicitly authorized copying the repository's generated synthetic KEYNOTE-189-style data for this demo. The authorization is data-only. It does not authorize reuse of the repository's source code, generator, agent-panel behavior, or inference code.

The documented imported output contains 60 fictional patients and the following recomputed source-row counts: 260 AE, 80 CM, 1,771 EX, 391 TR, and 4,962 LB. Its recorded raw SHA-256 is `4dd5639d3b9799ee6c8b31615659d2433452fd6e077aca1ba8cb7d26064fbb54`.

This fixture is synthetic. It is not real trial data, not clinical evidence, and not a submission-ready dataset. It must not be represented as real KEYNOTE-189 data or used as a submission-ready dataset.

## Code-licensing status

At the inspected commit, the recursive repository tree contained 16 files and no `LICENSE`, `COPYING`, or `NOTICE` file. The repository API reported `license: null` on 2026-10-31, and the README contained no reuse grant.

For this project, the engineering rule is therefore: no external source code was copied; only concepts are reimplemented from scratch unless written reuse permission or a compatible license covering the pinned commit is verified. Public availability is not permission to copy source code. Yue's data-only authorization is not a source-code license.

This is a conservative reuse boundary, not legal advice. Evidence that could change it must be verified in writing: permission from the copyright holder, a license that explicitly covers the pinned commit, or a provenance-linked compatible prior publication.

## Evidence map

- External feature comparison and concept verdicts: `AUDIT-EXTERNAL-REPO.md`, sections 2 through 5.
- External source locations, pinned-commit metadata, and local evidence references: `AUDIT-SOURCES.md`.
- Licensing evidence and reuse boundary: `AUDIT-EXTERNAL-REPO.md`, section 6.
- Fixture extraction, attribution, hash, counts, and local limitations: `fixtures/keynote189-synthetic/README.md` and `fixtures/keynote189-synthetic/provenance.json`.

Verification of final integration and acceptance remains separate from this documentation. The evidence above does not claim a live deployment, independent clinical review, or execution of the external application.
