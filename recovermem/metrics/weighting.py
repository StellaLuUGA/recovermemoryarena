"""Episode-level grouping.

The exchangeability unit is an EPISODE, never a decision. Every risk quantity in this
package is built on top of ``EpisodeDecisions`` so that pooling decisions IID -- the
defect found in the old code (``run_evaluation.py:490-495``) -- is structurally
impossible rather than merely discouraged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence


@dataclass
class EpisodeDecisions:
    """All controlled decisions belonging to one native episode.

    Attributes:
        episode_id: native episode identifier (task id + trial).
        scores: recoverability score s_it, one per controlled decision.
        r_mem: binary recoverability label R_mem_it = 1[u_mem >= gamma].
    """

    episode_id: str
    scores: list[float] = field(default_factory=list)
    r_mem: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.scores) != len(self.r_mem):
            raise ValueError(
                f"episode {self.episode_id}: {len(self.scores)} scores but "
                f"{len(self.r_mem)} labels"
            )
        for label in self.r_mem:
            if label not in (0, 1):
                raise ValueError(f"episode {self.episode_id}: R_mem must be 0/1, got {label!r}")

    @property
    def n_decisions(self) -> int:
        """T_i, the number of controlled decisions in this episode."""
        return len(self.scores)

    @property
    def is_empty(self) -> bool:
        return self.n_decisions == 0


def group_by_episode(rows: Iterable[dict]) -> list[EpisodeDecisions]:
    """Build episode groups from paired-decision-log rows.

    Rows must carry ``episode_id``, ``score`` and ``r_mem``. Order within an episode is
    preserved, which keeps random-score sidecars aligned positionally.
    """
    order: list[str] = []
    buckets: dict[str, EpisodeDecisions] = {}
    for row in rows:
        ep = str(row["episode_id"])
        if ep not in buckets:
            buckets[ep] = EpisodeDecisions(episode_id=ep)
            order.append(ep)
        buckets[ep].scores.append(float(row["score"]))
        buckets[ep].r_mem.append(int(row["r_mem"]))
    return [buckets[e] for e in order]


def drop_empty(episodes: Sequence[EpisodeDecisions]) -> tuple[list[EpisodeDecisions], list[str]]:
    """Separate usable episodes from zero-decision ones.

    Episodes with T_i = 0 have an undefined per-episode mean and must be excluded from
    the averages, but the brief (§7) requires them to be recorded and diagnosed, so their
    ids are returned rather than silently dropped.
    """
    keep = [e for e in episodes if not e.is_empty]
    dropped = [e.episode_id for e in episodes if e.is_empty]
    return keep, dropped
