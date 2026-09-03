"""Offline Table-2 routing reconstruction for PersonaMem-v2.

No LLM calls. The query phase is read-only (memory_unchanged_during_queries is true on
every row), so a frozen routing policy's deployed output is exactly the existing paired
branch outcome selected per decision.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/aristella/recoverappworld")

from recovermem.integrations.personamem_v2.analysis import (
    decision_key, feature_record, to_personas,
)
from recovermem.metrics.risk import coverage, fs, any_fs_rate
from recovermem.scoring.predictor import RecoverabilityPredictor

ROOT = Path("/home/aristella/recoverappworld/personamem_recovermem_outputs")
FORMAL = ROOT / "formal"
FROZEN = ROOT / "frozen_protocol"
OUT = ROOT / "table2"
ALPHA = 0.10


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def tau_of(entry):
    v = entry["tau"]
    return float("inf") if v == "Infinity" else (float("-inf") if v == "-Infinity" else float(v))


def main():
    rows = [json.loads(l) for l in (FORMAL / "final_test.jsonl").read_text().splitlines() if l.strip()]
    thresholds = json.loads((FORMAL / "thresholds.json").read_text())
    table1 = json.loads((FORMAL / "table1_rows.json").read_text())
    rnd = json.loads((FORMAL / "calibration_artifacts" / "random_scores.json").read_text())["scores"]
    amend = json.loads((FROZEN / "AMENDMENT_A1.json").read_text())

    # ---- provenance / invariants ----------------------------------------
    personas = [int(p) for p in amend["persona_subsets"]["final_test"]]
    selected = amend["selected_questions"]["final_test"]
    n_selected = sum(len(selected[str(p)]["selected_question_ids"]) for p in personas)

    seen = {(r["persona_id"], r["question_id"]) for r in rows}
    expected = {(p, q) for p in personas for q in selected[str(p)]["selected_question_ids"]}

    inv = {
        "n_rows": len(rows),
        "n_personas": len({r["persona_id"] for r in rows}),
        "expected_personas": len(personas),
        "expected_selected_questions": n_selected,
        "all_selected_question_ids_present": seen == expected,
        "missing_selected": sorted(f"{p}::{q}" for p, q in (expected - seen)),
        "unexpected_rows": sorted(f"{p}::{q}" for p, q in (seen - expected)),
        "memory_unchanged_during_queries": all(r["memory_unchanged_during_queries"] for r in rows),
        "mem0_count_pre_equals_post": all(
            r["mem0_memory_count"] == r["mem0_memory_count_after_queries"] for r in rows),
        "pair_valid_all": all(r["pair_valid"] for r in rows),
        "paired_branches_share_frozen_state": all(
            r["state_hash"] == r["memory_branch_state_hash"] == r["recovery_branch_state_hash"]
            for r in rows),
        "distinct_state_hashes": len({r["state_hash"] for r in rows}),
        "query_phase_write_path_absent": None,   # filled below by source inspection
        "b_mem_respected": all(r["memory_evidence_tokens"] <= r["b_mem"] for r in rows),
        "b_rec_respected": all(r["recovery_evidence_tokens"] <= r["b_rec"] for r in rows),
        "budgets": sorted({(r["b_mem"], r["b_rec"]) for r in rows})[0],
        "parser_failures_inherited": sum(
            (not r["memory_parse_ok"]) + (not r["recovery_parse_ok"]) for r in rows),
        "external_api_calls": 0, "llm_judge_calls": 0, "multimodal_calls": 0,
    }

    # Static check: the per-question path (V2Runner.run_instance) must contain no host write.
    src = Path("/home/aristella/recoverappworld/recovermem/integrations/personamem_v2/runner.py").read_text()
    body = src.split("def run_instance(")[1]
    inv["query_phase_write_path_absent"] = ("host.write" not in body) and ("host.add" not in body)
    inv["query_phase_calls"] = sorted(
        {c for c in ("self.host.retrieve", "self.host.write", "self.recovery.recover")
         if c in body})

    for k in ("all_selected_question_ids_present", "memory_unchanged_during_queries",
              "pair_valid_all", "paired_branches_share_frozen_state",
              "query_phase_write_path_absent", "mem0_count_pre_equals_post"):
        if not inv[k]:
            raise SystemExit(f"INVARIANT FAILED: {k}")
    if inv["distinct_state_hashes"] != len(rows):
        raise SystemExit("INVARIANT FAILED: duplicate state hashes")

    inv["hashes"] = {
        "parent_split": amend["parent_split"]["split_hash"],
        "amendment_a1": sha(FROZEN / "AMENDMENT_A1.json"),
        "question_selection": (FROZEN / "AMENDMENT_A1.question_selection.sha256").read_text().split()[0],
        "scorer": sha(FORMAL / "scorer.json"),
        "thresholds": sha(FORMAL / "thresholds.json"),
        "random_scores": sha(FORMAL / "calibration_artifacts" / "random_scores.json"),
        "final_test_jsonl": sha(FORMAL / "final_test.jsonl"),
    }
    inv["hashes_match_thresholds_record"] = {
        "scorer": inv["hashes"]["scorer"] == thresholds["scorer_hash"],
        "random_scores": inv["hashes"]["random_scores"] == thresholds["random_scores_hash"],
        "amendment": inv["hashes"]["amendment_a1"] == thresholds["amendment_hash"],
    }

    # ---- frozen scores ---------------------------------------------------
    pred = RecoverabilityPredictor.load(FORMAL / "scorer.json")
    model_scores = pred.predict_scores([feature_record(r) for r in rows])
    rand_scores = [rnd[decision_key(r)] for r in rows]

    taus = {
        "Always Trust": (float("-inf"), "model"),
        "Always Recover": (float("inf"), "model"),
        "Empirical-risk": (tau_of(thresholds["rules"][f"empirical_risk@{ALPHA}"]), "model"),
        "Random score + CRC": (tau_of(thresholds["rules"][f"random_crc@{ALPHA}"]), "random"),
        "ReCoverMem + CRC": (tau_of(thresholds["rules"][f"marginal_crc@{ALPHA}"]), "model"),
    }

    # ---- routed decisions ------------------------------------------------
    routed = []
    for i, r in enumerate(rows):
        rec = {
            "persona_id": r["persona_id"], "question_id": r["question_id"],
            "decision_key": decision_key(r),
            "model_score": model_scores[i], "random_score": rand_scores[i],
            "r_mem": r["r_mem"], "r_rec": r["r_rec"],
            "memory_choice": r["memory_choice"], "recovery_choice": r["recovery_choice"],
            "correct_letter": r["correct_letter"],
            "memory_parse_ok": r["memory_parse_ok"], "recovery_parse_ok": r["recovery_parse_ok"],
            "policies": {},
        }
        for name, (tau, kind) in taus.items():
            s = model_scores[i] if kind == "model" else rand_scores[i]
            trust = s >= tau
            rec["policies"][name] = {
                "score_used": s, "tau": tau if tau not in (float("inf"), float("-inf"))
                else ("Infinity" if tau > 0 else "-Infinity"),
                "route": "TRUST" if trust else "RECOVER",
                "correct": int(r["r_mem"] if trust else r["r_rec"]),
                "branch_used": "MEMORY" if trust else "RECOVERY",
            }
        routed.append(rec)

    # ---- persona-equal aggregation --------------------------------------
    order, buckets = [], {}
    for rec in routed:
        p = rec["persona_id"]
        if p not in buckets:
            buckets[p] = []
            order.append(p)
        buckets[p].append(rec)

    results = {}
    for name in taus:
        per_persona = {}
        for p in order:
            g = buckets[p]
            T = len(g)
            K = sum(1 for x in g if x["policies"][name]["route"] == "RECOVER")
            C = sum(x["policies"][name]["correct"] for x in g)
            per_persona[p] = {"T_i": T, "K_i": K, "Rec_i": K / T,
                              "Cov_i": (T - K) / T, "Task_i": C / T, "n_correct": C}
        results[name] = {
            "Task": sum(v["Task_i"] for v in per_persona.values()) / len(per_persona),
            "Rec": sum(v["Rec_i"] for v in per_persona.values()) / len(per_persona),
            "Cov_reconstructed": sum(v["Cov_i"] for v in per_persona.values()) / len(per_persona),
            "n_recover_decisions": sum(v["K_i"] for v in per_persona.values()),
            "n_trust_decisions": sum(v["T_i"] - v["K_i"] for v in per_persona.values()),
            "per_persona": {str(k): v for k, v in per_persona.items()},
        }

    # ---- Table-1 coverage cross-check -----------------------------------
    t1 = {("Always Trust", None): "Always Trust", ("Always Recover", None): "Always Recover",
          ("Empirical-risk", ALPHA): "Empirical-risk",
          ("Random score + CRC", ALPHA): "Random score + CRC",
          ("ReCoverMem + marginal CRC", ALPHA): "ReCoverMem + CRC"}
    check = {}
    for row in table1:
        key = (row["rule"], row["alpha"])
        if key not in t1:
            continue
        name = t1[key]
        rc = results[name]["Cov_reconstructed"]
        check[name] = {
            "table1_Cov": row["Cov"], "reconstructed_Cov": rc,
            "abs_diff": abs(row["Cov"] - rc), "exact_match": row["Cov"] == rc,
            "reconstructed_Rec": results[name]["Rec"],
            "one_minus_table1_Cov": 1.0 - row["Cov"],
            "Rec_plus_Cov_minus_1": results[name]["Rec"] + rc - 1.0,
        }
        # also verify FS reproduces, as a second independent check on tau semantics
        eps = to_personas(rows, model_scores if name != "Random score + CRC" else rand_scores)
        tau = taus[name][0]
        check[name]["table1_FS"] = row["FS"]
        check[name]["reconstructed_FS"] = fs(eps, tau)
        check[name]["FS_abs_diff"] = abs(fs(eps, tau) - row["FS"])
        check[name]["FS_exact_match"] = fs(eps, tau) == row["FS"]
        check[name]["reconstructed_any_FS"] = any_fs_rate(eps, tau)
        check[name]["table1_any_FS"] = row["any_FS"]

    bad = [k for k, v in check.items() if v["abs_diff"] > 1e-12 or v["FS_abs_diff"] > 1e-12
           or v["reconstructed_any_FS"] != v["table1_any_FS"]
           or abs(v["Rec_plus_Cov_minus_1"]) > 1e-12]
    if bad:
        raise SystemExit(f"ROUTING RECONSTRUCTION MISMATCH vs Table 1: {bad}\n"
                         + json.dumps(check, indent=2))

    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "routed_decisions.jsonl").open("w") as fh:
        for rec in routed:
            fh.write(json.dumps(rec) + "\n")
    (OUT / "invariants.json").write_text(json.dumps(inv, indent=2))
    (OUT / "routing_reconstruction.json").write_text(json.dumps(
        {"alpha": ALPHA,
         "taus": {k: (v[0] if v[0] not in (float("inf"), float("-inf"))
                      else ("Infinity" if v[0] > 0 else "-Infinity")) for k, v in taus.items()},
         "score_used": {k: v[1] for k, v in taus.items()},
         "results": results, "table1_crosscheck": check}, indent=2))

    print("INVARIANTS OK")
    for name in taus:
        r = results[name]
        print(f"{name:22s} Task={r['Task']:.6f} Rec={r['Rec']:.6f} Cov={r['Cov_reconstructed']:.6f} "
              f"nRec={r['n_recover_decisions']}/{len(rows)}")
    print("\nTable-1 cross-check:")
    for k, v in check.items():
        print(f"  {k:22s} Cov t1={v['table1_Cov']!r} recon={v['reconstructed_Cov']!r} "
              f"diff={v['abs_diff']:.3e} FSdiff={v['FS_abs_diff']:.3e}")


if __name__ == "__main__":
    main()
