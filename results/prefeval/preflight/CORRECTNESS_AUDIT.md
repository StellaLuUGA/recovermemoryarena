# PrefEval classification correctness / judge audit (§6)

Line-by-line read of `classification_task/benchmark_classification.py`,
`utils/utils_mcq.py`. **No model was called.**

## Classification: **PROGRAMMATIC**

No LLM judge exists anywhere on the classification path. `generation_task/` contains
`llm_based_evaluation_errortypes.py` and
`get_preference_following_accuracy_generation_task.py`, which *do* use an LLM judge — those
belong to the generation task and are not on this path.

## The exact metric

```python
# utils/utils_mcq.py
def shuffle_options(options):
    """Note: In the MCQ datasets, the first choice in the JSON file is the correct answer."""
    correct_answer   = options[0]
    shuffled_options = random.sample(options, len(options))
    correct_index    = shuffled_options.index(correct_answer)
    return shuffled_options, correct_index

# classification_task/benchmark_classification.py
options              = mcq_data[task_id]["classification_task_options"]
new_options, correct_idx = shuffle_options(options)
...
choice               = extract_choice(end_generation)
task["correct_idx"]  = ["A", "B", "C", "D"][correct_idx]
if task["choice"] == task["correct_idx"]:
    correct_count += 1
accuracy = correct_count / processed_tasks
```

Formally, for instance *i* with options *O_i* and shuffling permutation *π_i*:

```
gold_i    = letter( π_i^{-1}(0) )                    # options[0] is the gold, pre-shuffle
pred_i    = extract_choice(response_i) ∈ {A,B,C,D,None}
correct_i = 1[ pred_i == gold_i ]                    # None => 0
accuracy  = (1/N) Σ_i correct_i
```

## Answers to the audited points

1. **Correctness function.** Exact string equality between the extracted letter and
   `["A","B","C","D"][correct_idx]`. No normalization, no partial credit, no judge.
2. **Gold form.** An **option index into the pre-shuffle list — always index 0** — converted
   to a letter after shuffling. There is no `answer` field in the data; the gold is a
   positional convention, documented in `shuffle_options`' docstring and used nowhere else.
3. **Output parsing.** `extract_choice(response)` runs BeautifulSoup over the response,
   finds a `<choice>` tag, and regex-matches `[ABCD]` inside it. For Claude/Mistral the
   driver prepends the literal `"<choice>"` to the completion first (the prompt ends with an
   assistant prefix `<choice>`), so the model only has to emit the letter and `</choice>`.
   `extract_choice_mistral` (JSON `{"choice": "A"}`) exists but is **not called** by the
   classification driver.
4. **Exact / programmatic?** Yes, fully. Pure string and regex operations.
5. **LLM judge?** **No.**
6. **External API?** Only for *generation* (AWS Bedrock `boto3` for the answer itself). The
   *scoring* step needs no API at all — it is `==`. Swapping the answer model for our local
   OpenAI-compatible endpoint leaves scoring untouched.
7. **Malformed answers.** Deterministically incorrect. `extract_choice` returns `None` when
   there is no `<choice>` tag or no `[ABCD]` inside it (the bare `except: return None`, plus
   an implicit `None` fallthrough when `choice_tag` is falsy or the regex misses).
   `None == "A"` is `False`, so the instance scores 0. There is no abstention category and
   no re-prompt.
8. **Ambiguous / multiple-correct options.** Checked over all 1000 instances:
   **0** have duplicate option strings, **0** have empty options, all have exactly 4. Exactly
   one option is designated correct. Semantic near-duplicates were not machine-checkable and
   are not claimed to be absent.

## Two upstream defects found

### 1. `benchmark_classification.py` crashes on import-time symbol `random`

Line 68 calls `random.seed(41)` and line ~120 calls `shuffle_options` (which uses
`random.sample`), but **`random` is never imported** in that file — its imports are
`argparse, boto3, json, logging, os, sys, yaml, tqdm, botocore`, plus explicit `from … import`
names that do not include `random`. As released, the classification driver raises
`NameError: name 'random' is not defined` before doing any work.

This is trivially fixable (`import random`) and does not affect the audit: we would write
our own runner regardless. It does mean **no released classification result can have been
produced by this exact file revision**, so the shuffle seed used for published numbers is
unknown.

### 2. The gold is a positional convention with no redundancy

`options[0]` being correct is asserted only in a docstring. There is no `answer`,
`correct_option` or `gold` field to cross-check against, and no validator. Any future
reordering of a `classification_task_options` list would silently corrupt the labels.

For ReCoverMem this is a **hard leakage boundary**: `classification_task_options[0]` is
benchmark-private metadata. The shuffle must happen before anything reaches the memory
host, the scorer or the reader, and the pre-shuffle order must never be logged into a
feature.

## Surface-cue probes (zero-LLM)

| probe | observed | chance |
|---|---|---|
| correct option is the **longest** of the four | **44.6%** | 25% |
| correct option has the **highest lexical overlap with the preference** | 17.8% | 25% |
| mean correct-option length | 13.96 tok | distractors 13.57 tok |

The length cue is real and worth recording: a reader with no memory at all can reach ~45%
by always choosing the longest option, versus 25% random. Any reported memory-route
accuracy must be read against that floor, not against 25%.

The overlap result runs the *other* way — the correct option lexically resembles the
preference **less** than distractors do (17.8% < 25% chance). The task is genuinely
semantic, not solvable by lexical matching against the preference. That is good for
validity, and it also means a lexical recovery operator can locate the preference turn in
the history easily while the reader still has to do the real work.

## Classification

```
PROGRAMMATIC
```

Preferred for Table 1: correctness is a deterministic function of the response string and
the option list, requires no API, and is reproducible offline.
