"""TRUST / RECOVER routing (brief §12, §13).

The controller is the only component that touches both routes, and it is deliberately the
place where the leakage boundary is enforced:

    scoring sees   (x_t, E_t, a_mem)          -- and is *called with nothing else*
    recovery sees  (x_t, H_t, B_rec)          -- and its output never reaches the scorer

It runs in two modes:

``collect``   both branches are executed from the SAME checkpointed state so u_mem and
              u_rec are both observed. This is what produces the Table 1 dataset. No
              threshold is needed or used.
``route``     the calibrated tau is applied: TRUST executes the memory action, RECOVER
              executes the recovery action. Only one branch runs.

Adapted from the old routing at ``full_replicate/recovermem/agent.py:213-284``, moved
from episode level to step level and stripped of its Three-Layer Memory coupling.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol

from recovermem.interfaces.host_memory import HostMemoryAdapter, MemoryEvidence
from recovermem.interfaces.recovery import RecoveredEvidence, RecoveryBackend
from recovermem.logging.schema import CheckpointInfo, DecisionRecord, TokenAccounting
from recovermem.scoring.features import (
    CandidateAction,
    DecisionState,
    FeatureRecord,
    extract_features,
)
from recovermem.scoring.predictor import RecoverabilityPredictor
from recovermem.tokens import BudgetConfig, TokenCounter

TRUST = "TRUST"
RECOVER = "RECOVER"


class ActionProposer(Protocol):
    """Produces a candidate action from a decision state plus a block of evidence."""

    def __call__(self, state: DecisionState, evidence_text: str, **kwargs: Any) -> CandidateAction: ...


@dataclass
class ControllerConfig:
    gamma: float = 0.5
    #: None in ``collect`` mode; the calibrated threshold in ``route`` mode.
    tau: Optional[float] = None
    mode: str = "collect"  # "collect" | "route"

    def __post_init__(self) -> None:
        if self.mode not in ("collect", "route"):
            raise ValueError(f"unknown controller mode {self.mode!r}")
        if self.mode == "route" and self.tau is None:
            raise ValueError("route mode needs a calibrated tau; run calibration first")


@dataclass
class Decision:
    """What the controller produced for one step."""

    route: str
    score: float
    features: FeatureRecord
    memory_evidence: MemoryEvidence
    memory_action: CandidateAction
    recovery_evidence: Optional[RecoveredEvidence] = None
    recovery_action: Optional[CandidateAction] = None
    action: CandidateAction = field(default_factory=CandidateAction)
    latency_s: float = 0.0
    memory_latency_s: float = 0.0
    recovery_latency_s: float = 0.0


class ReCoverMemController:
    """Host-agnostic recoverability controller."""

    def __init__(
        self,
        host: HostMemoryAdapter,
        recovery: RecoveryBackend,
        predictor: Optional[RecoverabilityPredictor],
        counter: TokenCounter,
        budget: BudgetConfig,
        config: ControllerConfig,
        proposer: ActionProposer,
    ):
        budget.require_frozen()
        if config.mode == "route":
            if predictor is None:
                raise ValueError("route mode needs a fitted predictor")
            if not predictor.frozen:
                raise ValueError(
                    "predictor must be frozen before it is used for routing; an unfrozen "
                    "predictor could still be refitted after calibration"
                )
        self.host = host
        self.recovery = recovery
        self.predictor = predictor
        self.counter = counter
        self.budget = budget
        self.config = config
        self.proposer = proposer

    # -- the two routes ----------------------------------------------------

    def memory_route(self, state: DecisionState) -> tuple[MemoryEvidence, CandidateAction, float]:
        """x_t -> E_t (<= B_mem) -> a_mem."""
        started = time.perf_counter()
        evidence = self.host.retrieve(state.query, self.budget.memory_budget_tokens)
        action = self.proposer(state, evidence.text, route=TRUST)
        return evidence, action, time.perf_counter() - started

    def recovery_route(
        self, state: DecisionState, history: list[dict[str, Any]]
    ) -> tuple[RecoveredEvidence, CandidateAction, float]:
        """x_t -> bounded evidence from H_t (<= B_rec) -> a_rec."""
        started = time.perf_counter()
        evidence = self.recovery.recover(
            state.query, history, self.budget.recovery_budget_tokens
        )
        action = self.proposer(state, evidence.text, route=RECOVER)
        return evidence, action, time.perf_counter() - started

    # -- scoring -----------------------------------------------------------

    def score(
        self, state: DecisionState, evidence: MemoryEvidence, candidate: CandidateAction
    ) -> tuple[float, FeatureRecord]:
        """Score the memory route. Note the three arguments -- there is no fourth."""
        features = extract_features(state, evidence, candidate)
        if self.predictor is None:
            # Collection runs before a predictor exists. A constant score is honest here;
            # the features are what matter, and 0.5 is recorded as such in the log.
            return 0.5, features
        return self.predictor.predict_score(features), features

    # -- the decision ------------------------------------------------------

    def decide(
        self,
        state: DecisionState,
        history: Optional[list[dict[str, Any]]] = None,
    ) -> Decision:
        """Run the controller for one step.

        In ``collect`` mode ``history`` is required: both branches must be produced.
        """
        started = time.perf_counter()
        mem_evidence, mem_action, mem_latency = self.memory_route(state)
        score, features = self.score(state, mem_evidence, mem_action)

        rec_evidence = rec_action = None
        rec_latency = 0.0

        if self.config.mode == "collect":
            if history is None:
                raise ValueError("collect mode requires H_t to produce the recovery branch")
            rec_evidence, rec_action, rec_latency = self.recovery_route(state, history)
            route = TRUST if score >= 0.5 else RECOVER  # recorded, not acted upon
            chosen = mem_action
        else:
            route = TRUST if score >= self.config.tau else RECOVER
            if route == RECOVER:
                if history is None:
                    raise ValueError("RECOVER route requires H_t")
                rec_evidence, rec_action, rec_latency = self.recovery_route(state, history)
                chosen = rec_action
            else:
                chosen = mem_action

        return Decision(
            route=route,
            score=score,
            features=features,
            memory_evidence=mem_evidence,
            memory_action=mem_action,
            recovery_evidence=rec_evidence,
            recovery_action=rec_action,
            action=chosen,
            latency_s=time.perf_counter() - started,
            memory_latency_s=mem_latency,
            recovery_latency_s=rec_latency,
        )

    # -- logging -----------------------------------------------------------

    def build_record(
        self,
        decision: Decision,
        *,
        episode_id: str,
        decision_id: str,
        task_id: str,
        step_index: int,
        u_mem: float,
        u_rec: float,
        history_tokens: int,
        base_tokens: int,
        checkpoint: Optional[CheckpointInfo] = None,
        state: Optional[DecisionState] = None,
        memory_branch_state_hash: str = "",
        recovery_branch_state_hash: str = "",
        group: str = "",
        group_attributes: Optional[dict[str, Any]] = None,
        split: str = "",
        model: str = "",
    ) -> DecisionRecord:
        """Assemble the full §13 record. Every token field is filled here or nowhere."""
        tokens = TokenAccounting(
            history_tokens=history_tokens,
            memory_evidence_tokens=decision.memory_evidence.tokens,
            recovered_evidence_tokens=(
                decision.recovery_evidence.tokens if decision.recovery_evidence else 0
            ),
            base_tokens=base_tokens,
            available_tokens=self.budget.available(base_tokens),
            mem0_write_tokens=getattr(self.host, "write_prompt_tokens", 0),
            controller_tokens=self.counter.count_text(decision.memory_evidence.text),
            memory_route_tokens=base_tokens + decision.memory_evidence.tokens,
            recovery_route_tokens=(
                base_tokens + decision.recovery_evidence.tokens
                if decision.recovery_evidence
                else 0
            ),
        )
        return DecisionRecord(
            episode_id=episode_id,
            decision_id=decision_id,
            task_id=task_id,
            step_index=step_index,
            u_mem=u_mem,
            u_rec=u_rec,
            common_state_text=state.query if state else "",
            common_state_tokens=state.state_tokens if state else 0,
            common_state_hash=state.state_hash if state else "",
            memory_branch_common_state_hash=memory_branch_state_hash,
            recovery_branch_common_state_hash=recovery_branch_state_hash,
            score=decision.score,
            features=decision.features.to_log(),
            group=group,
            group_attributes=dict(group_attributes or {}),
            checkpoint=checkpoint or CheckpointInfo(),
            tokens=tokens,
            b_ctx=self.budget.context_limit,
            b_mem=self.budget.memory_budget_tokens,
            b_rec=self.budget.recovery_budget_tokens,
            memory_action={"name": decision.memory_action.name,
                           "arguments": decision.memory_action.arguments},
            recovery_action=(
                {"name": decision.recovery_action.name,
                 "arguments": decision.recovery_action.arguments}
                if decision.recovery_action else {}
            ),
            memory_evidence=decision.memory_evidence.to_log(),
            recovery_evidence=(
                decision.recovery_evidence.to_log() if decision.recovery_evidence else {}
            ),
            latency_s=decision.latency_s,
            memory_latency_s=decision.memory_latency_s,
            recovery_latency_s=decision.recovery_latency_s,
            split=split,
            model=model,
        )
