#!/usr/bin/env python3
"""Self-verification of golden inputs/oracles. Not the generator or lane-view UI."""
import argparse
import copy
import hashlib
import io
import json
import platform
import re
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent
LOCKED_FILES = ["contract.json", "fixtures.json", "expected_results.json", "schemas.json",
                "evidence.json", "README.txt", "validate.py", "normalized_spec.json"]


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_digest(name):
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


def write_json(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2, ensure_ascii=True,
                                       allow_nan=False) + "\n", encoding="utf-8")


def schema_check(definition, value):
    schemas = load("schemas.json")
    Draft202012Validator({"$schema": schemas["$schema"], "$defs": schemas["$defs"],
                          "$ref": "#/$defs/" + definition},
                         format_checker=FormatChecker()).validate(value)


def seal():
    """Bind example spec and file lock to actual bytes; never rewrite golden inputs/oracle."""
    contract, fixtures = load("contract.json"), load("fixtures.json")
    request = next(x for x in fixtures["requests"] if x["fixture_id"] == "F01_counts")
    spec = {
        "contract_version": contract["contract_version"],
        "snapshot_id": fixtures["snapshot_id"], "snapshot_sha256": file_digest("fixtures.json"),
        "rule_bundle_id": contract["rule_bundle"]["rule_bundle_id"],
        "rule_bundle_version": contract["rule_bundle"]["rule_bundle_version"],
        "rule_bundle_sha256": digest(contract["rule_bundle"]),
        "analysis_state": {
            "population": sorted([[x["STUDYID"], x["USUBJID"]] for x in fixtures["population"]]),
            "ae_predicate": request["ae_predicate"], "temporal_window": None},
        "view_state": {"patient_sort": [{"field": "USUBJID", "direction": "asc"}],
                       "hidden_lanes": [], "focus_patient_keys": [], "display_date_window": None,
                       "selection": {"mark_id": "mark:" + fixtures["snapshot_id"] + ":AE-001-2",
                                     "source_record_ids": ["AE-001-2"]}}}
    schema_check("normalized_spec", spec)
    write_json("normalized_spec.json", spec)
    write_json("manifest.json", {
        "manifest_version": "1.0.0", "snapshot_id": fixtures["snapshot_id"],
        "synthetic_only": True, "seed": fixtures["seed"],
        "snapshot_sha256": spec["snapshot_sha256"],
        "rule_bundle_id": spec["rule_bundle_id"],
        "rule_bundle_version": spec["rule_bundle_version"],
        "rule_bundle_sha256": spec["rule_bundle_sha256"],
        "file_sha256": {name: file_digest(name) for name in LOCKED_FILES},
        "digest_note": "File hashes are exact bytes; rule bundle hash is canonical JSON. Manifest and generated verification outputs are not self-hashed."})


def patient_key(record):
    v = record.get("values", record)
    return (v["STUDYID"], v["USUBJID"])


