"""Budget audit, predictor fitting, calibration and Table 1 for formal ALFWorld."""
from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path

import numpy as np

from af_formal.common import (CANDIDATE_BUDGETS, GAMMA, N_RESAMPLES, QWEN_MAX_MODEL_LEN,
                              RESULTS, SEED, jdump, jload, log, sha256_file, sha256_json)
from af_formal import collect as CO
from af_formal import host as H
from af_formal import memhost as M

from recovermem.calibration.empirical_risk import calibrate_empirical_risk
from recovermem.calibration.fixed_f1 import calibrate_fixed_f1
from recovermem.calibration.marginal_crc import calibrate_marginal_crc
from recovermem.calibration.random_crc import generate_random_scores, episodes_with_random_scores
from recovermem.metrics.discrimination import auroc
from recovermem.metrics.risk import (ALWAYS_RECOVER_TAU, ALWAYS_TRUST_TAU, any_fs_rate,
                                     coverage, fs, pi_hat)
from recovermem.metrics.weighting import EpisodeDecisions, drop_empty, group_by_episode
from recovermem.scoring.features import FeatureRecord, HOST_AGNOSTIC_FEATURES
from recovermem.scoring.predictor import RecoverabilityPredictor

FP = RESULTS / "frozen_protocol"
BUD = RESULTS / "budget"
CAL = RESULTS / "calibration"
T1 = RESULTS / "table1"


def quantile(vals, q):
    v = sorted(vals)
    if not v:
        return float("nan")
    k = (len(v) - 1) * q
    f, c = int(math.floor(k)), min(int(math.floor(k)) + 1, len(v) - 1)
    return v[f] + (v[c] - v[f]) * (k - f)


def _dist(vals):
    if not vals:
        return {"n": 0}
    return {"n": len(vals), "min": min(vals), "q05": round(quantile(vals, .05), 1),
            "median": round(quantile(vals, .5), 1), "mean": round(statistics.fmean(vals), 1),
            "q75": round(quantile(vals, .75), 1), "q90": round(quantile(vals, .90), 1),
            "q95": round(quantile(vals, .95), 1), "max": max(vals)}


