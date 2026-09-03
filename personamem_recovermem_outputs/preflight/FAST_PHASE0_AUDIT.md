# PersonaMem — fast Phase-0 structural audit for ReCoverMem

Static/structural only. **No LLM call, no paid API, no benchmark inference, no Mem0, no
ReCoverMem outcome inspected.** The upstream PersonaMem repository was not modified
(`git status` clean); every artifact is under `personamem_recovermem_outputs/`.

- Repo `https://github.com/bowen-upenn/PersonaMem.git` @ **`caaae44b3f236b8751d499a770e94e5aecffcff1`** (2026-03-19)
- Machine-readable: `fast_phase0_audit.json`, `source_units_v1.json`,
  `source_overlap_matrix.json`, `source_units_v2.json`

## Decision

```
BEST_SETTING   = NONE  (for PersonaMem-v1)
RECOMMENDATION = POSSIBLE_WITH_PROTOCOL_DECISION  (only via PersonaMem-v2, unverified)
```

Blocking condition for all three v1 sizes: **20 defensibly independent source histories**
against a requirement of 72 — and 20 is below the 60 floor, so it is `SOURCE_COUNT_FAIL`,
not `NEAR_PASS_SOURCE_COUNT`.

## 0. Repo / data inventory

The benchmark data is **not in the repository**: `data/` holds only
`random_questions.txt` and `random_code_questions.txt` (distractor pools). No prior local
HuggingFace cache existed.

The full v1 release on HF (`bowen-upenn/PersonaMem`, sha `fd7c30f0…`) is **251.9 MB** — small
enough that downloading it was proportionate and is what makes the raw-context hash audit in
§2 possible. It was fetched into `personamem_recovermem_outputs/_data_v1`, **outside** the
upstream repo. No model API was contacted.

| file | size | sha256 (16) | status |
|---|---|---|---|
| `questions_32k.csv` | 1.31 MB | `cccd34cf53e0bc4d` | LOCAL |
| `questions_128k.csv` | 5.26 MB | `f0e137c3167fadbf` | LOCAL |
| `questions_1M.csv` | 5.15 MB | `f24db37c1ef49e8f` | LOCAL |
| `shared_contexts_32k.jsonl` | 5.61 MB | `217247ebfec9e844` | LOCAL |
| `shared_contexts_128k.jsonl` | 73.66 MB | `733cc009e84a138b` | LOCAL |
| `shared_contexts_1M.jsonl` | 160.93 MB | `283c1d4714970284` | LOCAL |

## 1. Question / source census

| | 32k | 128k | 1M |
|---|---:|---:|---:|
| question rows | 589 | 2,727 | 2,674 |
| unique `question_id` | 589 | 2,727 | 2,674 |
| **unique `persona_id`** | **20** | **20** | **20** |
| unique `shared_context_id` | 37 | 60 | 31 |
| contexts in the jsonl | 37 | 110 | 33 |
| unreferenced extra contexts | 0 | 50 | 2 |
| questions / shared context (min·med·max) | 5·16·28 | 24·45·64 | 61·85·114 |
| questions / persona (min·med·max) | 17·30·43 | 105·139.5·184 | 75·150·227 |
| shared contexts / persona (min·med·max) | 1·2·2 | 3·3·3 | 1·2·2 |
| context tokens (min·med·max) | 15.6k·25.7k·29.5k | 100k·118k·128k | 405k·925k·959k |
| distinct topics | 13 | 15 | 15 |

Explicit flags:

- **one `shared_context_id` → multiple `persona_id`: NO** (max 1 persona per context, all sizes).
- **one `persona_id` → multiple `shared_context_id`: YES** (2–3 contexts per persona everywhere).

The `persona_id` values are literally `0…19` in all three sizes.

## 2. Raw-context identity audit

SHA-256 over the complete serialized context, plus a message-level representation preserving
role and text in order.

```
contexts hashed (all sizes)                    180
unique full-context hashes                     180
exact duplicate contexts                         0
duplicate hashes across shared_context_ids       0
duplicate hashes across personas                 0
```

No two released contexts are byte-identical. **But that is not evidence of independence** —
the decisive measurement is the persona definition:

```
distinct system persona prompts, all sizes pooled          = 20
personas whose contexts all share one identical system prompt = 20/20 in each size
personas with the IDENTICAL system prompt in all three sizes  = 20/20
```

`shared_context_id` is itself a content hash, so distinct IDs are guaranteed by construction
and carry no information about independence.

## 3. Persona / variant dependence — the decisive check

