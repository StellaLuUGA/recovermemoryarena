# LongMemEval-V2 multimodal dependency audit (§6)

Structural only. No screenshots were downloaded; every claim below comes from
`questions.jsonl`, `SCHEMA.md`, the HF file listing, and the released reader/memory code.

## Query images

| | count |
|---|---|
| questions with `image != null` | **29** |
| … all of which are `question_type = errors-gotchas` | 29 / 29 |
| `errors-gotchas` questions **without** an image | **0** |
| by domain | web 15, enterprise 14 |
| other 6 question types with images | 0 |

The mapping is exact: **`errors-gotchas` ⇔ has a query screenshot.** Query screenshots are
33 PNGs totalling 3.4 MB (a few ids are shared), stored under `question_screenshots/`.

## Trajectory-side screenshots

`SCHEMA.md`: every state carries `screenshot: screenshots/<trajectory_id>/<step>.png`
**alongside** `url`, `action`, `thought` and `accessibility_tree`. Verified on a fetched
trajectory record: 101 states, each with a 12k-character AXTree plus a screenshot *path*.
Screenshot bytes are never embedded in `trajectories.jsonl`; they live in two tarballs
(`web_screenshots.tar.gz` 2.56 GB, `enterprise_screenshots_base.tar.gz` 3.35 GB).

So a text/state/action record exists for **every** step that has a screenshot. Every
trajectory step is therefore textually representable.

## Do official reader prompts include images? **Yes.**

`harness.build_messages` converts any `{"type": "image"}` memory-context item into an
`image_url` part with a base64 data URL, and appends the question image as a second
`image_url` part when present. The official baselines do emit images:

- `AgentRunbookR._build_raw_state_context_items` appends the **center state screenshot**
  after each retrieved slice, and `rag.py` reuses that exact method — so
  `rag_query_to_slice` and `rag_query_to_slice_notes` are multimodal.
- `_build_event_context_items` appends **pre- and post-state screenshots** per event.
- `count_memory_context_tokens` budgets images through `AutoProcessor.from_pretrained("Qwen/Qwen3.5-9B")`,
  i.e. the official `--memory-context-max-tokens` accounting charges image tokens.

`no_retrieval` returns `[]` and is the only text-only released backend.

## Classification

| scope | classification | basis |
|---|---|---|
| `errors-gotchas` (29) | **IMAGE_REQUIRED** | The query screenshot is part of the question; 100% of this type has one, and no text substitute is released. |
| the other 422 questions | **FULLY_TEXT_COMPATIBLE** *at the question level* | `image` is null; the question is a plain string. |
| official **evidence channel**, both domains, all types | **MIXED_MULTIMODAL** | The released RAG/AgentRunbook backends attach screenshots to retrieved evidence, and the token budget counts them. |
| whole benchmark as officially run | **MIXED_MULTIMODAL** | text-only is a *method choice*, image-required is a *question property* for 29 items. |

## Would a text-only run preserve official task semantics?

Split the question in two:

1. **Evidence side — yes, defensibly.** A memory backend is free to return only
   `{"type": "text"}` items; `no_retrieval` already does, and the harness imposes no
   requirement to emit images. A text-only backend is a legitimate method under the
   released protocol, evaluated by the same official metric. It is weaker than the released
   RAG baselines on questions where the AXTree under-describes a visual state, but it does
   not change what is being measured.

2. **Question side — no, for 29 questions.** For `errors-gotchas` the screenshot is
   *required evidence*: the question text alone does not identify the situation being asked
   about. Dropping the image changes the task. Our current reader cannot accept it either
   (see `READER_COMPATIBILITY.md`: the local Llama server returns HTTP 400
   *"is not a multimodal model"*).

**Do not** assume screenshots are discardable merely because AXTree text exists. The
correct statement is narrower: *trajectory* screenshots are optional context under the
released API, *question* screenshots are required evidence for one question type.

## Defensible text-only subset (reported, NOT selected)

```
selection rule:  image == null
size:            422 of 451
composition:     static-environment 134, dynamic-environment 86, procedure 74,
                 static-environment-abs 55, dynamic-environment-abs 41, procedure-abs 32
excluded:        all 29 errors-gotchas (drops the "environment gotchas" memory ability)
```

Intersecting with the judge-free subset (`JUDGE_AUDIT.md`) gives the fully local,
fully programmatic, text-only pool:

```
selection rule:  image == null  AND  eval_function is programmatic
size:            294 of 451
composition:     static-environment 134, dynamic-environment 86, procedure 74
excluded:        128 abstention questions (LLM judge) + 29 gotchas (image + judge)
abilities kept:  static state recall, dynamic state tracking, workflow knowledge
abilities lost:  environment gotchas, premise awareness
```

294 = 451 − 128 − 29 (the one programmatic `errors-gotchas` question still has an image
and is excluded by the image rule). Neither subset is selected here.
