"""OPTIONAL Three-Layer Memory host -- INACTIVE for Table 1 (brief §3-C, §16).

Three-Layer Memory is *not* part of ReCoverMem. The old implementation instantiated it
unconditionally inside the agent constructor (``full_replicate/recovermem/agent.py:115-136``),
which silently coupled the scorer to one particular host. Here it is demoted to what it
actually is: one host among several, behind the same ``HostMemoryAdapter`` interface.

It is intentionally left unimplemented. The host-generality experiment will fill it in;
until then, constructing it fails loudly rather than quietly returning empty evidence
that would look like a legitimate result.
"""

from __future__ import annotations

from typing import Any

from recovermem.interfaces.host_memory import HostMemoryAdapter, MemoryEvidence, WriteResult


class ThreeLayerAdapter(HostMemoryAdapter):
    """Placeholder for the host-generality experiment. Not used by Table 1."""

    name = "three_layer"

    def __init__(self, *args: Any, **kwargs: Any):
        import recovermem.hosts as _hosts

        _hosts.THREE_LAYER_INSTANTIATED = True
        raise NotImplementedError(
            "Three-Layer Memory is an optional future host and is not implemented for "
            "the Table 1 experiment. Use host='mem0'."
        )

    def reset(self, episode_id: str) -> None:  # pragma: no cover
        raise NotImplementedError

    def write(self, messages: list[dict[str, Any]], **kwargs: Any) -> WriteResult:  # pragma: no cover
        raise NotImplementedError

    def retrieve(self, query: str, budget_tokens: int) -> MemoryEvidence:  # pragma: no cover
        raise NotImplementedError

    def snapshot(self) -> dict[str, Any]:  # pragma: no cover
        raise NotImplementedError

    def metadata(self) -> dict[str, Any]:  # pragma: no cover
        raise NotImplementedError
