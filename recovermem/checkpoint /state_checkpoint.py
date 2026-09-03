"""Same-state paired evaluation (brief §14).

To compare the memory route against the recovery route we must run BOTH from the
identical pre-decision state. This module provides that guarantee generically -- it makes
no assumption that the environment supports snapshots, which is why two modes exist:

* ``native_snapshot``      -- the environment can serialise and restore its own state.
* ``deterministic_replay`` -- it cannot, so the state is rebuilt by replaying the action
                              prefix from a fresh environment.

``pair_valid`` is set to True only after the state hash entering the second branch is
*verified equal* to the hash entering the first. Nothing in this package ever assumes a
pair is valid; the old code had no pairing concept at all, so there is nothing to inherit
here and everything to prove.
"""

from __future__ import annotations

import abc
import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from recovermem.logging.schema import CheckpointInfo


def hash_state(state: Any) -> str:
    """Stable hash of any JSON-serialisable environment state."""
    payload = json.dumps(state, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


@dataclass
class CheckpointHandle:
    checkpoint_id: str
    mode: str
    state_hash: str
    payload: Any = None
    action_prefix: list[Any] = field(default_factory=list)
    path: str = ""


class StateCheckpoint(abc.ABC):
    """Capture/restore a pre-decision environment state."""

    mode: str = "none"

    @abc.abstractmethod
    def capture(self, env: Any, checkpoint_id: str) -> CheckpointHandle: ...

    @abc.abstractmethod
    def restore(self, env: Any, handle: CheckpointHandle) -> Any: ...

    @abc.abstractmethod
    def state_hash(self, env: Any) -> str: ...


class NativeSnapshotCheckpoint(StateCheckpoint):
    """Uses the environment's own state serialisation.

    ``get_state_fn``/``set_state_fn``/``hash_fn`` are injected rather than hard-coded so
    this class stays benchmark-agnostic; the tau^3 wiring lives in ``integrations/tau3``.
    """

    mode = "native_snapshot"

    def __init__(
        self,
        get_state_fn: Callable[[Any], Any],
        set_state_fn: Callable[[Any, Any], Any],
        hash_fn: Optional[Callable[[Any], str]] = None,
    ):
        self._get = get_state_fn
        self._set = set_state_fn
        self._hash = hash_fn

    def capture(self, env: Any, checkpoint_id: str) -> CheckpointHandle:
        state = copy.deepcopy(self._get(env))
        return CheckpointHandle(
            checkpoint_id=checkpoint_id,
            mode=self.mode,
            state_hash=self.state_hash(env),
            payload=state,
        )

    def restore(self, env: Any, handle: CheckpointHandle) -> Any:
        return self._set(env, copy.deepcopy(handle.payload))

    def state_hash(self, env: Any) -> str:
        if self._hash is not None:
            return self._hash(env)
        return hash_state(self._get(env))


class DeterministicReplayCheckpoint(StateCheckpoint):
    """Rebuilds state by replaying the action prefix into a fresh environment.

    Adapted from ``recovermem_probe/part0_replay_check.py``. Slower than a snapshot but
    it needs no environment support, and the resulting hash check is just as strict.
    """

    mode = "deterministic_replay"

    def __init__(
        self,
        make_env_fn: Callable[[], Any],
        apply_action_fn: Callable[[Any, Any], Any],
        hash_fn: Callable[[Any], str],
    ):
        self._make_env = make_env_fn
        self._apply = apply_action_fn
        self._hash = hash_fn

    def capture(self, env: Any, checkpoint_id: str, action_prefix: Optional[list] = None) -> CheckpointHandle:
        return CheckpointHandle(
            checkpoint_id=checkpoint_id,
            mode=self.mode,
            state_hash=self.state_hash(env),
            action_prefix=list(action_prefix or []),
        )

    def restore(self, env: Any, handle: CheckpointHandle) -> Any:
        fresh = self._make_env()
        for action in handle.action_prefix:
            self._apply(fresh, action)
        replayed = self.state_hash(fresh)
        if replayed != handle.state_hash:
            raise RuntimeError(
                f"replay diverged: {replayed} != {handle.state_hash}. The environment is "
                f"not deterministic under replay; paired evaluation is invalid."
            )
        return fresh

    def state_hash(self, env: Any) -> str:
        return self._hash(env)


@dataclass
class PairedOutcome:
    """Result of running both branches from one checkpoint."""

    info: CheckpointInfo
    memory_result: Any = None
    recovery_result: Any = None
    error: str = ""


class PairedEvaluator:
    """Runs the memory branch and the recovery branch from the same captured state.

    Both branches may MUTATE the environment -- that is the point of executing their
    proposed actions. So the evaluation must leave no trace: with ``restore_after`` (the
    default) the environment is returned to the captured state once both branches have
    run, and the restored hash is verified. Without it, the caller's episode would
    silently continue from whichever branch happened to run last, and every subsequent
    decision in that episode would be evaluated from a state no protocol intended.
    """

    def __init__(self, checkpoint: StateCheckpoint, restore_after: bool = True):
        self.checkpoint = checkpoint
        self.restore_after = restore_after

    def evaluate(
        self,
        env: Any,
        checkpoint_id: str,
        memory_branch: Callable[[Any], Any],
        recovery_branch: Callable[[Any], Any],
        **capture_kwargs: Any,
    ) -> PairedOutcome:
        info = CheckpointInfo(checkpoint_id=checkpoint_id, checkpoint_mode=self.checkpoint.mode)
        try:
            handle = self.checkpoint.capture(env, checkpoint_id, **capture_kwargs)
        except Exception as exc:
            info.invalid_reason = f"capture failed: {exc}"
            return PairedOutcome(info=info, error=str(exc))

        info.path = handle.path
        info.state_hash_before = handle.state_hash

        try:
            mem_env = self.checkpoint.restore(env, handle) or env
            info.state_hash_memory_branch = self.checkpoint.state_hash(mem_env)
            memory_result = memory_branch(mem_env)
        except Exception as exc:
            info.invalid_reason = f"memory branch failed: {exc}"
            return PairedOutcome(info=info, error=str(exc))

        try:
            rec_env = self.checkpoint.restore(env, handle) or env
            info.state_hash_recovery_branch = self.checkpoint.state_hash(rec_env)
            recovery_result = recovery_branch(rec_env)
        except Exception as exc:
            info.invalid_reason = f"recovery branch failed: {exc}"
            return PairedOutcome(info=info, memory_result=memory_result, error=str(exc))

        # The pair is valid only if both branches genuinely started from the same state.
        same = (
            info.state_hash_before
            == info.state_hash_memory_branch
            == info.state_hash_recovery_branch
            != ""
        )
        info.pair_valid = same
        if not same:
            info.invalid_reason = (
                f"state hashes differ: before={info.state_hash_before} "
                f"mem={info.state_hash_memory_branch} rec={info.state_hash_recovery_branch}"
            )

        if self.restore_after:
            try:
                restored = self.checkpoint.restore(env, handle) or env
                info.state_hash_after = self.checkpoint.state_hash(restored)
            except Exception as exc:
                info.state_hash_after = ""
                info.pair_valid = False
                info.invalid_reason = f"post-pair restore failed: {exc}"
                return PairedOutcome(info=info, memory_result=memory_result,
                                     recovery_result=recovery_result, error=str(exc))
            if info.state_hash_after != info.state_hash_before:
                # The episode would carry a branch's side effects forward.
                info.pair_valid = False
                # Keep the first diagnosis: if the pair was already invalid, that is the
                # root cause and this is only its downstream symptom.
                info.invalid_reason = info.invalid_reason or (
                    f"environment not restored after pairing: "
                    f"{info.state_hash_after} != {info.state_hash_before}"
                )

        return PairedOutcome(info=info, memory_result=memory_result, recovery_result=recovery_result)
