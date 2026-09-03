# `AGENT_CONFIG_C_QWEN32B` — backbone-scale feasibility, frozen before outcomes

```
config_sha256    = 9de15556a9d1aa3e638c76cd1740d1860015e0428b143e30af54dd677791d629
CONFIG_C_20_HASH = 3250bc02df510146db6e86cbba0f101699e118423237e317a82814f9cb238a7f
```

Machine-readable: `competence_c/agent_config_c.json`.

## The only change vs frozen Config B: the backbone

`agent_c.py` imports `SYSTEM`, `_render`, `format_admissible`, `build_prompt` and
`parse_action` **verbatim from `agent_b`** (`SYSTEM = B.SYSTEM`, `parse_action = B.parse_action`,
…). Prompt wording, admissible-command formatting, ICL example, observation / history /
inventory serialisation, action output contract and the entity-preserving exact parser are
therefore byte-identical to Config B, not re-derived. Horizons unchanged:
`MAX_AGENT_STEPS = 50`, `MAX_NEXT_SUBGOAL_STEPS = 20`. Temperature 0, top_p 1.0, seed 13,
max_tokens 32, stop `["\n"]`. Same ALFWorld 0.5.0, same `AlfredTWEnv`, same
`pf_lib.SubgoalMonitor`.

The one invocation-level addition is `chat_template_kwargs={"enable_thinking": false}` — the
model-format requirement strictly necessary to run Qwen3 in non-thinking mode. Verified
necessary: with it, the model returns `'go to desk 1'`; without it, the same request returns
`'<think>'`.

Nothing else was added: no anti-loop instructions, no expert hints, no `high_pddl`, no hidden
PDDL facts, no subgoal rank, no expert actions, no task-specific rules.

## Backbone

| | |
|---|---|
| requested | `Qwen3-32B-Instruct-AWQ` |
| actual | **`Qwen/Qwen3-32B-AWQ`** — Qwen3-32B is a hybrid-reasoning model; there is no separate `-Instruct-AWQ` release. Non-thinking / direct-answer mode is selected via `enable_thinking=false`. |
| local path | `/home/aristella/models/Qwen3-32B-AWQ` (19 G) |
| quantization | AWQ 4-bit, group_size 128, `gemm`; vLLM runtime kernel **awq_marlin** |
| dtype | `torch.float16` |
| architecture | `Qwen3ForCausalLM`, 64 layers, 64 heads, 8 KV heads, head_dim 128 |
| served name / endpoint | `qwen3-32b-awq-local` @ `http://localhost:8124/v1` |
| vLLM / torch | 0.18.0 / 2.10.0+cu128 |
| max_model_len | 16384 |
| kv_cache_dtype | `auto` (fp16); GPU KV cache 34 192 tokens, 8.35 GiB |
| gpu_memory_utilization | 0.90 |
| attention backend | FLASH_ATTN (FlashAttention 2) |
| enforce_eager / prefix caching | False / disabled |
| device | NVIDIA GeForce RTX 5090, 32607 MiB, driver 595.71.05, CUDA 13.2 |
| external API traffic | **none** — localhost only |

Launch command:

```
/home/aristella/.pipenv-venv/bin/python3 -m vllm.entrypoints.openai.api_server \
  --model /home/aristella/models/Qwen3-32B-AWQ --served-model-name qwen3-32b-awq-local \
  --port 8124 --max-model-len 16384 --gpu-memory-utilization 0.90 --no-enable-prefix-caching
```

The RTX 5090 held only one model at a time; the Llama-3.1-8B server on `:8123` was stopped for
the duration of this experiment with the user's explicit authorisation, and relaunched with its
original command afterwards.

## §1 Non-thinking verification — 3 smoke calls (`competence_c/smoke_c.json`)

| criterion | result |
|---|---|
| no hidden/unlabeled reasoning before the action | **3/3 PASS** (`reasoning_content` is `None`; no `<think>`, no preamble) |
| exactly one parseable action | **3/3 PASS** |
| entity identity preserved | **3/3 PASS** |
| action ∈ `admissible_commands` | **3/3** (was 1/3 for Config B) |
| no external API traffic | PASS — `http://localhost:8124/v1` |

Raw: `ACTION: go to cabinet 1` → `ACTION: open cabinet 1` → `go to cabinet 2`
(6–8 completion tokens each).

```
NON_THINKING_VERIFIED = YES
```

## Pre-registered gates (unchanged)

```
B32     >= 2 -> PASS_SUFFIX_COMPETENCE      == 1 -> STOP_FOR_REVIEW   == 0 -> close ALFWorld
W32     >= 5 -> PASS                        in {2,3,4} -> STOP_FOR_REVIEW  <= 1 -> FAIL_NATIVE
B32_new >= 2 -> PASS                        == 1 -> STOP_FOR_REVIEW   == 0 -> FAIL_SUFFIX
```
