"""Immutable raw-trajectory log H_t (adapted from ``recovermem_probe/run_one_episode.py``).

H_t is the ground truth the recovery backend reads and the scorer must never see. It is
append-only and defensively copied on read, so no downstream component can mutate the
history it was given and then be replayed differently.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Optional


class TrajectoryLog:
    """Append-only record of one episode's raw interaction."""

    def __init__(self, episode_id: str, path: Optional[str | Path] = None):
        self.episode_id = episode_id
        self._messages: list[dict[str, Any]] = []
        self.path = Path(path) if path else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists() and self.path.stat().st_size:
                # Writes append, so a pre-existing file would interleave two runs'
                # trajectories in one H_t on disk.
                raise RuntimeError(
                    f"trajectory file {self.path} already exists and is non-empty; "
                    f"refusing to append a second run's history onto it"
                )

    def append(self, message: dict[str, Any]) -> None:
        self._messages.append(copy.deepcopy(message))
        if self.path:
            with self.path.open("a") as fh:
                fh.write(json.dumps(message, default=str) + "\n")

    def extend(self, messages: list[dict[str, Any]]) -> None:
        for m in messages:
            self.append(m)

    @property
    def messages(self) -> list[dict[str, Any]]:
        """A deep copy. H_t is immutable to every consumer."""
        return copy.deepcopy(self._messages)

    def prefix(self, upto: int) -> list[dict[str, Any]]:
        """H_t as of just before step ``upto`` -- what recovery is allowed to read."""
        return copy.deepcopy(self._messages[:upto])

    def __len__(self) -> int:
        return len(self._messages)
