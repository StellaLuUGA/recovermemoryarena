# PrefEval memory-sufficiency and raw-recovery compatibility (§7, §10)

Audit only. Nothing implemented, no Mem0 constructed, no model called.

## Memory-sufficiency mapping

Each classification instance decomposes naturally into the objects ReCoverMem needs:

| ReCoverMem object | PrefEval realization |
|---|---|
| raw history `H_i` | the constructed conversation: **[preference expression]** ++ **[shared filler turns `fmsgs[:2N]`]** — a list of `{role, content}` messages |
| host memory `M(H_i)` | Mem0 store built by streaming those messages, one fresh store per instance |
| current query `x_i` | `question` + the 4 shuffled options, rendered identically for both routes |
| native correctness | `1[extract_choice(response) == correct_letter]` (programmatic, `CORRECTNESS_AUDIT.md`) |

```
R_mem,i = 1[ answer from Mem0 evidence (≤ B_mem) is classification-correct ]
R_rec,i = 1[ answer from bounded raw-history evidence (≤ B_rec) is classification-correct ]
```

The preference expression differs by form:

- **explicit** — 1 user turn (the preference) + 1 assistant acknowledgement. The
  acknowledgement is **LLM-generated at construction time** (`pref_generation`), not stored
  in the data. See "the one wrinkle" below.
- **implicit, choice-based** — 4 messages already in the data
  (`query` / `assistant_options` / `user_selection` / `assistant_acknowledgment`), 90–235 tokens.
- **implicit, persona-driven** — 6–14 messages already in the data, 399–3,311 tokens.

## Condition checks (§7)

| condition | verdict | evidence |
|---|---|---|
| target preference appears only in the history, not leaked in the current query | **PASS** (with a caveat) | 62.9% of instances have zero preference↔query content-word overlap; median 0, p90 0.167, max 0.429. The residual overlap is topical (both mention "restaurants"), not the preference constraint itself — the benchmark is built so a generic answer violates the preference. |
| correct option cannot be derived from benchmark-private metadata | **PASS, conditional on enforcement** | The gold is the positional convention `classification_task_options[0]`. It is derivable *only* from pre-shuffle order, so the shuffle must be applied before anything reaches the host, the scorer or the reader. This is a code-discipline requirement, and it is exactly the kind of thing `extract_features`' `FORBIDDEN_INPUTS` guard is for. |
| query + options can be shown identically to MEMORY and RECOVERY | **PASS** | `x_i` is a plain string built from `question` + `get_mcq_question_format(shuffled_options)`. One shuffle per instance, computed once, reused by both routes; the common-state hash makes the equality auditable. |
| raw historical evidence available for bounded recovery | **PASS** | The full message list is in the checkout; nothing is generated at query time. |
| no gold label needed to construct either evidence route | **PASS** | Both routes are functions of `(x_i, H_i)` only. The shuffle needs `options`, not which one is correct — `shuffle_options` returns the correct index as a by-product that goes to the scorer's *label*, never to evidence construction. |
| no surface cue substitutes for memory | **PARTIAL** | Choosing the longest option scores 44.6% with no memory at all (chance 25%). Not a semantic leak, but it raises the no-memory floor and must be reported alongside any accuracy number. |

## Bounded raw-history recovery (§10)

**PASS.** The history is a list of atomic, independently addressable conversation messages:

```
H_i = [ m_0, m_1, …, m_{k-1} ],   m_j = {"role": "user"|"assistant", "content": str}
```

- `m_0` (explicit) or `m_0…m_3` / `m_0…m_{2T-1}` (implicit) carry the preference;
- `m_j` for `j ≥ k_pref` are the shared filler turns, in a fixed order.

Every unit is an original benchmark message. ReCoverMem's existing
`recovery/trajectory_retriever.py` consumes exactly this shape — it calls `render_turn` on
`{role, content}` dicts, scores them with IDF-weighted lexical overlap (deterministic, no
LLM, no write path back to the host), and packs to the budget with
`pack_indices_to_budget`. **No new recovery backend is needed**; the interface already
matches.

Recovery therefore reads **original history turns**, not a second query over the compressed
Mem0 store — the property the brief requires.

### Can `B_rec = B_mem` be enforced naturally? **Yes.**

Message-level granularity makes the bound clean rather than lossy:

| unit | tokens |
|---|---|
| one preference message | 4 / 14 / 38 (min / median / max) |
| one filler message | 108,084 / 632 ≈ 171 mean |
| implicit-choice conversation, whole | 90 / 133 / 235 |
| implicit-persona conversation, whole | 399 / 809 / 3,311 |

A budget of 1,024 or 2,048 tokens holds many whole messages, so packing never has to
truncate mid-message and the recovery operator's output is always a set of intact original
turns. Contrast MAB-AR, where a single retrieval unit could exceed the entire budget.

The task is also **genuinely hard for lexical recovery in the right way**: the correct
option lexically resembles the preference *less* than the distractors do (17.8% highest-
overlap rate vs 25% chance), so a lexical recovery operator can surface the preference turn
but cannot thereby pick the answer — the reader still has to reason. That keeps `R_rec`
informative rather than a retrieval tautology.

## The one wrinkle: `pref_generation` in the explicit form

`benchmark_classification.py` builds the explicit history as

```python
user_pref_msg  = create_user_pref_message(preference, model_type, system_prompt)
pref_generation = generate_message(client, model_id, ...)      # an LLM call
messages = [ {"user": preference}, {"assistant": pref_generation}, *filler, {"user": question+options} ]
```

so the assistant's acknowledgement of the preference is generated by the *answering model*
at construction time and is not part of the released data. Three consequences:

1. It is one extra local generation per instance — cheap (≈300 tokens max by `config.yaml`),
   but it must be produced **once per instance** and reused byte-identically by both routes,
   or `H_i` differs between MEMORY and RECOVERY and the pairing is invalid.
2. It is model-dependent, so the constructed history is not reproducible across backbones.
   That is upstream's design, not ours; it must be pinned and hashed in the run manifest.
3. The **implicit forms have no such dependency** — their conversations ship in the data.
   If a fully data-determined `H_i` is wanted, the implicit choice-based or persona-driven
   form is the cleaner choice, and it is also the more realistic long-memory setting
   (the preference is never stated outright).

## Verdict

| axis | verdict |
|---|---|
| memory-sufficiency semantics | **PASS** (one PARTIAL: the 44.6% length-cue floor) |
| bounded raw-history recovery | **PASS** — existing `TrajectoryRetriever` fits with no new code |
| `B_rec = B_mem` enforceable | **PASS** — message-granular, no mid-unit truncation |
