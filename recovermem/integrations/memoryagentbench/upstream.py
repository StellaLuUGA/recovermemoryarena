"""Safe access to the upstream MemoryAgentBench modules (MAB-AR integration).

MemoryAgentBench is used as a *library*: its dataset loading, chunking, query templates
and native metric are imported verbatim so the benchmark definition stays upstream's.
Nothing here writes to the MAB checkout and nothing here is patched.

The one hazard is the import path. The MAB checkout vendors directories named ``mem0``,
``letta`` and ``cognee`` at its repository root. Putting that root at the FRONT of
``sys.path`` -- the obvious thing to do -- would make ``import mem0`` resolve to
MemoryAgentBench's vendored copy instead of the pinned Mem0 OSS checkout that is the
paper's scientific host. This module therefore:

1. imports the pinned Mem0 FIRST, so it is already in ``sys.modules``;
2. APPENDS the MAB root to ``sys.path`` (never inserts at 0);
3. asserts, after loading, that ``mem0`` still resolves inside the pinned checkout.

The assertion is the point: a silent host swap would be invisible in the results.
"""

from __future__ import annotations

import functools
import sys
from pathlib import Path
from typing import Any

MAB_ROOT = Path("/home/aristella/recoverappworld/MemoryAgentBench")
PINNED_MEM0_ROOT = Path("/home/aristella/recoverappworld/mem0")


def _assert_mem0_pinned() -> str:
    """Import the pinned Mem0 and return its resolved module path."""
    import os

    os.environ["MEM0_TELEMETRY"] = "False"
    os.environ["MEM0_TELEMETRY_SAMPLE_RATE"] = "0.0"
    import mem0

    resolved = Path(mem0.__file__).resolve()
    if PINNED_MEM0_ROOT not in resolved.parents:
        raise RuntimeError(
            f"mem0 resolved to {resolved}, outside the pinned checkout {PINNED_MEM0_ROOT}. "
            f"MemoryAgentBench vendors its own mem0/ -- the scientific host must not be it."
        )
    return str(resolved)


@functools.lru_cache(maxsize=1)
def load_mab() -> dict[str, Any]:
    """Return the upstream MAB callables this integration depends on."""
    if not MAB_ROOT.exists():
        raise FileNotFoundError(f"MemoryAgentBench checkout not found at {MAB_ROOT}")

    mem0_path = _assert_mem0_pinned()

    root = str(MAB_ROOT)
    if root not in sys.path:
        sys.path.append(root)  # APPEND, never insert(0): see module docstring.

    from utils.eval_data_utils import load_eval_data
    from utils.eval_other_utils import chunk_text_into_sentences, post_process
    from utils.templates import get_template

    # Re-check: loading MAB's utils must not have shadowed the pinned host.
    if _assert_mem0_pinned() != mem0_path:
        raise RuntimeError("mem0 module identity changed after importing MemoryAgentBench")

    return {
        "load_eval_data": load_eval_data,
        "chunk_text_into_sentences": chunk_text_into_sentences,
        "post_process": post_process,
        "get_template": get_template,
        "mab_root": root,
        "mem0_path": mem0_path,
    }


def mab_git_commit() -> str:
    import subprocess

    try:
        out = subprocess.run(
            ["git", "-C", str(MAB_ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10, check=True,
        )
        return out.stdout.strip()
    except Exception as exc:  # pragma: no cover
        return f"<unavailable: {exc}>"
