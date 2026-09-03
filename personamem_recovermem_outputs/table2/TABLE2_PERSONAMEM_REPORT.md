# ReCoverMem × PersonaMem-v2 (ImplicitPersona) — Table 2, routed performance

128K text MCQ, α = 0.10. Table 1 was neither rerun nor modified; `formal/` is untouched.

## A. Result

| Policy | Task | Rec. | Cost |
|---|---:|---:|---:|
| Always Trust | 0.283 | 0.000 | 13.067 |
| Always Recover | 0.371 | 1.000 | 13.258 |
| Empirical-risk | 0.347 | 0.847 | 13.913 |
| Random score + CRC | 0.347 | 0.948 | 14.015 |
| ReCoverMem + CRC | 0.357 | 0.906 | 13.973 |

```
Always Trust
0.283 / 0.000 / 13.067

Always Recover
0.371 / 1.000 / 13.258

Empirical-risk
0.347 / 0.847 / 13.913

Random score + CRC
0.347 / 0.948 / 14.015

ReCoverMem + CRC
0.357 / 0.906 / 13.973
```

Full precision is retained in `table2_personamem_rows.json`.

## B. Why routing was reconstructed offline rather than re-executed

PersonaMem-v2 has no persistent environment state between routed decisions. Each persona's
Mem0 store is built once from the frozen 128K history and is then **read-only**: the query
phase calls `Mem0.search` and never `add`. All three invariants were re-verified on the
frozen log before reconstruction:

* `memory_unchanged_during_queries` — true on 286/286 decisions, and the
  pre/post store counts are equal on every row;
* the per-question code path (`V2Runner.run_instance`) contains no host write — the only host
  calls in it are `self.host.retrieve, self.recovery.recover`;
* the MEMORY and RECOVERY branches share the same frozen question state —
  `pair_valid` and `state_hash == memory_branch_state_hash == recovery_branch_state_hash`
  hold on every row, with 286 distinct state hashes for
  286 decisions;
* all 286 frozen selected question ids are present, over
  24 final-test personas.

Choosing TRUST or RECOVER for one question therefore cannot change what any later question
sees, so a frozen policy's deployed output *is* the corresponding existing branch outcome.
No answer generation was rerun for Task or Rec.

## C. Routing rule and thresholds (frozen, full precision)

`TRUST iff score ≥ τ`, the Table-1 convention (`recovermem/metrics/risk.py`). Loaded from
`formal/thresholds.json`; nothing was recalibrated.

| Policy | score | τ |
|---|---|---|
| Always Trust | model | −Infinity |
| Always Recover | model | +Infinity |
| Empirical-risk α=.10 | frozen scorer | 0.6706030288410617 |
| Random score + CRC α=.10 | frozen Uniform(0,1), seed 20270113 | 0.9299063098699549 |
| ReCoverMem + marginal CRC α=.10 | frozen scorer | 0.7080483368706152 |

The random scores are the already-persisted sidecar covering all 716 formal decision keys
(`formal/calibration_artifacts/random_scores.json`); none were regenerated.

## D. Sanity check against Table 1

Reconstructed coverage from the actual decision logs, versus the frozen Table-1 values:

| Policy | Table-1 Cov. | reconstructed Cov. | |Δ| | reconstructed Rec. |
|---|---:|---:|---:|---:|
| Empirical-risk | 0.15309343434343434 | 0.15309343434343434 | 0.0e+00 | 0.8469065656565656 |
| Random score + CRC | 0.05208333333333332 | 0.05208333333333332 | 0.0e+00 | 0.9479166666666669 |
| ReCoverMem + CRC | 0.09375 | 0.09375 | 0.0e+00 | 0.90625 |

Every difference is 0 to machine precision, and `Rec + Cov = 1` exactly for all five
policies. FS and any-FS were recomputed from the reconstructed routing as an independent
check on the τ semantics and reproduce the Table-1 values as well.

Paper-facing three-decimal recovery frequencies: Always Trust 0.000, Always Recover 1.000,
Empirical-risk 0.847, Random+CRC 0.948,
ReCoverMem+CRC 0.906 — recomputed from full-precision per-persona
values, not typed in as 1 − Cov.

## E. Task

Native PersonaMem MCQ correctness, no judge and no external API. Per persona, the mean over
that persona's frozen selected questions of the deployed branch's correctness; then the mean
over the 24 personas. Three personas carry fewer than 12 questions (259: 11, 296: 10,
332: 11), so decision-pooling would have mis-weighted them — persona-equal weighting is used
throughout.

## F. Cost

`C_total = C_write + C_ctrl + C_mem + C_rec`, in exact server-reported tokens
(`usage.prompt_tokens + usage.completion_tokens`), normalized per persona against the
**raw-history-only** reference — no Mem0 instantiation, no writes, no retrieval, no
controller score, every selected question answered by the frozen RECOVERY route. That
reference is not a Table-2 row.

Persona-equal normalized decomposition (columns sum to Cost):

| Policy | C_write | C_ctrl | C_mem | C_rec | **Cost** |
|---|---:|---:|---:|---:|---:|
| Always Trust | 12.258 | 0.000 | 0.810 | 0.000 | **13.067** |
| Always Recover | 12.258 | 0.000 | 0.000 | 1.000 | **13.258** |
| Empirical-risk | 12.258 | 0.685 | 0.125 | 0.846 | **13.913** |
| Random score + CRC | 12.258 | 0.766 | 0.044 | 0.948 | **14.015** |
| ReCoverMem + CRC | 12.258 | 0.733 | 0.076 | 0.905 | **13.973** |

