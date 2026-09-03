# PrefEval primary setting — FROZEN

Frozen before any ReCoverMem route outcome was observed. Machine-readable and
authoritative: `PRIMARY_SETTING.json` (sha256 in `PRIMARY_SETTING.sha256`).

PrefEval repo `50795054`, source tree **unmodified**.

## Preference form: implicit, **choice-based**

```
exact form name  : implicit preference, choice-based conversation
CLI equivalent   : --pref_form=implicit --pref_type=choice
source file      : benchmark_dataset/implicit_preference/choice-based/<topic>.json
options + gold   : benchmark_dataset/mcq_options/<topic>.json   (positional index)
```

**Selection rule** — "the first canonical implicit form according to the repository's
existing dataset/config ordering". All three orderings the repo exposes agree, and all
three are metadata/configuration only; no model outcome was consulted:

1. sorted directory listing of `benchmark_dataset/implicit_preference/` →
   `choice-based` < `persona-driven`;
2. argparse default in `classification_task/benchmark_classification.py` →
   `--pref_type` `default="choice"`;
3. execution order in `example_scripts/run_mcq_task.sh` → `--pref_type=choice` runs before
   `--pref_type=persona`.

The **explicit** form is excluded from the primary experiment because its history
construction requires an LLM-generated `pref_generation` acknowledgement turn, which would
make `H_i` model-dependent.

The **persona-driven** form is reserved for an appendix robustness check only. The three
forms are re-expressions of one preference-query pair and are **never** counted as
independent examples.

## History length: `--inter_turns 300`

```
H_i = implicit choice-based conversation (4 messages) ++ filler[:600]
    = 604 messages
    ≈ 104,122 Llama tokens (median, exact tokenizer)
```

| setting | history tokens | × B_ctx (32,768) |
|---|---|---|
| 100 inter-turns | 34,849 | 1.06 — rejected, only marginally over the limit |
| **300 inter-turns** | **101,588–104,224** | **3.10–3.18** — chosen |

At 3.1× the answer context the raw history provably cannot be passed to the answerer, so
memory is necessary rather than optional.

The filler comes from `benchmark_dataset/filtered_inter_turns.json`, a single global pool
of 24 conversations / 632 messages. Upstream's `extract_multi_turn_conversation` takes
`fmsgs[:2N]` in file order with no sampling, so every instance sees the identical prefix and
different `--inter_turns` values are strict prefixes of one another. Reproduced exactly.

## Statistical unit

```
unit          : Phase-0 group-key component
n_independent : 985
group key     : connected components over
                {shared normalized preference (mcq OR explicit wording)}
              ∪ {shared normalized query}
```

The common distractor pool is **fixed background shared across instances**, not an
independently sampled history, and is never counted as a unit. Group-linked units never
cross a partition boundary.

## Correctness

```
R = 1[ extract_choice("<choice>" + completion) == gold_letter ]
```

Released programmatic metric only — `utils.utils_mcq.extract_choice` (BeautifulSoup
`<choice>` tag + regex `[ABCD]`), imported from the PrefEval checkout and applied verbatim.
Parse failures return `None` and are **deterministically incorrect**. No LLM judge. The
generation-task evaluation is not used.

Gold is `classification_task_options[0]` by positional convention (PrefEval ships no gold
field); it is shuffled away by a per-instance deterministic permutation before anything
reaches the memory host, the scorer or the reader. The shuffle is derived from the instance
id rather than a global seed because upstream's `random.seed(41)` is unreachable —
`benchmark_classification.py` never imports `random` — so no released permutation exists to
reproduce.

## Baselines that must accompany every reported accuracy

```
random choice              0.25
longest-option heuristic   0.446      <- established structurally in Phase 0,
                                         before any method outcome
```

0.25 is **not** the only meaningful floor.

## Routes

Both routes use `llama-3.1-8b-instruct-local` at `http://127.0.0.1:8123/v1`,
temperature 0, the same system prompt, the same `<choice>` assistant prefill (via vLLM
`continue_final_message`), and the same 8-token output budget. Only the evidence source
differs, and the `x_i` hash equality is asserted before a pair is logged.

```
MEMORY   : x_i + Mem0 evidence,                     |E| <= B_mem = 2048
RECOVERY : identical x_i + bounded evidence from
           the ORIGINAL message-level history,      |E| <= B_rec = 2048
```

Never exposed to either route or to the scorer: the pre-shuffle option order, `gold_letter`,
the `preference` field (the implicit form states it nowhere), `explanation`.

γ = 0.5. Correctness is binary {0,1}, so this gives `R = 1[correct]`; γ is retained only for
cross-setting consistency.

## Budget

`B_mem = B_rec = 2048`, frozen by the two-stage scorer-independent rule — see
`../preflight/BUDGET_DECISION.md`.

## Frozen partitions (seed 13, group-disjoint)

| slice | size | status |
|---|---|---|
| `budget_audit` | 3 | used |
| `smoke` | 3 | used |
| `pilot` | 8 | used |
| `reserved_predictor_train` | 24 | **untouched** |
| `reserved_calibration` | 24 | **untouched** |
| `reserved_final_test` | 24 | **untouched** |

All 86 selected ids are distinct; literal ids are in `PRIMARY_SETTING.json`.
