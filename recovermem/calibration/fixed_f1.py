"""Fixed-F1 threshold selection (brief §20).

Using CALIBRATION episodes only: treat "trust" (score >= tau) as a prediction of
R_mem = 1, and pick the threshold maximising F1 on the positive class. Among equal-F1
thresholds, choose the HIGHER threshold.

F1 here is a decision-level quantity by definition (it counts TP/FP/FN over decisions),
unlike FS and Coverage which are episode-equal-weighted. That asymmetry is intentional
and is noted in the result so it is not mistaken for the pooling defect the audit found
in the old code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from recovermem.metrics.risk import threshold_candidates
from recovermem.metrics.weighting import EpisodeDecisions


@dataclass
class FixedF1Result:
    rule: str
    tau: float
    calibration_f1: float
    calibration_precision: float
    calibration_recall: float
    n_cal_episodes: int
    n_cal_decisions: int
    note: str = ""

    def to_dict(self) -> dict:
        import math

        d = dict(self.__dict__)
        if math.isinf(d["tau"]):
            d["tau"] = "Infinity" if d["tau"] > 0 else "-Infinity"
        return d


def _prf(
    episodes: Sequence[EpisodeDecisions], tau: float
) -> tuple[float, float, float]:
    tp = fp = fn = 0
    for ep in episodes:
        for s, r in zip(ep.scores, ep.r_mem):
            trusted = s >= tau
            if trusted and r == 1:
                tp += 1
            elif trusted and r == 0:
                fp += 1
            elif not trusted and r == 1:
                fn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return f1, precision, recall


def calibrate_fixed_f1(
    cal_episodes: Sequence[EpisodeDecisions],
    candidates: Optional[Sequence[float]] = None,
) -> FixedF1Result:
    """Maximise F1 on calibration; ties broken toward the higher threshold."""
    if not cal_episodes:
        raise ValueError("no calibration episodes")

    cands = sorted(
        list(candidates) if candidates is not None else threshold_candidates(cal_episodes)
    )

    best_tau = cands[0]
    best = (-1.0, 0.0, 0.0)
    for tau in cands:
        f1, precision, recall = _prf(cal_episodes, tau)
        # Ascending tau with >= keeps the HIGHEST threshold among equal-F1 ties.
        if f1 >= best[0]:
            best = (f1, precision, recall)
            best_tau = tau

    return FixedF1Result(
        rule="fixed_f1",
        tau=best_tau,
        calibration_f1=best[0],
        calibration_precision=best[1],
        calibration_recall=best[2],
        n_cal_episodes=len(cal_episodes),
        n_cal_decisions=sum(e.n_decisions for e in cal_episodes),
        note="F1 is decision-level by definition; FS/Cov remain episode-equal-weighted",
    )
