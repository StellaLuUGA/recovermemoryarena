"""ALFWorld half-budget compression sensitivity (B=512).

NOT the default / corrected / formal ALFWorld setting. The canonical ALFWorld result is
the frozen B=1024 run under `results/alfworld/final/`, which this script treats as
strictly read-only. The only intended intervention is B_mem/B_rec 1024 -> 512; every
other component (split, host, Qwen, Mem0, features, horizons, seed) is reused frozen.

Table 1 only -- no Table 2 rollouts.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

REPO = Path("/home/aristella/recoverappworld")
CANONICAL = (REPO / "results/alfworld/final").resolve()
OUT = (REPO / "results/alfworld/budget_sensitivity/B512").resolve()

# ---------------------------------------------------------------- §0 hard separation
if OUT == CANONICAL or CANONICAL in OUT.parents:
    raise SystemExit(f"CANONICAL_OVERLAP_CHECK=FAIL: {OUT} is inside {CANONICAL}")
os.environ["AF_RESULTS_ROOT"] = str(OUT)

from af_formal.common import (N_CALIBRATION, N_FINAL_TEST, N_PREDICTOR_TRAIN, QWEN_BASE_URL,
                              RESULTS, SEED, STORES, jdump, jload, log, sha256_file,
                              sha256_json)
from af_formal import collect as CO
from af_formal import stages as ST
from recovermem.scoring.predictor import RecoverabilityPredictor

assert RESULTS == OUT, f"RESULTS misrouted: {RESULTS}"
FP, STATE = OUT / "frozen_protocol", OUT / "RUN_STATE.json"
CANON_FP = CANONICAL / "frozen_protocol"
B_MEM = B_REC = 512
CANONICAL_B = 1024
MANIFESTS = ("CLEAN_64", "PREDICTOR_TRAIN_16", "CALIBRATION_24", "FINAL_TEST_24")


def guard_paths(*paths):
    """Every write target must resolve OUTSIDE the canonical tree."""
    for p in paths:
        r = Path(p).resolve()
        if r == CANONICAL or CANONICAL in r.parents:
            raise SystemExit(f"CANONICAL_OVERLAP_CHECK=FAIL: {r} is inside {CANONICAL}")
    return True


def state_get():
    return jload(STATE) if STATE.exists() else {"stage": "start", "history": []}


def state_set(stage, **kw):
    s = state_get()
    s["stage"] = stage
    s["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    s.setdefault("history", []).append({"stage": stage, "at": s["updated"], **kw})
    s.update(kw)
    jdump(s, STATE)
    log(f"=== STAGE: {stage} ===")


# ---------------------------------------------------------------- §2 split reuse
def mirror_split():
    FP.mkdir(parents=True, exist_ok=True)
    rec = {}
    for name in MANIFESTS:
        src, dst = CANON_FP / f"{name}.json", FP / f"{name}.json"
        guard_paths(dst)
        payload = jload(src)
        canon_hash = payload["list_sha256"]
        # recompute from the records themselves -- proves the copy is identical, not trusted
        h = hashlib.sha256()
        for r in payload["games"]:
            h.update(r["game_file"].encode()); h.update(r["sha256"].encode())
        assert h.hexdigest() == canon_hash, f"{name}: canonical manifest self-hash mismatch"
        shutil.copy2(src, dst)
        copied = jload(dst)
        h2 = hashlib.sha256()
        for r in copied["games"]:
            h2.update(r["game_file"].encode()); h2.update(r["sha256"].encode())
        assert h2.hexdigest() == canon_hash, f"{name}: B512 copy hash != canonical"
        assert copied["games"] == payload["games"], f"{name}: record drift"
        rec[name] = {"n": copied["n"], "canonical_list_sha256": canon_hash,
                     "b512_list_sha256": h2.hexdigest(), "equal": True}
        log(f"  split {name}: n={copied['n']} sha={canon_hash[:16]} EQUAL")
    ids = {n: set(g["game_file"] for g in jload(FP / f"{n}.json")["games"]) for n in MANIFESTS}
    assert not (ids["PREDICTOR_TRAIN_16"] & ids["CALIBRATION_24"])
    assert not (ids["PREDICTOR_TRAIN_16"] & ids["FINAL_TEST_24"])
    assert not (ids["CALIBRATION_24"] & ids["FINAL_TEST_24"])
    union = ids["PREDICTOR_TRAIN_16"] | ids["CALIBRATION_24"] | ids["FINAL_TEST_24"]
    assert union == ids["CLEAN_64"], "split union != CLEAN_64"
    assert (len(ids["PREDICTOR_TRAIN_16"]), len(ids["CALIBRATION_24"]),
            len(ids["FINAL_TEST_24"])) == (N_PREDICTOR_TRAIN, N_CALIBRATION, N_FINAL_TEST)
    jdump({"note": "split identities reused verbatim from the canonical B=1024 freeze; "
                   "NOT resplit, NOT reordered, no games moved or removed",
           "seed": SEED, "manifests": rec, "pairwise_disjoint": True,
           "union_equals_clean_64": True}, FP / "SPLIT_MIRROR.json")
    return rec


# ---------------------------------------------------------------- §4 budget freeze
def freeze_budget(split_rec):
    payload = {
        "experiment": "ALFWorld half-budget compression sensitivity (B=512)",
        "not_the_default_setting": True,
        "canonical_B": CANONICAL_B, "sensitivity_B": B_MEM, "ratio": B_MEM / CANONICAL_B,
        "B_mem": B_MEM, "B_rec": B_REC,
        "rule": "B_mem = B_rec = 512, imposed by intervention; the canonical "
                "scorer-independent budget-selection procedure is NOT rerun",
        "seed": SEED,
        "canonical_budget_freeze_sha256": jload(CANON_FP / "BUDGET_FREEZE.json")["budget_freeze_sha256"],
        "split_manifests": {k: v["canonical_list_sha256"] for k, v in split_rec.items()},
        "tokenizer": "Qwen3-32B-AWQ (exact)",
    }
    payload["b512_freeze_sha256"] = sha256_json(payload)
    guard_paths(FP / "B512_FREEZE.json")
    jdump(payload, FP / "B512_FREEZE.json")
    log(f"BUDGET: B_mem=B_rec={B_MEM} (canonical {CANONICAL_B}, ratio {B_MEM/CANONICAL_B}) "
        f"sha={payload['b512_freeze_sha256'][:16]}")
    return payload


# ---------------------------------------------------------------- §9 diagnostics
def split_diag(jsonl, label):
    recs = ST.load_records(jsonl)
    ids = ST.episode_ids(jsonl)
    d = ST.diagnostics(recs, ids, label, require_score=False)
    c = d["joint_cells"]
    d["n_r_mem_negative"] = c["00"] + c["01"]
    d["n_recovery_rescue_01"] = c["01"]
    d["B_mem"], d["B_rec"] = B_MEM, B_REC
    return d


def main():
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    for sub in ("frozen_protocol", "collect", "predictor", "calibration", "table1",
                "logs", "_stores", "repairs"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    guard_paths(OUT, STORES, STATE, *[OUT / s for s in
                ("frozen_protocol", "collect", "predictor", "calibration", "table1")])
    log(f"CANONICAL_OVERLAP_CHECK=PASS (out={OUT})")
    log(f"resuming from stage={state_get()['stage']}")

    state_set("mirror_split")
    split_rec = mirror_split()
    state_set("freeze_budget")
    freeze = freeze_budget(split_rec)

    diags = {}

    # -------- predictor train: fresh B=512 labels --------
    train_jsonl = OUT / "collect" / "predictor_train.jsonl"
    if not (OUT / "predictor" / "PREDICTOR_FREEZE.json").exists():
        state_set("collect_predictor_train")
        CO.run_partition(FP / "PREDICTOR_TRAIN_16.json", train_jsonl, "train",
                         b_mem=B_MEM, b_rec=B_REC, collect_pairs=True)
        state_set("fit_predictor")
        ST.fit_predictor(train_jsonl)
    pmeta = jload(OUT / "predictor" / "PREDICTOR_FREEZE.json")
    predictor = RecoverabilityPredictor.load(OUT / "predictor" / "predictor.json")
    diags["predictor_train"] = split_diag(train_jsonl, "predictor_train")
    log(f"predictor_train B512: {diags['predictor_train']['n_controlled_decisions']} dec, "
        f"cells={diags['predictor_train']['joint_cells']}, "
        f"pi={diags['predictor_train']['r_mem_prevalence_decision']}")

    # -------- calibration: fresh B=512, thresholds frozen before test is unsealed --------
    cal_jsonl = OUT / "collect" / "calibration.jsonl"
    if not (OUT / "calibration" / "thresholds.json").exists():
        state_set("collect_calibration")
        CO.run_partition(FP / "CALIBRATION_24.json", cal_jsonl, "cal",
                         b_mem=B_MEM, b_rec=B_REC, collect_pairs=True)
        state_set("calibrate")
        ST.calibrate(cal_jsonl, predictor, pmeta)
    thresholds = jload(OUT / "calibration" / "thresholds.json")
    diags["calibration"] = split_diag(cal_jsonl, "calibration")
    log(f"THRESHOLDS FROZEN sha={thresholds['thresholds_sha256'][:16]} "
        f"nonempty={thresholds['calibration_nonempty_episodes']}/24")

    # -------- final test: unsealed ONLY after thresholds exist --------
    test_jsonl = OUT / "collect" / "final_test.jsonl"
    if not (OUT / "table1" / "table1_alfworld.json").exists():
        assert (OUT / "calibration" / "thresholds.json").exists(), "final_test before thresholds"
        state_set("collect_final_test", thresholds_sha256=thresholds["thresholds_sha256"])
        CO.run_partition(FP / "FINAL_TEST_24.json", test_jsonl, "test",
                         b_mem=B_MEM, b_rec=B_REC, collect_pairs=True)
        state_set("table1")
        ST.table1(cal_jsonl, test_jsonl, predictor, pmeta, thresholds)
    t1 = jload(OUT / "table1" / "table1_alfworld.json")
    diags["final_test"] = split_diag(test_jsonl, "final_test")

    # -------- §11 B512-named Table 1 artifacts --------
    state_set("write_table1_b512")
    t1_out = dict(t1)
    t1_out["experiment"] = "ALFWorld half-budget compression sensitivity (B=512)"
    t1_out["B_mem"], t1_out["B_rec"], t1_out["canonical_B"] = B_MEM, B_REC, CANONICAL_B
    t1_out["b512_freeze_sha256"] = freeze["b512_freeze_sha256"]
    t1_out["diagnostics"] = diags
    guard_paths(OUT / "table1" / "table1_alfworld_B512.json")
    jdump(t1_out, OUT / "table1" / "table1_alfworld_B512.json")
    rows = ["\\begin{tabular}{lrrrr}", "\\toprule",
            "Policy & $\\alpha$ & FS & Cov. & Exc. \\\\", "\\midrule"]
    for r in t1["table"]:
        a = f"{r['alpha']:.2f}" if isinstance(r["alpha"], (int, float)) else "--"
        exc = f"{r['Exc']:.3f}" if isinstance(r["Exc"], (int, float)) else "--"
        rows.append(f"{r['policy']} & {a} & {r['FS']:.3f} & {r['Cov']:.3f} & {exc} \\\\")
    rows += ["\\bottomrule", "\\end{tabular}"]
    (OUT / "table1" / "table1_alfworld_B512.tex").write_text("\n".join(rows) + "\n")
    tex_sha = sha256_file(OUT / "table1" / "table1_alfworld_B512.tex")
    json_sha = sha256_file(OUT / "table1" / "table1_alfworld_B512.json")
    log(f"Table 1 (B=512) written; json sha={json_sha[:16]}")

    # -------- §10 canonical comparison, ONLY after B512 result is written+hashed --------
    state_set("compare_to_canonical")
    from af_formal import b512_compare as CMP
    CMP.write_comparison(OUT, CANONICAL, t1_out, diags, freeze, thresholds,
                         {"table1_json_sha256": json_sha, "table1_tex_sha256": tex_sha})
    state_set("final_report")
    CMP.write_final_report(OUT, CANONICAL, t1_out, diags, freeze, thresholds, pmeta, t0)
    state_set("COMPLETE")
    log("ALFWORLD B=512 SENSITIVITY COMPLETE (Table 1 only; no Table 2 by design)")


if __name__ == "__main__":
    main()