# ----------------------------------------------------------------- budget
def budget_audit(audit_jsonl):
    rows = [r for line in Path(audit_jsonl).open()
            for r in json.loads(line)["audit_rows"]]
    if not rows:
        raise SystemExit("budget audit produced no controlled states")
    x_tok = [r["x_tokens"] for r in rows]
    mem_tok = [r["native_mem_evidence_tokens"] for r in rows]
    hist_tok = [r["raw_history_tokens"] for r in rows]
    base_tok = [r["base_prompt_tokens"] for r in rows]
    reserve_out, safety = 32, 256
    avail = [QWEN_MAX_MODEL_LEN - b - reserve_out - safety for b in base_tok]

    q05_avail = quantile(avail, 0.05)
    feasible_cap = [b for b in CANDIDATE_BUDGETS if b <= q05_avail]
    b_cap = max(feasible_cap) if feasible_cap else None
    max_mem = max(mem_tok)
    feasible_host = [b for b in CANDIDATE_BUDGETS if b >= max_mem]
    b_host = min(feasible_host) if feasible_host else None
    if b_cap is None or b_host is None:
        raise SystemExit(f"budget infeasible: B_cap={b_cap} B_host={b_host} max_mem={max_mem}")
    b_mem = min(b_cap, b_host)
    b_rec = b_mem

    trunc_rec = sum(1 for h in hist_tok if h > b_rec) / len(hist_tok)
    trunc_mem = sum(1 for m in mem_tok if m > b_mem) / len(mem_tok)
    audit = {
        "source": "PREDICTOR_TRAIN only; scorer-independent; no R_mem/R_rec computed",
        "n_controlled_states": len(rows), "n_episodes": len(set(r["episode_id"] for r in rows)),
        "candidate_budget_ladder": list(CANDIDATE_BUDGETS),
        "tokenizer": "Qwen3-32B-AWQ (exact, server tokenizer)",
        "serving": {"max_model_len": QWEN_MAX_MODEL_LEN, "reserved_output_tokens": reserve_out,
                    "safety_margin": safety},
        "current_state_tokens": _dist(x_tok),
        "native_mem0_evidence_tokens": _dist(mem_tok),
        "raw_observable_history_tokens": _dist(hist_tok),
        "base_prompt_tokens": _dist(base_tok),
        "available_evidence_capacity_tokens": _dist(avail),
        "two_stage_rule": {
            "B_cap": b_cap, "B_cap_basis": f"largest ladder budget <= Q0.05(avail)={q05_avail:.1f}",
            "B_host": b_host, "B_host_basis": f"smallest ladder budget >= max native Mem0 evidence={max_mem}",
        },
        "B_mem_frozen": b_mem, "B_rec_frozen": b_rec,
        "fraction_states_where_raw_history_exceeds_B_rec": round(trunc_rec, 4),
        "fraction_states_where_native_mem0_exceeds_B_mem": round(trunc_mem, 4),
        "note": ("B was chosen without any paired label, scorer output, AUROC, FS, coverage or "
                 "task-success quantity, and is frozen regardless of whether it binds."),
    }
    jdump(audit, BUD / "BUDGET_AUDIT.json")
    freeze = {"B_mem": b_mem, "B_rec": b_rec, "ladder": list(CANDIDATE_BUDGETS),
              "rule": "B_mem = min(B_cap, B_host); B_rec = B_mem", "seed": SEED}
    freeze["budget_freeze_sha256"] = sha256_json(freeze)
    jdump(freeze, FP / "BUDGET_FREEZE.json")
    (BUD / "BUDGET_DECISION.md").write_text(f"""# ALFWorld budget decision (scorer-independent)

Measured on the **16 PREDICTOR_TRAIN episodes only**, with the exact Qwen3-32B tokenizer, before
any paired utility label existed. No R_mem, R_rec, scorer, AUROC, FS or coverage quantity was
computed or inspected.

| quantity | median | q90 | max |
|---|---|---|---|
| current state x_t | {audit['current_state_tokens']['median']} | {audit['current_state_tokens']['q90']} | {audit['current_state_tokens']['max']} |
| native Mem0 serialized evidence | {audit['native_mem0_evidence_tokens']['median']} | {audit['native_mem0_evidence_tokens']['q90']} | {audit['native_mem0_evidence_tokens']['max']} |
| raw observable history | {audit['raw_observable_history_tokens']['median']} | {audit['raw_observable_history_tokens']['q90']} | {audit['raw_observable_history_tokens']['max']} |
| available serving evidence capacity | {audit['available_evidence_capacity_tokens']['median']} | {audit['available_evidence_capacity_tokens']['q90']} | {audit['available_evidence_capacity_tokens']['max']} |

Two-stage rule (identical in form to tau3):

```
B_cap  = largest ladder budget <= Q0.05(available capacity) = {b_cap}
B_host = smallest ladder budget >= max native Mem0 evidence ({max_mem}) = {b_host}
B_mem  = min(B_cap, B_host) = {b_mem}
B_rec  = B_mem = {b_rec}
```

Ladder: {list(CANDIDATE_BUDGETS)}.

Binding behaviour: raw observable history exceeds `B_rec` at **{trunc_rec:.1%}** of controlled
states (so recovery evidence is genuinely truncated there); native Mem0 evidence exceeds `B_mem`
at {trunc_mem:.1%}. Whether or not the budget binds, it is frozen here and is not retuned after
labels are seen.

`BUDGET_FREEZE.json` sha256 `{freeze['budget_freeze_sha256']}`.
""")
    log(f"BUDGET: B_cap={b_cap} B_host={b_host} -> B_mem=B_rec={b_mem}")
    return b_mem, b_rec


# ------------------------------------------------------------- records I/O
def load_records(jsonl):
    recs = []
    for line in Path(jsonl).open():
        ep = json.loads(line)
        recs.extend(ep.get("records", []))
    return recs


def episode_ids(jsonl):
    return [json.loads(l)["episode_id"] for l in Path(jsonl).open()]


def valid_records(recs):
    keep = [r for r in recs if r["pair_valid"]]
    excl = [{"decision_key": r["decision_key"],
             "reasons": [k for k in ("pair_valid", "reconstruction_ok_mem",
                                     "reconstruction_ok_rec", "budget_ok") if not r.get(k)]}
            for r in recs if not r["pair_valid"]]
    return keep, excl


