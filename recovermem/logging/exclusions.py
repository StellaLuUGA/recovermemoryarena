"""Frozen infrastructure-exclusion rule (frozen 2026-08-25, before any predictor fit).

A decision is excluded ONLY when the measurement apparatus failed. Agent behaviour --
however bad -- is the signal, not noise, and excluding it would silently redefine what
ReCoverMem is measuring.

EXCLUDE (mechanically detectable apparatus failure)
    pair_valid == False
    checkpoint / state-restoration mismatch
    failed or missing native utility evaluation
    harness or environment exception preventing valid trajectory progress
    token / evidence budget invariant violation
    corrupted or incomplete required logs

NEVER EXCLUDE (agent behaviour -- this IS the measurement)
    agent-generated invalid actions
    wrong tool selected
    nonexistent entity ids proposed by the agent
    repeated actions
    low u_mem or u_rec
    memory failures
    recovery failures

The negative list is enforced by tests, not only by documentation: a decision whose only
defect is that the agent behaved badly must survive this filter. Note in particular that
a *tool call that the environment rejected* is agent behaviour, not apparatus failure --
only an exception that prevented the harness from measuring the decision counts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

RULE_VERSION = "infrastructure-exclusion-v1"
FROZEN_AT = "2026-08-25"

#: Machine-readable reasons. Anything not on this list is not grounds for exclusion.
EXCLUSION_REASONS = (
    "pair_invalid",
    "state_restoration_mismatch",
    "missing_native_utility",
    "harness_exception",
    "budget_invariant_violation",
    "incomplete_log",
)

#: Documented for the tests that assert these never trigger an exclusion.
NEVER_EXCLUDED = (
    "agent_invalid_action",
    "wrong_tool",
    "nonexistent_entity_id",
    "repeated_action",
    "low_utility",
    "memory_failure",
    "recovery_failure",
)

_REQUIRED = (
    "episode_id", "decision_id", "task_id", "u_mem", "u_rec", "score",
    "features", "group", "b_mem", "b_rec",
)


@dataclass
class ExclusionVerdict:
    decision_key: str
    excluded: bool
    reasons: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_key": self.decision_key,
            "excluded": self.excluded,
            "reasons": list(self.reasons),
            "detail": dict(self.detail),
            "rule_version": RULE_VERSION,
        }


def _missing_utility(value: Any) -> bool:
    if value is None:
        return True
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return True


def classify(record: Any) -> ExclusionVerdict:
    """Apply the frozen rule to one ``DecisionRecord``."""
    key = f"{getattr(record, 'episode_id', '?')}::{getattr(record, 'decision_id', '?')}"
    reasons: list[str] = []
    detail: dict[str, Any] = {}

    ck = getattr(record, "checkpoint", None)
    if ck is None or not getattr(ck, "pair_valid", False):
        reasons.append("pair_invalid")
        detail["invalid_reason"] = getattr(ck, "invalid_reason", "no checkpoint recorded")

    if ck is not None and getattr(ck, "state_hash_after", ""):
        if ck.state_hash_after != ck.state_hash_before:
            reasons.append("state_restoration_mismatch")
            detail["state_hash_before"] = ck.state_hash_before
            detail["state_hash_after"] = ck.state_hash_after

    if _missing_utility(getattr(record, "u_mem", None)) or _missing_utility(
        getattr(record, "u_rec", None)
    ):
        reasons.append("missing_native_utility")

    # Only harness/environment exceptions count. An action the environment REJECTED is
    # agent behaviour and is recorded elsewhere; it must not reach this list.
    errors = list(getattr(record, "errors", []) or [])
    if errors:
        reasons.append("harness_exception")
        detail["errors"] = errors[:5]

    tokens = getattr(record, "tokens", None)
    if tokens is not None:
        if tokens.memory_evidence_tokens > getattr(record, "b_mem", 0):
            reasons.append("budget_invariant_violation")
            detail["memory_tokens"] = tokens.memory_evidence_tokens
        elif tokens.recovered_evidence_tokens > getattr(record, "b_rec", 0):
            reasons.append("budget_invariant_violation")
            detail["recovery_tokens"] = tokens.recovered_evidence_tokens

    missing = [f for f in _REQUIRED if getattr(record, f, None) in (None, "")]
    if missing:
        reasons.append("incomplete_log")
        detail["missing_fields"] = missing

    return ExclusionVerdict(
        decision_key=key,
        excluded=bool(reasons),
        reasons=sorted(set(reasons)),
        detail=detail,
    )


def apply_rule(records: Sequence[Any]) -> tuple[list[Any], list[ExclusionVerdict]]:
    """Split records into (kept, excluded_verdicts)."""
    kept, excluded = [], []
    for r in records:
        verdict = classify(r)
        (excluded if verdict.excluded else kept).append(verdict if verdict.excluded else r)
    return kept, excluded


def summarize(records: Sequence[Any]) -> dict[str, Any]:
    """Exclusion report for a collected run."""
    kept, excluded = apply_rule(records)
    counts: dict[str, int] = {}
    for v in excluded:
        for reason in v.reasons:
            counts[reason] = counts.get(reason, 0) + 1
    n = len(records)
    return {
        "rule_version": RULE_VERSION,
        "frozen_at": FROZEN_AT,
        "n_total": n,
        "n_kept": len(kept),
        "n_excluded": len(excluded),
        "exclusion_rate": (len(excluded) / n) if n else float("nan"),
        "reason_counts": counts,
        "excluded_keys": [v.decision_key for v in excluded][:50],
    }
