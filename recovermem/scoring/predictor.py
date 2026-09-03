"""The recoverability predictor (brief §9).

Model: L2-regularised logistic regression with ``class_weight='balanced'``, exactly the
model the old code used (``predictor.py:448-479``) -- the brief forbids inventing a
different one during a cleanup. Two things are new:

* ``save``/``load``. The old predictor never persisted its coefficients, so "frozen
  before calibration" was unenforceable in practice.
* A ``FEATURE_SCHEMA_VERSION`` + feature-name check on load, so a saved model can never
  be applied to a differently-ordered feature vector.

Training uses TRAIN episodes only. ``freeze()`` is required before the predictor may be
handed to calibration, and fitting a frozen predictor raises.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Sequence

import numpy as np

from recovermem.scoring.features import (
    FEATURE_SCHEMA_VERSION,
    HOST_AGNOSTIC_FEATURES,
    FeatureRecord,
)
from recovermem.scoring.normalizer import Normalizer


class RecoverabilityPredictor:
    """s = sigma(w . x + b), fitted on train episodes, frozen before calibration."""

    def __init__(self, feature_names: Sequence[str] = HOST_AGNOSTIC_FEATURES):
        self.feature_names = list(feature_names)
        self.schema_version = FEATURE_SCHEMA_VERSION
        self.coef: Optional[np.ndarray] = None
        self.intercept: float = 0.0
        self.normalizer: Optional[Normalizer] = None
        self.frozen: bool = False
        self.n_train_decisions: int = 0
        self.n_train_episodes: int = 0

    # -- training ----------------------------------------------------------

    def fit(
        self,
        features: Sequence[FeatureRecord] | Sequence[Sequence[float]],
        labels: Sequence[int],
        n_train_episodes: int = 0,
        seed: int = 13,
    ) -> "RecoverabilityPredictor":
        if self.frozen:
            raise RuntimeError("predictor is frozen; refit would invalidate calibration")
        from sklearn.linear_model import LogisticRegression

        X = self._matrix(features)
        y = np.asarray(labels, dtype=int)
        if X.shape[0] != y.shape[0]:
            raise ValueError(f"{X.shape[0]} feature rows but {y.shape[0]} labels")
        if len(set(y.tolist())) < 2:
            raise ValueError(
                f"training labels are all {y[0] if len(y) else 'empty'}; a predictor "
                "cannot be fitted on one class. Report this rather than working around it."
            )

        self.normalizer = Normalizer.fit(X, self.feature_names)
        Z = self.normalizer.transform(X)
        # class_weight='balanced' matters here: recoverability is heavily imbalanced, and
        # without it the intercept collapses every score toward 0, which would leave the
        # calibrated threshold degenerate.
        clf = LogisticRegression(max_iter=500, C=1.0, class_weight="balanced", random_state=seed)
        clf.fit(Z, y)

        # De-standardise so predict() needs no scaler:
        #   coef . (x - mean)/scale + b0  ==  (coef/scale) . x + (b0 - (coef/scale) . mean)
        scale = np.asarray(self.normalizer.scale)
        mean = np.asarray(self.normalizer.mean)
        adjusted = clf.coef_[0] / scale
        self.coef = adjusted
        self.intercept = float(clf.intercept_[0] - float(np.dot(adjusted, mean)))
        self.n_train_decisions = int(X.shape[0])
        self.n_train_episodes = int(n_train_episodes)
        return self

    def freeze(self) -> "RecoverabilityPredictor":
        if self.coef is None:
            raise RuntimeError("cannot freeze an unfitted predictor")
        self.frozen = True
        return self

    # -- inference ---------------------------------------------------------

    def predict_score(self, features: FeatureRecord | Sequence[float]) -> float:
        """Recoverability score in [0, 1] for one decision."""
        if self.coef is None:
            raise RuntimeError("predictor is not fitted")
        x = np.asarray(self._row(features), dtype=np.float64)
        logit = float(np.dot(x, self.coef)) + self.intercept
        # Numerically stable sigmoid; a saturated logit must not overflow to nan.
        if logit >= 0:
            return float(1.0 / (1.0 + np.exp(-logit)))
        z = np.exp(logit)
        return float(z / (1.0 + z))

    def predict_scores(self, features: Sequence[FeatureRecord] | Sequence[Sequence[float]]) -> list[float]:
        return [self.predict_score(f) for f in features]

    # -- persistence -------------------------------------------------------

    def save(self, path: str | Path) -> None:
        if self.coef is None:
            raise RuntimeError("refusing to save an unfitted predictor")
        payload = {
            "schema_version": self.schema_version,
            "feature_names": self.feature_names,
            "coef": self.coef.tolist(),
            "intercept": self.intercept,
            "frozen": self.frozen,
            "n_train_decisions": self.n_train_decisions,
            "n_train_episodes": self.n_train_episodes,
            "normalizer": self.normalizer.to_dict() if self.normalizer else None,
        }
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, indent=2))

    @classmethod
    def load(cls, path: str | Path) -> "RecoverabilityPredictor":
        payload = json.loads(Path(path).read_text())
        if payload["schema_version"] != FEATURE_SCHEMA_VERSION:
            raise ValueError(
                f"saved predictor uses feature schema {payload['schema_version']!r} but "
                f"this code is {FEATURE_SCHEMA_VERSION!r}; the vector layout may differ"
            )
        obj = cls(feature_names=payload["feature_names"])
        if list(obj.feature_names) != list(HOST_AGNOSTIC_FEATURES):
            raise ValueError(
                "saved feature names do not match the current host-agnostic schema"
            )
        obj.coef = np.asarray(payload["coef"], dtype=np.float64)
        obj.intercept = float(payload["intercept"])
        obj.frozen = bool(payload["frozen"])
        obj.n_train_decisions = int(payload.get("n_train_decisions", 0))
        obj.n_train_episodes = int(payload.get("n_train_episodes", 0))
        if payload.get("normalizer"):
            obj.normalizer = Normalizer.from_dict(payload["normalizer"])
        return obj

    # -- helpers -----------------------------------------------------------

    def _row(self, f: FeatureRecord | Sequence[float]) -> list[float]:
        if isinstance(f, FeatureRecord):
            if f.schema_version != self.schema_version:
                raise ValueError(
                    f"feature record schema {f.schema_version!r} != predictor schema "
                    f"{self.schema_version!r}"
                )
            return f.vector(self.feature_names)
        return [float(v) for v in f]

    def _matrix(self, features) -> np.ndarray:
        return np.asarray([self._row(f) for f in features], dtype=np.float64)
