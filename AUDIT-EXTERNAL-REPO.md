# External repo audit — concepts, licensing, reuse limits

Subject: https://github.com/pzhang724/patient-profile-linkage
Pinned commit: be3744cd7768373552e87201ea0efe90578c094f
("Add patient lanes and patient x domain x time event cube on synthetic KN189-style data", 2026-10-31 11:38:51 -0400)
Audit date: 2026-10-31 (EDT). Method: local git clone checked out at the pinned commit, read-only source inspection,
GitHub tree/repo API cross-check. Source record with URLs and evidence locations: AUDIT-SOURCES.md.

Scope note: the external application was inspected as source, not executed interactively. Statements below describe
what the code and README say the interface does; no claim is made that the running app behaves that way. No external
source code is copied into this project — this document records identifiers and behavioral facts only.

---

## 1. Repository inventory at the pinned commit (16 files)

| Path | Role |
|---|---|
| README.md | Feature description, build instructions, synthetic-data statement |
| build.sh | Concatenates src/ parts into the two standalone docs/ pages |
| docs/event-cube.html | Build output of the cube page (83 KB, assembled from src/cube/*) |
| docs/patient-lanes.html | Build output of the lanes page (56 KB, assembled from src/lanes/*) |
| src/cube/c0_data.js | Seeded synthetic generator (seed 189), planted anomalies, derived metrics + signal engine |
| src/cube/c1_base.html, c1_extra.html | Cube page markup/controls (mode buttons, filters, tabs, agent chat, patient card) |
| src/cube/c2_cube.js | Cube helpers: event-alignment anchors, per-patient feature columns, per-window measures, flat tables |
| src/cube/c3_lanes.js | 2D patient lanes renderer with semantic zoom, domain peel/merge |
| src/cube/c4_views.js | Collapsed views: patient × domain matrix, domain × time summary |
| src/cube/c5_agent.js | Agent panel: query engine, page tools, Claude integration, fallback commands |
| src/cube/c6_app.js | Interaction glue: animations, selection, drill-down, filters, panels, boot |
| src/lanes/p1_head.html | Lanes page styles/markup |
| src/lanes/p2_data.js | Same seeded generator as c0_data.js (lanes build copy) |
| src/lanes/p3_lanes.js | Lanes renderer (predecessor of c3_lanes.js) |
| src/lanes/p4_app.js | Lanes interaction + three.js layered 3D scene |

The docs/ pages are concatenation build artifacts of the src/ parts (per build.sh), not separate implementations.
The tree API at the pinned commit returned truncated=false and contains no LICENSE/COPYING/NOTICE file;
the repo-level API reports "license": null as of 2026-10-31. See the licensing memo (section 6).

---

## 2. Comparison — current patient-profile visualizer vs. this repo

| Aspect | Current visualizer (this project) | External repo at be3744c |
|---|---|---|
| Data | Pinned generic synthetic cohort (100 patients) plus the imported 60-patient synthetic KEYNOTE-189-style fixture (data copied under Yue's data-only authorization) | Seeded synthetic KEYNOTE-189-style generator, 60 patients, 2:1 pembro vs placebo, both + pemetrexed + platinum |
| Core model | Clinical engine with pinned analysis rules; display layer with sentinel tiers; additive patient × time × visual-layer lattice (one orthographic scene, four camera-normal projections) | Patient × domain × time "event cube" as four discrete canvas view modes (full cube, patient × time, patient × domain, domain × time); separate three.js layered scene on the lanes page |
| Views | / , /3d, /lattice (additive); collapsed lattice projections derived from one spatial model | Mode switch among four 2D painters over one record model; collapse = discrete view, not a geometric transformation |
| Clinical semantics | Sentinel tiers with date-priority overrides (e.g. fatal AE → death sentinel), interval end states (ongoing / end unknown), six view-only sorts, selection provenance to raw source rows, analytical-count invariants with replay verification | Display-level semantics: semantic zoom levels, severity-colored marks, feature/matrix summaries, per-window denominators; no source-lineage provenance, no analysis-spec concept |
| Time handling | Fixed calendar dates per record; documented display mapping | Event-based alignment (7 anchors); patients lacking the anchor event drop out of the view |
| Aggregation | Display summaries with explicit denominators; sentinel-copy dedup; analytical roster kept distinct from displayed counts | Feature columns (13) and per-window measures (7) with numerator/denominator, "patients observed" row, small-n thinning, arm-percentage rows |
| Signals / agents | None — deliberately out of scope; imported fixture preserved pre-inference rows | Rule-based signal engine (6 rules) with planted anomalies; agent panel (Claude tools + regex fallback commands) |

---

## 3. Interaction concepts — verdicts (the seven required)

| # | Concept | Verdict | One-line justification |
|---|---|---|---|
| 1 | Lattice / rotation behavior (patient × domain × time cube) | ADOPT-CONCEPT | The three-axis decomposition and four canonical collapsed views are exactly the primary prototype concept the owner specified; reimplementation from scratch is already underway (demo/lattice.js). |
| 2 | Layer collapse (domain peel/merge, axis collapse) | ADOPT-CONCEPT | Collapse as a transformation of one shared record model (peeled lanes ↔ merged line ↔ per-patient summary ↔ cohort windows) matches the local lattice requirement and is worth reimplementing. |
| 3 | Camera transitions | ADOPT-CONCEPT | Smooth eased moves to named views/zoom levels with prefers-reduced-motion respect are transferable; the external tween is not interruptible, so the owner's interruption requirement is a documented extension, not an external feature. |
| 4 | Selection provenance | ADOPT-CONCEPT (partially) | Aggregate → enumerate contributing patients → drill to detail is worth reusing (local lattice chooser already does it); the external repo has NO source-record lineage, so the local original_source chain stays authoritative. |
| 5 | Cohort summaries | ADOPT-CONCEPT (partially) | Windowed cohort measures with explicit per-window denominators, an observed-patients row and small-n caution are worth reusing; arm-percentage rows are rejected (row 10) and threshold highlighting needs review (row 13). |
| 6 | Agent panel | REJECTED-pending-separate-review | Owner instruction; adopting it would change privacy/service behavior (third-party model calls) and requires separate review. |
| 7 | Signal inference | REJECTED-pending-separate-review | Owner instruction; the rules are not authoritative in the local clinical engine and adopting them would alter interpretation and counts. |

### 3.1 Concept details

**1. Lattice / rotation behavior.** What it does: frames patient profiles as a patient × domain × time cube with
four named views — full cube with domains peeled into lanes; patient × time (domains merged onto one patient line);
patient × domain (time collapsed into a per-patient summary matrix); domain × time (patients collapsed into cohort
time windows). Conceptual implementation: the cube page is a 2D canvas application where one shared patient/record
model is painted by four mode-specific renderers selected by a mode radio group — "collapse" is a discrete view-mode
switch, not a geometric morph; the lanes page's three.js scene stacks one translucent plane per domain with patient
lines across planes and free orbit (drag) + dolly (wheel/pinch), but offers no canonical camera presets and no
projection-driven view semantics. Verdict rationale: the axis decomposition and the four canonical views are the
concept to adopt; free rotation that reveals meaningful collapsed views (the owner's primary requirement) is a
concept-level extension, since the external implementation reaches those views by switching tabs/modes, not by
rotating a single lattice.

**2. Layer collapse.** What it does: domain layers can be peeled into per-domain sub-lanes or merged onto one patient
line; collapsing time replaces each patient's events with pre-declared per-patient feature summaries; collapsing
patients replaces patient rows with per-arm, per-window cohort measures; layer chips toggle domains in/out.
Conceptual implementation: per-domain draw functions render either packed sub-lanes or superimposed marks over the
same record arrays; collapsed modes evaluate pre-declared feature/measure definitions over those same arrays, so all
views share one data model. Verdict rationale: this is the "collapse must be a real transformation of the same model"
behavior the local lattice must have; the declarative feature/measure definitions also give an explicit place to state
summary semantics, matching local display-summary safeguards.

**3. Camera transitions.** What it does (2D): eased ~300 ms animations to zoom presets (fit / overview / events /
detail) and to a selected patient or signal; double-click zoom-at-cursor; pinch/wheel zoom; prefers-reduced-motion
collapses the animation to an instant jump. What it does (3D lanes): free orbit + dolly only, plus an animated
"spread" slider that eases the vertical gap between domain planes; no animated camera destinations. Conceptual
implementation: a requestAnimationFrame tween interpolating zoom scale logarithmically and pan position linearly with
a cubic ease-out. Verdict rationale: smooth snap-to-view moves with reduced-motion respect transfer cleanly to the
lattice; the external tween writes camera state every frame until done and does not hand control back on new input,
so interrupt-on-drag/wheel (a stated local requirement) must be designed locally.

**4. Selection provenance.** What it does: every mark hit-region carries a tooltip naming the record (term, grade,
dates, values); clicking selects the patient and opens a card with its position ("n of N"), baseline/response facts,
anchor day and a chronological event list; clicking a cohort cell drills to exactly the contributing patients via a
"Selection: <label>" view filter; the agent query tool returns the USUBJIDs behind every aggregate. Conceptual
implementation: aggregates retain contributing patient IDs at compute time, so a cell can re-filter to its members;
record tooltips carry display facts only. Verdict rationale: contributor enumeration and aggregate→member drill-down
are worth adopting (the local lattice overlap chooser already implements the pattern); the external repo has no
source-row pointers, no derivation-rule ids and no replay concept, so it adds nothing to — and cannot replace — the
local "Open source records" provenance chain.

**5. Cohort summaries.** What it does: (a) a patient × domain matrix of 13 declared feature columns (cycles given,
longest dosing gap, AE count, worst grade, worst immune-AE grade, peak ALT/creatinine/TSH ×ULN, lowest ANC ×LLN,
best % change, best response, steroid days, treatment meds) with per-cell mini-bars, category dots and header-click
sorting; (b) domain × time rows of 7 declared measures (dosed, grade ≥3 AE ongoing, immune-related AE ongoing, lab
outside range, responding at scan, progressed so far, on corticosteroid) per arm per time window, with
numerator/denominator, a "patients observed" count row, small-n thinning when fewer than 3 are assessed, 21-day
windows (7-day at detail zoom) and click-to-drill on cells. Conceptual implementation: measures/features are
pre-declared functions evaluated per patient per window; denominators are either "observed in window" or "assessed in
window"; cells keep contributing IDs; when time is aligned to an anchor, windows shift per patient by that anchor.
Verdict rationale: explicit per-window denominators, observed counts and small-n caution are exactly the display-
summary discipline the local project already requires (COMPARISON-LATTICE safeguards) and are worth carrying into the
lattice cohort projection; the arm-percentage framing is rejected below; the "worth a look" cell highlighting is a
signal heuristic and is review-gated below.

**6. Agent panel** (REJECTED-pending-separate-review — owner instruction). What it does: an in-page chat that, when a
Claude artifact runtime is available, delegates to the model with four page tools — query_data (filter/group/aggregate
over flat SDTM-like tables DM, AE, LB, EX, TR, CM, SIG with count/patient-aware aggregates), set_view (mode, align,
arm, TPS, subset, sort, layers, lab, zoom), show_patients (restrict view to given USUBJIDs), open_patient (select +
zoom to one patient) — under a system prompt with a table dictionary and an answer discipline ("query before stating
any number", give denominators, 2–5 sentence answers, never invent data); when no runtime is available it falls back
to bilingual (English/Chinese) regex commands mapping phrases like "collapse time" / "align on confirmed PR" /
"sort by peak ALT" / "only placebo" to the same view operations; 12-turn memory cap, abort support, error-code-
specific UX. Conceptual implementation: tool schemas bound directly to the shared view state; a regex command parser
as the degraded mode. Reason for the verdict: per the task owner, agent-panel behavior is not to be adopted without
separate review; it would also introduce third-party model calls (privacy/service behavior change). This applies to
the fallback command surface as well, since it is agent-panel behavior.

**7. Signal inference** (REJECTED-pending-separate-review — owner instruction). What it does: after generation, a
derived-metrics + rule pass emits severity-tagged signal rows: potential Hy's law (ALT >3×ULN with bilirubin >2×ULN
at the same visit, crit), AE starting after the recorded death date (crit), grade ≥3 immune-related AE (excluding
thyroid terms) with no Prednisone start from AE onset minus 3 through plus 14 days (warn), non-crossover dosing gap >42 days (warn), dosing after
documented progression (info), crossover note (info). The generator plants four known anomalies targeting these rules
(a Hy's-law lab pattern with hepatitis and steroid; an AE recorded after death; a grade-3 immune AE with no steroid;
a +35-day shift of later cycles creating a long gap). Signals drive severity rings, a signal list with focus-on-click,
and the SIG table consumed by the agent. Reason for the verdict: per the task owner, signal-inference rules are not to
be adopted without separate review; they are not authoritative in the local clinical engine and would alter
interpretation and counts. Consistent boundary already honored locally: the imported synthetic fixture preserved
pre-inference rows (empty signal arrays); only data was copied.

---

## 4. Other notable concepts found

| # | Concept | Verdict | Reason |
|---|---|---|---|
| 8 | Event-based time alignment (7 anchors: randomization, first grade ≥3 AE, first immune-related AE, first AE of term, confirmed PR, progression, crossover); patients lacking the anchor drop out of the view | REJECT | Dropping patients alters counts and interpretation; conflicts with analytical-count invariants. Local keeps fixed calendar dates and pinned analysis rules (cf. COMPARISON-LATTICE). |
| 9 | Confirmed-response rule (PR/CR confirmed by a later scan ≥28 days) used as alignment anchor and in the external response framing | REJECT | Adopting a confirmation rule would change response interpretation; response semantics are pinned locally (response_order only orders recorded best responses). |
| 10 | Arm-specific percentage rows in the domain × time summary | REJECT | Local policy: cohort display is explicitly not an arm comparison; adopting arm percentages would require clinical review and change the meaning of the view. |
| 11 | Semantic zoom levels (overview / events / detail) with content gating (e.g. overview shows only grade ≥3 AEs and large lab flags) | NO-ACTION (already covered) | Local already has zoom-dependent annotations and sentinel tiers (tiers 0–2, auto by zoom); the external version is cruder and adds nothing. |
| 12 | Header-click sorting on summary columns; extra sort keys (peak ALT, best % change, anchor day, longest dosing gap, worst grade) | ADOPT-CONCEPT | Extends the local six view-only sorts with genuinely new keys and direct manipulation on headers; sorting stays view-only ("analysis unchanged"). |
| 13 | Matrix threshold highlighting ("worth a look" values: ALT ≥3×ULN, creatinine ≥1.5×, TSH ≥2×, ANC below LLN, worst grade ≥3, gap >42 days) | NEEDS-REVIEW | Functions as a simplified clinical signal heuristic in the display layer; borders the rejected signal-inference area — should be decided in the same separate review. |
| 14 | Flat SDTM-like query tables (DM/AE/LB/EX/TR/CM/SIG) with patient-aware aggregation and result caps | NEEDS-REVIEW | Potentially useful as a plain export/QA surface, but currently entangled with the rejected agent panel; adopting tables alone is a separate small decision. |
| 15 | Bilingual regex fallback view commands ("collapse time", "align on confirmed PR", …) | REJECT | Part of agent-panel behavior (owner gate); also brittle phrase matching that would need its own UX review. |
| 16 | Planted synthetic anomalies in the generator (Hy's-law pattern, AE after death, grade-3 irAE without steroid, long dosing gap) | NO-ACTION (data only) | Fixture content was copied under Yue's data-only authorization (preserved as-is in scenario/raw.json); the detection rules that target them remain rejected (row 7). |

---

## 5. Would the external repo improve what the current visualizer already has?

| Local capability | Evidence it exists locally | Does the external repo improve it? |
|---|---|---|
| Clinical engine (pinned analysis rules, analytical roster, replay verification) | demo/app.py Engine with replay_checks (exact_spec_restoration, analysis_reproduction, provenance_verified) | No. The external repo has no analysis engine; its additions in this area are derived metrics + inference rules (rejected scope) and view-only query helpers. |
| Sentinel tiers (tiers 0/1/2, date-priority overrides, fatal-AE → death sentinel) | demo/display-priorities-v1.json tiers + overrides; tier selector in static/index.html | No. External gating is generic zoom levels; its threshold highlighting is review-gated (row 13). Local kind-based priority semantics are stronger. |
| Sorting (six view-only sorts) | static/index.html sort options (duration default, ID asc/desc, best response, time to first PD, discontinuation reason) | Yes, partially. Adopt header-click column sorting and the new keys (peak lab ×ULN, best % change, anchor day, longest dosing gap) as additional view-only sorts (row 12). |
| Interval end states (ongoing flags, end-unknown, no imputation) | demo/display-priorities-v1.json interval_followup_fields + followup_note ("RFENDTC is never used") | No. External intervals end at recorded end/death with no ongoing/end-unknown distinction. |
| Provenance on selection (original_source raw row, derivation_rule_id provenance-v1) | demo/app.py original_source; "Selection and source records" panel in static/index.html | No. External has tooltips and contributor lists but no source lineage. The transferable pattern (aggregate → contributors) is already implemented locally in the lattice chooser. |
| Analytical-count invariants (roster vs displayed denominators, sentinel dedup, explicit denominators) | demo/app.py replay checks; view-controls copy ("Does not change the analysis population or record totals"); COMPARISON-LATTICE summary safeguards | No. External's per-window denominator discipline matches what local already requires; its anchor drop-out (row 8) and arm-percentage rows (row 10) would actively regress local invariants. |

Conclusion for the prototype task: the external repo improves exactly one local capability (sorting breadth and
header-click access) and supplies the conceptual framing for the lattice and its collapsed views. Everything clinical
(engine, tiers, interval end states, provenance, count invariants) is kept as-is; the agent panel and signal-inference
rules stay out pending separate review.

---

## 6. Licensing memo

Status at commit be3744cd7768373552e87201ea0efe90578c094f:

- The pinned tree (16 files, recursive tree API, truncated=false) contains NO LICENSE, COPYING or NOTICE file.
  The GitHub repo API reported "license": null on 2026-10-31. The README contains no reuse grant.
- Consequence: the code is ALL RIGHTS RESERVED by default. Public accessibility is not permission to copy.
- Rule in force for this project: NO source code is copied into the project; concepts are reimplemented from scratch
  at the behavioral level only. This audit and the prototype contain identifiers and behavioral facts, not code.
- Carve-out (data only): Yue explicitly authorized copying the repository's generated synthetic KEYNOTE-189-style
  data as synthetic demo fixtures. That authorization covers generated data only — it is NOT a source-code license.
  Extraction method, commit pin, hashes and attribution are recorded in demo/README.md and demo/scenario/provenance.json.
  The copied data must keep its synthetic disclaimer (not real trial data, not submission-ready) and must not be
  calibrated to published KEYNOTE-189 results.

Evidence that would change this conclusion (must be verified in writing before any code reuse):
1. A license grant from the copyright holder (pzhang724) that explicitly covers the pinned commit — e.g. a LICENSE
   added to the repo with the author's statement that it applies to that commit, or a license present at the commit
   itself on later inspection.
2. Explicit written permission from the copyright holder for source reuse, with scope stated (which files, which
   purposes, attribution requirements).
3. Discovery that this code was separately published under a compatible open-source license, with provenance linking
   that publication to this repository.

Until one of the above is verified in writing: concept-level reimplementation only, no source copying.

Dependency note: this project's own build dependencies (Three.js, GSAP) carry their own licenses as recorded in
COMPARISON-LATTICE.txt; they are unrelated to the external repo's code. (The external lanes page loads Three.js r128
from a CDN; that is noted for completeness, not adopted.)

---

## 7. Limits of this audit

- The external app was not executed; descriptions come from source and README inspection at the pinned commit.
- The GitHub API snapshots are from 2026-10-31; the repository may change after the pinned commit. All reuse rulings
  here are anchored to be3744c specifically.
- No legal advice is implied; "all rights reserved by default" is the conservative engineering rule for reuse.
