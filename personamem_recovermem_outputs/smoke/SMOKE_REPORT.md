# PersonaMem-v2 128K text MCQ — infrastructure / cost smoke

3 personas, deterministically the first three of the frozen `predictor_train` order
(**59, 70, 86**), 23 eligible questions each = **69 controlled decisions**, 138 paired
branch calls. `B_mem = B_rec = 2048` (frozen). `PYTHONHASHSEED=13`. `final_test` untouched.

```
SMOKE = PASS
```

## Gate

| check | result |
|---|---|
| `pair_valid` on every decision | **69 / 69** |
| MEMORY vs RECOVERY `x_t` hash mismatches | **0** |
| distinct `x_t` hashes == decisions | 69 == 69 |
| cross-persona contamination | **none** |
| memory unchanged across the query phase | 262→262, 234→234, 104→104 |
| `B_mem` respected | 1,398 / 1,654 / 1,885 (min/median/max) ≤ 2,048 |
| `B_rec` respected | 2,038 / 2,046 / 2,048 ≤ 2,048 |
| **parser failures** | **0 / 138** |
| external API attempts | 0 |
| LLM-judge attempts | 0 |
| multimodal calls | 0 |
| deterministic option shuffle | yes, 69 distinct option-order hashes |
| future-history leakage | none — the query is appended after the persona's complete released history |

## The defect this smoke caught, and the fix

The **first** run of this smoke had `parser_failures = 116 / 138`. `B_out = 256` truncated
the released MCQ prompt's reasoning before the model ever emitted `Final Answer: [Letter]`,
so the released `extract_final_answer` returned nothing. The nine apparent successes were
false positives: the fallback pattern `\b([A-Z])\.\s*$` was matching a truncated option label
(`D.`) at the cut point.

A separate probe on 10 held-out `predictor_train` queries with `max_tokens = 1024` parsed
**10 / 10** and measured the real requirement at **270 / 350 / 718** tokens (min / median /
max) to reach `Final Answer:`. `B_out` was corrected to **1024** (1.4× the observed worst
case) and this run reproduced with **0** parser failures.

The frozen budget survives the correction — recomputed, not asserted:

| | `B_out = 256` | `B_out = 1024` |
|---|---:|---:|
| `Q₀.₀₅(B_avail)` | 31,499 | 30,731 |
| `B_cap` | 16,384 | **16,384** |
| `B_host` (independent of `B_out`) | 2,048 | **2,048** |
| **`B_mem = B_rec`** | 2,048 | **2,048** |

My first run's script also printed `PASS` while 116 parses were failing — the gate expression
omitted `parser_failures`. The gate now includes it plus the API / judge / multimodal /
hash-uniqueness checks, and is recorded per-check in `smoke_summary.json`.

## Measurements

| persona | messages | history tokens | write chunks | build | Mem0 memories | queries |
|---|---:|---:|---:|---:|---:|---:|
| 59 | 1,049 | 129,650 | 34 | 307 s | 262 | 23 |
| 70 | 1,101 | 129,188 | 33 | 1,644 s | 234 | 23 |
| 86 | 807 | 91,082 | 24 | 453 s | 104 | 23 |

Evidence: Mem0 packs 50 candidates into 1,398–1,885 tokens; recovery packs 5–17 whole
original messages and saturates the same 2,048-token budget. Peak RSS 1,336 MB. Total
wall clock 53.0 min.

**Build time is highly variable and that is the main cost risk.** The same three personas
were built twice, giving `305 / 312 / 234` s on the first run and `307 / 1644 / 453` s on the
second — persona 70 alone swung 5×. Median across all six observations is **309 s**, mean
**543 s**. Query cost is stable at **4.68 s per branch call**.

## Debug outcomes — explicitly NOT a gate

Logged for debugging only and **not** used to pass or fail anything, per the protocol:

```
00 / 01 / 10 / 11 = 35 / 13 / 6 / 15
memory-route   0.304
recovery-route 0.406
```

Both sit above the 0.25 four-option chance line, which is a sanity signal that the pipeline
is now measuring answering rather than truncation. At n = 69 on three personas it means
nothing more than that.

## Runtime projection for the amended formal run

Amendment A1: 16 / 20 / 24 = **60 personas**, 12 questions each → **716 controlled decisions**
(three personas have < 12 eligible), **1,432 paired branch calls**.

| component | estimate |
|---|---|
| memory build, 60 personas | **5.2 h** at the 309 s median … **9.0 h** at the 543 s mean |
| paired QA, 1,432 calls × 4.68 s | **1.9 h** |
| **total** | **≈ 7 – 11 h** |

The spread is entirely build-time variance, not uncertainty about the query cost. My earlier
6.5–7.5 h figure used only the first run's builds and was too optimistic; this range reflects
both runs.