def rows_of(recs):
    return [{"episode_id": r["episode_id"], "decision_id": r["decision_id"],
             "score": r["score"], "r_mem": r["r_mem"]} for r in recs]


@dataclass
class LabelOnlyEpisode:
    """Score-free episode group for PRE-FIT diagnostics.

    Before `fit_predictor` runs there is no recoverability score: collection writes
    `score = None`, and fabricating one (0.0 / 0.5) would be a synthetic scientific
    quantity. Only the LABEL side of the diagnostics is defined at that point, so this
    carries `r_mem` alone and exposes the same read API that `drop_empty` and
    `pi_hat`/`episode_pi` consume (`episode_id`, `r_mem`, `n_decisions`, `is_empty`).
    It deliberately has NO `scores`, so any threshold quantity (FS, coverage) raises
    instead of silently reading a fabricated score.
    """

    episode_id: str
    r_mem: list[int] = dataclass_field(default_factory=list)

    def __post_init__(self) -> None:
        for label in self.r_mem:
            if label not in (0, 1):
                raise ValueError(f"episode {self.episode_id}: R_mem must be 0/1, got {label!r}")

    @property
    def n_decisions(self) -> int:
        return len(self.r_mem)

    @property
    def is_empty(self) -> bool:
        return self.n_decisions == 0


def group_by_episode_labels(rows):
    """`group_by_episode` without the score column. Order within an episode preserved."""
    order, buckets = [], {}
    for row in rows:
        ep = str(row["episode_id"])
        if ep not in buckets:
            buckets[ep] = LabelOnlyEpisode(episode_id=ep)
            order.append(ep)
        buckets[ep].r_mem.append(int(row["r_mem"]))
    return [buckets[e] for e in order]


def episodes_of(recs, all_episode_ids=None, *, require_score=True):
    """Group controlled decisions into episode units.

    `require_score=True` (calibration, final test, anything threshold-dependent) uses the
    shared score-aware `group_by_episode` unchanged. `require_score=False` is the
    pre-predictor path: it groups on `episode_id` + `r_mem` only and never touches
    `score`.
    """
    rows = rows_of(recs)
    if require_score:
        eps = group_by_episode(rows)
        empty_cls = EpisodeDecisions
    else:
        eps = group_by_episode_labels(rows)
        empty_cls = LabelOnlyEpisode
    have = {e.episode_id for e in eps}
    for eid in (all_episode_ids or []):
        if eid not in have:
            eps.append(empty_cls(episode_id=eid))
    return drop_empty(eps)


def joint_cells(recs):
    c = {"00": 0, "01": 0, "10": 0, "11": 0}
    for r in recs:
        c[f"{r['r_mem']}{r['r_rec']}"] += 1
    return c


def diagnostics(recs, all_ids, label, *, require_score=True):
    """Split diagnostics. None of the quantities below depend on the recoverability
    score, so `require_score=False` yields identical numbers before the predictor
    exists; it only changes which grouping implementation is used."""
    keep, _ = valid_records(recs)
    eps, empty = episodes_of(keep, all_ids, require_score=require_score)
    return {
        "split": label, "n_episodes_total": len(all_ids),
        "n_episodes_nonempty": len(eps), "n_episodes_empty": len(empty),
        "empty_episode_ids": empty,
        "n_controlled_decisions": len(keep),
        "mean_controlled_states_per_nonempty_episode":
            round(len(keep) / len(eps), 3) if eps else 0.0,
        "r_mem_prevalence_decision": round(sum(r["r_mem"] for r in keep) / len(keep), 4) if keep else None,
        "r_rec_prevalence_decision": round(sum(r["r_rec"] for r in keep) / len(keep), 4) if keep else None,
        "r_mem_prevalence_episode_weighted": round(pi_hat(eps), 4) if eps else None,
        "joint_cells": joint_cells(keep),
        "history_tokens": _dist([r["history_tokens"] for r in keep]),
        "common_state_tokens": _dist([r["common_state_tokens"] for r in keep]),
        "e_mem_tokens": _dist([r["e_mem_tokens"] for r in keep]),
        "e_rec_tokens": _dist([r["e_rec_tokens"] for r in keep]),
    }


