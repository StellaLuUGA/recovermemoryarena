"""Request-local server-reported token accounting for every OpenAI-compatible call.

Patches ``Completions.create`` at the class level, so it captures BOTH the Mem0 host's
internal extraction/update calls and the answerer's generation calls, whichever client
object issues them. Usage is read from ``resp.usage`` -- the server's own count -- never
from a local tokenizer, and every call is attributed to the phase that was open when it
was issued. Because attribution is request-local, no global server counter is consulted
and endpoint exclusivity is not required.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager

from openai.resources.chat.completions import Completions

_local = threading.local()
_orig = Completions.create
_installed = False

CALLS: list[dict] = []


def _phase() -> str:
    return getattr(_local, "phase", "unattributed")


def _patched(self, *a, **kw):
    resp = _orig(self, *a, **kw)
    u = getattr(resp, "usage", None)
    CALLS.append({
        "phase": _phase(),
        "model": kw.get("model"),
        "prompt_tokens": int(getattr(u, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(u, "completion_tokens", 0) or 0),
        "total_tokens": int(getattr(u, "total_tokens", 0) or 0),
        "usage_reported": u is not None,
    })
    return resp


def install() -> None:
    global _installed
    if not _installed:
        Completions.create = _patched  # type: ignore[method-assign]
        _installed = True


@contextmanager
def phase(name: str):
    prev = getattr(_local, "phase", "unattributed")
    _local.phase = name
    start = len(CALLS)
    try:
        yield
    finally:
        _local.phase = prev
    del start


def drain(name: str) -> dict:
    """Pop every call recorded so far under ``name`` and total it."""
    keep, taken = [], []
    for c in CALLS:
        (taken if c["phase"] == name else keep).append(c)
    CALLS[:] = keep
    return {
        "phase": name,
        "n_calls": len(taken),
        "prompt_tokens": sum(c["prompt_tokens"] for c in taken),
        "completion_tokens": sum(c["completion_tokens"] for c in taken),
        "total_tokens": sum(c["prompt_tokens"] + c["completion_tokens"] for c in taken),
        "all_usage_reported": all(c["usage_reported"] for c in taken),
        "server_total_tokens_field": sum(c["total_tokens"] for c in taken),
    }
