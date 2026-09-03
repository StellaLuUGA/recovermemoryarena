"""Host adapters. Table 1 uses ``mem0`` only.

``build_host`` is the single construction point, and it imports each adapter LAZILY.
That is what makes the brief's §16 requirement structural: selecting ``host="mem0"``
never executes the Three-Layer Memory module at all, so it cannot be instantiated by
accident.
"""

from __future__ import annotations

from typing import Any

SUPPORTED_HOSTS = ("mem0", "three_layer")

#: Set by the Three-Layer adapter when (and only when) it is actually constructed.
#: ``tests/test_no_three_layer.py`` asserts this stays False for the Mem0 path.
THREE_LAYER_INSTANTIATED = False


def build_host(host: str, **kwargs: Any):
    """Construct a host adapter by name, importing only that adapter's module."""
    if host == "mem0":
        from recovermem.hosts.mem0_adapter import Mem0Adapter

        return Mem0Adapter(**kwargs)
    if host == "three_layer":
        # Optional future host (brief §3-C). Never reached by the Table 1 config.
        from recovermem.hosts.three_layer_adapter import ThreeLayerAdapter

        return ThreeLayerAdapter(**kwargs)
    raise ValueError(f"unknown host {host!r}; supported: {SUPPORTED_HOSTS}")