# ------------------------------------------------------------- predictor
def fit_predictor(train_jsonl):
    recs = load_records(train_jsonl)
    keep, excl = valid_records(recs)
    ids = episode_ids(train_jsonl)
    # PRE-FIT: no predictor exists yet, so collection wrote score=None. Diagnose on
    # labels alone rather than inventing a score.
    diag = diagnostics(recs, ids, "predictor_train", require_score=False)
    jdump({"diagnostics": diag, "excluded": excl},
          RESULTS / "predictor" / "PRE_FIT_REPORT.json")
    log(f"predictor_train: {diag['n_controlled_decisions']} decisions, "
        f"pi={diag['r_mem_prevalence_decision']}, cells={diag['joint_cells']}")

    feats = [FeatureRecord(values=r["features"]["values"]) for r in keep]
    labels = [r["r_mem"] for r in keep]
    p = RecoverabilityPredictor()
    p.fit(feats, labels, n_train_episodes=diag["n_episodes_nonempty"], seed=SEED)
    p.freeze()
    path = RESULTS / "predictor" / "predictor.json"
    p.save(path)
    scores = p.predict_scores(feats)
    train_auroc = auroc(scores, labels)
    train_auprc = _auprc(scores, labels)
    meta = {"schema_version": p.schema_version, "feature_names": list(HOST_AGNOSTIC_FEATURES),
            "n_train_decisions": p.n_train_decisions, "n_train_episodes": p.n_train_episodes,
            "train_auroc": round(train_auroc, 4) if train_auroc == train_auroc else None,
            "train_auprc": round(train_auprc, 4) if train_auprc == train_auprc else None,
            "label_prevalence": diag["r_mem_prevalence_decision"],
            "predictor_sha256": sha256_file(path),
            "note": "AUROC/AUPRC are diagnostics, not selection criteria; no refit was performed"}
    jdump(meta, RESULTS / "predictor" / "PREDICTOR_FREEZE.json")
    log(f"predictor frozen sha={meta['predictor_sha256'][:16]} "
        f"train AUROC={meta['train_auroc']} AUPRC={meta['train_auprc']}")
    return p, meta


def _auprc(scores, labels):
    pos = sum(labels)
    if pos == 0 or pos == len(labels):
        return float("nan")
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    tp = fp = 0
    prev_r, ap = 0.0, 0.0
    for i in order:
        if labels[i] == 1:
            tp += 1
        else:
            fp += 1
        r = tp / pos
        prec = tp / (tp + fp)
        ap += prec * (r - prev_r)
        prev_r = r
    return ap


def score_records(recs, predictor):
    for r in recs:
        r["score"] = float(predictor.predict_score(FeatureRecord(values=r["features"]["values"])))
    return recs


# ------------------------------------------------------------- calibration
ALPHAS = (0.05, 0.10, 0.20)


def calibrate(cal_jsonl, predictor, predictor_meta):
    recs = load_records(cal_jsonl)
    keep, excl = valid_records(recs)
    score_records(keep, predictor)
    ids = episode_ids(cal_jsonl)
    eps, empty = episodes_of(keep, ids)
    diag = diagnostics(recs, ids, "calibration")

    keys = [r["decision_key"] for r in keep]
    rand = generate_random_scores(keys, seed=SEED)
    jdump({"seed": SEED, "n": len(rand), "scores": rand}, CAL / "random_scores.json")
    reps = rows_of(keep)
    rand_eps = episodes_with_random_scores(reps, rand)
    rand_eps, _ = drop_empty(rand_eps)

    rules = {}
    f1 = calibrate_fixed_f1(eps)
    rules["fixed_f1"] = f1.to_dict()
    for a in ALPHAS:
        rules[f"empirical_risk_{a:.2f}"] = calibrate_empirical_risk(eps, alpha=a).to_dict()
        rules[f"random_crc_{a:.2f}"] = calibrate_marginal_crc(rand_eps, alpha=a).to_dict()
        rules[f"recovermem_crc_{a:.2f}"] = calibrate_marginal_crc(eps, alpha=a).to_dict()
    rules["always_trust"] = {"rule": "always_trust", "tau": "-Infinity", "feasible": True}
    rules["always_recover"] = {"rule": "always_recover", "tau": "Infinity", "feasible": True}

    payload = {
        "predictor_sha256": predictor_meta["predictor_sha256"],
        "calibration_manifest_sha256": jload(FP / "CALIBRATION_24.json")["list_sha256"],
        "calibration_episodes_total": len(ids),
        "calibration_nonempty_episodes": len(eps),
        "calibration_empty_episodes": len(empty),
        "n_calibration_decisions": len(keep),
        "gamma": GAMMA, "seed": SEED, "alphas": list(ALPHAS),
        "crc_min_achievable": round(1.0 / (len(eps) + 1), 5),
        "random_score_seed": SEED, "random_score_key": "episode_id::decision_id",
        "rules": rules, "excluded": excl, "diagnostics": diag,
    }
    payload["thresholds_sha256"] = sha256_json(
        {k: v for k, v in payload.items() if k != "excluded"})
    jdump(payload, CAL / "thresholds.json")
    log(f"thresholds frozen sha={payload['thresholds_sha256'][:16]} "
        f"nonempty_cal={len(eps)}/{len(ids)}")
    for k, v in rules.items():
        if "tau" in v:
            log(f"    {k:24s} tau={v['tau']}  feasible={v.get('feasible')}")
    return payload


