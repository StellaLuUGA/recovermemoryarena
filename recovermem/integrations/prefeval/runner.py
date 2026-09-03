"""Per-instance paired collection for PrefEval.

Contract enforced here, once per instance:

1. a FRESH Mem0 store and a FRESH raw-history store;
2. the 604-message history is streamed into the host exactly once, in native order;
3. the query is never written to memory, and neither is any model answer;
4. both routes receive byte-identical ``x_i`` (asserted by hash before logging);
5. ``|E_mem| <= B_mem`` and ``|E_rec| <= B_rec`` with ``B_rec == B_mem``;
6. every token number is measured with the exact served Llama tokenizer.

Nothing in this module reads a correctness label while constructing evidence.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from recovermem.hosts.mem0_adapter import Mem0Adapter, Mem0Config
from recovermem.integrations.prefeval.answerer import LocalLlamaAnswerer
from recovermem.integrations.prefeval.dataset import PrefInstance, load_filler
from recovermem.recovery.trajectory_retriever import TrajectoryRetriever
from recovermem.scoring.features import CandidateAction, DecisionState, extract_features
from recovermem.tokens import TokenCounter

LLAMA_SNAPSHOT = (
    "/home/aristella/.cache/huggingface/hub/models--meta-llama--Llama-3.1-8B-Instruct/"
    "snapshots/0e9e39f249a16976918f6564b8830bc894c89659"
)
#: Mem0 write granularity. Matches MemoryAgentBench's 4096-token streaming convention;
#: message boundaries are never split, so the host always ingests whole turns.
WRITE_CHUNK_TOKENS = 4096


class _Mem0ErrorCounter(logging.Handler):
    """Counts Mem0's fact-extraction failures instead of letting them vanish into stderr.

    ``mem0/memory/main.py:983`` logs ``Error parsing extraction response`` and then silently
    drops that chunk's facts. On a local 8B extractor this happens often enough that the
    number belongs in the record: it is a measured property of the host, and the brief
    requires these to be logged, never repaired.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
        except Exception:
            return
        if "Error parsing extraction response" in msg:
            self.messages.append(msg)

    def reset(self) -> None:
        self.messages.clear()

    @property
    def count(self) -> int:
        return len(self.messages)


def chunk_messages(
    messages: list[dict[str, str]], counter: TokenCounter, chunk_tokens: int = WRITE_CHUNK_TOKENS
) -> list[list[dict[str, str]]]:
    """Group consecutive messages into <= ``chunk_tokens`` batches without splitting one."""
    chunks: list[list[dict[str, str]]] = []
    cur: list[dict[str, str]] = []
    cur_tok = 0
    for m in messages:
        t = counter.count_message(m)
        if cur and cur_tok + t > chunk_tokens:
            chunks.append(cur)
            cur, cur_tok = [], 0
        cur.append(m)
        cur_tok += t
    if cur:
        chunks.append(cur)
    return chunks


@dataclass
class InstanceResult:
    pair_id: str
    topic: str
    group_id: str
    # history / memory construction
    n_history_messages: int
    history_tokens: int
    n_write_chunks: int
    memory_build_s: float
    mem0_memory_count: int
    mem0_write_prompt_tokens: int
    mem0_extraction_parse_failures: int
    # evidence
    b_mem: int
    b_rec: int
    memory_evidence_tokens: int
    recovery_evidence_tokens: int
    n_memory_candidates: int
    n_memory_packed: int
    n_recovery_packed: int
    # common state
    state_tokens: int
    state_hash: str
    memory_branch_state_hash: str
    recovery_branch_state_hash: str
    pair_valid: bool
    # outcomes
    gold_letter: str = ""
    memory_choice: Optional[str] = None
    recovery_choice: Optional[str] = None
    memory_completion: str = ""
    recovery_completion: str = ""
    u_mem: float = 0.0
    u_rec: float = 0.0
    r_mem: int = 0
    r_rec: int = 0
    longest_option_letter: str = ""
    longest_option_correct: int = 0
    #: The order the reader actually saw. The pre-shuffle order (where index 0 is the gold)
    #: is never stored on a result object.
    shuffled_options: list[str] = field(default_factory=list)
    memory_parse_ok: bool = True
    recovery_parse_ok: bool = True
    # scorer
    features: dict[str, float] = field(default_factory=dict)
    # cost
    memory_latency_s: float = 0.0
    recovery_latency_s: float = 0.0
    memory_prompt_tokens: int = 0
    recovery_prompt_tokens: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


