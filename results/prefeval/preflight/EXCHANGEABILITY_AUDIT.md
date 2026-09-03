# PrefEval exchangeability unit and split feasibility (§4, §5, §9)

No outcomes were inspected. No splits were generated.

## The candidate units

| candidate | count | verdict |
|---|---|---|
| classification row (all 3 preference forms) | 3000 | **No.** The three forms are re-expressions of one preference-query pair; 970/1000 indices are byte-identical across the four files and the other 30 differ only by a preference paraphrase with an identical question. |
| classification row (one form) | 1000 | Almost — but 3 pairs, 9 preferences and 6 queries recur across rows. |
| **preference-query pair** | **997** | Yes, before merging the recurrences. |
| final constructed history | 988–1000 (form-dependent) | Same thing as the pair, plus the shared background; not a distinct unit. |
| source conversation / background history | **1** | The distractor pool is global (see below). |
| `--inter_turns` variant | — | **Never a unit.** Strict prefixes of one source. |

## Why the shared background is not disqualifying here

`filtered_inter_turns.json` supplies one 632-message pool; `extract_multi_turn_message` is
called once per run and returns `fmsgs[:2N]` in file order, so **every instance sees the
identical distractor turns**. Under class C that is one cluster of size 1000.

This looks like the MAB-AR / LongMemEval-V2 failure at first glance. It is not the same
thing, and the distinction is the whole decision:

| | MAB-AR | LongMemEval-V2 | **PrefEval** |
|---|---|---|---|
| what is shared across instances | the **answer-bearing** context (one book answers 100 queries) | the **answer-bearing** haystack (one 100-trajectory history answers 240 questions) | only the **answer-irrelevant** filler |
| what is unique per instance | the query | the query | the **preference** — i.e. the evidence itself |
| can memory be built once and reused? | yes, and the harness does | yes, and the harness does | **no** — each instance injects a different preference, so each needs its own store |
| effective independent draws | 7 | 2 | **985** |

Exchangeability requires the units to be permutation-invariant draws from one distribution;
it does not require them to have disjoint content. A fixed, task-independent background
shared by all units is a *constant of the experimental design* — like a fixed system prompt
or a fixed environment — not a leaked evidence source. What would break the guarantee is
placing the same **evidence** in training, calibration and test, and here the evidence (the
preference) is distinct in 990 of 1000 instances.

Two honest caveats, recorded rather than hidden:

1. Difficulty is correlated across instances through the common distractor set: retrieval
   always competes against the same 316 turns. This inflates the *correlation* of `R_mem`
   across units without breaking exchangeability, and it means the calibrated τ is specific
   to this one background. It should be reported as such.
2. Because the background is a single fixed object, PrefEval measures *one* haystack
   condition, not a distribution over haystacks. A CRC guarantee here is conditional on that
   haystack.

## Recommended group key

Recurrences must not cross partitions. Three overlapping relations exist — shared
preference, shared query, shared pair — so the group key is the connected component of
their union:

```
group_id = connected_component(
              instance,
              edges = { shared normalized preference (mcq wording OR explicit wording) }
                    ∪ { shared normalized query }
           )
normalize(s) = collapse_whitespace(strip(lower(s)))
```

The explicit wording is included as an edge source specifically to catch the 30 paraphrase
pairs, so a preference that appears verbatim in one file and paraphrased in another still
lands in one group.

```
n_groups     = 985
size         min 1 / median 1 / max 3
multi-member = 14 groups
largest      ['entertain_games#011', 'entertain_games#016', 'entertain_games#039']
cross-topic  ['education_learning_styles#003', 'education_resources#044'] and 3 more
```

If a run mixes preference forms, the group must additionally absorb all three form variants
of a pair — the key above already does this, since the forms share both preference and
query.

Also fixed at the run level, not the group level, and therefore **not** part of the key:
`--inter_turns` (one prefix chain) and `--task` (zero-shot / remind / cot / rag /
selfcritic). Those are configuration axes; a single value must be frozen for the whole
experiment.

```
n_independent = 985
```

## Formal-split feasibility

| target | requirement | available | verdict |
|---|---|---|---|
| 24 / 24 / 24 | ≥ 72 groups | 985 | **PASS** (13.7× headroom) |
| 30 / 30 / remainder | ≥ 61 groups | 985 | **PASS**, final_test = 925 |
| α = .05 | ≥ 20 non-empty calibration units; CRC needs `n_cal ≥ ⌈1/α−1⌉ = 19` | 985 | **PASS** |
| α = .10 | `n_cal ≥ 9` | 985 | **PASS** |
| α = .20 | `n_cal ≥ 4` | 985 | **PASS** |

985 groups also leaves ample room for the 200 history-level calibration resamples: unlike
the previous two candidates, resampling here draws genuinely distinct subsets rather than
near-duplicate partitions of a handful of units.

Stratification is available and clean: 20 topics with 31–61 groups each, so a deterministic
seed-13 stratified split by topic is feasible at any of the target sizes without splitting
a group.

**No splits were generated.** This is a feasibility statement only.
