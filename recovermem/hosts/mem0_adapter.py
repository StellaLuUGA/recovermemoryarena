"""Mem0 OSS host adapter -- the Table 1 host (brief §6).

This is a THIN wrapper over the real local Mem0 OSS implementation at
``update_replicate/mem0``. Mem0's native fact-extraction / add-update-delete logic and
its native vector search are used verbatim; ReCoverMem adds exactly two things Mem0 does
not provide:

1. a decision-time token budget on the retrieved evidence (|E_t| <= B_mem), and
2. retention of the full ranked candidate list so budget ablations are recomputable.

There is NO total store-capacity limit, per the brief. The only budget is on retrieval.

Three-Layer Memory is not imported, referenced, or instantiated anywhere in this module.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from recovermem.interfaces.host_memory import HostMemoryAdapter, MemoryEvidence, WriteResult
from recovermem.tokens import TokenCounter, pack_indices_to_budget

#: The pinned local Mem0 OSS checkout.
MEM0_REPO = Path(__file__).resolve().parents[2] / "mem0"

_LOCAL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "::1")


def _disable_mem0_telemetry() -> None:
    """Turn off Mem0's PostHog telemetry BEFORE the package is imported.

    Mem0 OSS ships anonymous usage telemetry that posts to ``us.i.posthog.com``, and the
    flag is read at import time in ``mem0/memory/telemetry.py``. Left on, the Table 1 run
    would be making external network calls -- which the brief forbids outright, and which
    also leaks experiment metadata off the machine. Setting it here (not in a shell
    profile) makes the guarantee travel with the code.
    """
    os.environ["MEM0_TELEMETRY"] = "False"
    os.environ["MEM0_TELEMETRY_SAMPLE_RATE"] = "0.0"


def _ensure_local_mem0() -> Any:
    """Import Mem0 from the pinned local checkout, never from a site-packages copy."""
    _disable_mem0_telemetry()
    if "mem0" in sys.modules and os.environ.get("MEM0_TELEMETRY") != "False":
        raise RuntimeError("mem0 was imported before telemetry could be disabled")
    if str(MEM0_REPO) not in sys.path:
        sys.path.insert(0, str(MEM0_REPO))
    import mem0  # noqa: PLC0415

    resolved = Path(mem0.__file__).resolve()
    if MEM0_REPO not in resolved.parents:
        raise RuntimeError(
            f"mem0 resolved to {resolved}, which is outside the pinned checkout "
            f"{MEM0_REPO}. Refusing to run against an unpinned Mem0."
        )
    return mem0


def _git_commit(repo: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10, check=True,
        )
        return out.stdout.strip()
    except Exception as exc:  # pragma: no cover - provenance must never crash a run
        return f"<unavailable: {exc}>"


def _assert_local_endpoint(url: Optional[str], what: str) -> None:
    """Fail loudly if a configured endpoint would leave the machine (brief §6)."""
    if not url:
        raise ValueError(f"{what} has no base_url; a default would reach the OpenAI cloud")
    from urllib.parse import urlparse

    host = urlparse(url).hostname or ""
    if host not in _LOCAL_HOSTS:
        raise ValueError(
            f"{what} points at '{host}', which is not local. The Table 1 configuration "
            f"forbids external API calls."
        )


@dataclass
class Mem0Config:
    """Local-only Mem0 configuration.

    ``candidate_top_k`` is deliberately larger than what fits in B_mem: the adapter
    retrieves wide, keeps the whole ranked list, then packs down to the budget.
    """

    llm_model: str = "llama-3.1-8b-instruct-local"
    llm_base_url: str = "http://localhost:8123/v1"
    llm_temperature: float = 0.0
    llm_max_tokens: int = 1024
    embedder_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dims: int = 384
    embedder_device: str = "cpu"
    vector_store_path: str = ""
    #: MUST be set per episode. Mem0 defaults this to ``~/.mem0/history.db``, a database
    #: shared by every run on the machine, and ``Memory.add()`` READS from it
    #: (``mem0/memory/main.py:920``, Phase 0 context gathering) keyed on a session scope
    #: derived from ``user_id``. Since episode ids repeat across runs, the default leaks
    #: one run's messages into another run's fact extraction.
    history_db_path: str = ""
    collection_name: str = "recovermem_table1"
    candidate_top_k: int = 50
    search_threshold: float = 0.0
    tokenizer_name_or_path: str = ""
    api_key: str = "EMPTY"
    extra: dict[str, Any] = field(default_factory=dict)

    def to_mem0_dict(self) -> dict[str, Any]:
        _assert_local_endpoint(self.llm_base_url, "Mem0 LLM")
        if not self.history_db_path:
            raise ValueError(
                "history_db_path is unset; Mem0 would fall back to the shared "
                "~/.mem0/history.db and read another run's messages during add(). "
                "Mem0Adapter.reset() sets this per episode."
            )
        return {
            "history_db_path": self.history_db_path,
            "llm": {
                "provider": "openai",
                "config": {
                    "model": self.llm_model,
                    "openai_base_url": self.llm_base_url,
                    "api_key": self.api_key,
                    "temperature": self.llm_temperature,
                    "max_tokens": self.llm_max_tokens,
                },
            },
            "embedder": {
                "provider": "huggingface",
                "config": {
                    "model": self.embedder_model,
                    "embedding_dims": self.embedding_dims,
                    "model_kwargs": {"device": self.embedder_device},
                },
            },
            "vector_store": {
                "provider": "faiss",
                "config": {
                    "collection_name": self.collection_name,
                    "path": self.vector_store_path,
                    "embedding_model_dims": self.embedding_dims,
                    "distance_strategy": "cosine",
                },
            },
        }


class Mem0Adapter(HostMemoryAdapter):
    """The Table 1 host. Wraps the real ``mem0.Memory``."""

    name = "mem0"

    def __init__(self, config: Mem0Config, counter: TokenCounter, store_root: str | Path):
        self.config = config
        self.counter = counter
        self.store_root = Path(store_root)
        self.store_root.mkdir(parents=True, exist_ok=True)
        self._mem0 = _ensure_local_mem0()
        self._memory: Any = None
        self._resolved_cfg: Optional[Mem0Config] = None
        self.episode_id: Optional[str] = None
        self.write_count = 0
        self.retrieve_count = 0
        self.write_prompt_tokens = 0
        # Any accidental cloud call must fail, not silently succeed on a real key.
        os.environ.setdefault("OPENAI_API_KEY", self.config.api_key)

    # -- lifecycle ---------------------------------------------------------

    def reset(self, episode_id: str) -> None:
        """Fresh, isolated Mem0 store per episode.

        tau^3 episodes are independent (brief §15), so memory must not leak across them.
        A per-episode on-disk FAISS path gives isolation that a shared store with
        ``user_id`` filtering could not guarantee.
        """
        self.episode_id = episode_id
        cfg = Mem0Config(**{**self.config.__dict__})
        episode_dir = self.store_root / episode_id
        cfg.vector_store_path = str(episode_dir)
        # Per-episode history DB: no run, and no episode, shares message state with any
        # other. This is the isolation the shared default silently broke.
        cfg.history_db_path = str(episode_dir / "history.db")
        cfg.collection_name = f"{self.config.collection_name}_{episode_id}"

        if episode_dir.exists() and any(episode_dir.iterdir()):
            raise RuntimeError(
                f"Mem0 store for episode '{episode_id}' already exists at {episode_dir} "
                f"and is non-empty. Reusing it would carry a previous run's memories into "
                f"this one. Use a fresh --out directory."
            )
        episode_dir.mkdir(parents=True, exist_ok=True)

        self._memory = self._mem0.Memory.from_config(cfg.to_mem0_dict())
        self._resolved_cfg = cfg
        self.write_count = 0
        self.retrieve_count = 0
        self.write_prompt_tokens = 0
        self.assert_empty()

    def assert_empty(self) -> None:
        """Startup assertion: the freshly bound store must hold zero memories."""
        snap = self.snapshot()
        n = snap.get("n_memories")
        if n:
            raise RuntimeError(
                f"Mem0 store for episode '{self.episode_id}' starts with {n} memories; "
                f"expected 0. The episode is not isolated."
            )

    def _require_bound(self) -> Any:
        if self._memory is None:
            raise RuntimeError("Mem0Adapter.reset(episode_id) must be called first")
        return self._memory

    # -- write -------------------------------------------------------------

    def write(self, messages: list[dict[str, Any]], **kwargs: Any) -> WriteResult:
        """Native Mem0 add(). ``infer=True`` keeps Mem0's own fact extraction."""
        memory = self._require_bound()
        prompt_tokens = self.counter.count_messages(messages)
        started = time.perf_counter()
        raw = memory.add(
            messages,
            user_id=kwargs.pop("user_id", self.episode_id),
            metadata=kwargs.pop("metadata", None),
            infer=kwargs.pop("infer", True),
            **kwargs,
        )
        latency = time.perf_counter() - started
        results = (raw or {}).get("results", []) if isinstance(raw, dict) else []
        counts = {"ADD": 0, "UPDATE": 0, "DELETE": 0}
        for item in results:
            event = str(item.get("event", "")).upper()
            if event in counts:
                counts[event] += 1
        self.write_count += 1
        self.write_prompt_tokens += prompt_tokens
        return WriteResult(
            n_added=counts["ADD"],
            n_updated=counts["UPDATE"],
            n_deleted=counts["DELETE"],
            prompt_tokens=prompt_tokens,
            latency_s=latency,
            raw=raw,
        )

    # -- retrieve ----------------------------------------------------------

    def retrieve(self, query: str, budget_tokens: int) -> MemoryEvidence:
        """Retrieve wide, keep the full ranked list, pack in rank order to B_mem."""
        memory = self._require_bound()
        started = time.perf_counter()
        raw = memory.search(
            query,
            top_k=self.config.candidate_top_k,
            filters={"user_id": self.episode_id},
            threshold=self.config.search_threshold,
        )
        latency = time.perf_counter() - started
        results = (raw or {}).get("results", []) if isinstance(raw, dict) else (raw or [])

        candidates: list[dict[str, Any]] = []
        for rank, item in enumerate(results):
            text = str(item.get("memory", ""))
            candidates.append(
                {
                    "rank": rank,
                    "id": item.get("id"),
                    "memory": text,
                    "score": item.get("score"),
                    "tokens": self.counter.count_text(text),
                    "metadata": item.get("metadata"),
                }
            )

        kept_idx, used, packed_text = pack_indices_to_budget(
            [c["memory"] for c in candidates], budget_tokens, self.counter
        )
        items = [candidates[i] for i in kept_idx]
        self.retrieve_count += 1
        return MemoryEvidence(
            text=packed_text,
            tokens=used,
            budget_tokens=budget_tokens,
            items=items,
            candidates=candidates,
            latency_s=latency,
            host=self.name,
        )

    # -- provenance --------------------------------------------------------

    #: Mem0's ``get_all`` defaults to ``top_k=20`` (mem0/memory/main.py:1259), which is a
    #: display cap, not a store size. Left at the default, ``snapshot()`` would report 20
    #: for every store large enough to matter and ``assert_empty`` would still pass while
    #: the audited memory count was silently wrong.
    SNAPSHOT_TOP_K = 100_000

    def snapshot(self) -> dict[str, Any]:
        memory = self._require_bound()
        try:
            allmem = memory.get_all(
                filters={"user_id": self.episode_id}, top_k=self.SNAPSHOT_TOP_K
            )
            results = (allmem or {}).get("results", []) if isinstance(allmem, dict) else allmem
        except Exception as exc:
            return {"error": str(exc)}
        return {
            "episode_id": self.episode_id,
            "n_memories": len(results),
            "memories": [
                {"id": r.get("id"), "memory": r.get("memory")} for r in results
            ],
        }

    def metadata(self) -> dict[str, Any]:
        return {
            "host": self.name,
            "implementation": "mem0 OSS (local checkout)",
            "mem0_path": str(MEM0_REPO),
            "mem0_module": getattr(self._mem0, "__file__", "?"),
            "mem0_commit": _git_commit(MEM0_REPO),
            "llm_model": self.config.llm_model,
            "llm_base_url": self.config.llm_base_url,
            "embedder_model": self.config.embedder_model,
            "embedding_dims": self.config.embedding_dims,
            "embedder_device": self.config.embedder_device,
            "vector_store": "faiss",
            "candidate_top_k": self.config.candidate_top_k,
            "cloud": False,
            "history_db_path": (
                self._resolved_cfg.history_db_path if self._resolved_cfg else "<per-episode, set on reset()>"
            ),
            "shared_default_history_db": False,
            # Hash the TEMPLATE, excluding the per-episode paths: the run's identity is
            # the configuration, not which episode happens to be bound right now.
            "config_hash": json.dumps(
                {k: v for k, v in sorted(self.config.__dict__.items())
                 if k not in ("history_db_path", "vector_store_path", "collection_name")},
                sort_keys=True, default=str,
            ),
        }
