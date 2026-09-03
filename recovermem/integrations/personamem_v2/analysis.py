"""Persona-equal analysis for PersonaMem-v2.

Identical statistical machinery to the Retail / Airline / PrefEval Table-1 pipeline -- the
same ``metrics.risk``, ``calibration.*`` and ``calibration.resample`` code paths -- with one
difference that is the whole point of this workload: the exchangeability unit is a PERSONA
carrying up to 12 controlled decisions, so ``EpisodeDecisions`` is keyed on ``persona_id``.
``metrics.risk`` then averages within a persona first and across personas second, which is
the required weighting. PrefEval's units held exactly one decision each, so its analysis
module keyed on the row id; reusing that here would have weighted personas by question count.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from recovermem.calibration.empirical_risk import calibrate_empirical_risk
from recovermem.calibration.fixed_f1 import calibrate_fixed_f1
from recovermem.calibration.marginal_crc import calibrate_marginal_crc, min_achievable_crc
from recovermem.calibration.random_crc import DEFAULT_RANDOM_SCORE_SEED, generate_random_scores
from recovermem.calibration.resample import run_resampling, summarize
from recovermem.metrics.discrimination import episode_auprc, episode_auroc
from recovermem.metrics.risk import (
    ALWAYS_RECOVER_TAU, ALWAYS_TRUST_TAU, any_fs_rate, coverage, fs, pi_hat, threshold_candidates,
)
from recovermem.metrics.weighting import EpisodeDecisions
from recovermem.scoring.features import HOST_AGNOSTIC_FEATURES, FeatureRecord
from recovermem.scoring.predictor import RecoverabilityPredictor

ALPHAS = (0.05, 0.10, 0.20)


def decision_key(row: dict[str, Any]) -> str:
    return f"{row['persona_id']}::{row['question_id']}"


def feature_record(row: dict[str, Any]) -> FeatureRecord:
    return FeatureRecord(values={k: float(row["features"][k]) for k in HOST_AGNOSTIC_FEATURES})


def to_personas(rows: Sequence[dict[str, Any]], scores: Sequence[float]) -> list[EpisodeDecisions]:
    """One EpisodeDecisions per persona; order within a persona is the row order."""
    if len(rows) != len(scores):
        raise ValueError("rows and scores differ in length")
    order: list[int] = []
    buckets: dict[int, EpisodeDecisions] = {}
    for r, s in zip(rows, scores):
        p = int(r["persona_id"])
        if p not in buckets:
            buckets[p] = EpisodeDecisions(episode_id=str(p))
            order.append(p)
        buckets[p].scores.append(float(s))
        buckets[p].r_mem.append(int(r["r_mem"]))
    return [buckets[p] for p in order]


def train_predictor(train_rows, seed: int = 13) -> RecoverabilityPredictor:
    pred = RecoverabilityPredictor()
    pred.fit([feature_record(r) for r in train_rows], [int(r["r_mem"]) for r in train_rows],
             n_train_episodes=len({r["persona_id"] for r in train_rows}), seed=seed)
    return pred.freeze()


def scorer_metrics(pred, rows, split: str) -> dict[str, Any]:
    scores = pred.predict_scores([feature_record(r) for r in rows])
    eps = to_personas(rows, scores)
    labels = [int(r["r_mem"]) for r in rows]
    return dict(split=split, n_personas=len(eps), n_decisions=len(rows),
                n_positive=sum(labels), n_negative=len(labels) - sum(labels),
                pi_hat_persona_equal=pi_hat(eps),
                pi_hat_decision_pooled=sum(labels) / len(labels),
                auroc=episode_auroc(eps), auprc=episode_auprc(eps),
                score_min=min(scores), score_median=sorted(scores)[len(scores) // 2],
                score_max=max(scores), n_distinct_scores=len(set(scores)))


def calibrate_all(cal_rows, pred, random_scores) -> dict[str, Any]:
    model = to_personas(cal_rows, pred.predict_scores([feature_record(r) for r in cal_rows]))
    rand = to_personas(cal_rows, [random_scores[decision_key(r)] for r in cal_rows])
    grid, rgrid = threshold_candidates(model), threshold_candidates(rand)
    n = len(model)
    out: dict[str, Any] = {"n_cal_personas": n, "n_cal_decisions": len(cal_rows),
                           "crc_floor_1_over_n_plus_1": min_achievable_crc(n),
                           "random_score_seed": DEFAULT_RANDOM_SCORE_SEED, "rules": {}}
    out["rules"]["fixed_f1"] = calibrate_fixed_f1(model, candidates=grid).to_dict()
    for a in ALPHAS:
        out["rules"][f"empirical_risk@{a}"] = calibrate_empirical_risk(model, alpha=a, candidates=grid).to_dict()
        out["rules"][f"random_crc@{a}"] = calibrate_marginal_crc(rand, alpha=a, candidates=rgrid).to_dict()
        out["rules"][f"marginal_crc@{a}"] = calibrate_marginal_crc(model, alpha=a, candidates=grid).to_dict()
    return out


def _tau(entry) -> float:
    v = entry["tau"]
    return float("inf") if v == "Infinity" else (float("-inf") if v == "-Infinity" else float(v))


def table1_rows(test_rows, thresholds, pred, random_scores) -> list[dict[str, Any]]:
    model = to_personas(test_rows, pred.predict_scores([feature_record(r) for r in test_rows]))
    rand = to_personas(test_rows, [random_scores[decision_key(r)] for r in test_rows])

    def row(name, alpha, tau, eps, extra):
        return dict(rule=name, alpha=alpha,
                    tau=(tau if tau not in (float("inf"), float("-inf"))
                         else ("Infinity" if tau > 0 else "-Infinity")),
                    FS=fs(eps, tau), Cov=coverage(eps, tau), any_FS=any_fs_rate(eps, tau),
                    n_test_personas=len(eps), **extra)

    rows = [row("Always Trust", None, ALWAYS_TRUST_TAU, model, {"feasible": True}),
            row("Always Recover", None, ALWAYS_RECOVER_TAU, model, {"feasible": True}),
            row("Fixed-F1", None, _tau(thresholds["rules"]["fixed_f1"]), model,
                {"feasible": True, "calibration_f1": thresholds["rules"]["fixed_f1"]["calibration_f1"]})]
    for a in ALPHAS:
        e = thresholds["rules"][f"empirical_risk@{a}"]
        rows.append(row("Empirical-risk", a, _tau(e), model,
                        {"feasible": e["feasible"], "calibration_loss": e["calibration_loss"]}))
    for a in ALPHAS:
        e = thresholds["rules"][f"random_crc@{a}"]
        rows.append(row("Random score + CRC", a, _tau(e), rand,
                        {"feasible": e["feasible"], "calibration_loss": e["calibration_loss"],
                         "note": e.get("note", "")}))
    for a in ALPHAS:
        e = thresholds["rules"][f"marginal_crc@{a}"]
        rows.append(row("ReCoverMem + marginal CRC", a, _tau(e), model,
                        {"feasible": e["feasible"], "calibration_loss": e["calibration_loss"],
                         "note": e.get("note", "")}))
    return rows


def resampling(pool_rows, pred, random_scores, n_repetitions: int = 200,
               n_cal: Optional[int] = None, base_seed: int = 13) -> dict[str, Any]:
    """The frozen Table-1 repeated-calibration protocol, resampled at the PERSONA level."""
    model = to_personas(pool_rows, pred.predict_scores([feature_record(r) for r in pool_rows]))
    rand = to_personas(pool_rows, [random_scores[decision_key(r)] for r in pool_rows])
    if n_cal is None:
        n_cal = len(model) // 2
    out: dict[str, Any] = dict(n_repetitions=n_repetitions, n_cal_per_repetition=n_cal,
                               pool_personas=len(model), base_seed=base_seed, mode="split", rules={})
    for a in ALPHAS:
        out["rules"][f"empirical_risk@{a}"] = summarize(run_resampling(
            model, lambda c, al: calibrate_empirical_risk(c, alpha=al), "empirical_risk",
            a, n_repetitions, n_cal, base_seed, "split"))
        out["rules"][f"random_crc@{a}"] = summarize(run_resampling(
            rand, lambda c, al: calibrate_marginal_crc(c, alpha=al), "random_crc",
            a, n_repetitions, n_cal, base_seed, "split"))
        out["rules"][f"marginal_crc@{a}"] = summarize(run_resampling(
            model, lambda c, al: calibrate_marginal_crc(c, alpha=al), "marginal_crc",
            a, n_repetitions, n_cal, base_seed, "split"))
    out["rules"]["fixed_f1"] = {"exc": None, "note": "no alpha; exceedance undefined"}
    return out
