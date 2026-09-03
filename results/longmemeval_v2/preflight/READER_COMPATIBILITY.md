# Reader / model compatibility (§10)

No reader was changed. One local capability probe was run against the already-running
vLLM server; no paid API was contacted.

## The harness accepts an arbitrary OpenAI-compatible reader

`evaluation/run_eval.py`:

```python
parser.add_argument("--reader-model",    default=os.getenv("READER_MODEL",    "Qwen/Qwen3.5-9B"))
parser.add_argument("--reader-base-url", default=os.getenv("READER_BASE_URL", "http://localhost:8023/v1"))
```

which are forwarded to `harness.py --model / --base-url`; the harness builds an
`AsyncOpenAI(base_url=..., api_key=...)` and calls `chat.completions.create`. So

```bash
export READER_BASE_URL=http://127.0.0.1:8123/v1
export READER_MODEL=llama-3.1-8b-instruct-local
```

is sufficient, with **no code change**, and evaluation semantics (prompt layout, memory
context cap, `\boxed{}` parsing, scoring functions) are untouched by the swap.

Related endpoints: `LME_CONTROLLER_BASE_URL` / `LME_EMBEDDING_BASE_URL` are only needed by
the `rag` and `agentrunbook_r` baselines, not by a ReCoverMem backend. The evaluator
endpoint is separate and discussed in `JUDGE_AUDIT.md`.

## What swapping the reader does and does not mean

- Using Llama-3.1-8B-Instruct **reproduces the benchmark protocol** — same questions, same
  haystacks, same prompt construction, same official scoring functions.
- It does **not** reproduce the paper's leaderboard numbers, which are fixed to
  Qwen3.5-9B as reader. Any number produced under our reader is not comparable to the
  published leaderboard and must never be placed in the same table.
- It is acceptable for an **internal method comparison only**, and only if every compared
  route — MEMORY, RECOVERY, and every baseline row — uses the identical reader, identical
  generation settings and identical prompt wrapper. That condition is satisfiable here
  because the harness owns prompt construction for all backends.

## Blocking issue: the local reader is text-only

Probe against the running server (`POST /v1/chat/completions` with one `image_url` part):

```
HTTP 400 BadRequestError
".../models--meta-llama--Llama-3.1-8B-Instruct/snapshots/0e9e39f2... is not a multimodal model"
```

Consequences, all structural:

| affected input | count / scope | outcome under the current reader |
|---|---|---|
| question screenshots | 29 `errors-gotchas` questions | `build_messages` appends an `image_url` part → **hard 400, the run dies on those questions** |
| memory-context images from official baselines | every `rag_query_to_slice`, `rag_query_to_slice_notes`, `agentrunbook_r` query | **hard 400**; those baselines cannot be reproduced at all |
| a text-only ReCoverMem backend | 422 image-free questions | works — `build_messages` emits no `image_url` when the backend returns only text items |

So the multimodal question is a **separate compatibility issue** from the reader swap:
it blocks 29 questions outright and blocks reproduction of the released RAG/AgentRunbook
comparison rows, regardless of which text model we point at.

## Second blocking issue: context window

| quantity | value |
|---|---|
| official `--memory-context-max-tokens` default | 200,000 |
| official `--max-completion-tokens` default | 20,000 |
| our server `--max-model-len` | **32,768** |

The official operating point needs a reader window of roughly 220k. Ours is 32,768 — a
~6.7× shortfall on the memory context alone, before the system prompt, question and
completion reserve. Running here therefore requires lowering
`--memory-context-max-tokens` to at most ~24k and `--max-completion-tokens` to ~1–2k,
which is a materially different operating point from the released baselines. It is
internally consistent (all routes share it) but not leaderboard-comparable.

## Verdict

**PARTIAL.** The reader is swappable with no semantic change to the protocol, and a
text-only ReCoverMem backend runs on 422 of 451 questions. But (a) 29 image questions and
every official multimodal baseline are hard-blocked by the text-only server, and (b) the
32k window forces a memory-context budget ~8× below the official default. Neither is
fixable by configuration; both would need a multimodal, long-context local server.