def complete_date(raw):
    if not isinstance(raw, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def source_key(record):
    v, domain = record["values"], record["dataset"]
    if domain in ("AE", "CM", "EX", "RS"):
        fields = ["STUDYID", "USUBJID", domain + "SEQ"]
    else:
        fields = ["STUDYID", "RDOMAIN", "USUBJID", "IDVAR", "IDVARVAL",
                  "RELID" if domain == "RELREC" else "QNAM"]
    return {field: v[field] for field in fields}


def source_ref(fixtures, record):
    return {"snapshot_id": fixtures["snapshot_id"], "record_id": record["record_id"],
            "dataset": record["dataset"], "row_number": record["row_number"],
            "source_key": source_key(record)}


def analyze(fixtures, state):
    schema_check("analysis_state", state)
    roster = {patient_key(p) for p in fixtures["population"]}
    population = set(map(tuple, state["population"]))
    if not population <= roster:
        raise ValueError("unknown_population_patient")
    ae_rows = [r for r in fixtures["datasets"]["AE"] if patient_key(r) in population]
    predicate, window = state["ae_predicate"], state["temporal_window"]
    anchors = {}
    if window:
        for r in fixtures["datasets"]["EX"]:
            d = complete_date(r["values"].get("EXSTDTC"))
            key = patient_key(r)
            if d is not None and key in population:
                anchors[key] = min(d, anchors.get(key, d))
    qualified, diagnostics, deltas = [], [], {}
    for r in ae_rows:
        v, rid = r["values"], r["record_id"]
        if predicate and v.get(predicate["variable"]) != predicate["value"]:
            continue
        if window:
            d = complete_date(v.get("AESTDTC"))
            if d is None:
                diagnostics.append({"code": "incomplete_event_date", "source_record_id": rid,
                                    "raw_value": v.get("AESTDTC", "")})
                continue
            anchor = anchors.get(patient_key(r))
            if anchor is None:
                diagnostics.append({"code": "missing_anchor", "source_record_id": rid})
                continue
            elapsed = (d - anchor).days
            deltas[rid] = elapsed
            if not window["lower_days"] <= elapsed <= window["upper_days"]:
                continue
        qualified.append(r)
    qualified_ids = sorted({r["record_id"] for r in qualified})
    patients = sorted({patient_key(r) for r in qualified})
    result = {"status": "executed", "population_patient_count": len(population),
              "population_ae_record_count": len(ae_rows),
              "qualifying_patient_keys": [list(p) for p in patients],
              "qualifying_ae_record_ids": qualified_ids, "qualifying_patient_count": len(patients),
              "qualifying_ae_record_count": len(qualified_ids),
              "diagnostics": sorted(diagnostics, key=lambda x: x["source_record_id"])}
    if window:
        result["elapsed_days_by_ae_record_id"] = deltas
    return result


def resolve_selector(fixtures, selector):
    domain, variable = selector["RDOMAIN"], selector["IDVAR"]
    allowed = load("contract.json")["rule_bundle"]["relrec-v1"]["allowed_idvars"]
    if variable not in allowed.get(domain, []):
        raise ValueError("unsupported_idvar")
    result = []
    for r in fixtures["datasets"][domain]:
        v = r["values"]
        if v["STUDYID"] != selector["STUDYID"] or v["USUBJID"] != selector["USUBJID"]:
            continue
        candidate = v.get(variable)
        if variable == domain + "SEQ":
            if not isinstance(candidate, int) or isinstance(candidate, bool):
                raise ValueError("invalid_sequence_type")
            candidate = str(candidate)
        if candidate == selector["IDVARVAL"]:
            result.append(r["record_id"])
    return sorted(result)


def resolve_relationship(fixtures, selector):
    rows = [r for r in fixtures["datasets"]["RELREC"]
            if all(r["values"][k] == v for k, v in selector.items())]
    if not rows:
        raise ValueError("relationship_not_found")
    if any(not r["values"]["USUBJID"] or not r["values"]["IDVARVAL"] for r in rows):
        return {"resolution_status": "unsupported_scope", "raw_relrec_rows": copy.deepcopy(rows),
                "diagnostic": "dataset_scope_not_supported"}
    if len(rows) < 2:
        raise ValueError("incomplete_relationship")
    endpoints = []
    for row in rows:
        v = row["values"]
        s = {k: v[k] for k in ["STUDYID", "RDOMAIN", "USUBJID", "IDVAR", "IDVARVAL"]}
        ids = resolve_selector(fixtures, s)
        endpoints.append({"relrec_source_record_id": row["record_id"], "selector": s,
                          "raw_reltype": v["RELTYPE"],
                          "endpoint_kind": "record" if v["IDVAR"] == v["RDOMAIN"] + "SEQ" else "group",
                          "resolved_source_record_ids": ids, "observed_record_count": len(ids)})
    docs = [doc for doc in fixtures["synthetic_relationship_documentation"]
            if all(doc[k] == v for k, v in selector.items())]
    if len(docs) > 1:
        raise ValueError("conflicting_semantics_documentation")
    doc = docs[0] if docs else None
    return {
        "relationship_id": ":".join([fixtures["snapshot_id"], selector["STUDYID"], selector["USUBJID"], selector["RELID"]]),
        "snapshot_id": fixtures["snapshot_id"],
        "scope": {k: selector[k] for k in ["STUDYID", "USUBJID"]},
        "source_relid": selector["RELID"], "relrec_source_record_ids": [r["record_id"] for r in rows],
        "endpoints": endpoints,
        "resolution_status": "resolved" if all(e["observed_record_count"] > 0 for e in endpoints) else "unresolved",
        "clinical_meaning": doc["clinical_meaning"] if doc else "unknown",
        "clinical_direction": doc["clinical_direction"] if doc else "unknown",
        "semantics_evidence_refs": ["fixtures.json#synthetic_relationship_documentation/" + doc["document_id"]] if doc else [],
        "derivation_rule_id": "relrec-v1"}


def clarification_gate(parameters):
    required = load("contract.json")["rule_bundle"]["time-v1"]["required_parameters"]
    missing = [k for k in required if k not in parameters or parameters[k] is None]
    if not missing:
        schema_check("temporal_window", parameters)
        return {"status": "ready"}
    return {"status": "clarification_required", "normalized_analysis_state": None, "result": None,
            "missing_parameters": missing,
            "questions": ["Which anchor domain and date variable, and first, last or each occurrence?",
                          "Which AE date or interval should be evaluated?",
                          "Before, after or either side; what lower limit and inclusive/exclusive boundaries?",
                          "How should missing/partial dates and missing anchors be handled?"]}


def check_pins(spec):
    contract, fixtures = load("contract.json"), load("fixtures.json")
    if spec["snapshot_id"] != fixtures["snapshot_id"] or spec["snapshot_sha256"] != file_digest("fixtures.json"):
        raise ValueError("snapshot_mismatch")
    for k, v in {"rule_bundle_id": contract["rule_bundle"]["rule_bundle_id"],
                 "rule_bundle_version": contract["rule_bundle"]["rule_bundle_version"],
                 "rule_bundle_sha256": digest(contract["rule_bundle"])}.items():
        if spec[k] != v:
            raise ValueError("rule_bundle_mismatch")


def normalize_spec(spec):
    schema_check("normalized_spec", spec)
    check_pins(spec)
    result = copy.deepcopy(spec)
    result["analysis_state"]["population"].sort()
    result["view_state"]["hidden_lanes"].sort()
    result["view_state"]["focus_patient_keys"].sort()
    fixtures = load("fixtures.json")
    roster = {patient_key(p) for p in fixtures["population"]}
    if not set(map(tuple, result["view_state"]["focus_patient_keys"])) <= roster:
        raise ValueError("unknown_focus_patient")
    analysis = analyze(fixtures, result["analysis_state"])
    selection = result["view_state"]["selection"]
    if selection:
        ids = selection["source_record_ids"]
        if len(ids) != 1 or selection["mark_id"] != "mark:" + spec["snapshot_id"] + ":" + ids[0]:
            raise ValueError("invalid_mark_identity")
        if ids[0] not in analysis["qualifying_ae_record_ids"]:
            raise ValueError("selection_not_eligible")
    window = result["view_state"]["display_date_window"]
    if window and window["start"] > window["end"]:
        raise ValueError("invalid_display_date_window")
    return result


def analysis_signature(spec):
    normalized = normalize_spec(spec)
    return digest({k: v for k, v in normalized.items() if k != "view_state"})


def visible_patients(fixtures, spec):
    keys = analyze(fixtures, spec["analysis_state"])["qualifying_patient_keys"]
    focus = spec["view_state"]["focus_patient_keys"]
    if focus:
        keys = [k for k in keys if k in focus]
    # USUBJID primary key, complete patient-key tie-break. IDs never become row indexes.
    return sorted(keys, key=lambda p: (p[1], p[0]),
                  reverse=spec["view_state"]["patient_sort"][0]["direction"] == "desc")


def pick(fixtures, spec, mark_id):
    check_pins(spec)
    rows = fixtures["datasets"]["AE"]
    eligible = analyze(fixtures, spec["analysis_state"])["qualifying_ae_record_ids"]
    visible = visible_patients(fixtures, spec)
    for row in rows:
        if mark_id == "mark:" + fixtures["snapshot_id"] + ":" + row["record_id"]:
            if row["record_id"] not in eligible or list(patient_key(row)) not in visible or "AE" in spec["view_state"]["hidden_lanes"]:
                raise ValueError("mark_not_pickable")
            window = spec["view_state"]["display_date_window"]
            if window and not window["start"] <= row["values"]["AESTDTC"] <= window["end"]:
                raise ValueError("mark_not_pickable")
            return source_ref(fixtures, row)
    raise ValueError("unknown_mark")


class GoldenContractChecks(unittest.TestCase):
    def setUp(self):
        self.c, self.f, self.o = load("contract.json"), load("fixtures.json"), load("expected_results.json")
        self.expected = self.o["fixtures"]
        self.spec = load("normalized_spec.json")
        self.requests = {r["fixture_id"]: r for r in self.f["requests"]}

    def assert_expected_subset(self, actual, expected):
        for key, value in actual.items():
            self.assertIn(key, expected)
            self.assertEqual(value, expected[key], key)

    def test_01_schema_and_manifest_integrity(self):
        schemas = load("schemas.json")
        Draft202012Validator.check_schema(schemas)
        manifest = load("manifest.json")
        self.assertEqual(set(manifest["file_sha256"]), set(LOCKED_FILES))
        for name, sha in manifest["file_sha256"].items():
            self.assertEqual(file_digest(name), sha, name)
        self.assertEqual(manifest["snapshot_sha256"], file_digest("fixtures.json"))
        self.assertEqual(manifest["rule_bundle_sha256"], digest(self.c["rule_bundle"]))
        self.assertEqual(self.c["fixture_ids"], list(self.expected))
        self.assertEqual(set(self.c["fixture_ids"]), set(self.requests))
        self.assertEqual(self.c["contract_version"], self.o["contract_version"])
        self.assertEqual(self.f["snapshot_id"], self.o["snapshot_id"])
        self.assertEqual(self.f["seed"], self.c["snapshot"]["seed"])

    def test_02_fixture_identity_and_provenance(self):
        self.assertIs(self.f["synthetic_only"], True)
        self.assertEqual(set(self.f["datasets"]), set(self.c["scope"]["required_datasets"]))
        self.assertEqual({d: len(rs) for d, rs in self.f["datasets"].items()}, self.o["dataset_counts"])
        roster = {patient_key(p) for p in self.f["population"]}
        self.assertEqual(len(roster), len(self.f["population"]))
        ids, keys = set(), set()
        for domain, rows in self.f["datasets"].items():
            for n, row in enumerate(rows, 1):
                schema_check("record_envelope", row)
                self.assertEqual(row["dataset"], domain)
                self.assertEqual(row["row_number"], n)
                self.assertNotIn(row["record_id"], ids)
                ids.add(row["record_id"])
                self.assertIn(patient_key(row), roster)
                key = (domain, canonical(source_key(row)))
                self.assertNotIn(key, keys)
                keys.add(key)
                ref = source_ref(self.f, row)
                schema_check("source_record_ref", ref)
                self.assertEqual(rows[ref["row_number"] - 1]["record_id"], ref["record_id"])
                if domain in ("AE", "CM", "EX", "RS"):
                    self.assertEqual(row["values"]["DOMAIN"], domain)
                    self.assertIs(type(row["values"][domain + "SEQ"]), int)
                if domain == "SUPPAE":
                    self.assertRegex(row["values"]["QNAM"], r"^[A-Za-z_][A-Za-z_0-9]{0,7}$")
                    self.assertTrue(row["values"]["QVAL"])
        for doc in self.f["synthetic_relationship_documentation"]:
            self.assertIs(doc["synthetic_only"], True)

    def test_03_patient_vs_ae_record_counts(self):
        actual = analyze(self.f, self.spec["analysis_state"])
        self.assert_expected_subset(actual, self.expected["F01_counts"])
        self.assertNotEqual(actual["qualifying_patient_count"], actual["qualifying_ae_record_count"])

    def test_04_relationship_golden_outputs(self):
        for fid in ["F02_group_endpoint", "F03_blank_reltype", "F04_undocumented_meaning"]:
            with self.subTest(fixture=fid):
                actual = resolve_relationship(self.f, self.requests[fid]["relationship_selector"])
                schema_check("relationship", actual)
                self.assertEqual(actual, self.expected[fid])

    def test_05_group_scope_collision_and_no_count_inflation(self):
        group = resolve_relationship(self.f, self.requests["F02_group_endpoint"]["relationship_selector"])
        self.assertEqual(group["endpoints"][1]["resolved_source_record_ids"], ["CM-001-1", "CM-001-2"])
        collision = resolve_relationship(self.f, {"STUDYID": "SYN-SPIKE", "USUBJID": "SYN-002", "RELID": "RG"})
        self.assertEqual(collision["relrec_source_record_ids"], ["REL-7", "REL-8"])
        self.assertEqual(collision["endpoints"][1]["resolved_source_record_ids"], ["CM-002-1"])
        self.assertEqual(collision["clinical_meaning"], "unknown")
        # Count qualifying IDs after a simulated one-to-many join; deduplication is mandatory.
        expanded = ["AE-001-1", "AE-001-1", "AE-001-2", "AE-002-1"]
        self.assertEqual(len(set(expanded)), self.expected["F01_counts"]["qualifying_ae_record_count"])
        self.assertNotEqual(len(expanded), self.expected["F01_counts"]["qualifying_ae_record_count"])

    def test_06_raw_blanks_and_documentation_not_inferred(self):
        before = canonical(self.f)
        for r in self.f["datasets"]["RELREC"]:
            self.assertEqual(r["values"]["RELTYPE"], "")
        mutated = copy.deepcopy(self.f)
        mutated["synthetic_relationship_documentation"] = []
        result = resolve_relationship(mutated, self.requests["F03_blank_reltype"]["relationship_selector"])
        self.assertEqual(result["clinical_meaning"], "unknown")
        self.assertEqual(result["clinical_direction"], "unknown")
        self.assertEqual(result["semantics_evidence_refs"], [])
        self.assertEqual(result["resolution_status"], "resolved")
        self.assertEqual(canonical(self.f), before)

    def test_07_unresolved_group_preserves_evidence(self):
        mutated = copy.deepcopy(self.f)
        mutated["datasets"]["RELREC"][1]["values"]["IDVARVAL"] = "NO-SUCH-GROUP"
        result = resolve_relationship(mutated, self.requests["F02_group_endpoint"]["relationship_selector"])
        schema_check("relationship", result)
        self.assertEqual(result["resolution_status"], "unresolved")
        self.assertEqual(result["endpoints"][1]["selector"]["IDVARVAL"], "NO-SUCH-GROUP")
        self.assertEqual(result["endpoints"][1]["resolved_source_record_ids"], [])
        self.assertEqual(result["relrec_source_record_ids"], ["REL-1", "REL-2"])

    def test_08_dataset_scope_fails_closed(self):
        mutated = copy.deepcopy(self.f)
        for row in mutated["datasets"]["RELREC"][:2]:
            row["values"]["USUBJID"] = ""
            row["values"]["IDVARVAL"] = ""
        result = resolve_relationship(mutated, {"STUDYID": "SYN-SPIKE", "USUBJID": "", "RELID": "RG"})
        schema_check("unsupported_relationship", result)
        self.assertEqual(result["resolution_status"], "unsupported_scope")
        self.assertEqual(result["raw_relrec_rows"], mutated["datasets"]["RELREC"][:2])

    def test_09_ambiguous_time_clarification(self):
        actual = clarification_gate(self.requests["F05_ambiguous_time"]["temporal_parameters"])
        schema_check("clarification", actual)
        expected = self.expected["F05_ambiguous_time"]
        for k in ("status", "normalized_analysis_state", "result", "missing_parameters"):
            self.assertEqual(actual[k], expected[k])
        self.assertEqual(len(actual["questions"]), 4)
        complete = self.requests["F06_explicit_time"]["temporal_window"]
        self.assertEqual(clarification_gate(complete), {"status": "ready"})
        for key in complete:
            missing = dict(complete)
            del missing[key]
            self.assertIn(key, clarification_gate(missing)["missing_parameters"])

    def test_10_explicit_time_boundaries_and_partial_dates(self):
        state = copy.deepcopy(self.spec["analysis_state"])
        request = self.requests["F06_explicit_time"]
        state.update(ae_predicate=request["ae_predicate"], temporal_window=request["temporal_window"])
        self.assert_expected_subset(analyze(self.f, state), self.expected["F06_explicit_time"])
        self.assertIsNone(complete_date("2025-02-30"))
        self.assertIsNone(complete_date("2025-02"))

    def test_11_suppqual_parent_no_new_events(self):
        row = next(r for r in self.f["datasets"]["SUPPAE"] if r["record_id"] == self.requests["F08_suppqual"]["source_record_id"])
        v = row["values"]
        actual = {"supplement_source_record_id": row["record_id"],
                  "parent_source_record_ids": resolve_selector(self.f, v),
                  "qualifier": {k: v[k] for k in ("QNAM", "QVAL", "QORIG", "QEVAL")},
                  "ae_record_count_before": len(self.f["datasets"]["AE"]),
                  "ae_record_count_after": len(self.f["datasets"]["AE"])}
        self.assert_expected_subset(actual, self.expected["F08_suppqual"])

    def test_12_spec_exact_restore_and_analysis_reproduction(self):
        normalized = normalize_spec(self.spec)
        self.assertEqual(normalized, self.spec)
        serialized = canonical(normalized)
        restored = normalize_spec(json.loads(serialized))
        self.assertEqual(canonical(restored), serialized)
        self.assertEqual(analyze(self.f, normalized["analysis_state"]), analyze(self.f, restored["analysis_state"]))
        self.assertEqual(analysis_signature(normalized), analysis_signature(restored))

    def test_13_view_sort_peel_focus_and_stable_pick(self):
        spec = copy.deepcopy(self.spec)
        golden = self.expected["F07_view_replay_picking"]
        self.assertEqual(visible_patients(self.f, spec), golden["base_eligible_patient_order"])
        baseline = analyze(self.f, spec["analysis_state"])
        signature = analysis_signature(spec)
        spec["view_state"]["patient_sort"][0]["direction"] = "desc"
        self.assertEqual(visible_patients(self.f, spec), golden["operations"][0]["visible_patient_order"])
        spec["view_state"]["hidden_lanes"] = ["CM"]
        spec["view_state"]["focus_patient_keys"] = [["SYN-SPIKE", "SYN-001"]]
        self.assertEqual(visible_patients(self.f, spec), golden["operations"][1]["visible_patient_order"])
        self.assertEqual(analyze(self.f, spec["analysis_state"]), baseline)
        self.assertEqual(analysis_signature(spec), signature)
        picked = pick(self.f, spec, golden["operations"][2]["mark_id"])
        self.assertEqual(picked["record_id"], golden["operations"][2]["source_record_ids"][0])
        self.assertEqual(picked["row_number"], golden["operations"][2]["source_row_number"])
        self.assertEqual(picked["source_key"], golden["operations"][2]["source_key"])
        spec["view_state"]["hidden_lanes"] = ["AE", "CM"]
        self.assertEqual(analysis_signature(spec), signature)
        self.assertIsNotNone(spec["view_state"]["selection"])
        with self.assertRaisesRegex(ValueError, "mark_not_pickable"):
            pick(self.f, spec, golden["operations"][2]["mark_id"])

    def test_14_analytical_filter_clears_selection_never_retargets(self):
        spec = copy.deepcopy(self.spec)
        spec["analysis_state"]["population"] = [["SYN-SPIKE", "SYN-002"]]
        actual = analyze(self.f, spec["analysis_state"])
        expected = self.expected["F07_view_replay_picking"]["operations"][3]
        self.assertEqual(actual["qualifying_patient_count"], expected["qualifying_patient_count"])
        self.assertEqual(actual["qualifying_ae_record_count"], expected["qualifying_ae_record_count"])
        self.assertEqual(actual["qualifying_ae_record_ids"], expected["qualifying_ae_record_ids"])
        with self.assertRaisesRegex(ValueError, "selection_not_eligible"):
            normalize_spec(spec)
        reason = None
        if not set(spec["view_state"]["selection"]["source_record_ids"]) <= set(actual["qualifying_ae_record_ids"]):
            spec["view_state"]["selection"] = None
            reason = "analysis_excluded"
        self.assertEqual(spec["view_state"]["selection"], expected["selection"])
        self.assertEqual(reason, expected["selection_cleared_reason"])
        self.assertNotEqual(analysis_signature(spec), analysis_signature(self.spec))
        with self.assertRaisesRegex(ValueError, "mark_not_pickable"):
            pick(self.f, spec, "mark:synthetic-spike-v1:AE-001-2")

    def test_15_pin_mismatches_rejected(self):
        for field, value, error in [("snapshot_id", "different-snapshot", "snapshot_mismatch"),
                                     ("snapshot_sha256", "0" * 64, "snapshot_mismatch"),
                                     ("rule_bundle_sha256", "0" * 64, "rule_bundle_mismatch")]:
            with self.subTest(field=field):
                mutated = copy.deepcopy(self.spec)
                mutated[field] = value
                with self.assertRaisesRegex(ValueError, error):
                    normalize_spec(mutated)

    def test_16_unknown_state_fields_and_semantic_inventions_rejected(self):
        mutated = copy.deepcopy(self.spec)
        mutated["view_state"]["ae_predicate"] = {"variable": "AESEV", "operator": "eq", "value": "MILD"}
        with self.assertRaises(Exception):
            schema_check("normalized_spec", mutated)
        invented = copy.deepcopy(self.expected["F04_undocumented_meaning"])
        invented["clinical_meaning"] = "medication_used_to_treat_ae"
        with self.assertRaises(Exception):
            schema_check("relationship", invented)
        mutated = copy.deepcopy(self.spec)
        mutated["view_state"]["selection"]["mark_id"] = "mark:synthetic-spike-v1:AE-002-1"
        with self.assertRaisesRegex(ValueError, "invalid_mark_identity"):
            normalize_spec(mutated)

    def test_17_display_clip_does_not_filter_analysis(self):
        clipped = copy.deepcopy(self.spec)
        clipped["view_state"]["display_date_window"] = {"start": "2025-01-30", "end": "2025-02-01"}
        self.assertEqual(analysis_signature(clipped), analysis_signature(self.spec))
        self.assertEqual(analyze(self.f, clipped["analysis_state"]), analyze(self.f, self.spec["analysis_state"]))
        with self.assertRaisesRegex(ValueError, "mark_not_pickable"):
            pick(self.f, clipped, "mark:synthetic-spike-v1:AE-001-2")

    def test_18_normalization_and_zero_not_clarification(self):
        spec = copy.deepcopy(self.spec)
        spec["analysis_state"]["population"].reverse()
        spec["view_state"]["hidden_lanes"] = ["RS", "CM"]
        normalized = normalize_spec(spec)
        self.assertEqual(normalized["analysis_state"]["population"], self.spec["analysis_state"]["population"])
        self.assertEqual(normalized["view_state"]["hidden_lanes"], ["CM", "RS"])
        empty = copy.deepcopy(self.spec["analysis_state"])
        empty["population"] = [["SYN-SPIKE", "SYN-003"]]
        result = analyze(self.f, empty)
        self.assertEqual(result["status"], "executed")
        self.assertEqual(result["qualifying_patient_count"], 0)
        self.assertEqual(result["qualifying_ae_record_count"], 0)
        self.assertEqual(result["population_patient_count"], 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seal", action="store_true", help="Rebind example spec and manifest to present source bytes before checks")
    args = parser.parse_args()
    if args.seal:
        seal()
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(GoldenContractChecks)
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    transcript = stream.getvalue()
    print(transcript, end="")
    (ROOT / "verification.txt").write_text(transcript, encoding="utf-8")
    success = result.wasSuccessful()
    report = {
        "status": "PASS" if success else "CHANGES_REQUIRED", "review_independent": False,
        "scope": "Golden contract/fixture self-verification and reference harness only; not downstream generator, UI or submission validation",
        "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "python_version": platform.python_version(),
        "command": "python3 validate.py" + (" --seal" if args.seal else ""),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "transcript_file": "verification.txt", "transcript_sha256": file_digest("verification.txt"),
        "snapshot_sha256": file_digest("fixtures.json"),
        "rule_bundle_sha256": digest(load("contract.json")["rule_bundle"]),
        "analysis_signature": analysis_signature(load("normalized_spec.json")) if success else None,
        "not_checked": ["Google Antigravity execution", "downstream synthetic generator", "rendered UI/pixel picking", "full SDTM conformance", "independent third-party review"]}
    write_json("verification.json", report)
    print("Verification evidence:", ROOT / "verification.json")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