# ------------------------------------------------------------- table 1
ROWS = [("Always Trust", "always_trust", None),
        ("Always Recover", "always_recover", None),
        ("Fixed-F1", "fixed_f1", None),
        ("Empirical-risk alpha=.05", "empirical_risk_0.05", 0.05),
        ("Empirical-risk alpha=.10", "empirical_risk_0.10", 0.10),
        ("Empirical-risk alpha=.20", "empirical_risk_0.20", 0.20),
        ("Random+CRC alpha=.05", "random_crc_0.05", 0.05),
        ("Random+CRC alpha=.10", "random_crc_0.10", 0.10),
        ("Random+CRC alpha=.20", "random_crc_0.20", 0.20),
        ("ReCoverMem+CRC alpha=.05", "recovermem_crc_0.05", 0.05),
        ("ReCoverMem+CRC alpha=.10", "recovermem_crc_0.10", 0.10),
        ("ReCoverMem+CRC alpha=.20", "recovermem_crc_0.20", 0.20)]


def _tau(v):
    if isinstance(v, str):
        return math.inf if v == "Infinity" else -math.inf
    return float(v)


def table1(cal_jsonl, test_jsonl, predictor, predictor_meta, thresholds):
    cal_recs, _ = valid_records(load_records(cal_jsonl))
    test_recs, test_excl = valid_records(load_records(test_jsonl))
    score_records(cal_recs, predictor)
    score_records(test_recs, predictor)
    cal_ids, test_ids = episode_ids(cal_jsonl), episode_ids(test_jsonl)
    cal_eps, _ = episodes_of(cal_recs, cal_ids)
    test_eps, test_empty = episodes_of(test_recs, test_ids)

    rand_cal, _ = generate_random_scores([r["decision_key"] for r in cal_recs], seed=SEED), None
    rand_test = generate_random_scores([r["decision_key"] for r in test_recs], seed=SEED)
    cal_eps_r, _ = drop_empty(episodes_with_random_scores(rows_of(cal_recs), rand_cal))
    test_eps_r, _ = drop_empty(episodes_with_random_scores(rows_of(test_recs), rand_test))

    rule_fn = {"empirical_risk": calibrate_empirical_risk,
               "random_crc": calibrate_marginal_crc,
               "recovermem_crc": calibrate_marginal_crc,
               "fixed_f1": lambda c, a: calibrate_fixed_f1(c)}

    table, resamples = [], {}
    for label, key, alpha in ROWS:
        spec = thresholds["rules"][key]
        tau = _tau(spec["tau"])
        on_random = key.startswith("random_crc")
        ev = test_eps_r if on_random else test_eps
        row = {"policy": label, "key": key, "alpha": alpha,
               "tau": ("Infinity" if math.isinf(tau) and tau > 0 else
                       "-Infinity" if math.isinf(tau) else round(tau, 6)),
               "feasible": spec.get("feasible", True),
               "FS": round(fs(ev, tau), 4), "Cov": round(coverage(ev, tau), 4),
               "AnyFS": round(any_fs_rate(ev, tau), 4)}
        if key in ("always_trust", "always_recover", "fixed_f1"):
            row["Exc"] = None
            table.append(row)
            continue
        fam = key.rsplit("_", 1)[0]
        fn = rule_fn[fam]
        pool = cal_eps_r if on_random else cal_eps
        n_pool = len(pool)
        n_cal = max(2, n_pool // 2)
        exceed, fsv, covv, taus, infeas = 0, [], [], [], 0
        for rep in range(N_RESAMPLES):
            rng = np.random.default_rng(SEED + rep)
            sub = [pool[i] for i in rng.permutation(n_pool)[:n_cal]]
            res = fn(sub, alpha)
            t = float(res.tau)
            if not getattr(res, "feasible", True):
                infeas += 1
            taus.append(t)
            f = fs(ev, t); fsv.append(f); covv.append(coverage(ev, t))
            if f > alpha:
                exceed += 1
        row.update({"Exc": round(exceed / N_RESAMPLES, 4),
                    "FS_mean": round(statistics.fmean(fsv), 4),
                    "FS_sd": round(statistics.pstdev(fsv), 4),
                    "Cov_mean": round(statistics.fmean(covv), 4),
                    "Cov_sd": round(statistics.pstdev(covv), 4),
                    "n_resamples_always_recover": sum(1 for t in taus if math.isinf(t)),
                    "n_resamples_infeasible": infeas})
        resamples[key] = {"n_resamples": N_RESAMPLES, "n_cal_per_resample": n_cal,
                          "n_pool": n_pool, "FS_mean": row["FS_mean"], "FS_sd": row["FS_sd"],
                          "Cov_mean": row["Cov_mean"], "Cov_sd": row["Cov_sd"],
                          "Exc": row["Exc"], "n_infeasible": infeas}
        table.append(row)

    ts = [r["score"] for r in test_recs]; tl = [r["r_mem"] for r in test_recs]
    summary = {
        "predictor_sha256": predictor_meta["predictor_sha256"],
        "thresholds_sha256": thresholds["thresholds_sha256"],
        "final_test_manifest_sha256": jload(FP / "FINAL_TEST_24.json")["list_sha256"],
        "n_test_episodes_total": len(test_ids),
        "n_test_episodes_nonempty": len(test_eps),
        "n_test_episodes_empty": len(test_empty),
        "n_test_decisions": len(test_recs),
        "test_r_mem_prevalence": round(sum(tl) / len(tl), 4) if tl else None,
        "test_r_rec_prevalence": round(sum(r["r_rec"] for r in test_recs) / len(test_recs), 4) if test_recs else None,
        "test_joint_cells": joint_cells(test_recs),
        "test_auroc": round(auroc(ts, tl), 4) if len(set(tl)) > 1 else None,
        "test_auprc": round(_auprc(ts, tl), 4) if len(set(tl)) > 1 else None,
        "train_auroc": predictor_meta["train_auroc"],
        "train_auprc": predictor_meta["train_auprc"],
        "always_trust_sanity": {
            "FS": round(fs(test_eps, ALWAYS_TRUST_TAU), 4),
            "episode_weighted_mean_1_minus_r_mem": round(1.0 - pi_hat(test_eps), 4)},
        "excluded_test": test_excl,
    }
    out = {"table": table, "summary": summary, "n_resamples": N_RESAMPLES,
           "convention": ("FS/Cov are canonical frozen final-test point estimates; Exc is the "
                          "200-resample exceedance frequency. Resampling mean/SD are appendix "
                          "quantities and are NOT the main-table FS/Cov.")}
    jdump(out, T1 / "table1_alfworld.json")
    jdump({"n_resamples": N_RESAMPLES, "seed": SEED, "unit": "episode",
           "rules": resamples}, T1 / "resampling_summary.json")
    _tex(table, T1 / "table1_alfworld.tex")
    return out


def _tex(table, path):
    lines = [r"\begin{tabular}{lrrr}", r"\toprule",
             r"Policy & FS & Cov. & Exc. \\", r"\midrule"]
    for r in table:
        exc = "--" if r["Exc"] is None else f"{r['Exc']:.3f}"
        lines.append(f"{r['policy']} & {r['FS']:.3f} & {r['Cov']:.3f} & {exc} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines) + "\n")
