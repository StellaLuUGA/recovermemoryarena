"""Mem0 host + bounded recovery for the formal ALFWorld run.

Uses the pinned OSS Mem0 checkout (commit 39bc0233...) through the tau3
``recovermem.hosts.mem0_adapter.Mem0Adapter`` -- unmodified. Mem0's internal LLM is the
same local Qwen3-32B-AWQ server as the action agent (declared in MODEL_ROLE_AUDIT.md).
"""
from __future__ import annotations

import shutil
from pathlib import Path

from af_formal.common import (EMBEDDER, LEDGER, QWEN_BASE_URL, QWEN_MODEL, QWEN_PATH,
                              STORES, assert_local, instrument_openai_client, set_bucket)

from af_formal.common import install_global_openai_instrumentation
install_global_openai_instrumentation()

from recovermem.hosts.mem0_adapter import Mem0Adapter, Mem0Config, MEM0_REPO
from recovermem.recovery.trajectory_retriever import TrajectoryRetriever
from recovermem.tokens import TokenCounter

COUNTER = TokenCounter(QWEN_PATH)
assert COUNTER.exact, "Qwen tokenizer must load exactly; refusing heuristic token counts"

RETRIEVER = TrajectoryRetriever(COUNTER, window=1)

BASE_CFG = dict(
    llm_model=QWEN_MODEL,
    llm_base_url=QWEN_BASE_URL,
    llm_temperature=0.0,
    llm_max_tokens=1024,
    embedder_model=EMBEDDER,
    embedding_dims=384,
    embedder_device="cpu",
    collection_name="alfworld_formal",
    candidate_top_k=50,
    search_threshold=0.0,
    api_key="EMPTY",
)


class Mem0Host:
    """Per-episode Mem0 store with metered, non-thinking Qwen calls."""

    def __init__(self, run_tag: str):
        assert_local(QWEN_BASE_URL, "Mem0 LLM")
        self.root = STORES / run_tag
        self.adapter = Mem0Adapter(Mem0Config(**BASE_CFG), COUNTER, self.root)
        self.episode_id = None

    def reset(self, episode_id: str):
        d = self.root / episode_id
        if d.exists():
            shutil.rmtree(d)
        self.adapter.reset(episode_id)
        self.episode_id = episode_id
        # meter Mem0's own LLM traffic and force non-thinking mode
        mem = self.adapter._memory
        for attr in ("llm",):
            obj = getattr(mem, attr, None)
            cl = getattr(obj, "client", None)
            if cl is not None:
                instrument_openai_client(cl, bucket_hint=None)

    def write_turn(self, action: str, observation: str, bucket="write"):
        set_bucket(bucket)
        msgs = [{"role": "assistant", "content": f"action: {action}"},
                {"role": "user", "content": f"observation: {observation.strip()}"}]
        return self.adapter.write(msgs)

    def write_task(self, instruction: str, intro: str, bucket="write"):
        set_bucket(bucket)
        msgs = [{"role": "user", "content": f"task: {instruction.strip()}"},
                {"role": "user", "content": f"observation: {intro.strip()}"}]
        return self.adapter.write(msgs)

    def retrieve(self, query: str, budget_tokens: int):
        set_bucket("mem")
        return self.adapter.retrieve(query, budget_tokens)

    def n_memories(self) -> int:
        return self.adapter.live_memory_count()

    def metadata(self):
        return self.adapter.metadata()

    def close(self):
        self.adapter._memory = None


def recover(query: str, history_messages, budget_tokens: int):
    """Bounded raw-trajectory recovery; deterministic, lexical, no LLM call."""
    return RETRIEVER.recover(query, history_messages, budget_tokens)


def mem0_provenance():
    import subprocess
    try:
        commit = subprocess.run(["git", "-C", str(MEM0_REPO), "rev-parse", "HEAD"],
                                capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception as e:
        commit = f"<unavailable: {e}>"
    return {"mem0_repo": str(MEM0_REPO), "mem0_commit": commit,
            "llm": QWEN_MODEL, "llm_base_url": QWEN_BASE_URL,
            "embedder": EMBEDDER, "embedding_dims": 384, "vector_store": "faiss",
            "candidate_top_k": 50, "telemetry": "disabled", "cloud": False}
