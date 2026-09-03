"""Shared plumbing for the formal ALFWorld ReCoverMem experiment.

Local-only. No external APIs. Mem0 telemetry and litellm remote cost maps are disabled
before mem0 is ever imported.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# ---- hard safeguards, set BEFORE any mem0 / litellm import ----------------
os.environ["MEM0_TELEMETRY"] = "False"
os.environ["MEM0_TELEMETRY_SAMPLE_RATE"] = "0.0"
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ.setdefault("OPENAI_API_KEY", "EMPTY")
os.environ.setdefault("ALFWORLD_DATA", "/home/aristella/.cache/alfworld")

REPO = Path("/home/aristella/recoverappworld")
PREFLIGHT = REPO / "alfworld_recovermem_preflight"
RM_ROOT = Path("/home/aristella/RecoverMemMinimal/update_replicate")
# Output root. Defaults to the canonical B=1024 tree; `AF_RESULTS_ROOT` redirects every
# artifact and Mem0 store for side experiments (e.g. the B=512 budget-sensitivity run) so
# they can never write into the frozen canonical directory.
_RESULTS_ROOT = os.environ.get("AF_RESULTS_ROOT")
RESULTS = Path(_RESULTS_ROOT).resolve() if _RESULTS_ROOT else REPO / "results/alfworld/final"
STORES = RESULTS / "_stores"

for p in (str(PREFLIGHT), str(RM_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

# ---- frozen constants -----------------------------------------------------
SEED = 13
GAMMA = 1.0                      # utility is already binary; R = 1[u >= gamma]
MAX_TOTAL_AGENT_ACTIONS = 50     # Config C horizon
MAX_BRANCH_ACTIONS = 20          # paired / routed segment horizon
CANDIDATE_BUDGETS = (256, 512, 1024, 2048, 4096, 8192, 16384)

QWEN_MODEL = "qwen3-32b-awq-local"
QWEN_PATH = "/home/aristella/models/Qwen3-32B-AWQ"
QWEN_BASE_URL = "http://localhost:8124/v1"
QWEN_MAX_MODEL_LEN = 16384
EMBEDDER = "sentence-transformers/all-MiniLM-L6-v2"

N_PREDICTOR_TRAIN, N_CALIBRATION, N_FINAL_TEST = 16, 24, 24   # resized: only 64 clean games exist
N_TABLE2 = 20
N_RESAMPLES = 200


def sha256_text(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


def sha256_json(obj: Any) -> str:
    return sha256_text(json.dumps(obj, sort_keys=True, default=str))


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def jdump(obj, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(path) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2, default=str)
    os.replace(tmp, path)


def jload(path):
    with open(path) as f:
        return json.load(f)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---- token ledger ---------------------------------------------------------
class TokenLedger:
    """Exact prompt+completion token accounting per cost bucket."""

    BUCKETS = ("ctrl", "mem", "rec", "write", "native")

    def __init__(self):
        self.reset()

    def reset(self):
        self.data = {b: {"prompt": 0, "completion": 0, "calls": 0} for b in self.BUCKETS}

    def add(self, bucket: str, prompt: int, completion: int):
        d = self.data.setdefault(bucket, {"prompt": 0, "completion": 0, "calls": 0})
        d["prompt"] += int(prompt or 0)
        d["completion"] += int(completion or 0)
        d["calls"] += 1

    @property
    def total(self) -> int:
        return sum(d["prompt"] + d["completion"] for d in self.data.values())

    def snapshot(self) -> dict:
        s = {k: dict(v) for k, v in self.data.items()}
        s["total_tokens"] = self.total
        s["total_calls"] = sum(v["calls"] for v in self.data.values())
        return s


LEDGER = TokenLedger()
_ACTIVE_BUCKET = {"name": "native"}


def set_bucket(name: str):
    _ACTIVE_BUCKET["name"] = name


def current_bucket() -> str:
    return _ACTIVE_BUCKET["name"]


EXTERNAL_ATTEMPTS = {"count": 0, "urls": []}


def assert_local(url: str, what: str):
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    if host not in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        EXTERNAL_ATTEMPTS["count"] += 1
        EXTERNAL_ATTEMPTS["urls"].append(f"{what}:{url}")
        raise RuntimeError(f"{what} points at non-local host {host!r}")


def instrument_openai_client(client, bucket_hint=None):
    """Wrap client.chat.completions.create so every call is metered and forced into
    Qwen non-thinking mode. Returns the same client."""
    comp = client.chat.completions
    if getattr(comp, "_rm_instrumented", False):
        return client
    orig = comp.create

    def create(*args, **kwargs):
        eb = dict(kwargs.get("extra_body") or {})
        ctk = dict(eb.get("chat_template_kwargs") or {})
        ctk.setdefault("enable_thinking", False)
        eb["chat_template_kwargs"] = ctk
        kwargs["extra_body"] = eb
        resp = orig(*args, **kwargs)
        u = getattr(resp, "usage", None)
        if u is not None:
            LEDGER.add(bucket_hint or current_bucket(),
                       getattr(u, "prompt_tokens", 0), getattr(u, "completion_tokens", 0))
        return resp

    comp.create = create
    comp._rm_instrumented = True
    return client


def install_global_openai_instrumentation():
    """Instrument EVERY openai.OpenAI client at construction time.

    Guarantees complete token accounting no matter where a client is created (mem0
    creates its own internally), and forces Qwen non-thinking mode on every call.
    """
    import openai
    if getattr(openai.OpenAI, "_rm_patched", False):
        return
    orig_init = openai.OpenAI.__init__

    def __init__(self, *a, **kw):
        orig_init(self, *a, **kw)
        try:
            base = str(getattr(self, "base_url", "") or "")
            if base:
                assert_local(base, "openai client")
            instrument_openai_client(self)
        except RuntimeError:
            raise
        except Exception:
            pass

    openai.OpenAI.__init__ = __init__
    openai.OpenAI._rm_patched = True
