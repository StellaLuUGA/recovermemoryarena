# PrefEval Phase-0 structural audit (§1–§3, §8, §11)

Zero-LLM. No inference, no Mem0, no outcome inspected, no dependency from
`requirements.txt` installed. The PrefEval source tree was not modified.

- Repo `https://github.com/amazon-science/PrefEval.git` @ `50795054b5ff5f418d2b768a331d71e480f93331` (2025-04-21)
- All data ships **inside the checkout** (169 MB) — no external download needed
- Token counts: exact `meta-llama/Llama-3.1-8B-Instruct` tokenizer, snapshot `0e9e39f2…`
- Machine-readable: `structural_audit.json`

## Selected protocol: the classification (MCQ) task

`classification_task/benchmark_classification.py` is the driver. Its data path:

| role | file |
|---|---|
| options + gold | `benchmark_dataset/mcq_options/<topic>.json` → `classification_task_options` |
| explicit preference form | `benchmark_dataset/explicit_preference/<topic>.json` |
| implicit choice-based form | `benchmark_dataset/implicit_preference/choice-based/<topic>.json` |
| implicit persona-driven form | `benchmark_dataset/implicit_preference/persona-driven/<topic>.json` |
| distractor history | `benchmark_dataset/filtered_inter_turns.json` |

`mcq_data[task_id]` is indexed **positionally** against the preference-form file, so the
list index is the pair identity. Positional alignment was verified across all four files
(see "wording variants" below).

Excluded: `benchmark_dataset/mcq_options/travel_hotel copy.json` — a stray 52-record file
that differs from the 54-record `travel_hotel.json` and is referenced by no code path.

## Census

20 topics. Each topic has the **same record count in all four files**, and the four files
are positionally aligned.

| form | files | records |
|---|---|---|
| explicit preference | 20 | **1000** |
| implicit, choice-based | 20 | **1000** |
| implicit, persona-driven | 20 | **1000** |
| MCQ options (shared gold) | 20 | **1000** |

Records per topic range 31 (`education_learning_styles`) to 62 (`entertain_shows`).

| quantity | value |
|---|---|
| raw classification records, one preference form | **1000** |
| raw classification records, all three forms | 3000 |
| unique preference-query pairs | **997** |
| unique preferences (normalized) | 990 |
| unique queries (normalized) | 994 |
| unique underlying source histories (distractor pool) | **1** |
| options per instance | 4 for all 1000 |

## Duplication / cluster audit (§3)

### The three preference forms are variants of ONE pair

For each `(topic, index)` the explicit, implicit-choice and implicit-persona files carry
**the same `preference`, `question` and `explanation`**; they differ only in *how* the
preference is expressed to the model. 970/1000 indices match byte-for-byte across all four
files. The remaining 30 are **paraphrases of the same preference** with an identical
question — always the same pattern: `explicit` says e.g. *"I dislike watching traditional
team sports…"* where the other three say *"I absolutely **dislike** watching traditional
team sports…"*. This is a wording variant, not a misalignment.

**Consequence:** the three forms may not be counted as 3000 independent units, and the
three variants of one pair may never cross a partition boundary.

### Equivalence classes over the 1000 instances

| definition | clusters | size min / median / max |
|---|---|---|
| **A.** same final history — explicit varying part | 988 | 1 / 1 / 3 |
| **A.** same implicit-choice conversation | 1000 | 1 / 1 / 1 |
| **A.** same implicit-persona conversation | 1000 | 1 / 1 / 1 |
| **B.** same preference-query pair | **997** | 1 / 1 / 2 |
| **C.** same base/source history | **1** | 1000 / 1000 / 1000 |
| **D.** same preference identity | 990 | 1 / 1 / 3 |

Reuse detail: 9 preferences appear in 2–3 instances (19 rows, 4 of them spanning two
topics); 6 queries appear twice; 3 preference-query pairs appear twice.

### Class C is the one that needs explaining

`load_turns_data` reads `filtered_inter_turns.json` — **24 conversations, 632 messages,
108,084 tokens** — once per run. `extract_multi_turn_message` is called **once, outside the
task loop**, and `extract_multi_turn_conversation` walks the concatenated message list
**from the beginning** and stops at `2 × inter_turns`:

```python
for turn in multi_turn_message:
    message.append(...)
    if len(message) == turn_number * 2:
        break
```

There is no sampling and no per-task variation. So:

- **every instance in a run receives the identical distractor history**, and
- **`--inter_turns` settings are strict prefixes of one another** — the 10-turn history is
  literally the first 20 messages of the 300-turn history.

Different `--inter_turns` values are therefore **truncations of one source, not independent
examples**, and must never be counted as separate units. Neither may different `--topic`
runs be treated as having different backgrounds: the background is global.

**But note what is and is not shared.** The distractor turns are answer-irrelevant filler
(a WildChat-style pool: the first message is a Python fibonacci snippet). The
*answer-bearing* content — the preference — is unique per instance (990 distinct). This is
the opposite of MAB-AR and LongMemEval-V2, where the **evidence-bearing** context was the
shared object. Sharing a fixed, task-independent background across units does not break
exchangeability; sharing the evidence does. See `EXCHANGEABILITY_AUDIT.md`.

## Long-context structure (§8)

Exact Llama tokens:

| quantity | min | median | p90 | max |
|---|---|---|---|---|
| question | 7 | 14 | 25 | 40 |
| preference | 4 | 14 | 23 | 38 |
| one option | 6 | 13 | 18 | 46 |
| implicit-choice conversation (4 msgs, all instances) | 90 | 133 | 160 | 235 |
| implicit-persona conversation | 399 | 809 | 1,092 | 3,311 |
| implicit-persona messages | 6 | 10 | 12 | 14 |

Constructed history size, explicit form (preference ≈ 15 tok + filler prefix):

| `--inter_turns` | filler tokens | history tokens | × B_ctx (32,768) |
|---|---|---|---|
| 0 | 0 | 15 | 0.00 |
| 3 | 1,131 | 1,146 | 0.03 |
| 10 | 3,854 | 3,869 | 0.12 |
| 50 | 16,115 | 16,130 | 0.49 |
| 100 | 34,834 | 34,849 | **1.06** |
| 300 | 101,573 | 101,588 | **3.10** |
| 316 (max available) | 108,084 | 108,099 | 3.30 |

The pool caps at **316 inter-turns / 108k tokens**. This is a *moderate*-context workload —
three orders of magnitude smaller than LongMemEval-V2 (30M+ per haystack) and ~5× smaller
than MAB-AR's smallest history. It crosses our 32,768-token window at ≈100 inter-turns,
which is exactly the regime where a memory system becomes necessary rather than optional.

### Preference depth

Degenerate by construction: the target preference is **always the first user turn**, and
the query always comes after all `inter_turns` filler turns. There is no depth
distribution to report — depth is a single controlled knob (`--inter_turns`), not a
per-instance property.

## Programmatic classification subset (§11)

The classification task **is** the selected evaluation protocol, not an extra dataset. It
covers the same 1000 preference-query pairs as the generation task; the generation task's
LLM-judge outcomes are not mixed in and contribute nothing to the unit count.

```
independent units available in the programmatic classification subset alone = 985
```

(see `EXCHANGEABILITY_AUDIT.md` for the derivation of 985 from the 997 pairs)