`scripts/run_generate_benchmark.sh` loops `idx_persona` from 0 to 19 and calls
`--n_variants 2`. In `prepare_blocks.py`:

```python
def topological_sort(processed_blocks, tokenizer=None, num_variants=1, verbose=False):
    ...
    for variant in range(num_variants):
        random.seed(variant)
        # Mode A: long distance from the last session to previous sessions
        # Mode B: long distance from the end-of-text questions to the last sessions
        mode = "A" if variant == 0 else "B"
```

Both variants are **orderings of the same `processed_blocks` pool for one persona**, and the
three benchmark sizes differ only in `n_blocks` (10 / 20 / 60) drawn from that same pool.

Classification of every within-persona context pair:

| relation | count |
|---|---:|
| `SAME_HISTORY_REORDERING` (identical message sets, different order) | 6 |
| `SAME_UNDERLYING_SESSION_POOL` | all remaining pairs |
| `INDEPENDENT_GENERATION` | **0** |

Nothing in the release supports treating two contexts of persona *k* as independent
generative histories. Applying the brief's conservative default:

```
exchangeability unit = persona_id
```

## 4. Cross-size dependence

| Pair | Persona overlap | Context-ID overlap | Exact hash overlap | System-prompt overlap | Same underlying histories? |
|---|---:|---:|---:|---:|---|
| 32k / 128k | **20 / 20 (identical sets)** | 0 | 0 | **20** | **YES** |
| 32k / 1M | **20 / 20 (identical sets)** | 0 | 0 | **20** | **YES** |
| 128k / 1M | **20 / 20 (identical sets)** | 0 | 0 | **20** | **YES** |

Same-persona cross-size message Jaccard: median 0.072 (32k↔128k), 0.051 (32k↔1M),
0.213 (128k↔1M) — every cross-size pair shares at least some messages, and none is a prefix
of another. The sizes are separately ordered draws of different block counts from one
per-persona pool, not truncations and not independent samples.

**Pooling the three sizes is not permitted**: it would triple-count the same 20 users.

## 5. Correctness / judge audit — **PROGRAMMATIC_MC**

`inference.py::extract_answer` is pure regex:

```python
in_parens = re.findall(r'\(([a-d])\)', text)
...
if pred_options == {correct}: return True, predicted_answer
```

| | 32k | 128k | 1M |
|---|---:|---:|---:|
| rows whose `correct_answer` is a single `(a)`–`(d)` | **589/589** | **2727/2727** | **2674/2674** |
| rows with exactly 4 parsed options | 589 | 2,727 | 2,674 |

| class | count |
|---|---:|
| PROGRAMMATIC_MC | **5,990 (100%)** |
| PROGRAMMATIC_OTHER / LLM_JUDGE / UNKNOWN | 0 |

**No LLM judge anywhere on the evaluation path**, and scoring needs no external API. Note
that `--filter_questions` does use an LLM — but at *dataset generation* time, to drop
questions answerable without context. That filtering is already baked into the release and
is not part of evaluation.

This axis passes cleanly, and it is the axis LongMemEval-V2 and Gaia2 both failed.

## 6. History dependence — **CLEAR_MEMORY_DEPENDENT**

Computed from released metadata only.

| | 32k | 128k | 1M |
|---|---|---|---|
| `distance_to_ref_in_blocks` (min·med·max) | 1·4·7 | −17·12·21 | 2·37·60 |
| fraction with distance > 0 | 100.0% | 98.4% | 100.0% |
| `distance_to_ref_in_tokens` (med·max) | 15,604 · 28,862 | 65,445 · 127,040 | 533,771 · 940,450 |
| `num_irrelevant_tokens` (median) | 0 | 15,712 | 628,964 |

The referenced preference sits a median of 4 / 12 / 37 sessions before the question, and the
1M setting buries it under a median of 629k irrelevant tokens. Structurally this is an
excellent compressed-memory workload — 1M contexts are ~28× a 32,768-token reader window.

## 7. Defensible independent source-unit count

| | 32k | 128k | 1M |
|---|---:|---:|---:|
| raw question rows | 589 | 2,727 | 2,674 |
| unique `persona_id` | 20 | 20 | 20 |
| unique `shared_context_id` | 37 | 60 | 31 |
| unique raw-context hashes | 37 | 60 | 31 |
| **defensibly independent source histories** | **20** | **20** | **20** |
| max equal 3-way split `floor(n/3)` | **6 / 6 / 6** | **6 / 6 / 6** | **6 / 6 / 6** |
| ≥ 72 independent histories? | NO | NO | NO |
| programmatic scoring | YES | YES | YES |
| decision | `SOURCE_COUNT_FAIL` | `SOURCE_COUNT_FAIL` | `SOURCE_COUNT_FAIL` |

