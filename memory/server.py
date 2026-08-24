import json
import os
import time
from pathlib import Path
from typing import Dict, Callable, NamedTuple, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv
import tiktoken

from memory_systems import (
    LongContextMemorySystem, 
    MirixMemorySystem, 
    Mem0MemorySystem, 
    LettaMemorySystem, 
    RAGMemorySystem, 
    MemoRAGMemorySystem,
    GraphRAGMemorySystem,
    AMemMemorySystem,
    LightMemMemorySystem,
    ReasoningBankMemorySystem,
    ZepMemorySystem,
)


load_dotenv()

# ---------- Request schemas ----------
class InitializeRequest(BaseModel):
    user_id: str
    memory_system_name: str
    budget_tokens: Optional[int] = None


class AddRequest(BaseModel):
    user_id: str
    chunk: str
    memory_system_name: str


class QueryRequest(BaseModel):
    user_id: str
    question: str
    memory_system_name: str

class ActRequest(BaseModel):
    user_id: str
    prompt: str
    memory_system_name: str

# ---------- Memory/Agent implementations (unified) ----------
MEMORY_FACTORIES: Dict[str, Callable[[], object]] = {
    "mirix": MirixMemorySystem,
    "long_context": LongContextMemorySystem,
    "mem0": Mem0MemorySystem,
    "mem0-g": lambda: Mem0MemorySystem(enable_graph=True),
    "letta": LettaMemorySystem,
    "rag": RAGMemorySystem,
    "memorag": MemoRAGMemorySystem,
    "graphrag": GraphRAGMemorySystem,
    "amem": AMemMemorySystem,
    "lightmem": LightMemMemorySystem,
    "reasoningbank": ReasoningBankMemorySystem, # You must add user_id when initializing ReasoningBankMemorySystem
    "zep": ZepMemorySystem,
}


# ---------- FastAPI wiring ----------
app = FastAPI(title="Memory Agent Server")


class MemorySystemEntry(NamedTuple):
    name: str
    system: object


MEMORY_SYSTEMS: Dict[str, MemorySystemEntry] = {}

# ---------- Gate C instrumentation: accumulated raw-history token tracking ----------
# Not part of the upstream framework: the memory server has no built-in way to observe
# how large the *uncompressed* interaction history would have grown, which is exactly what
# Gate C (does history actually exceed the serving context window?) needs. We track, per
# user_id (== task_id in this repo's convention), a running total of tokens across every
# raw chunk ever added, independent of what any given backend chooses to keep/compress.
_TOKEN_LOG_PATH = Path(
    os.environ.get(
        "RECOVERMEM_TOKEN_LOG",
        str(Path.home() / "recovermem_results" / "gate_c_token_log.jsonl"),
    )
)
_TOKEN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
_CUMULATIVE_RAW_TOKENS: Dict[str, int] = {}
_TOKENIZER = tiktoken.get_encoding("cl100k_base")

# Budget verification (BUDGET_VERIFICATION.md): configured-vs-actual memory token counts,
# separate log from the general Gate C one above so it's easy to isolate.
_BUDGET_LOG_PATH = Path(
    os.environ.get(
        "RECOVERMEM_BUDGET_LOG",
        str(Path.home() / "recovermem_results" / "budget_verification_log.jsonl"),
    )
)
_BUDGET_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_TOKENIZER.encode(text, disallowed_special=()))


