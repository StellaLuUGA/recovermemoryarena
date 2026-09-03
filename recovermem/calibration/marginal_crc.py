"""Marginal conformal risk control at the episode level (brief §22).

For n calibration EPISODES:

    Lhat_n(tau) = (1/n) sum_i L_i_FS(tau)

    tau_hat = inf { tau : [n/(n+1)] * Lhat_n(tau) + 1/(n+1) <= alpha }

Because L_i_FS is non-increasing in tau, the feasible set is upward-closed, so the
infimum is the *lowest* feasible candidate -- which is also the coverage-maximising one.
Always Recover (tau = +inf) is included as the maximally conservative candidate; at that
point Lhat = 0 and the criterion reduces to 1/(n+1) <= alpha, so the rule is infeasible
for every threshold when n < 1/alpha - 1. That case is reported, never silently patched.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

from recovermem.metrics.risk import (
    ALWAYS_RECOVER_TAU,
    empirical_loss,
    threshold_candidates,
)
from recovermem.metrics.weighting import EpisodeDecisions


@dataclass
class CalibrationResult:
    rule: str
    alpha: float
    tau: float
    n_cal_episodes: int
    calibration_loss: float
    feasible: bool
    note: str = ""

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        # +/-inf is not valid JSON; encode the sentinels as strings.
        if math.isinf(d["tau"]):
            d["tau"] = "Infinity" if d["tau"] > 0 else "-Infinity"
        return d


def crc_criterion(loss: float, n: int, alpha: float) -> float:
    """Left-hand side of the CRC condition: [n/(n+1)] * Lhat + 1/(n+1)."""
    if n <= 0:
        raise ValueError("CRC needs at least one calibration episode")
    return (n / (n + 1)) * loss + 1.0 / (n + 1)


def min_achievable_crc(n: int) -> float:
    """CRC value at Always Recover, i.e. 1/(n+1).

    If alpha is below this, no threshold can satisfy the rule.
    """
    return 1.0 / (n + 1)


def calibrate_marginal_crc(
    cal_episodes: Sequence[EpisodeDecisions],
    alpha: float,
    candidates: Optional[Sequence[float]] = None,
) -> CalibrationResult:
    """Select tau_hat by episode-level marginal CRC."""
    n = len(cal_episodes)
    if n == 0:
        raise ValueError("no calibration episodes")

    cands = list(candidates) if candidates is not None else threshold_candidates(cal_episodes)
    if ALWAYS_RECOVER_TAU not in cands:
        cands.append(ALWAYS_RECOVER_TAU)
    cands = sorted(cands)

    for tau in cands:
        loss = empirical_loss(cal_episodes, tau)
        if crc_criterion(loss, n, alpha) <= alpha:
            return CalibrationResult(
                rule="marginal_crc",
                alpha=alpha,
                tau=tau,
                n_cal_episodes=n,
                calibration_loss=loss,
                feasible=True,
            )

    floor = min_achievable_crc(n)
    return CalibrationResult(
        rule="marginal_crc",
        alpha=alpha,
        tau=ALWAYS_RECOVER_TAU,
        n_cal_episodes=n,
        calibration_loss=empirical_loss(cal_episodes, ALWAYS_RECOVER_TAU),
        feasible=False,
        note=(
            f"infeasible: even Always Recover gives 1/(n+1)={floor:.4f} > alpha={alpha}. "
            f"Needs n >= {math.ceil(1.0 / alpha - 1)} calibration episodes. "
            "Falling back to Always Recover."
        ),
    )