Even the most permissive defensible reading — counting each `shared_context_id` as its own
unit, which §3 shows is *not* defensible — yields at most 60 (128k), still short of 72 and
achieved only by treating Mode-A/Mode-B reorderings of one pool as independent users.

## 8. PersonaMem-v2 / ImplicitPersona — `NOT_LOCAL`

4.58 GB across 9,001 files; **not downloaded**. Inspected through the HuggingFace file
listing alone (sha `0622e56d…`), which is genuinely informative because persona ids appear in
the filenames:

```
data/chat_history_32k             1998 files   999 distinct persona ids   2 run timestamps
data/chat_history_128k            1998 files   999 distinct persona ids   2 run timestamps
data/chat_history_multimodal_32k  1998 files   999 distinct persona ids   2 run timestamps
data/chat_history_multimodal_128k 1998 files   999 distinct persona ids   2 run timestamps
data/raw_data                      999 files
union of distinct persona ids                  999   (range 0..999)
```

So the README's **"1000 preferences" corresponds to ~999 distinct persona ids**, not 1,000
rows over a handful of users. Each persona appears under 2 generation timestamps × {32k,128k}
× {text, multimodal}; those 4–8 files per persona are variants and must be grouped, but the
persona count itself would comfortably clear the 72 threshold.

Unverified, and blocking a decision:

- `benchmark/text/benchmark.csv` (42 MB) was not downloaded — row counts, questions per user,
  answer format and context structure are **unknown**;
- whether the 2 run timestamps are regenerations of the same personas or genuinely separate
  histories is **unknown** (conservatively they would be grouped);
- the multimodal half needs a vision-capable reader; the local Llama-3.1-8B endpoint is
  text-only (verified earlier: HTTP 400 *"is not a multimodal model"*).

## 9. Eligibility summary

| criterion | v1 (all sizes) |
|---|---|
| ≥ 72 defensibly independent source histories | **FAIL (20)** |
| source grouping clear | PASS (persona_id, proven by the generator) |
| split without persona/history leakage | possible in principle, but only 6/6/6 |
| correctness programmatic | **PASS** |
| questions structurally history-dependent | **PASS** |
| raw history long enough for compressed memory | **PASS** (25.7k / 118k / 925k median tokens) |

```
32k  -> SOURCE_COUNT_FAIL
128k -> SOURCE_COUNT_FAIL
1M   -> SOURCE_COUNT_FAIL
```

Not `JUDGE_FAIL` (scoring is fully programmatic) and not primarily `INDEPENDENCE_FAIL` (the
grouping is clean and provable) — the benchmark simply contains 20 users.

## The exact structural reason

PersonaMem-v1 was generated by looping over **20 personas** and emitting, for each, two
orderings (Mode A / Mode B) of one session-block pool at three block depths. Every axis that
killed the other candidates passes here — correctness is 100 % programmatic 4-option MC,
history dependence is universal and deep, and contexts are long enough that compressed memory
genuinely matters. What is missing is simply **users**: 5,990 question rows sit on top of 20
distinct people, and the 148–299× inflation from rows to personas is exactly the
inject-once/query-many pattern that must not be mistaken for sample size.

## What PersonaMem could still be

1. **PersonaMem-v2 / ImplicitPersona — the only route to a main table.** ~999 persona ids
   would clear 72 with large margin, correctness is plausibly the same MC format, and the
   32k text split is the natural target. Requires downloading and auditing
   `benchmark/text/benchmark.csv` (42 MB) plus the persona-grouping question. **Recommend
   authorising that specific 42 MB fetch as the next step** — it is small, and it is the only
   open question that could still yield a second main-table domain.
2. **v1 as an appendix / transfer setting.** 20 histories, 6/6/6 at best. Usable only with a
   threshold imported from another domain and reported without an in-domain calibration
   claim. The 1M setting is the most interesting of the three (median 629k irrelevant tokens).
3. **v1 as a qualitative long-context example.** No calibration claim at all.

Not recommended: pooling the three sizes, or counting `shared_context_id` as the unit — both
manufacture independence from reorderings of the same 20 users.

## Stop

Phase 0 ends here. No Mem0 built, no Llama run, no scorer trained, no `R_mem`/`R_rec`/FS/Cov
computed, no thresholds selected, no outcome inspected.
