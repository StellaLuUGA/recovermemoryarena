"""The recovery backend interface (brief §12).

Recovery reads the immutable raw trajectory H_t and returns BOUNDED evidence. The old
implementation dumped the whole history into the prompt (``agent.py:355-407``), which
gave the recovery route an unbounded context while the memory route was budgeted -- any
TRUST-vs-RECOVER comparison built on that is invalid. The bound is therefore part of the
interface, not a policy a caller may forget.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RecoveredEvidence:
    """Bounded evidence recovered from H_t."""

    text: str
    tokens: int
    budget_tokens: int
    items: list[dict[str, Any]] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    latency_s: float = 0.0
    backend: str = ""

    def __post_init__(self) -> None:
        if self.tokens > self.budget_tokens:
            raise ValueError(
                f"recovery backend '{self.backend}' returned {self.tokens} tokens > "
                f"B_rec {self.budget_tokens}; the memory/recovery comparison would be unfair"
            )

    def to_log(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "tokens": self.tokens,
            "budget_tokens": self.budget_tokens,
            "n_packed": len(self.items),
            "n_candidates": len(self.candidates),
            "latency_s": self.latency_s,
        }


class RecoveryBackend(abc.ABC):
    """Bounded retrieval over the immutable raw trajectory."""

    name: str = "abstract"

    @abc.abstractmethod
    def recover(
        self,
        query: str,
        history: list[dict[str, Any]],
        budget_tokens: int,
    ) -> RecoveredEvidence:
        """Return <= ``budget_tokens`` tokens of evidence drawn from ``history``.

        Implementations MUST NOT mutate ``history`` and MUST NOT write to the host memory.
        """