`C_write` is incurred **once per persona**, from the single 128K history build, and is
identical across every memory-maintaining policy — the history, the Mem0 construction and
the read-only query phase do not depend on the routing rule. It was not multiplied by the
question count and Mem0 was not rebuilt per policy. Always Recover still maintains the host
and so still pays it; its Cost is therefore **not** forced to 1.000.

For the scored policies the frozen scorer needs a MEMORY-side candidate before it can
decide (`extract_features` consumes the memory branch's completion and mean logprob), so a
memory generation is issued on every question. Where the policy then recovers, that draft is
never deployed and its cost is booked to `C_ctrl`. Random+CRC keeps the identical controller
skeleton — it is not made artificially cheaper by removing the common work.

The raw-history-only reference reuses the replayed RECOVERY calls: `run_instance` recovers
through `TrajectoryRetriever` over the immutable raw history and the answerer sees only
`rec_ev.text`, so a separate raw-only execution would issue byte-identical requests. This is
confirmed empirically — the replayed recovery prompt-token counts equal the formal ones on
286/286 decisions.

## G. Cost fast path

`COST_FAST_PATH = PARTIAL`

| quantity | in the formal log? |
|---|---|
| MEMORY branch prompt tokens | yes — server-reported, persisted |
| RECOVERY branch prompt tokens | yes — server-reported, persisted |
| MEMORY branch completion tokens | **no** — read from `usage` but dropped by `V2Runner.run_instance` |
| RECOVERY branch completion tokens | **no** — same |
| `C_write` server-reported usage | **no** — `Mem0Adapter.write` recorded only a local tokenizer count of the `add()` input, and even that was never written to a row |

Two minimal replays were run, and nothing else (in particular, **not** five independent
policy executions):

1. **`C_write`** — one Mem0 rebuild per final-test persona into a scratch store root, with
   every `chat.completions.create` instrumented. 24 rebuilds,
   757 LLM calls, no question answered.
2. **branch usage** — the frozen final-test Mem0 store was reused (through a byte copy, so
   `formal/` was never opened for writing) and the frozen recovery retrieval recomputed, then
   each branch answer call re-issued once to read `usage`.
   572 LLM calls.

Total new LLM calls used solely for Table 2: **1329**.
Total Mem0 rebuilds used solely for Table 2: **24**.

Attribution is request-local — every count comes from that request's own `usage` object, so
no global endpoint counter is consulted and endpoint exclusivity was not required.

## H. Replay equivalence

| check | result |
|---|---|
| frozen state hash reproduced | 286/286 |
| frozen option order reproduced | 286/286 |
| Mem0 store size matches the frozen store | 286/286 |
| memory evidence tokens match | 286/286 |
| recovery evidence tokens match | 286/286 |
| MEMORY prompt tokens match the formal server-reported value | 286/286 |
| RECOVERY prompt tokens match the formal server-reported value | 286/286 |
| LLM calls during memory retrieval | 0 |
| replay completion byte-identical to formal (MEMORY / RECOVERY) | 38 / 21 of 286 |
| replay parsed choice equals formal (MEMORY / RECOVERY) | 224 / 225 of 286 |

Both prompts are byte-identical to the formal run's, which is what the prompt-token equality
demonstrates. The **completions** are not: the local vLLM server is not bitwise
deterministic under continuous batching even at temperature 0. Per the frozen protocol the
replay is used **only** to measure cost; every Task number in this table is the original
formal Table-1 correctness. The divergence is reported here diagnostically and nothing was
repaired, refitted or overwritten. Details in `cost_replay_report.md`.

## I. Diagnostics

```
final-test personas                 24
routed decisions                    286
Task computation, persona-equal     YES
Rec computation, persona-equal      YES
Cost computation, persona-equal
  normalized against raw-history    YES
COST_FAST_PATH                      PARTIAL
new LLM calls solely for Table 2    1329  (757 Mem0 build + 572 branch)
Mem0 rebuilds solely for Table 2    24
parser failures inherited           0  (of 572 final-test branch calls)
provenance violations               0
external API attempts               0
LLM-judge calls                     0
multimodal calls                    0
```

Hashes, all re-verified in this run:

```
parent split         25decf6c9afa2c3ddc8dc009a674e9c70def883146594b8d879593f7a6417e1d
Amendment A1         3b1565169561bf2561a4ac7ec6a8074d32043fd473f316f4505b8cbcc17c12d4
question selection   267554892adf0cfc3931190904b8d41affcde4628893c2aa819c675bf9ac288c
scorer               f3b9519da36838aa63ada40a1ab2bb860d5b3aa4d4947e959157b845633531c8
thresholds           6fb3081e36f0d065b2aee0455f4bdf4e70d943aba2fe39b5aec624578ffd3914
random scores        830aa45647ba09ba83f7bad03008f8585e222999a33bdc342e8b186d7ff3a040
final_test.jsonl     803e73c6d2273b423ff70010a7123cba308b34c048e42df6f6a07fda285d5908
```

The scorer, random-score and amendment hashes equal the values recorded inside
`thresholds.json` at freeze time: {"scorer": true, "random_scores": true, "amendment": true}.

## J. What was not touched

The scorer was not refit, nothing was recalibrated, α was not varied (Table 2 uses α = .10
only), the question selection, final-test personas, option shuffle, parser, scorer, feature
schema, CRC implementation and budgets (B_mem = B_rec = 2048, B_out = 1024) are the frozen
ones, the single inherited parser failure was not replaced, Mem0 extraction failures were not
repaired, and no final-test answer was altered. `formal/` was not written to.
