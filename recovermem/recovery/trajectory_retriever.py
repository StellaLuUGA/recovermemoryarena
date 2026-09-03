"""Bounded recovery from the immutable raw trajectory H_t (brief §12).

The old recovery path concatenated the entire raw history into the prompt
(``agent.py:355-407``), giving the recovery route ~60k tokens while the memory route was
budgeted -- that comparison measures context size, not recoverability. This backend
retrieves over H_t and returns at most B_rec tokens, with B_rec = B_mem for the main
experiment.

Scoring is lexical (IDF-weighted overlap) and therefore deterministic, host-independent,
and free of any LLM call. That matters twice over: recovery must not become a second
model whose sampling noise contaminates the paired comparison, and it must not be able
to write anything back into the host.
"""

from __future__ import annotations

import math
import re
import time
from collections import Counter
from typing import Any, Iterable, Sequence

from recovermem.interfaces.recovery import RecoveredEvidence, RecoveryBackend
from recovermem.tokens import TokenCounter, pack_indices_to_budget

_WORD = re.compile(r"[a-z0-9_]+")


def tokenize(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def render_turn(message: dict[str, Any]) -> str:
    """Flatten one raw-history message into the text a retriever can match against."""
    role = message.get("role", "?")
    parts: list[str] = []
    content = message.get("content")
    if isinstance(content, str) and content:
        parts.append(content)
    elif content:
        parts.append(str(content))
    for call in message.get("tool_calls") or []:
        fn = (call or {}).get("function", {})
        parts.append(f"{fn.get('name', '')}({fn.get('arguments', '')})")
    return f"[{role}] " + " ".join(p for p in parts if p)


class TrajectoryRetriever(RecoveryBackend):
    """IDF-weighted lexical retrieval over raw history turns."""

    name = "trajectory_lexical"

    def __init__(self, counter: TokenCounter, window: int = 1):
        self.counter = counter
        #: Number of neighbouring turns glued to each hit. Tool results follow the call
        #: that produced them, so a window of 1 keeps call/result pairs intact.
        self.window = window

    def _idf(self, docs: Sequence[list[str]]) -> dict[str, float]:
        n = len(docs)
        df = Counter()
        for doc in docs:
            df.update(set(doc))
        return {term: math.log(1.0 + n / (1.0 + count)) for term, count in df.items()}

    def recover(
        self,
        query: str,
        history: list[dict[str, Any]],
        budget_tokens: int,
    ) -> RecoveredEvidence:
        started = time.perf_counter()
        if budget_tokens <= 0:
            raise ValueError("B_rec must be positive")

        rendered = [render_turn(m) for m in history]
        docs = [tokenize(r) for r in rendered]
        idf = self._idf(docs)
        q_terms = set(tokenize(query))

        scored: list[tuple[float, int]] = []
        for i, doc in enumerate(docs):
            if not doc:
                scored.append((0.0, i))
                continue
            counts = Counter(doc)
            # Sub-linear term frequency, length-normalised: long tool dumps must not
            # win on sheer size.
            raw = sum(
                idf.get(t, 0.0) * (1.0 + math.log(counts[t]))
                for t in q_terms
                if t in counts
            )
            scored.append((raw / math.sqrt(len(doc)), i))

        # Ties break on recency: a later turn reflects more of the episode's state.
        order = sorted(scored, key=lambda si: (-si[0], -si[1]))

        chosen: list[int] = []
        seen: set[int] = set()
        for _, idx in order:
            for j in range(max(0, idx - self.window), min(len(rendered), idx + self.window + 1)):
                if j not in seen:
                    seen.add(j)
                    chosen.append(j)

        candidates = [
            {
                "rank": rank,
                "turn_index": idx,
                "score": next(s for s, i in scored if i == idx),
                "text": rendered[idx],
                "tokens": self.counter.count_text(rendered[idx]),
            }
            for rank, idx in enumerate(chosen)
        ]

        kept_idx, used, _packed = pack_indices_to_budget(
            [c["text"] for c in candidates], budget_tokens, self.counter
        )
        # Emit in chronological order: a trajectory read out of order is misleading.
        # Reordering changes the joined string, so the count is taken on the final text
        # rather than inherited from the packer -- the log must describe the real prompt.
        items = sorted((candidates[i] for i in kept_idx), key=lambda c: c["turn_index"])
        text = "\n".join(i["text"] for i in items)
        used = self.counter.count_text(text)
        while used > budget_tokens and items:
            # Reordering can only change the count by tokenizer boundary effects; drop
            # the lowest-ranked item until the bound holds again rather than emitting
            # an over-budget prompt.
            worst = max(items, key=lambda c: c["rank"])
            items.remove(worst)
            text = "\n".join(i["text"] for i in items)
            used = self.counter.count_text(text)
        return RecoveredEvidence(
            text=text,
            tokens=used,
            budget_tokens=budget_tokens,
            items=items,
            candidates=candidates,
            latency_s=time.perf_counter() - started,
            backend=self.name,
        )
