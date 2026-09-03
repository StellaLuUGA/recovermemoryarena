"""Discrimination metrics (reused from ``full_replicate/.../metrics.py:346``).

AUROC answers a different question from FS: it measures whether the score *ranks*
recoverable decisions above non-recoverable ones, independent of any threshold. A
calibrated rule can be safe (low FS) while the underlying score is uninformative, and
only AUROC separates those two cases.

Computed via the Mann-Whitney U identity with mid-ranks, so ties contribute 0.5 rather
than being broken arbitrarily.
"""

from __future__ import annotations

from typing import Sequence

from recovermem.metrics.weighting import EpisodeDecisions


def auroc(scores: Sequence[float], labels: Sequence[int]) -> float:
    """AUROC over pooled decisions. Returns nan if either class is absent."""
    if len(scores) != len(labels):
        raise ValueError("scores and labels differ in length")
    pos = [s for s, y in zip(scores, labels) if y == 1]
    neg = [s for s, y in zip(scores, labels) if y == 0]
    if not pos or not neg:
        return float("nan")

    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        mid = (i + j) / 2.0 + 1.0  # 1-based mid-rank
        for k in range(i, j + 1):
            ranks[order[k]] = mid
        i = j + 1

    rank_sum_pos = sum(r for r, y in zip(ranks, labels) if y == 1)
    n_pos, n_neg = len(pos), len(neg)
    u = rank_sum_pos - n_pos * (n_pos + 1) / 2.0
    return u / (n_pos * n_neg)


def episode_auroc(episodes: Sequence[EpisodeDecisions]) -> float:
    """Pooled AUROC across episodes.

    Pooling is acceptable HERE and nowhere else: AUROC is a ranking diagnostic, not a
    risk guarantee, so it carries no exchangeability claim. Every quantity that does --
    FS, Coverage, the CRC criterion -- stays episode-weighted in ``metrics.risk``.
    """
    scores = [s for e in episodes for s in e.scores]
    labels = [r for e in episodes for r in e.r_mem]
    return auroc(scores, labels)


def auprc(scores: Sequence[float], labels: Sequence[int]) -> float:
    """Average precision over pooled decisions. Returns nan if the positive class is absent.

    Computed as the step-wise sum ``sum_k (R_k - R_{k-1}) * P_k`` over decisions ranked by
    descending score -- the interpolation-free definition, so a small sample is not flattered
    by trapezoidal smoothing. Tied scores are consumed as one block, which stops an arbitrary
    within-tie order from changing the number.
    """
    if len(scores) != len(labels):
        raise ValueError("scores and labels differ in length")
    n_pos = sum(1 for y in labels if y == 1)
    if n_pos == 0:
        return float("nan")

    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    ap = 0.0
    tp = 0
    seen = 0
    prev_recall = 0.0
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        for k in range(i, j + 1):
            tp += int(labels[order[k]] == 1)
            seen += 1
        recall = tp / n_pos
        precision = tp / seen
        ap += (recall - prev_recall) * precision
        prev_recall = recall
        i = j + 1
    return ap


def episode_auprc(episodes: Sequence[EpisodeDecisions]) -> float:
    """Pooled AUPRC across episodes. Like ``episode_auroc``, a ranking diagnostic only."""
    scores = [s for e in episodes for s in e.scores]
    labels = [r for e in episodes for r in e.r_mem]
    return auprc(scores, labels)
