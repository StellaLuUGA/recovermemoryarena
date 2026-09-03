# PersonaMem-v2 / ImplicitPersona — TEXT-only Phase-0 eligibility audit

Structural only. **No model run, no Mem0, no scorer, no ReCoverMem outcome inspected.**
Neither upstream repository was modified. All artifacts live under
`personamem_recovermem_outputs/`.

## Decision

```
MAIN_TABLE_DECISION = PASS
RECOMMENDATION      = PROCEED_TO_FORMAL
```

All six killer gates pass. This is the **second** workload after PrefEval to clear the
structural bar, and the first long-context one.

## What was fetched

| item | size | note |
|---|---|---|
| `benchmark/text/benchmark.csv` | 42,426,457 B | the only large download |
| `README.md`, `column_descriptions.md` | 20 KB | official field semantics |
| 6 deterministic sample histories from `data/chat_history_32k/` | ~1.0 MB | §10 sample, chosen by history length, outcome-free |
| `github.com/bowen-upenn/PersonaMem-v2` (code, `--depth 1`) | 29 MB | **required by §7** — the official v2 evaluator is not in the v1 checkout |

Not fetched: `train.csv` (157 MB), `val.csv` (17.5 MB), every multimodal file, the other
994 chat histories.

```
V2_DATASET_REVISION  = 0622e56d1cc6f1bc990a5100a6ec4022a60e66a6
BENCHMARK_CSV_SHA256 = 95f2a8a324aab7baf2af937feae12731369e2abf7cad5ab3e170594cb25a3e52
V2_CODE_COMMIT       = dd52429f83ced4394be46c3849186a423942b2a5
```

## 2. Schema

27 columns. Meanings taken from the dataset's own `column_descriptions.md`, not from names.

| role | column(s) |
|---|---|
| user / persona id | `persona_id` (official: 0–999) |
| history reference | `chat_history_32k_link`, `chat_history_128k_link` |
| persona source file | `raw_persona_file` |
| query | `user_query` — a `{'role','content'}` dict literal |
| answer | `correct_answer` — free-form personalized response text |
| distractors | `incorrect_answers` — JSON list, **exactly 3 in all 5,000 rows** |
| evidence pointer | `related_conversation_snippet` — the turns that implicitly revealed the preference |
| categories | `topic_query`, `topic_preference`, `conversation_scenario`, `pref_type`, `who`, `updated`, `sensitive_info` |
| context metadata | `total_tokens_in_chat_history_{32k,128k}`, `distance_from_related_snippet_to_query_{32k,128k}`, `num_persona_{relevant,irrelevant}_tokens_{32k,128k}` |

**Absent**: no `question_id`, no `history_id`, no modality column (text vs multimodal is the
*file*, not a field), and **no inline context** — the history is referenced by path. There is
also **no stored correct-option letter**: the A–D label is created at evaluation time.

## 3. Row / user / history census

```
total rows                 5000
unique persona_id           200      (ids in 10..998, not a contiguous 0..199)
unique chat_history_32k     200
unique chat_history_128k    200
unique raw_persona_file     200
rows per persona            min 6  /  median 25  /  max 42
histories per persona       exactly 1 per size
personas per history file   1
```

The parsed persona id in every path equals the `persona_id` column (verified on all 5,000
rows), so the filename convention is safe to rely on.

**Correcting the Phase-0 v1 estimate:** the HF file listing showed 999 persona ids
*dataset-wide*, but `benchmark/text/benchmark.csv` uses **200** of them. The official README
states that `train.csv` (18,500 queries) and `val.csv` (2,600) have **no `persona_id`
overlap** with the benchmark split. 200 is the eligible benchmark pool — comfortably above 72,
so the correction does not change the decision.

## 4–5. Independence unit and run relationship

```
RAW_UNIQUE_HISTORY_FILES            = 200 (32k) / 200 (128k) / 200 raw persona files
UNIQUE_PERSONAS                     = 200
DEFENSIBLE_INDEPENDENT_SOURCE_UNITS = 200
```

`MULTIPLE_RUNS_PER_PERSONA = NO` within this split. The dataset-wide listing carries two run
timestamps per size, but the released text benchmark references exactly one of each —
`250913_163134` (32k) and `250913_163556` (128k). Had both been referenced they would have
been merged as `SAME_PERSONA_REGENERATION`; the question does not arise here.

`RUN_RELATIONSHIP = N/A (single run per persona in the released text benchmark)`