class PrefEvalRunner:
    """Builds one memory per instance and runs the paired decision."""

    def __init__(
        self,
        store_root: str | Path,
        b_mem: Optional[int] = None,
        answerer: Optional[LocalLlamaAnswerer] = None,
        write_chunk_tokens: int = WRITE_CHUNK_TOKENS,
    ):
        self.counter = TokenCounter(LLAMA_SNAPSHOT)
        if not self.counter.exact:
            raise RuntimeError("exact Llama tokenizer unavailable; refusing to run")
        self.store_root = Path(store_root)
        self.b_mem = b_mem
        self.b_rec = b_mem
        self.answerer = answerer or LocalLlamaAnswerer()
        self.recovery = TrajectoryRetriever(self.counter, window=0)
        self.filler = load_filler()
        self.write_chunk_tokens = write_chunk_tokens
        self.mem0_errors = _Mem0ErrorCounter()
        logging.getLogger("mem0").addHandler(self.mem0_errors)
        logging.getLogger("mem0.memory.main").addHandler(self.mem0_errors)
        self.host = Mem0Adapter(
            config=Mem0Config(
                llm_base_url="http://127.0.0.1:8123/v1",
                llm_model="llama-3.1-8b-instruct-local",
                llm_temperature=0.0,
                embedder_device="cpu",
                collection_name="recovermem_prefeval",
            ),
            counter=self.counter,
            store_root=self.store_root,
        )

    # -- memory construction ------------------------------------------------

    def build_memory(self, inst: PrefInstance) -> tuple[list[dict[str, str]], float, int, int]:
        """Fresh store, stream H_i once, return (history, seconds, n_chunks, n_memories)."""
        episode_dir = self.store_root / inst.pair_id.replace("#", "_")
        if episode_dir.exists():
            shutil.rmtree(episode_dir)
        self.host.reset(inst.pair_id.replace("#", "_"))

        history = inst.history(self.filler)
        chunks = chunk_messages(history, self.counter, self.write_chunk_tokens)
        self.mem0_errors.reset()
        started = time.perf_counter()
        for ch in chunks:
            self.host.write(ch)
        elapsed = time.perf_counter() - started
        snap = self.host.snapshot()
        return history, elapsed, len(chunks), int(snap.get("n_memories") or 0)

    def uncapped_memory_evidence_tokens(self, inst: PrefInstance) -> dict[str, Any]:
        """Native Mem0 decision-time evidence with NO budget applied (for the budget audit).

        Uses a budget large enough that packing is a no-op, so the number reported is the
        host's own uncapped output rather than a truncation of it.
        """
        state = inst.common_state_text()
        ev = self.host.retrieve(state, budget_tokens=10 ** 9)
        return {
            "uncapped_evidence_tokens": ev.tokens,
            "n_candidates": ev.n_candidates,
            "n_packed": ev.n_packed,
            "candidate_tokens": [c["tokens"] for c in ev.candidates],
            "retrieval_latency_s": ev.latency_s,
        }

    # -- the paired decision -------------------------------------------------

    def run_instance(self, inst: PrefInstance, group_id: str) -> InstanceResult:
        if self.b_mem is None:
            raise RuntimeError("B_mem is not frozen; run the budget audit first")

        history, build_s, n_chunks, n_mem = self.build_memory(inst)
        history_tokens = self.counter.count_messages(history)

        shuffled = inst.shuffled()
        state_text = inst.common_state_text()
        state_hash = hashlib.sha256(state_text.encode()).hexdigest()
        state = DecisionState(
            query=state_text,
            step_index=0,
            max_steps=1,
            state_hash=state_hash,
            state_tokens=self.counter.count_text(state_text),
        )

        # MEMORY route
        mem_ev = self.host.retrieve(state_text, self.b_mem)
        mem_started = time.perf_counter()
        mem_ans = self.answerer.answer(state_text, mem_ev.text)
        mem_latency = time.perf_counter() - mem_started
        mem_hash = hashlib.sha256(state_text.encode()).hexdigest()

        # RECOVERY route -- bounded, over the ORIGINAL message-level history
        rec_ev = self.recovery.recover(state_text, history, self.b_rec)
        rec_started = time.perf_counter()
        rec_ans = self.answerer.answer(state_text, rec_ev.text)
        rec_latency = time.perf_counter() - rec_started
        rec_hash = hashlib.sha256(state_text.encode()).hexdigest()

        # Scorer: sees x, E_mem and a_mem only -- never H, E_rec, or any label.
        cand = CandidateAction(
            name="mcq_choice",
            arguments={"choice": mem_ans.parsed_choice} if mem_ans.parsed_choice else {},
            text=mem_ans.completion,
            mean_logprob=mem_ans.mean_logprob,
        )
        feats = extract_features(state, mem_ev, cand)

        # Memory must not have changed across the query phase.
        post = int((self.host.snapshot().get("n_memories") or 0))
        errors: list[str] = []
        if post != n_mem:
            errors.append(f"memory count changed during query phase: {n_mem} -> {post}")

        u_mem = 1.0 if mem_ans.parsed_choice == shuffled.gold_letter else 0.0
        u_rec = 1.0 if rec_ans.parsed_choice == shuffled.gold_letter else 0.0
        longest = max(range(4), key=lambda i: len(shuffled.options[i]))
        longest_letter = "ABCD"[longest]

        return InstanceResult(
            pair_id=inst.pair_id,
            topic=inst.topic,
            group_id=group_id,
            n_history_messages=len(history),
            history_tokens=history_tokens,
            n_write_chunks=n_chunks,
            memory_build_s=build_s,
            mem0_memory_count=n_mem,
            mem0_write_prompt_tokens=self.host.write_prompt_tokens,
            mem0_extraction_parse_failures=self.mem0_errors.count,
            b_mem=self.b_mem,
            b_rec=self.b_rec,
            memory_evidence_tokens=mem_ev.tokens,
            recovery_evidence_tokens=rec_ev.tokens,
            n_memory_candidates=mem_ev.n_candidates,
            n_memory_packed=mem_ev.n_packed,
            n_recovery_packed=len(rec_ev.items),
            state_tokens=state.state_tokens,
            state_hash=state_hash,
            memory_branch_state_hash=mem_hash,
            recovery_branch_state_hash=rec_hash,
            pair_valid=(state_hash == mem_hash == rec_hash),
            gold_letter=shuffled.gold_letter,
            memory_choice=mem_ans.parsed_choice,
            recovery_choice=rec_ans.parsed_choice,
            memory_completion=mem_ans.completion,
            recovery_completion=rec_ans.completion,
            u_mem=u_mem,
            u_rec=u_rec,
            r_mem=int(u_mem >= 0.5),
            r_rec=int(u_rec >= 0.5),
            longest_option_letter=longest_letter,
            longest_option_correct=int(longest_letter == shuffled.gold_letter),
            shuffled_options=list(shuffled.options),
            memory_parse_ok=mem_ans.parsed_choice is not None,
            recovery_parse_ok=rec_ans.parsed_choice is not None,
            features=dict(feats.values),
            memory_latency_s=mem_latency,
            recovery_latency_s=rec_latency,
            memory_prompt_tokens=mem_ans.prompt_tokens,
            recovery_prompt_tokens=rec_ans.prompt_tokens,
            errors=errors,
        )
