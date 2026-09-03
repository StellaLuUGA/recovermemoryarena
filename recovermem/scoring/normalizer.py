"""Feature standardisation with persistable statistics.

The old code fitted a ``StandardScaler`` inside ``fit_weights`` and then threw it away,
keeping only de-standardised coefficients (``predictor.py:461-479``). That trick is
correct and is preserved in ``predictor.py``, but the statistics themselves are still
worth keeping: feature-ablation and drift checks need to know the train-split mean and
scale of every feature. This class stores them explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass
class Normalizer:
    """Per-feature mean/scale fitted on TRAIN episodes only."""

    names: list[str]
    mean: list[float]
    scale: list[float]

    @classmethod
    def fit(cls, matrix: Sequence[Sequence[float]], names: Sequence[str]) -> "Normalizer":
        arr = np.asarray(matrix, dtype=np.float64)
        if arr.ndim != 2 or arr.shape[1] != len(names):
            raise ValueError(f"expected (N, {len(names)}) matrix, got {arr.shape}")
        mean = arr.mean(axis=0)
        scale = arr.std(axis=0)
        # A constant feature carries no information; scale 1.0 maps it to a constant 0
        # instead of producing inf/nan.
        scale[scale == 0.0] = 1.0
        return cls(names=list(names), mean=mean.tolist(), scale=scale.tolist())

    def transform(self, matrix: Sequence[Sequence[float]]) -> np.ndarray:
        arr = np.asarray(matrix, dtype=np.float64)
        return (arr - np.asarray(self.mean)) / np.asarray(self.scale)

    def to_dict(self) -> dict:
        return {"names": self.names, "mean": self.mean, "scale": self.scale}

    @classmethod
    def from_dict(cls, d: dict) -> "Normalizer":
        return cls(names=list(d["names"]), mean=list(d["mean"]), scale=list(d["scale"]))