One dependence that **does** matter: **32k and 128k are two versions of the same persona's
history** (128k pads with persona-irrelevant math/coding content — `num_persona_irrelevant_tokens_32k`
is 0 everywhere, median 83,488 at 128k). They are not independent and **only one size may be
used**. Grouping key is therefore simply `persona_id`.

## 6. Modality — `TEXT_ONLY = YES`

| | count |
|---|---:|
| text-only rows | **5,000** |
| rows requiring images | 0 |
| rows requiring audio/video/other | 0 |
| unknown | 0 |

Three independent confirmations: the file is `benchmark/text/benchmark.csv` (multimodal is a
separate file behind a separate `--use_multimodal` flag); the official README says
`data/chat_history_32k` and `data/chat_history_128k` are *"All histories are text-only"*; and
the 6 sampled history files contain messages whose keys are exactly `{role, content}` — no
image or media field anywhere.

## 7. Correctness — `PROGRAMMATIC_MC`, no judge

From the official evaluator (`PersonaMem-v2/inference.py`):

```python
parser.add_argument('--eval_mode', choices=['mcq','generative','both'], default='mcq', ...)

def create_mcq_options(self, correct_answer, incorrect_answers, ...):
    options = [correct_answer] + incorrect_answers
    random.shuffle(options)          # letters A..D

def check_mcq_correctness(self, predicted_answer, correct_answer, option_mapping):
    predicted_text = option_mapping.get(predicted_answer.upper(), "")
    return predicted_text == correct_answer
```

```
PROGRAMMATIC_ROWS    = 5000
LLM_JUDGE_ROWS       = 0
UNKNOWN_SCORING_ROWS = 0
SCORING_TYPE         = PROGRAMMATIC_MC
```

`evaluate_narrow_judge` / `evaluate_broad_judge` (each "3 LLMs, average score") exist, but are
reached **only** under `eval_mode='generative'`. The default and the mode we would use is
exact string equality. No external API is needed for scoring.

**Reproducibility caveat, recorded not patched:** the option shuffle seed is
`hash(f"{persona_id}_{content}") % 2**32`. Python's `str` hash is randomised per process
unless `PYTHONHASHSEED` is set, so the official shuffle is **not reproducible across runs by
default**. ReCoverMem would derive a deterministic per-row seed and record it — the same
treatment PrefEval's missing `import random` received.

## 8. History / query boundary — `HISTORY_BOUNDARY_CLEAN`

`inference.py` assembles the prompt as

```python
full_chat_history = chat_history + [user_query_dict]
```

The **entire** history file is the observable context and the query is appended after it, so
there is no future segment to leak from and no cutoff to compute. All rows of a persona share
that one history — the inject-once/query-many pattern again, which is exactly why the unit
must be the persona and not the row.

Sampled history structure: `{"chat_history": [{role, content}, ...], "metadata": {...}}`,
275+ messages, roles `system` / `user` / `assistant`. Atomic message units are directly
available for a bounded recovery operator.

**Leakage probe (the one real risk, and it comes out clean).** The first message is a
`system` turn embedding the persona JSON. It carries `short_persona`, name, demographics,
`personality`, `education`, `occupation` and (in 3 of 6 sampled personas) `hobbies_and_interests`.
It does **not** carry `stereotypical_preferences`, `anti_stereotypical_preferences`,
`neutral_preferences`, `therapy_background`, `health_and_medical_conditions`,
`sensitive_information` or `preference_updates` — i.e. none of the fields the questions test.

```
tested `preference` found verbatim in the system message : 0 / 155 sampled rows (6 personas)
related_conversation_snippet located inside the history  : 139 / 155 fully matched
snippet relative position in history: min 0.004 / median 0.380 / max 0.882
```

The 16 unmatched snippets differ by whitespace or light rewriting; **none** matched inside the
system message. The evidence genuinely sits in the conversation body, in the past.

## 9. History dependence — `CLEAR_MEMORY_DEPENDENT`

```
CLEAR_HISTORY_DEPENDENT_ROWS    = 4492   (89.8%)  distance_from_related_snippet_to_query_32k > 0
POSSIBLE_HISTORY_DEPENDENT_ROWS =  508   (10.2%)  distance == 0
NON_HISTORY_DEPENDENT_ROWS      =    0
```

