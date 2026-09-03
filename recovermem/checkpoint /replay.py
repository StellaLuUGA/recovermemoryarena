"""Replay verification helper (adapted from ``recovermem_probe/part0_replay_check.py``).

Before a benchmark may be used in ``deterministic_replay`` mode, it must be *shown* to be
deterministic. This runs the same action prefix twice from fresh environments and
compares state hashes; anything less would let a non-deterministic environment produce
pairs that look valid and are not.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence


@dataclass
class ReplayCheck:
    deterministic: bool
    hash_a: str
    hash_b: str
    n_actions: int
    error: str = ""

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def verify_replay_determinism(
    make_env_fn: Callable[[], Any],
    apply_action_fn: Callable[[Any, Any], Any],
    hash_fn: Callable[[Any], str],
    actions: Sequence[Any],
) -> ReplayCheck:
    """Replay ``actions`` twice from scratch and compare the resulting state hashes."""
    try:
        hashes = []
        for _ in range(2):
            env = make_env_fn()
            for action in actions:
                apply_action_fn(env, action)
            hashes.append(hash_fn(env))
    except Exception as exc:
        return ReplayCheck(False, "", "", len(actions), error=str(exc))
    return ReplayCheck(
        deterministic=hashes[0] == hashes[1],
        hash_a=hashes[0],
        hash_b=hashes[1],
        n_actions=len(actions),
    )
