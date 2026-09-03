"""The host memory interface (brief §5).

ReCoverMem treats the host memory as *external and opaque*. The controller consumes

    E_t = host.retrieve(query, budget_tokens)

and nothing else. It never inspects the host's internal representation, which is what
makes the same controller valid for Mem0, Three-Layer Memory, or any future host without
a single conditional on the host type.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class MemoryEvidence:
    """E_t: the packed, budget-respecting evidence handed to the agent.

    ``candidates`` keeps the FULL ranked candidate list returned by the host before
    packing. The brief (§6) requires this so budget ablations can be recomputed without
    rerunning retrieval -- re-running it would resample the LLM and change the evidence
    for reasons unrelated to the budget.
    """

    text: str
    tokens: int
    budget_tokens: int
    items: list[dict[str, Any]] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    latency_s: float = 0.0
    host: str = ""

    def __post_init__(self) -> None:
        if self.tokens > self.budget_tokens:
            raise ValueError(
                f"host '{self.host}' returned {self.tokens} tokens > budget "
                f"{self.budget_tokens}; packing is broken"
            )

    @property
    def n_candidates(self) -> int:
        return len(self.candidates)

    @property
    def n_packed(self) -> int:
        return len(self.items)

    def to_log(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "tokens": self.tokens,
            "budget_tokens": self.budget_tokens,
            "n_candidates": self.n_candidates,
            "n_packed": self.n_packed,
            "latency_s": self.latency_s,
            "candidates": self.candidates,
        }


@dataclass
class WriteResult:
    """Outcome of one host write, for token/cost accounting."""

    n_added: int = 0
    n_updated: int = 0
    n_deleted: int = 0
    prompt_tokens: int = 0
    latency_s: float = 0.0
    raw: Any = None

    def to_log(self) -> dict[str, Any]:
        return {
            "n_added": self.n_added,
            "n_updated": self.n_updated,
            "n_deleted": self.n_deleted,
            "prompt_tokens": self.prompt_tokens,
            "latency_s": self.latency_s,
        }


class HostMemoryAdapter(abc.ABC):
    """Common interface every memory host must satisfy."""

    #: Short host identifier recorded in every log row.
    name: str = "abstract"

    @abc.abstractmethod
    def reset(self, episode_id: str) -> None:
        """Drop all state and bind the host to a fresh episode."""

    @abc.abstractmethod
    def write(self, messages: list[dict[str, Any]], **kwargs: Any) -> WriteResult:
        """Ingest new interaction content using the host's own native write logic."""

    @abc.abstractmethod
    def retrieve(self, query: str, budget_tokens: int) -> MemoryEvidence:
        """Return evidence of at most ``budget_tokens`` tokens (B_mem)."""

    @abc.abstractmethod
    def snapshot(self) -> dict[str, Any]:
        """Serializable description of current store contents, for auditing."""

    @abc.abstractmethod
    def metadata(self) -> dict[str, Any]:
        """Provenance: implementation, commit, models, endpoints."""
