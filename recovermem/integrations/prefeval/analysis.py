"""Predictor training, calibration, Table-1 evaluation and resampling for PrefEval.

Every statistical quantity is delegated to the existing ReCoverMem modules -- the exact
same code paths the tau^3 Retail Table 1 uses -- so nothing is redefined for PrefEval.
The exchangeability unit is the frozen group-key component, and each unit contributes
exactly one controlled decision (T_i = 1), so unit-equal and decision-equal weighting
coincide numerically while the *count* of independent units stays 24 per split.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Sequence

from recovermem.calibration.fixed_f1 import calibrate_fixed_f1
from recovermem.calibration.empirical_risk import calibrate_empirical_risk
from recovermem.calibration.marginal_crc import calibrate_marginal_crc, min_achievable_crc
from recovermem.calibration.random_crc import (
    DEFAULT_RANDOM_SCORE_SEED,
    generate_random_scores,
)
from recovermem.calibration.resample import run_resampling, summarize
from recovermem.metrics.discrimination import episode_auprc, episode_auroc
from recovermem.metrics.risk import (
    ALWAYS_RECOVER_TAU,
    ALWAYS_TRUST_TAU,
    any_fs_rate,
    coverage,
    fs,
    pi_hat,
    threshold_candidates,
)
from recovermem.metrics.weighting import EpisodeDecisions
from recovermem.scoring.features import FEATURE_SCHEMA_VERSION, HOST_AGNOSTIC_FEATURES, FeatureRecord
from recovermem.scoring.predictor import RecoverabilityPredictor

ALPHAS = (0.05, 0.10, 0.20)


def decision_key(row: dict[str, Any]) -> str:
    return f"{row['pair_id']}::d0"


def feature_record(row: dict[str, Any]) -> FeatureRecord:
    return FeatureRecord(values={k: float(row["features"][k]) for k in HOST_AGNOSTIC_FEATURES})


def to_episodes(rows: Sequence[dict[str, Any]], scores: Sequence[float]) -> list[EpisodeDecisions]:
    """One episode per unit, one decision inside it."""
    if len(rows) != len(scores):
        raise ValueError("rows and scores differ in length")
    return [
        EpisodeDecisions(episode_id=r["pair_id"], scores=[float(s)], r_mem=[int(r["r_mem"])])
        for r, s in zip(rows, scores)
    ]


# -- predictor ------------------------------------------------------------------

def train_predictor(train_rows: Sequence[dict[str, Any]], seed: int = 13) -> RecoverabilityPredictor:
    """Fit the pre-specified L2 logistic scorer on TRAIN units only, then freeze it."""
    feats = [feature_record(r) for r in train_rows]
    labels = [int(r["r_mem"]) for r in train_rows]
    pred = RecoverabilityPredictor()
    pred.fit(feats, labels, n_train_episodes=len(train_rows), seed=seed)
    return pred.freeze()


def scorer_metrics(pred: RecoverabilityPredictor, rows: Sequence[dict[str, Any]], split: str) -> dict[str, Any]:
    scores = pred.predict_scores([feature_record(r) for r in rows])
    eps = to_episodes(rows, scores)
    labels = [int(r["r_mem"]) for r in rows]
    return {
        "split": split,
        "n_units": len(rows),
        "n_positive": sum(labels),
        "n_negative": len(labels) - sum(labels),
        "pi_hat": pi_hat(eps),
        "auroc": episode_auroc(eps),
        "auprc": episode_auprc(eps),
        "score_min": min(scores) if scores else None,
        "score_median": sorted(scores)[len(scores) // 2] if scores else None,
        "score_max": max(scores) if scores else None,
        "n_distinct_scores": len(set(scores)),
    }


# -- calibration ----------------------------------------------------------------

def calibrate_all(
    cal_rows: Sequence[dict[str, Any]],
    pred: RecoverabilityPredictor,
    random_scores: dict[str, float],
) -> dict[str, Any]:
    """Every threshold, from CALIBRATION units only. No test row is touched."""
    model_scores = pred.predict_scores([feature_record(r) for r in cal_rows])
    cal_eps = to_episodes(cal_rows, model_scores)
    rand_eps = to_episodes(cal_rows, [random_scores[decision_key(r)] for r in cal_rows])

    grid = threshold_candidates(cal_eps)
    rand_grid = threshold_candidates(rand_eps)
    n = len(cal_rows)

    out: dict[str, Any] = {
        "n_cal_units": n,
        "crc_floor_1_over_n_plus_1": min_achievable_crc(n),
        "random_score_seed": DEFAULT_RANDOM_SCORE_SEED,
        "always_trust": {"tau": "-Infinity"},
        "always_recover": {"tau": "Infinity"},
        "rules": {},
    }

    f1 = calibrate_fixed_f1(cal_eps, candidates=grid)
    out["rules"]["fixed_f1"] = f1.to_dict()

    for a in ALPHAS:
        out["rules"][f"empirical_risk@{a}"] = calibrate_empirical_risk(cal_eps, alpha=a, candidates=grid).to_dict()
        out["rules"][f"random_crc@{a}"] = calibrate_marginal_crc(rand_eps, alpha=a, candidates=rand_grid).to_dict()
        out["rules"][f"marginal_crc@{a}"] = calibrate_marginal_crc(cal_eps, alpha=a, candidates=grid).to_dict()
    return out


def _tau(entry: dict[str, Any]) -> float:
    v = entry["tau"]
    if v == "Infinity":
        return float("inf")
    if v == "-Infinity":
        return float("-inf")
    return float(v)


# -- final test -----------------------------------------------------------------

def table1_rows(
    test_rows: Sequence[dict[str, Any]],
    thresholds: dict[str, Any],
    pred: RecoverabilityPredictor,
    random_scores: dict[str, float],
) -> list[dict[str, Any]]:
    """Canonical frozen final-test point estimates, unit-equal weighted."""
    model_scores = pred.predict_scores([feature_record(r) for r in test_rows])
    test_eps = to_episodes(test_rows, model_scores)
    rand_eps = to_episodes(test_rows, [random_scores[decision_key(r)] for r in test_rows])

    def row(name: str, alpha: Optional[float], tau: float, eps, extra: dict[str, Any]) -> dict[str, Any]:
        return {
            "rule": name,
            "alpha": alpha,
            "tau": tau if tau not in (float("inf"), float("-inf")) else ("Infinity" if tau > 0 else "-Infinity"),
            "FS": fs(eps, tau),
            "Cov": coverage(eps, tau),
            "any_FS": any_fs_rate(eps, tau),
            "n_test_units": len(eps),
            **extra,
        }

    rows = [
        row("Always Trust", None, ALWAYS_TRUST_TAU, test_eps, {"feasible": True}),
        row("Always Recover", None, ALWAYS_RECOVER_TAU, test_eps, {"feasible": True}),
        row("Fixed-F1", None, _tau(thresholds["rules"]["fixed_f1"]), test_eps,
            {"feasible": True, "calibration_f1": thresholds["rules"]["fixed_f1"]["calibration_f1"]}),
    ]
    for a in ALPHAS:
        e = thresholds["rules"][f"empirical_risk@{a}"]
        rows.append(row("Empirical-risk", a, _tau(e), test_eps,
                        {"feasible": e["feasible"], "calibration_loss": e["calibration_loss"]}))
    for a in ALPHAS:
        e = thresholds["rules"][f"random_crc@{a}"]
        rows.append(row("Random score + CRC", a, _tau(e), rand_eps,
                        {"feasible": e["feasible"], "calibration_loss": e["calibration_loss"], "note": e.get("note", "")}))
    for a in ALPHAS:
        e = thresholds["rules"][f"marginal_crc@{a}"]
        rows.append(row("ReCoverMem + marginal CRC", a, _tau(e), test_eps,
                        {"feasible": e["feasible"], "calibration_loss": e["calibration_loss"], "note": e.get("note", "")}))
    return rows


# -- exceedance -----------------------------------------------------------------

def resampling(
    pool_rows: Sequence[dict[str, Any]],
    pred: RecoverabilityPredictor,
    random_scores: dict[str, float],
    n_repetitions: int = 200,
    n_cal: int = 24,
    base_seed: int = 13,
) -> dict[str, Any]:
    """The tau^3 repeated-calibration protocol, unchanged.

    Pool = calibration + final_test units (never the predictor's training units). Each
    repetition draws a disjoint cal/held-out split of the pool, re-applies the rule, and
    records whether held-out FS exceeded alpha. The frozen random scores are reused across
    repetitions rather than redrawn, so the variability measured is the calibration
    sample's, not the noise source's.
    """
    model_eps = to_episodes(pool_rows, pred.predict_scores([feature_record(r) for r in pool_rows]))
    rand_eps = to_episodes(pool_rows, [random_scores[decision_key(r)] for r in pool_rows])

    out: dict[str, Any] = {"n_repetitions": n_repetitions, "n_cal_per_repetition": n_cal,
                           "pool_units": len(pool_rows), "base_seed": base_seed,
                           "mode": "split", "rules": {}}
    for a in ALPHAS:
        recs = run_resampling(model_eps, lambda c, al: calibrate_empirical_risk(c, alpha=al),
                              "empirical_risk", a, n_repetitions, n_cal, base_seed, "split")
        out["rules"][f"empirical_risk@{a}"] = summarize(recs)
        recs = run_resampling(rand_eps, lambda c, al: calibrate_marginal_crc(c, alpha=al),
                              "random_crc", a, n_repetitions, n_cal, base_seed, "split")
        out["rules"][f"random_crc@{a}"] = summarize(recs)
        recs = run_resampling(model_eps, lambda c, al: calibrate_marginal_crc(c, alpha=al),
                              "marginal_crc", a, n_repetitions, n_cal, base_seed, "split")
        out["rules"][f"marginal_crc@{a}"] = summarize(recs)

    # Fixed-F1 has no alpha; Exc. is undefined for it, and Always Trust / Always Recover are
    # threshold-free. Recorded explicitly rather than left blank.
    out["rules"]["fixed_f1"] = {"exc": None, "note": "no alpha; exceedance undefined"}
    return out
