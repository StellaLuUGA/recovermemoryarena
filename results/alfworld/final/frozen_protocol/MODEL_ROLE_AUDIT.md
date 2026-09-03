# Model-role audit — ALFWorld Qwen3-32B stack configuration

| role | model | endpoint |
|---|---|---|
| action agent | `qwen3-32b-awq-local` (Qwen3-32B-AWQ, non-thinking, T=0) | `http://localhost:8124/v1` |
| Mem0 internal LLM | `qwen3-32b-awq-local` (same server) | `http://localhost:8124/v1` |
| embedding | `sentence-transformers/all-MiniLM-L6-v2`, 384-d, CPU | local |
| recovery | `recovermem.recovery.TrajectoryRetriever` — IDF lexical, **no LLM** | n/a |
| vector store | FAISS, per-episode on-disk path | local |

**This is labelled explicitly: `ALFWorld Qwen3-32B stack configuration`.** The RTX 5090 cannot
reliably hold Qwen3-32B-AWQ and a separate Llama-3.1-8B Mem0 LLM simultaneously, so Mem0's
internal LLM is the same Qwen server as the action agent. It is not presented as an agent-only
Qwen experiment.

Mem0: pinned OSS checkout `/home/aristella/RecoverMemMinimal/update_replicate/mem0` at commit `39bc02330563764e7d4465f1ecff5f002d94da1a`
(the tau3 commit). Not upgraded.

Safeguards: `MEM0_TELEMETRY=False` and `MEM0_TELEMETRY_SAMPLE_RATE=0.0` set before `mem0` is
imported; `LITELLM_LOCAL_MODEL_COST_MAP=True`; `HF_HUB_OFFLINE=1`; `TRANSFORMERS_OFFLINE=1`.
Every `openai.OpenAI` client is instrumented at construction — a non-local `base_url` raises,
all prompt/completion tokens are metered into the cost ledger, and `enable_thinking=false` is
forced on every call. During formal execution there is no outbound network access beyond
localhost.

Recorded honestly: during environment **setup**, before any formal collection, mem0's spaCy
dependency downloaded `en_core_web_sm` once. It is cached and no download occurs during the run.

Code hash (af_formal + frozen preflight interface modules): `7c11c87a2d4c80fcb3c1e8dffb4c13020d157e42ecc840c8a6507a6e35f8200a`
