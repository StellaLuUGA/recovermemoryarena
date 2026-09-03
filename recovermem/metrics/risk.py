"""Episode-equal-weighted risk quantities (brief §16).

For episode i with T_i controlled decisions and threshold tau (trust iff score >= tau):

    L_i_FS(tau) = (1/T_i) sum_t 1[s_it >= tau AND R_mem_it == 0]
    FS(tau)     = (1/N) sum_i L_i_FS(tau)

    Cov_i(tau)  = (1/T_i) sum_t 1[s_it >= tau]
    Cov(tau)    = (1/N) sum_i Cov_i(tau)

    pi_hat      = (1/N) sum_i (1/T_i) sum_t R_mem_it

Sentinels: tau = -inf is Always Trust (Cov = 1), tau = +inf is Always Recover
(Cov = 0, FS = 0).
"""

from __future__ import annotations

import math
from typing import Sequence

from recovermem.metrics.weighting import EpisodeDecisions

ALWAYS_TRUST_TAU = -math.inf
ALWAYS_RECOVER_TAU = math.inf


def episode_fs_loss(episode: EpisodeDecisions, tau: float) -> float:
    """L_i_FS(tau) for a single episode."""
    if episode.is_empty:
        raise ValueError(f"episode {episode.episode_id} has no decisions; L_i is undefined")
    hits = sum(
        1 for s, r in zip(episode.scores, episode.r_mem) if s >= tau and r == 0
    )
    return hits / episode.n_decisions


def episode_coverage(episode: EpisodeDecisions, tau: float) -> float:
    """Cov_i(tau) for a single episode."""
    if episode.is_empty:
        raise ValueError(f"episode {episode.episode_id} has no decisions; Cov_i is undefined")
    return sum(1 for s in episode.scores if s >= tau) / episode.n_decisions


def episode_pi(episode: EpisodeDecisions) -> float:
    """Per-episode recoverability prevalence (1/T_i) sum_t R_mem_it."""
    if episode.is_empty:
        raise ValueError(f"episode {episode.episode_id} has no decisions; pi_i is undefined")
    return sum(episode.r_mem) / episode.n_decisions


def fs(episodes: Sequence[EpisodeDecisions], tau: float) -> float:
    """FS(tau), episode-equal-weighted."""
    if not episodes:
        return float("nan")
    return sum(episode_fs_loss(e, tau) for e in episodes) / len(episodes)


def coverage(episodes: Sequence[EpisodeDecisions], tau: float) -> float:
    """Cov(tau), episode-equal-weighted."""
    if not episodes:
        return float("nan")
    return sum(episode_coverage(e, tau) for e in episodes) / len(episodes)


def pi_hat(episodes: Sequence[EpisodeDecisions]) -> float:
    """Recoverability prevalence, episode-equal-weighted."""
    if not episodes:
        return float("nan")
    return sum(episode_pi(e) for e in episodes) / len(episodes)


def empirical_loss(episodes: Sequence[EpisodeDecisions], tau: float) -> float:
    """Lhat_n(tau) = (1/n) sum_i L_i_FS(tau). Identical to ``fs``; named for the
    calibration rules, where it reads as the empirical risk on the calibration split."""
    return fs(episodes, tau)


def always_trust(episodes: Sequence[EpisodeDecisions]) -> dict[str, float]:
    """Analytical Always Trust row. FS must equal 1 - pi_hat."""
    return {
        "tau": ALWAYS_TRUST_TAU,
        "fs": fs(episodes, ALWAYS_TRUST_TAU),
        "coverage": coverage(episodes, ALWAYS_TRUST_TAU),
    }


def always_recover(episodes: Sequence[EpisodeDecisions]) -> dict[str, float]:
    """Analytical Always Recover row: FS = 0, Cov = 0."""
    return {
        "tau": ALWAYS_RECOVER_TAU,
        "fs": fs(episodes, ALWAYS_RECOVER_TAU),
        "coverage": coverage(episodes, ALWAYS_RECOVER_TAU),
    }


def threshold_candidates(episodes: Sequence[EpisodeDecisions]) -> list[float]:
    """Exact score-induced breakpoints plus both sentinels (brief §17).

    With the rule ``trust iff s >= tau``, the risk/coverage pair only changes when tau
    crosses an observed score, so enumerating the distinct observed scores plus +inf
    covers every achievable operating point exactly. -inf is included so Always Trust is
    always an explicit candidate even when the score set is empty.
    """
    seen = {s for e in episodes for s in e.scores}
    return [ALWAYS_TRUST_TAU] + sorted(seen) + [ALWAYS_RECOVER_TAU]


def risk_coverage_curve(
    episodes: Sequence[EpisodeDecisions],
) -> list[dict[str, float]]:
    """(tau, FS, Cov) at every candidate threshold, ascending in tau.

    FS and Cov are both non-increasing along this curve by construction.
    """
    return [
        {"tau": t, "fs": fs(episodes, t), "coverage": coverage(episodes, t)}
        for t in threshold_candidates(episodes)
    ]


def any_fs_rate(episodes: Sequence[EpisodeDecisions], tau: float) -> float:
    """Any-FS (brief §26): fraction of episodes with >= 1 false-safe decision."""
    if not episodes:
        return float("nan")
    return sum(1 for e in episodes if episode_fs_loss(e, tau) > 0) / len(episodes)
