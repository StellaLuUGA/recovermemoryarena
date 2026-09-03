"""Repeated calibration resampling and the Exc. column (brief §24).

    Exc. = fraction of repeated calibration trials whose held-out empirical FS exceeds
           alpha

This is DESCRIPTIVE finite-sample stability, not a theorem-violation probability.

Resampling is EPISODE-level only. Individual decisions are never resampled: doing so
would break the exchangeability unit and manufacture optimistic variance estimates.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Literal, Optional, Sequence

import numpy as np

from recovermem.metrics.risk import coverage, fs, pi_hat
from recovermem.metrics.weighting import EpisodeDecisions

Rule = Callable[[Sequence[EpisodeDecisions], float], object]


@dataclass
class ResampleRecord:
    resample_id: int
    seed: int
    rule: str
    alpha: float
    calibration_episode_ids: list[str]
    heldout_episode_ids: list[str]
    selected_tau: float
    calibration_FS: float
    heldout_FS: float
    heldout_Cov: float
    heldout_pi: float
    exceeds_alpha: bool
    feasible: bool

    def to_dict(self) -> dict:
        d = asdict(self)
        if math.isinf(d["selected_tau"]):
            d["selected_tau"] = "Infinity" if d["selected_tau"] > 0 else "-Infinity"
        return d


def run_resampling(
    episodes: Sequence[EpisodeDecisions],
    rule: Rule,
    rule_name: str,
    alpha: float,
    n_repetitions: int = 200,
    n_cal: Optional[int] = None,
    base_seed: int = 13,
    mode: Literal["split", "bootstrap"] = "split",
) -> list[ResampleRecord]:
    """Repeatedly split ``episodes`` into calibration/held-out and re-apply the rule.

    Args:
        episodes: the resampling pool. Must be episodes the predictor was NOT trained
            on. Passing test episodes here makes the result descriptive-only and is the
            caller's responsibility to disclose.
        rule: callable (cal_episodes, alpha) -> object with a ``.tau`` attribute.
        n_cal: calibration episodes per repetition. Defaults to half the pool. Supports
            the {20, 40, 80, 160} sweep of brief §25 without rerunning the environment.
        mode: ``split`` draws a disjoint cal/held-out partition (default; keeps held-out
            genuinely unseen). ``bootstrap`` samples calibration with replacement and
            uses the out-of-bag episodes as held-out.

    Returns one record per repetition.
    """
    pool = list(episodes)
    n_pool = len(pool)
    if n_pool < 2:
        raise ValueError(f"need >= 2 episodes to resample, got {n_pool}")

    if n_cal is None:
        n_cal = max(1, n_pool // 2)
    if mode == "split" and n_cal >= n_pool:
        raise ValueError(
            f"n_cal={n_cal} leaves no held-out episodes from a pool of {n_pool}. "
            "Reduce n_cal or collect more episodes; do not fabricate a larger sample."
        )

    records: list[ResampleRecord] = []
    for rep in range(n_repetitions):
        seed = base_seed + rep
        rng = np.random.default_rng(seed)

        if mode == "split":
            perm = rng.permutation(n_pool)
            cal_idx = perm[:n_cal]
            held_idx = perm[n_cal:]
        else:
            cal_idx = rng.integers(0, n_pool, size=n_cal)
            held_idx = np.array(sorted(set(range(n_pool)) - set(cal_idx.tolist())))
            if held_idx.size == 0:
                continue

        cal = [pool[i] for i in cal_idx]
        held = [pool[i] for i in held_idx]

        result = rule(cal, alpha)
        tau = float(getattr(result, "tau"))
        feasible = bool(getattr(result, "feasible", True))

        held_fs = fs(held, tau)
        records.append(
            ResampleRecord(
                resample_id=rep,
                seed=seed,
                rule=rule_name,
                alpha=alpha,
                calibration_episode_ids=[pool[i].episode_id for i in cal_idx],
                heldout_episode_ids=[pool[i].episode_id for i in held_idx],
                selected_tau=tau,
                calibration_FS=fs(cal, tau),
                heldout_FS=held_fs,
                heldout_Cov=coverage(held, tau),
                heldout_pi=pi_hat(held),
                exceeds_alpha=bool(held_fs > alpha),
                feasible=feasible,
            )
        )
    return records


def summarize(records: Sequence[ResampleRecord]) -> dict:
    """FS/Cov/tau mean and std across repetitions, plus Exc."""
    if not records:
        return {
            "n_repetitions": 0,
            "fs_mean": float("nan"),
            "fs_std": float("nan"),
            "coverage_mean": float("nan"),
            "coverage_std": float("nan"),
            "exc": float("nan"),
            "tau_mean": float("nan"),
            "tau_std": float("nan"),
        }

    fs_vals = np.array([r.heldout_FS for r in records], dtype=float)
    cov_vals = np.array([r.heldout_Cov for r in records], dtype=float)
    taus = np.array([r.selected_tau for r in records], dtype=float)
    finite_taus = taus[np.isfinite(taus)]

    return {
        "n_repetitions": len(records),
        "fs_mean": float(np.mean(fs_vals)),
        "fs_std": float(np.std(fs_vals, ddof=0)),
        "coverage_mean": float(np.mean(cov_vals)),
        "coverage_std": float(np.std(cov_vals, ddof=0)),
        "exc": float(np.mean([r.exceeds_alpha for r in records])),
        # Always Recover contributes tau=+inf; report finite-tau stats and how often the
        # sentinel was selected rather than letting inf poison the mean.
        "tau_mean": float(np.mean(finite_taus)) if finite_taus.size else float("nan"),
        "tau_std": float(np.std(finite_taus, ddof=0)) if finite_taus.size else float("nan"),
        "frac_always_recover": float(np.mean(~np.isfinite(taus))),
        "frac_infeasible": float(np.mean([not r.feasible for r in records])),
    }


def write_records(records: Sequence[ResampleRecord], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        for record in records:
            fh.write(json.dumps(record.to_dict()) + "\n")
