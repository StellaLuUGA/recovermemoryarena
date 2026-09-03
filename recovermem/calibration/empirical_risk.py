"""Empirical-risk threshold selection (brief §21).

Select the LOWEST threshold satisfying Lhat_cal(tau) <= alpha, because Lhat is
non-increasing in tau and the lowest feasible threshold therefore maximises trust
coverage. If no finite threshold is feasible, fall back to Always Recover.

This is the old ``recovermem_minimal/calibration.py:22-70`` breakpoint search with its
risk functional replaced: the old code used a *pooled, decision-level, conditional*
false-safe rate, which is not the quantity Table 1 controls.
"""

from __future__ import annotations

from typing import Optional, Sequence

from recovermem.calibration.marginal_crc import CalibrationResult
from recovermem.metrics.risk import (
    ALWAYS_RECOVER_TAU,
    empirical_loss,
    threshold_candidates,
)
from recovermem.metrics.weighting import EpisodeDecisions


def calibrate_empirical_risk(
    cal_episodes: Sequence[EpisodeDecisions],
    alpha: float,
    candidates: Optional[Sequence[float]] = None,
) -> CalibrationResult:
    """Lowest tau with Lhat_cal(tau) <= alpha (no finite-sample correction)."""
    n = len(cal_episodes)
    if n == 0:
        raise ValueError("no calibration episodes")

    cands = list(candidates) if candidates is not None else threshold_candidates(cal_episodes)
    if ALWAYS_RECOVER_TAU not in cands:
        cands.append(ALWAYS_RECOVER_TAU)
    cands = sorted(cands)

    for tau in cands:
        loss = empirical_loss(cal_episodes, tau)
        if loss <= alpha:
            return CalibrationResult(
                rule="empirical_risk",
                alpha=alpha,
                tau=tau,
                n_cal_episodes=n,
                calibration_loss=loss,
                feasible=True,
            )

    # Unreachable in practice: Lhat(+inf) = 0 <= alpha for any alpha >= 0.
    return CalibrationResult(
        rule="empirical_risk",
        alpha=alpha,
        tau=ALWAYS_RECOVER_TAU,
        n_cal_episodes=n,
        calibration_loss=0.0,
        feasible=False,
        note="no feasible finite threshold; using Always Recover",
    )