def _log_budget_verification(event: dict) -> None:
    event["timestamp"] = time.time()
    with open(_BUDGET_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _log_token_event(event: dict) -> None:
    event["timestamp"] = time.time()
    with open(_TOKEN_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _get_memory(user_id: str, memory_system: str):
    entry = MEMORY_SYSTEMS.get(user_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="User not initialized")
    if entry.name != memory_system:
        raise HTTPException(status_code=400, detail="Mismatched memory_system for user")
    return entry.system


@app.post("/memory/initialize")
def initialize(req: InitializeRequest):
    name = req.memory_system_name
    if name in {"bm25", "text-embedding-3-small"}:
        rag_kwargs = {"retrieval_method": name}
        if req.budget_tokens is not None:
            # Budget sweep (Gate D / usable-base-rate search): cap this episode's memory
            # backend at a fixed TOTAL token budget. NOTE: RAGMemorySystem.max_tokens only
            # bounds each individual chunk's size at add-time, not the total wrapped context
            # (which can still be top_k * max_tokens) — total_budget_tokens is the real cap,
            # enforced in wrap_user_prompt.
            rag_kwargs["total_budget_tokens"] = req.budget_tokens
        memory_system = RAGMemorySystem(**rag_kwargs)
    # elif name == "graphrag":
    #     if not os.getenv("GRAPHRAG_LOCAL_DIR"):
    #         raise HTTPException(status_code=400, detail="GRAPHRAG_LOCAL_DIR is required to initialize GraphRAG.")
    #     memory_system = GraphRAGMemorySystem(local_dir=os.getenv("GRAPHRAG_LOCAL_DIR"))
    elif name in {"reasoningbank"}:
        memory_system = ReasoningBankMemorySystem(user_id=req.user_id)
    else:
        factory = MEMORY_FACTORIES.get(name)
        if factory is None:
            raise HTTPException(status_code=400, detail=f"Unsupported memory_system: {name}")
        memory_system = factory()
    MEMORY_SYSTEMS[req.user_id] = MemorySystemEntry(name=name, system=memory_system)
    return {"status": "ok", "user_id": req.user_id, "memory_system_name": name}


@app.post("/memory/add")
def add(req: AddRequest):
    memory_system = _get_memory(req.user_id, req.memory_system_name)
    response = memory_system.add_chunk(req.chunk)

    chunk_tokens = _count_tokens(req.chunk)
    cumulative = _CUMULATIVE_RAW_TOKENS.get(req.user_id, 0) + chunk_tokens
    _CUMULATIVE_RAW_TOKENS[req.user_id] = cumulative
    _log_token_event({
        "event": "add",
        "user_id": req.user_id,
        "memory_system_name": req.memory_system_name,
        "chunk_tokens": chunk_tokens,
        "cumulative_raw_tokens": cumulative,
    })

    outputs = {"status": "ok", "user_id": req.user_id}
    outputs['response'] = response
    return outputs


@app.post("/memory/wrap_user_prompt")
def wrap_user_prompt(req: QueryRequest):
    memory_system = _get_memory(req.user_id, req.memory_system_name)
    prompt = memory_system.wrap_user_prompt(req.question)

    _log_token_event({
        "event": "wrap_user_prompt",
        "user_id": req.user_id,
        "memory_system_name": req.memory_system_name,
        "wrapped_prompt_tokens": _count_tokens(prompt),
        "cumulative_raw_tokens_at_call": _CUMULATIVE_RAW_TOKENS.get(req.user_id, 0),
    })

    # Budget verification (BUDGET_VERIFICATION.md): only meaningful for backends that expose
    # a real per-call memory-content token count, distinct from the full wrapped prompt.
    last_memory_tokens = getattr(memory_system, "last_memory_tokens", None)
    if last_memory_tokens is not None:
        last_memory_text = getattr(memory_system, "last_memory_text", "") or ""
        _log_budget_verification({
            "user_id": req.user_id,
            "memory_system_name": req.memory_system_name,
            "configured_budget_tokens": getattr(memory_system, "total_budget_tokens", None),
            "actual_memory_tokens": last_memory_tokens,
            "cumulative_raw_tokens_at_call": _CUMULATIVE_RAW_TOKENS.get(req.user_id, 0),
            "memory_text_first_200": last_memory_text[:200],
            "memory_text_last_200": last_memory_text[-200:],
        })

    return {"status": "ok", "user_id": req.user_id, "prompt": prompt}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