Every one of the 508 `distance == 0` rows is `pref_type = 'sensitive_info'` — a pre-defined
released category, so excluding them (if desired) is an outcome-independent decision, not a
post-hoc filter. All 5,000 rows carry a non-empty `related_conversation_snippet`.

The benchmark's whole premise is implicit revelation: a preference surfaces inside an
*unrelated* request (the paper's example: a pollen allergy mentioned while asking for help
rewording an email). The query alone cannot contain the answer by construction.

## 10. Context length

| quantity | min | p25 | median | p75 | p95 | max |
|---|---:|---:|---:|---:|---:|---:|
| total tokens, 32k history | 23,875 | 31,690 | **31,855** | 31,948 | 31,993 | 34,137 |
| total tokens, 128k history | 68,497 | 105,487 | **122,747** | 123,966 | 125,777 | 127,873 |
| distance snippet → query, 32k | 0 | 13,326 | **18,861** | 24,764 | 29,834 | 33,184 |
| distance snippet → query, 128k | 0 | 38,525 | **64,170** | 89,379 | 114,455 | 124,639 |
| persona-irrelevant tokens, 32k | 0 | 0 | 0 | 0 | 0 | 0 |
| persona-irrelevant tokens, 128k | 18,258 | 63,473 | **83,488** | 88,470 | 95,523 | 99,754 |

Against our 32,768-token reader window: the **32k** histories sit right at the boundary
(median 31,855 ≈ 0.97×) — the memory route would be meaningful but the raw history would
*almost* fit, weakening the compressed-memory-vs-recovery contrast. The **128k** histories are
**≈ 3.7× the window** with a median 83,488 tokens of deliberate distractor padding, and the
evidence sits a median of 64,170 tokens back. **128k is the scientifically stronger choice**
and matches the ratio PrefEval used at 300 inter-turns (3.1×).

## 11–12. Split feasibility and killer gates

| gate | result |
|---|---|
| ≥ 72 defensible source units | **PASS** — 200, i.e. 128 spare |
| `TEXT_ONLY = YES` | **PASS** |
| programmatic evaluation, no mandatory judge | **PASS** |
| history boundary clean or fixable | **PASS** (CLEAN) |
| queries genuinely history/preference dependent | **PASS** |
| source units separable by persona without leakage | **PASS** (1 history per persona; `persona_id` is the whole grouping key) |
| enough raw textual history for compressed-memory vs bounded-recovery | **PASS** (128k: 3.7× the reader window) |

```
CAN_SUPPORT_24_24_24 = YES
```

## 13. Proposed formal protocol — **proposal only, nothing frozen**

Written to `v2_text_proposed_split.json`. **No file was written to `frozen_protocol/`.**

```
rule : seed-13 numpy permutation within strata defined by each persona's dominant
       conversation_scenario, interleaved round-robin across strata, first 72 taken,
       then dealt 0/1/2 mod 3 into predictor_train / calibration / final_test
sizes: 24 / 24 / 24, disjoint, 72 of 200 personas
rows : predictor_train 601 | calibration 602 | final_test 592
```

`conversation_scenario` (9 balanced values) is the natural stratification axis;
`topic_query` has 335 values and is too sparse. Selection uses no outcome of any kind.

Download needed for the formal run:

```
ELIGIBLE_PERSONA_POOL                 = 200
ESTIMATED_HISTORY_FILES_NEEDED_FOR_72 = 72   (one text history per persona, one size)
ESTIMATED_DOWNLOAD_SIZE_FOR_72        = ~9 MB at 32k  /  ~37 MB at 128k
                                        (6 sampled 32k files averaged 166 KB; 128k scales ~4x)
```

Trivially small either way. Fetching all 200 personas' 32k histories would be ~25 MB.

## Open items before formal collection

1. **Choose the size: 128k recommended** (3.7× the reader window vs 0.97× at 32k). Changes the
   scientific meaning, so it is your call, not mine.
2. **Decide on the 508 `sensitive_info` rows** (`distance == 0`). Keep or exclude — either is
   defensible as long as it is decided now, from the released category, before any outcome.
3. **Fix the option-shuffle seed** deterministically (§7 caveat) and record it in the protocol.
4. Two-stage budget audit and `B_mem = B_rec` freeze, exactly as done for PrefEval.

## Stop

Phase 0 ends here. No Mem0 built, no Llama run, no scorer trained, no `R_mem`/`R_rec`/FS/Cov
computed, no thresholds selected, no split frozen.
