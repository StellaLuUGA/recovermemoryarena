"""The paired-decision record (brief §13).

This schema is written BEFORE any expensive collection because every downstream analysis
-- calibration, gamma sensitivity, feature ablation, group FS, Mondrian CRC,
calibration-size sensitivity, Any-FS, risk-coverage curves, token/cost accounting --
reads these rows and nothing else. A field missing here is an experiment that has to be
re-run.

Two deliberate choices:

* CONTINUOUS ``u_mem`` and ``u_rec`` are stored, never only the derived ``R_mem``.
  Storing the binary label alone would hard-wire one gamma and make §11's gamma
  sensitivity impossible to compute after the fact.
* ``pair_valid`` defaults to False. A pair is valid only once same-state equivalence has
  been *verified*; the old code had no such notion, and assuming validity is exactly the
  failure that would silently invalidate Table 1.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

SCHEMA_VERSION = "recovermem-decision-v1"


@dataclass
class RunManifest:
    """Provenance shared by every decision in a run."""

    run_id: str
    seed: int
    split: str
    host: str
    agent_model: str
    mem0_llm_model: str
    embedding_model: str
    gamma: float
    b_ctx: int
    b_mem: int
    b_rec: int
    git_commits: dict[str, str] = field(default_factory=dict)
    host_metadata: dict[str, Any] = field(default_factory=dict)
    feature_schema_version: str = ""
    notes: str = ""

    def config_hash(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["config_hash"] = self.config_hash()
        d["schema_version"] = SCHEMA_VERSION
        return d


@dataclass
class TokenAccounting:
    """Every token quantity the cost analysis needs, measured with the served tokenizer."""

    history_tokens: int = 0
    memory_evidence_tokens: int = 0
    recovered_evidence_tokens: int = 0
    base_tokens: int = 0            # B_base_t
    available_tokens: int = 0       # B_avail_t
    mem0_write_tokens: int = 0
    controller_tokens: int = 0
    memory_route_tokens: int = 0
    recovery_route_tokens: int = 0
    logging_policy_prompt_tokens: int = 0
    logging_policy_completion_tokens: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass
class CheckpointInfo:
    """Same-state pairing evidence (brief §14)."""

    checkpoint_id: str = ""
    #: "native_snapshot" | "deterministic_replay" | "none"
    checkpoint_mode: str = "none"
    path: str = ""
    state_hash_before: str = ""
    state_hash_memory_branch: str = ""
    state_hash_recovery_branch: str = ""
    #: Hash after the pair, once the environment has been restored. Must equal
    #: ``state_hash_before``, otherwise a branch's side effects leaked into the episode.
    state_hash_after: str = ""
    #: True ONLY when both branches were verified to start from the same state.
    pair_valid: bool = False
    invalid_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DecisionRecord:
    """One controlled decision, with both branches evaluated from the same state."""

    # identity
    episode_id: str
    decision_id: str
    task_id: str
    step_index: int

    # paired utilities -- CONTINUOUS, never only the binary label
    u_mem: float = 0.0
    u_rec: float = 0.0

    # the common decision state x_t, handed identically to both branches
    common_state_text: str = ""
    common_state_tokens: int = 0
    common_state_hash: str = ""
    #: Hash of the x_t each branch actually received. Equality is asserted at collection
    #: time; both are stored so the claim is auditable from the log alone.
    memory_branch_common_state_hash: str = ""
    recovery_branch_common_state_hash: str = ""

    # scorer
    score: float = 0.0
    features: dict[str, Any] = field(default_factory=dict)

    # grouping for group FS / Mondrian CRC
    group: str = ""
    group_attributes: dict[str, Any] = field(default_factory=dict)

    # pairing + budgets + tokens
    checkpoint: CheckpointInfo = field(default_factory=CheckpointInfo)
    tokens: TokenAccounting = field(default_factory=TokenAccounting)
    b_ctx: int = 0
    b_mem: int = 0
    b_rec: int = 0

    # routes
    memory_action: dict[str, Any] = field(default_factory=dict)
    recovery_action: dict[str, Any] = field(default_factory=dict)
    #: The action the frozen logging policy executed to reach S_{t+1}. Recorded so the
    #: state distribution the decisions were collected on is reconstructible.
    logging_policy_action: dict[str, Any] = field(default_factory=dict)
    memory_evidence: dict[str, Any] = field(default_factory=dict)
    recovery_evidence: dict[str, Any] = field(default_factory=dict)

    # cost
    latency_s: float = 0.0
    memory_latency_s: float = 0.0
    recovery_latency_s: float = 0.0

    # provenance
    run_id: str = ""
    environment: str = "tau3-bench"
    domain: str = "retail"
    split: str = ""
    subset: str = ""
    seed: int = 0
    model: str = ""
    tokenizer: str = ""

    # artefact paths and integrity
    trajectory_path: str = ""
    trajectory_hash: str = ""
    mem0_store_path: str = ""
    recovery_query: str = ""
    provenance_audit: dict[str, Any] = field(default_factory=dict)

    # frozen logging policy (see §8): full record of what advanced the trajectory
    logging_policy: dict[str, Any] = field(default_factory=dict)

    # status
    episode_terminated: bool = False
    native_task_success: Optional[bool] = None
    git_commits: dict[str, str] = field(default_factory=dict)
    config_hash: str = ""
    schema_version: str = SCHEMA_VERSION
    errors: list[str] = field(default_factory=list)

    def common_state_is_shared(self) -> bool:
        """True iff both branches provably received the same x_t bytes."""
        return bool(self.common_state_hash) and (
            self.memory_branch_common_state_hash
            == self.recovery_branch_common_state_hash
            == self.common_state_hash
        )

    def r_mem(self, gamma: float) -> int:
        """R_mem = 1[u_mem >= gamma]. Derived on demand so gamma stays a free parameter."""
        return int(self.u_mem >= gamma)

    def r_rec(self, gamma: float) -> int:
        return int(self.u_rec >= gamma)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["schema_version"] = SCHEMA_VERSION
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DecisionRecord":
        d = dict(d)
        d.pop("schema_version", None)
        d["checkpoint"] = CheckpointInfo(**d.get("checkpoint", {}) or {})
        d["tokens"] = TokenAccounting(**d.get("tokens", {}) or {})
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


#: Fields whose absence would make a downstream analysis impossible. The serialization
#: test asserts every one of these survives a write/read round-trip.
REQUIRED_LOG_FIELDS = (
    "u_mem", "u_rec", "score", "features", "group", "group_attributes",
    "common_state_text", "common_state_tokens", "common_state_hash",
    "memory_branch_common_state_hash", "recovery_branch_common_state_hash",
    "checkpoint", "tokens", "b_ctx", "b_mem", "b_rec",
    "episode_id", "decision_id", "task_id", "split", "seed", "model",
    "git_commits", "config_hash", "latency_s",
)
