"""JSONL writer/reader for paired decisions.

JSONL rather than a single JSON document: a run that dies mid-episode must leave every
already-collected decision readable, and appends must never require rewriting the file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional, Sequence

from recovermem.logging.schema import (
    REQUIRED_LOG_FIELDS,
    DecisionRecord,
    RunManifest,
)


class PairedDecisionLog:
    """Append-only decision log with a sidecar manifest."""

    def __init__(self, path: str | Path, manifest: Optional[RunManifest] = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if manifest is not None and self.path.exists() and self.path.stat().st_size:
            # A manifest means a NEW run is starting; appending to an existing log would
            # silently mix two runs' decisions under one manifest.
            raise RuntimeError(
                f"decision log {self.path} already exists and is non-empty; refusing to "
                f"start a new run on top of it. Use a fresh output directory."
            )
        self.manifest = manifest
        if manifest is not None:
            self.manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2, default=str))

    @property
    def manifest_path(self) -> Path:
        return self.path.with_suffix(".manifest.json")

    def append(self, record: DecisionRecord) -> None:
        if self.manifest is not None:
            record.config_hash = record.config_hash or self.manifest.config_hash()
            record.git_commits = record.git_commits or self.manifest.git_commits
            record.seed = record.seed or self.manifest.seed
            record.split = record.split or self.manifest.split
        missing = [f for f in REQUIRED_LOG_FIELDS if not hasattr(record, f)]
        if missing:
            raise ValueError(f"decision record missing required fields: {missing}")
        with self.path.open("a") as fh:
            fh.write(json.dumps(record.to_dict(), default=str) + "\n")

    def extend(self, records: Iterable[DecisionRecord]) -> None:
        for r in records:
            self.append(r)

    def read(self) -> list[DecisionRecord]:
        return list(self.iter_records())

    def iter_records(self) -> Iterator[DecisionRecord]:
        if not self.path.exists():
            return
        with self.path.open() as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield DecisionRecord.from_dict(json.loads(line))


def to_episode_rows(
    records: Sequence[DecisionRecord],
    gamma: float,
    only_valid_pairs: bool = True,
) -> list[dict[str, Any]]:
    """Project decision records into the ``{episode_id, score, r_mem}`` rows the
    calibration layer consumes.

    Invalid pairs are excluded by default: a decision whose two branches did not start
    from the same state carries no evidence about recoverability, and including it would
    quietly bias FS.
    """
    rows = []
    for r in records:
        if only_valid_pairs and not r.checkpoint.pair_valid:
            continue
        rows.append(
            {
                "episode_id": r.episode_id,
                "score": r.score,
                "r_mem": r.r_mem(gamma),
                "group": r.group,
                "decision_id": r.decision_id,
            }
        )
    return rows
