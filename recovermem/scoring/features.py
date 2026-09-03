"""Host-agnostic recoverability features (brief §8).

WHAT THE SCORER MAY SEE
    x_t          the current decision state (instruction, step index, tool schema names)
    E_t          the host-retrieved evidence and its observable retrieval statistics
    a_mem        the candidate memory-route action

WHAT IT MAY NEVER SEE
    H_t          the raw trajectory
    E_rec        recovered raw-history evidence
    u_mem, u_rec, R_mem, or any future task outcome

The second list is enforced, not documented: ``extract_features`` takes exactly three
positional inputs and rejects any keyword whose name is on ``FORBIDDEN_INPUTS``. The old
code violated this by conditioning the score on the already-generated draft answer
(``predictor.py:324-334``); making the leak a ``TypeError`` is the only way it stays
fixed.

Every feature is computed from observable quantities only and lands in [0, 1].
``FEATURE_SCHEMA_VERSION`` guards the positional vector -- the old 7-dim vector had no
version, so a reordering would have silently invalidated saved coefficients.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

FEATURE_SCHEMA_VERSION = "recovermem-features-v1"

#: Ordered, host-agnostic. The vector layout is this tuple; never reorder without
#: bumping FEATURE_SCHEMA_VERSION.
HOST_AGNOSTIC_FEATURES: tuple[str, ...] = (
    "retrieval_coverage",
    "entity_coverage",
    "action_arg_support",
    "top_similarity",
    "similarity_margin",
    "support_count_norm",
    "evidence_utilization",
    "conflict_density_inv",
    "action_confidence",
    "step_progress",
)

#: Keyword names that would leak an oracle or the raw trajectory into the scorer.
FORBIDDEN_INPUTS = frozenset(
    {
        "history", "h_t", "raw_history", "trajectory", "messages",
        "recovered", "recovered_evidence", "e_rec",
        "u_mem", "u_rec", "r_mem", "reward", "outcome", "label", "gold",
    }
)

_WORD = re.compile(r"[a-z0-9_#@.\-]+")
#: Identifier-like literals: tau^3 Retail is full of #W0000000 order ids, emails and
#: numeric quantities, and whether those specific tokens survived into memory is far
#: more informative than generic word overlap.
_ENTITY = re.compile(r"(#[A-Za-z]*\d{3,}|\b[\w.+-]+@[\w-]+\.\w+\b|\b\d{3,}\b|\b[A-Z]{2,}\d+\b)")
_STOP = frozenset(
    "a an the is are was were be been being of to in on for with and or if then that this "
    "it its as at by from i you he she they we me my your our their do does did not no yes "
    "please can could would should will shall may might must have has had".split()
)


def _terms(text: str) -> set[str]:
    return {t for t in _WORD.findall((text or "").lower()) if t not in _STOP and len(t) > 1}


def _entities(text: str) -> set[str]:
    return set(_ENTITY.findall(text or ""))


@dataclass
class DecisionState:
    """x_t -- everything about the current step that is observable before acting.

    Note there is no history field. That absence is the point.

    ``query`` is the SERIALIZED common state: the identical bytes handed to both the
    memory branch and the recovery branch. ``state_hash`` pins those bytes so a paired
    decision can prove the two branches saw the same x_t rather than assuming it.
    """

    query: str
    step_index: int = 0
    max_steps: int = 30
    tool_names: list[str] = field(default_factory=list)
    state_hash: str = ""
    state_tokens: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CandidateAction:
    """a_mem -- the action the memory route proposes, before it is executed."""

    name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    text: str = ""
    #: Mean token logprob of the generated action, when the server returns logprobs.
    mean_logprob: Optional[float] = None

    def argument_literals(self) -> set[str]:
        lits: set[str] = set()
        for value in (self.arguments or {}).values():
            if isinstance(value, (str, int, float)):
                lits |= _terms(str(value)) | _entities(str(value))
        return lits


@dataclass
class FeatureRecord:
    """The complete raw feature dictionary plus its ordered vector (brief §8)."""

    values: dict[str, float]
    schema_version: str = FEATURE_SCHEMA_VERSION

    def vector(self, names: Sequence[str] = HOST_AGNOSTIC_FEATURES) -> list[float]:
        return [float(self.values[n]) for n in names]

    def to_log(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "values": dict(self.values)}


def _conflict_density(texts: Sequence[str]) -> float:
    """Fraction of evidence pairs that disagree on a shared entity's context.

    Proxy: two items mention the same entity but one of them negates. Cheap, observable,
    and does not need a second LLM call at decision time.
    """
    if len(texts) < 2:
        return 0.0
    negation = re.compile(r"\b(not|no longer|cancell?ed|failed|denied|invalid|removed)\b", re.I)
    pairs = 0
    conflicts = 0
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            shared = _entities(texts[i]) & _entities(texts[j])
            if not shared:
                continue
            pairs += 1
            if bool(negation.search(texts[i])) != bool(negation.search(texts[j])):
                conflicts += 1
    return conflicts / pairs if pairs else 0.0


def extract_features(
    state: DecisionState,
    evidence: Any,
    candidate: CandidateAction,
    **forbidden: Any,
) -> FeatureRecord:
    """Compute the host-agnostic feature record for one controlled decision.

    ``evidence`` must be a ``MemoryEvidence`` (host output). Any extra keyword is
    rejected: the signature is the leakage boundary.
    """
    if forbidden:
        offending = sorted(set(forbidden) & FORBIDDEN_INPUTS) or sorted(forbidden)
        raise TypeError(
            f"extract_features() received disallowed input(s) {offending}. The scorer is "
            f"host-agnostic and blind to H_t, recovered evidence and all oracle labels "
            f"(brief §8)."
        )

    items = list(getattr(evidence, "items", []) or [])
    candidates = list(getattr(evidence, "candidates", []) or [])
    texts = [str(i.get("memory", i.get("text", ""))) for i in items]
    joined = "\n".join(texts)

    q_terms = _terms(state.query)
    q_ents = _entities(state.query)
    e_terms = _terms(joined)
    e_ents = _entities(joined)

    sims = [c.get("score") for c in candidates if isinstance(c.get("score"), (int, float))]
    sims = sorted((float(s) for s in sims), reverse=True)
    top_sim = _clip01(sims[0]) if sims else 0.0
    margin = _clip01(sims[0] - sims[1]) if len(sims) >= 2 else (top_sim if sims else 0.0)

    arg_lits = candidate.argument_literals()
    budget = max(1, int(getattr(evidence, "budget_tokens", 1) or 1))
    used = int(getattr(evidence, "tokens", 0) or 0)

    values = {
        "retrieval_coverage": _ratio(q_terms & e_terms, q_terms),
        "entity_coverage": _ratio(q_ents & e_ents, q_ents),
        "action_arg_support": _ratio(arg_lits & (e_terms | e_ents), arg_lits),
        "top_similarity": top_sim,
        "similarity_margin": margin,
        # Saturating at 8 supporting items: beyond that, more items stop being evidence
        # of support and start being evidence of a diffuse match.
        "support_count_norm": _clip01(math.log1p(len(items)) / math.log(9.0)),
        "evidence_utilization": _clip01(used / budget),
        "conflict_density_inv": 1.0 - _conflict_density(texts),
        "action_confidence": _confidence(candidate.mean_logprob),
        "step_progress": _clip01(state.step_index / max(1, state.max_steps)),
    }
    missing = set(HOST_AGNOSTIC_FEATURES) - set(values)
    if missing:
        raise AssertionError(f"feature schema incomplete, missing {sorted(missing)}")
    return FeatureRecord(values=values)


def _ratio(hit: set, total: set) -> float:
    """Coverage ratio; an empty reference set means 'nothing was required', i.e. 1.0."""
    return 1.0 if not total else len(hit) / len(total)


def _clip01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


def _confidence(mean_logprob: Optional[float]) -> float:
    """Map mean token logprob to [0, 1]; 0.5 (maximally uninformative) when absent."""
    if mean_logprob is None:
        return 0.5
    return _clip01(math.exp(mean_logprob))
