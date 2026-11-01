# Source record — external repo audit

All retrievals 2026-10-31 EDT unless noted. Findings document: AUDIT-EXTERNAL-REPO.md.

Release note: paths of the form `demo/...` in this record are relative to the repository root in this
public release. Internal task identifiers and local machine paths from the build have been removed.

## External sources

S1. Repo: https://github.com/pzhang724/patient-profile-linkage
S2. Pinned commit: be3744cd7768373552e87201ea0efe90578c094f — "Add patient lanes and patient x domain x time event
    cube on synthetic KN189-style data", 2026-10-31 11:38:51 -0400 (verified via local `git log -1` on a clean clone).
S3. Recursive tree API (retrieved 2026-10-31):
    https://api.github.com/repos/pzhang724/patient-profile-linkage/git/trees/be3744cd7768373552e87201ea0efe90578c094f?recursive=1
    Evidence: identifies the exact SHA, "truncated": false, 16 blobs; NO LICENSE/COPYING/NOTICE path in the tree.
S4. Repo API (retrieved 2026-10-31): https://api.github.com/repos/pzhang724/patient-profile-linkage
    Evidence: "license": null, "visibility": "public", default_branch "main", language JavaScript.
S5. README at commit (raw): https://raw.githubusercontent.com/pzhang724/patient-profile-linkage/be3744cd7768373552e87201ea0efe90578c094f/README.md
    Evidence passages (paraphrased/short quotes):
    - "Interactive patient-profile views built on synthetic KEYNOTE-189-style raw data (60 patients,
      pembrolizumab or placebo + pemetrexed + platinum, 2:1). No real trial data is used."
    - Pages table: patient-lanes.html (lanes, semantic zoom, subset/sort/signals, 3D layered view); event-cube.html
      ("patient x domain x time cube. Collapse one dimension at a time, re-align time on an event, and drive the view
      from an agent panel").
    - Event cube views: full cube; Patient x Time (domains merged); Patient x Domain (time collapsed matrix,
      click header to sort); Domain x Time ("% of each arm per time window", click a cell to drill back into lanes).
    - Alignment: randomization, first grade >=3 AE, first immune-related AE, first AE of a chosen term, confirmed PR
      ("PR or CR confirmed by a scan at least 28 days later"), progression, crossover; "Patients without the chosen
      event drop out of the view."
    - Agent panel: Claude with page tools query_data (DM, AE, LB, EX, TR, CM, SIG), set_view, show_patients,
      open_patient; plain-HTML fallback commands ("collapse time", "align on confirmed PR", "sort by peak ALT",
      "only placebo").
    - Data: generator is seeded (60 patients); "plants a few known issues for the signal engine to find: a potential
      Hy's law case, an AE starting after death, a grade 3 immune-related AE with no steroid recorded, and a dosing
      gap over 6 weeks."
    - No license or reuse terms anywhere in the README.
S6. Local clone of S1 at S2 (read-only inspection; kept OUTSIDE the project, in a researcher scratch directory
    that is not part of this release).

## External code locations inspected (identifiers/behavioral facts only; no code copied)

E1. src/cube/c0_data.js — seeded generator (rngFrom(189); makePatient x60), planted-anomaly IIFE ("plant"), derived
    metrics + signal engine. Signal rules evidenced: Hy's law (ALT >3xULN + bilirubin >2xULN same visit -> crit);
    AE start after death day -> crit; grade >=3 immune AE without Prednisone starting within [start-3, start+14] ->
    warn; non-crossover dose-day gap >42 -> warn; dosing after documented PD -> info; crossover -> info. Planted
    anomalies: Hy's-law labs (ALT 172 / 4.3x, AST 150 / 3.75x, BILI 2.9 / 2.42x ULN) + grade-3 immune hepatitis +
    Prednisone; AE ("Fatigue") starting death day +9; grade-3 immune Colitis with no steroid; later cycles shifted
    +35 days. The no-Prednisone rule excludes thyroid terms.
E2. src/cube/c2_cube.js — Flat tables TB (DM, AE, LB, EX, TR, CM, SIG) constructed at lines 46–55; anchorDay (7 alignment anchors incl. confirmed-PR rule requiring a later confirming scan
    >=28 days); FEAT: 13 feature columns (cycles, longest gap, AE count, worst grade, worst immune grade, peak
    ALT/CREAT/TSH xULN, lowest ANC xLLN, best % change, best response, steroid days, treatment meds); MEAS: 7 window
    measures (dosed; grade>=3 AE ongoing; immune AE ongoing; lab outside range, denominator = assessed in window;
    responding at scan, denominator = scan in window; progressed so far; on corticosteroid); observed() censoring
    (window start <= last day, window end > -14).
E3. src/cube/c3_lanes.js — semantic zoom levels via level() (pixels-per-day <0.8 overview / <3 events / else detail);
    per-domain draw functions with peeled (packed sub-lanes) vs merged rendering; DS sentinels (PD diamond, crossover,
    death cross, alive tick); signal severity rings.
E4. src/cube/c4_views.js — patient x domain matrix (ALERT thresholds: alt>=3, cre>=1.5, tsh>=2, anc<1, gap>42,
    mxg>=3, irg>=3; header-click sortBy; per-cell mini-bars); domain x time summary (per arm x measure rows;
    "patients observed" count row; 7/21-day bins by zoom; num/den with percent; small-n thinning when den<3;
    click cell -> drill(ids) to lanes; denominators "assessed in window" vs "observed in window").
E5. src/cube/c5_agent.js — TOOLS: query_data (where ops eq/ne/gt/ge/lt/le/in/contains/is_null/not_null; aggs
    count/patients/max/min/mean/median; group_by; caps 50 groups / 80 USUBJIDs / <=40 rows), set_view, show_patients,
    open_patient; rules() system prompt (table dictionary; "Query before stating any number"; give denominators;
    2-5 sentence answers; never invent data); localCommand() bilingual regex fallback ("collapse time", "align on
    confirmed PR", "sort by peak ALT", "only placebo"); 12-turn memory cap; abort; error-code handling.
E6. src/cube/c6_app.js — anim() tween (~300 ms, cubic ease-out, log-scale zoom, prefers-reduced-motion honored; runs
    to completion, not input-interruptible); zoom presets fit/overview/events/detail; drill(ids,label) sets a
    "Selection:" view filter; openPatient() animates to the patient row; MODES radio (PDT/PT/PD/DT) with collapse
    descriptions; patient card with "n of ROWS", anchor day, event list; signal list with focusSignal() camera move.
E7. src/lanes/p4_app.js — three.js scene (T3): PerspectiveCamera(38), orbit params th/ph/r, drag rotates, wheel/
    pinch dollies radius, raycaster picking on instanced meshes, one translucent plane per domain stacked in Y with
    eased "spread" gap animation, PD/death pillars cutting all layers, selection slab, projected layer labels.
    No canonical camera presets or projection-driven view semantics in the 3D scene.
E8. build.sh — docs/*.html are concatenation of src/ parts (wrap + cat); docs are build outputs, not separate code.

## Local-side sources (current visualizer evidence)

L1. demo/display-priorities-v1.json — tiers 0/1/2 with zoom gating; AE.AETOXGR=5 override -> death kind with
    date_priority [DTHDTC, AEENDTC] and replace_ae_tick; AESEV=SEVERE tier escalation; mid_zoom_max_days 90;
    close_zoom_max_days 30; default_sort "duration"; response_order CR/PR/SD/PD/NE; interval_followup_fields
    (AE: AEONGO/AEFUDTC; CM: CMONGO/CMFUDTC) and followup_note ("RFENDTC is never used. No end date and no
    documented ongoing follow-up means end unknown.").
L2. demo/static/index.html — six patient sorts (Treatment duration default; Patient ID asc; Patient ID desc; Best
    overall response CR/PR/SD/PD/NE; Time to first PD earliest first; Discontinuation reason alphabetical) with
    "Changes what you see. Does not change the analysis population or record totals."; tier selector
    (auto / sentinel only / 0+1 / all); "Selection and source records" section with "Open source records".
L3. demo/static/app.js — displaySort handling (duration/pd/response/reason/asc/desc), "View-only patient sort
    changed. Analysis unchanged." status on sort.
L4. demo/app.py — Engine class; original_source deep copy on selection (lines ~170-171);
    derivation_rule_id 'provenance-v1'; replay_checks {exact_spec_restoration, analysis_reproduction,
    provenance_verified} (lines ~283-284).
L5. demo/COMPARISON-LATTICE.txt — existing event-cube comparison and reuse boundary (pinned URLs, no LICENSE in
    tree, adopted/rejected lists, summary safeguards, dependency license note).
L6. demo/README.md — synthetic-data provenance for the copied fixture (source repo + commit, generator entrypoint
    src/cube/c0_data.js seed 189, extraction method, raw SHA-256 4dd5639d3b9799ee6c8b31615659d2433452fd6e077aca1ba8cb7d26064fbb54,
    recomputed counts 60 patients / 260 AE / 80 CM / 1771 EX / 391 TR / 4962 LB; synthetic disclaimer).
L7. Owner instruction record for the audit and integration tasks: data-only authorization for the synthetic
    fixture by the project owner; agent-panel behavior and signal-inference rules require separate review;
    lattice and camera requirements.

## Uncertainty register

U1. External app not executed; all behavioral claims are source/README-level, not runtime-verified.
U2. GitHub API values are point-in-time (2026-10-31); later commits could add a license — re-verify before reuse.
U3. "All rights reserved by default" is the conservative engineering reading (no license = no permission granted);
    it is not legal advice.
U4. Whether a future license added by the author would retroactively cover commit be3744c is the author's call —
    hence the "verified in writing" requirement in the licensing memo.
