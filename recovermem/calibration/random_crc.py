"""Random score + marginal CRC baseline (brief §23).

Every logged decision gets ONE Uniform(0,1) score, generated with a fixed seed and
FROZEN. The same frozen values are reused across every calibration resample; regenerating
them per resample would average away exactly the finite-sample variability that Exc. is
supposed to measure.

The identical episode-level marginal CRC rule is then applied. This isolates the two
contributions: calibration provides risk control, scorer discrimination provides useful
coverage. Expected AUROC ~= 0.5 -- observed, never forced.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import numpy as np

from recovermem.metrics.weighting import EpisodeDecisions

DEFAULT_RANDOM_SCORE_SEED = 20270113


def generate_random_scores(
    decision_keys: Sequence[str], seed: int = DEFAULT_RANDOM_SCORE_SEED
) -> dict[str, float]:
    """One frozen Uniform(0,1) score per decision key.

    Keyed by ``decision_key`` (episode_id::decision_id) rather than positional index so
    the mapping survives re-ordering, resumed collection, and partial reruns.
    """
    rng = np.random.default_rng(seed)
    ordered = sorted(decision_keys)
    values = rng.random(len(ordered))
    return {k: float(v) for k, v in zip(ordered, values)}


def save_random_scores(scores: dict[str, float], path: str | Path, seed: int) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"seed": seed, "n": len(scores), "scores": scores}, indent=2, sort_keys=True
        )
    )


def load_random_scores(path: str | Path) -> tuple[dict[str, float], int]:
    payload = json.loads(Path(path).read_text())
    return payload["scores"], payload["seed"]


def episodes_with_random_scores(
    rows: Sequence[dict], random_scores: dict[str, float]
) -> list[EpisodeDecisions]:
    """Rebuild episode groups with the score replaced by its frozen random value.

    Labels R_mem are untouched -- only the evidence-ranking signal is randomised.
    """
    order: list[str] = []
    buckets: dict[str, EpisodeDecisions] = {}
    missing: list[str] = []
    for row in rows:
        key = f"{row['episode_id']}::{row['decision_id']}"
        if key not in random_scores:
            missing.append(key)
            continue
        ep = str(row["episode_id"])
        if ep not in buckets:
            buckets[ep] = EpisodeDecisions(episode_id=ep)
            order.append(ep)
        buckets[ep].scores.append(random_scores[key])
        buckets[ep].r_mem.append(int(row["r_mem"]))
    if missing:
        raise KeyError(
            f"{len(missing)} decisions have no frozen random score "
            f"(first: {missing[0]}). Regenerate the sidecar over the full decision set "
            "before analysis; do not generate scores on the fly."
        )
    return [buckets[e] for e in order]
