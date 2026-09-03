"""Token counting and context-budget accounting.

Every budget quantity in the brief (B_ctx, B_base, B_out, B_safe, B_avail, B_mem, B_rec)
is measured with the *serving model's own tokenizer* so the numbers mean what they say.
"""

from __future__ import annotations

import functools
import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Optional


@functools.lru_cache(maxsize=4)
def _hf_tokenizer(name_or_path: str):
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(name_or_path)


class TokenCounter:
    """Counts tokens with the served model's tokenizer.

    Falls back to a conservative character heuristic only if the tokenizer cannot be
    loaded; ``exact`` records which path was taken so budget audits never silently
    report heuristic numbers as measured ones.
    """

    def __init__(self, tokenizer_name_or_path: str):
        self.tokenizer_name = tokenizer_name_or_path
        try:
            self._tok = _hf_tokenizer(tokenizer_name_or_path)
            self.exact = True
        except Exception:
            self._tok = None
            self.exact = False

    def count_text(self, text: str) -> int:
        if not text:
            return 0
        if self._tok is not None:
            return len(self._tok.encode(text, add_special_tokens=False))
        # Conservative fallback: ~3.5 chars/token.
        return int(len(text) / 3.5) + 1

    def count_message(self, message: dict[str, Any]) -> int:
        """Token cost of one chat message, including tool-call payloads.

        The +4 approximates the per-message role/delimiter overhead of the chat
        template; it keeps B_base slightly pessimistic, which is the safe direction
        for a context budget.
        """
        total = 4
        content = message.get("content")
        if isinstance(content, str):
            total += self.count_text(content)
        elif content is not None:
            total += self.count_text(json.dumps(content, default=str))
        for key in ("tool_calls", "function_call", "name", "tool_call_id"):
            val = message.get(key)
            if val:
                total += self.count_text(json.dumps(val, default=str))
        return total

    def count_messages(self, messages: Iterable[dict[str, Any]]) -> int:
        return sum(self.count_message(m) for m in messages)

    def count_tools(self, tools: Any) -> int:
        """Token cost of the serialized tool/function schemas."""
        if not tools:
            return 0
        return self.count_text(json.dumps(tools, default=str))


@dataclass
class BudgetConfig:
    """Fixed context-budget reservations.

    ``memory_budget_tokens`` (B_mem) and ``recovery_budget_tokens`` (B_rec) are left
    ``None`` until the budget audit freezes them; constructing a controller with
    ``None`` is an error, so an unfrozen budget can never silently reach a run.
    """

    context_limit: int  # B_ctx
    generation_reserve: int  # B_out
    safety_margin: int  # B_safe
    memory_budget_tokens: Optional[int] = None  # B_mem
    recovery_budget_tokens: Optional[int] = None  # B_rec

    def available(self, base_tokens: int) -> int:
        """B_avail_t = B_ctx - B_base_t - B_out - B_safe."""
        return self.context_limit - base_tokens - self.generation_reserve - self.safety_margin

    def require_frozen(self) -> None:
        if self.memory_budget_tokens is None or self.recovery_budget_tokens is None:
            raise ValueError(
                "B_mem/B_rec are not frozen. Run the budget audit "
                "(recovermem.integrations.tau3.budget_audit) before collecting decisions."
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


#: Standard budget ladder from the brief (§4). B_mem is the largest rung <= q05.
STANDARD_BUDGETS = (1024, 2048, 4096, 8192, 16384, 32768)


def select_budget(q05: float, ladder: Iterable[int] = STANDARD_BUDGETS) -> Optional[int]:
    """Largest standard budget B with B <= q05, or None if even the smallest exceeds q05.

    Returning None is deliberate: the brief forbids inventing a non-standard budget, so
    an infeasible serving configuration must surface as a failure, not a silent shrink.
    """
    feasible = [b for b in ladder if b <= q05]
    return max(feasible) if feasible else None


def pack_indices_to_budget(
    items: list[str],
    budget_tokens: int,
    counter: TokenCounter,
    separator: str = "\n",
) -> tuple[list[int], int, str]:
    """Greedily take items in rank order until the budget would be exceeded.

    Returns ``(kept_indices, tokens_used, packed_text)`` where ``tokens_used`` is the
    token count of ``packed_text`` EXACTLY -- the cost of each candidate is measured on
    the joined string, not by summing per-item counts. Summing is both wrong and
    unfixably so: tokenizers are not additive across a join (BPE merges over the
    boundary, and the character fallback accumulates its per-call rounding), so a summed
    figure and the real prompt disagree. Since the log's token numbers are supposed to
    describe the actual prompt, the equality

        recorded_tokens == counter.count_text(packed_text)

    has to hold by construction, which is what re-measuring gives.

    Indices rather than texts: evidence lists routinely contain duplicate strings
    (identical tool results, a memory retrieved under two ids), and matching kept items
    back by content would pull in every duplicate and silently blow the budget.

    Items are never truncated mid-way: one that does not fit is skipped and the next
    (lower-ranked, possibly shorter) one is tried, so packing stays deterministic and
    every emitted item is intact.
    """
    kept: list[int] = []
    text = ""
    used = 0
    for idx, item in enumerate(items):
        candidate_text = item if not kept else text + separator + item
        cost = counter.count_text(candidate_text)
        if cost > budget_tokens:
            continue
        kept.append(idx)
        text = candidate_text
        used = cost
    return kept, used, text


def pack_to_budget(
    items: list[str],
    budget_tokens: int,
    counter: TokenCounter,
    separator: str = "\n",
) -> tuple[list[str], int]:
    """Text-returning wrapper around :func:`pack_indices_to_budget`."""
    idxs, used, _ = pack_indices_to_budget(items, budget_tokens, counter, separator)
    return [items[i] for i in idxs], used
