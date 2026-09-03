# PrefEval smoke report (Phase-1 §7)

3 independent units, IDs frozen **before** inference in
`results/prefeval/configs/PRIMARY_SETTING.json` (seed-13 group permutation, disjoint from
the budget-audit and pilot slices). `B_mem = B_rec = 2048`, frozen by the two-stage rule in
`BUDGET_DECISION.md` before this run.

Machine-readable: `smoke_summary.json`.

Frozen unit ids: `travel_hotel#044`, `lifestyle_dietary#004`, `travel_activities#035`.

## Infrastructure verification — all PASS

| check | result |
|---|---|
| `pair_valid` | **100 %** (3/3) |
| common `x_i` identical across branches | 3/3 — `state_hash == memory_branch_hash == recovery_branch_hash` |
| fresh Mem0 per instance | yes — per-instance store dir removed then `reset()`, which asserts the store starts at 0 memories |
| fresh raw-history store | yes — `H_i` is rebuilt per instance from the released data; nothing is carried over |
| no cross-instance leakage | 3 distinct `x_i` hashes; 3 distinct store directories; `assert_empty()` passed on each |
| `B_mem` respected | yes — 1,266 / 1,393 / 1,772 ≤ 2,048 |
| `B_rec` respected | yes — 2,045 / 2,046 / 2,047 ≤ 2,048 |
| queries/answers never memorized | yes — Mem0 memory count unchanged across the query phase on all 3 (asserted, 0 errors) |
| exact tokenizer accounting | yes — every count from the Llama-3.1-8B-Instruct snapshot tokenizer, `exact=True` |
| external API calls | **0** — answerer and Mem0 LLM both pinned to `127.0.0.1:8123`; `Mem0Adapter` refuses a non-local endpoint |
| LLM judge calls | **0** |
| programmatic parser works | yes — upstream `utils.utils_mcq.extract_choice` imported and applied verbatim |

## Per-instance measurements

| unit | history msgs | history tokens | write chunks | build | Mem0 memories | `E_mem` | packed | `E_rec` | packed | `x_i` tok |
|---|---|---|---|---|---|---|---|---|---|---|
| `travel_hotel#044` | 604 | 104,130 | 27 | 132.5 s | 111 | 1,772 | 50/50 | 2,047 | 10 | 224 |
| `lifestyle_dietary#004` | 604 | 104,112 | 27 | 131.0 s | 128 | 1,393 | 50/50 | 2,046 | 11 | 211 |
| `travel_activities#035` | 604 | 104,122 | 27 | 132.0 s | 128 | 1,266 | 50/50 | 2,045 | 10 | 222 |

Mean memory construction: **131.8 s**. Retrieval ~0.01 s; answer latency 0.19–0.27 s per
route. Reader prompt: 1,602–2,111 tokens (memory) / 2,371–2,386 tokens (recovery), both far
inside the 32,768 window.

Note the asymmetry in *packing*: Mem0's 50 candidates are short facts and all 50 fit inside
2,048 tokens, while recovery packs only 10–11 whole original messages before saturating the
same budget. Both routes receive the same token budget; they simply spend it on units of
different granularity. That is the intended comparison.

## Outcomes

| unit | gold | memory choice | recovery choice | `R_mem` | `R_rec` |
|---|---|---|---|---|---|
| `travel_hotel#044` | C | **none** (parse failure) | C | 0 | 1 |
| `lifestyle_dietary#004` | A | D | D | 0 | 0 |
| `travel_activities#035` | C | C | C | 1 | 1 |

```
00 / 01 / 10 / 11  =  1 / 1 / 0 / 1
memory-route accuracy    0.333
recovery-route accuracy  0.667
longest-option heuristic 0.333   (on these 3 instances)
```

Baselines that must accompany these numbers: random choice **0.25**, longest-option
heuristic **0.446** (established structurally in Phase 0, before any method outcome). At
n = 3 no comparison is meaningful; these are reported for completeness only.

### The one parse failure

`travel_hotel#044`, memory route, emitted the literal completion `None</choice>`. With the
prefill re-attached the parser sees `<choice>None</choice>`; the regex `[ABCD]` finds no
match inside `None`, so `extract_choice` returns `None` and the instance scores 0. This is
the released metric behaving exactly as specified — malformed answers are deterministically
incorrect — not a harness defect. It is recorded, and the parser was **not** loosened.

## Cost projection

| quantity | measured |
|---|---|
| memory construction | 131.8 s / unit |
| query evaluation (both routes) | ~0.5 s / unit |
| total | ~2.2 min / unit |

Projected for the intended 24/24/24 formal protocol (72 units): **≈ 2.7 hours**, essentially
all of it Mem0 fact extraction (27 sequential `add()` calls per unit against one local 8B
server). Well inside an 8-hour budget.

## Effect on frozen settings

**None.** No smoke outcome changed the preference form, `--inter_turns`, `B_mem`, `B_rec`,
γ, the recovery operator, the option parser, or instance selection. Infrastructure is clean,
so the run continued automatically to the pilot.
