"""Evaluate every Table 1 rule on one exact threshold grid (brief §11).

All six rules are scored on the SAME score-induced breakpoint grid so their operating
points are directly comparable; a grid that differed per rule would confound the rule
with its discretisation. Calibration quantities come from CAL episodes, reported FS and
Coverage from TEST episodes -- and the two sets must be disjoint, which this module
checks rather than trusts (the old code silently had cal subset of test,
``run_evaluation.py:896``).
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from recovermem.calibration.empirical_risk import calibrate_empirical_risk
from recovermem.calibration.fixed_f1 import calibrate_fixed_f1
from recovermem.calibration.marginal_crc import calibrate_marginal_crc
from recovermem.metrics.discrimination import episode_auroc
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

#: The six Table 1 rows, in report order.
RULES = (
    "always_trust",
    "always_recover",
    "fixed_f1",
    "empirical_risk",
    "random_crc",
    "marginal_crc",
)


def assert_disjoint(cal: Sequence[EpisodeDecisions], test: Sequence[EpisodeDecisions]) -> None:
    """Refuse to report numbers from an overlapping calibration/test split."""
    overlap = {e.episode_id for e in cal} & {e.episode_id for e in test}
    if overlap:
        raise ValueError(
            f"calibration and test share {len(overlap)} episode(s), e.g. "
            f"{sorted(overlap)[:3]}. This is defect #1 from the audit; results would be "
            f"invalid."
        )


def evaluate_at(test: Sequence[EpisodeDecisions], tau: float) -> dict[str, float]:
    """Reported quantities at one threshold, all episode-equal-weighted."""
    return {
        "fs": fs(test, tau),
        "coverage": coverage(test, tau),
        "any_fs": any_fs_rate(test, tau),
    }


def evaluate_all_rules(
    cal: Sequence[EpisodeDecisions],
    test: Sequence[EpisodeDecisions],
    alpha: float,
    random_cal: Optional[Sequence[EpisodeDecisions]] = None,
    random_test: Optional[Sequence[EpisodeDecisions]] = None,
) -> list[dict[str, Any]]:
    """One row per rule.

    ``random_cal``/``random_test`` carry the FROZEN Uniform(0,1) scores; they are passed
    in rather than generated here so the same frozen draw is reused across every
    resample (brief §11).
    """
    assert_disjoint(cal, test)
    grid = threshold_candidates(cal)
    rows: list[dict[str, Any]] = []

    def row(rule: str, tau: float, extra: dict[str, Any], on=test) -> dict[str, Any]:
        d = {"rule": rule, "alpha": alpha, "tau": tau, "n_cal_episodes": len(cal),
             "n_test_episodes": len(on)}
        d.update(evaluate_at(on, tau))
        d.update(extra)
        return d

    rows.append(row("always_trust", ALWAYS_TRUST_TAU, {"feasible": True}))
    rows.append(row("always_recover", ALWAYS_RECOVER_TAU, {"feasible": True}))

    f1r = calibrate_fixed_f1(cal, candidates=grid)
    rows.append(row("fixed_f1", f1r.tau, {"calibration_f1": f1r.calibration_f1,
                                          "feasible": True, "note": f1r.note}))

    er = calibrate_empirical_risk(cal, alpha=alpha, candidates=grid)
    rows.append(row("empirical_risk", er.tau, {"calibration_loss": er.calibration_loss,
                                               "feasible": er.feasible, "note": er.note}))

    if random_cal is not None and random_test is not None:
        assert_disjoint(random_cal, random_test)
        rgrid = threshold_candidates(random_cal)
        rr = calibrate_marginal_crc(random_cal, alpha=alpha, candidates=rgrid)
        rows.append(row("random_crc", rr.tau, {"calibration_loss": rr.calibration_loss,
                                               "feasible": rr.feasible, "note": rr.note},
                        on=random_test))
    else:
        rows.append({"rule": "random_crc", "alpha": alpha, "note": "frozen random scores not supplied"})

    cr = calibrate_marginal_crc(cal, alpha=alpha, candidates=grid)
    rows.append(row("marginal_crc", cr.tau, {"calibration_loss": cr.calibration_loss,
                                             "feasible": cr.feasible, "note": cr.note}))

    for r in rows:
        r["pi_hat_test"] = pi_hat(test)
        r["auroc_test"] = episode_auroc(test)
    return rows
