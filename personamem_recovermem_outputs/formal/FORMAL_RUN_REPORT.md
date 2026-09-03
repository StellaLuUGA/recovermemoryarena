# ReCoverMem × PersonaMem-v2 (ImplicitPersona) — formal Table 1

128K text MCQ. Completed 2026-08-29T02:02:42Z. Every scientific choice was frozen before
collection; nothing below was tuned on an observed outcome.

## A. Frozen setting

| | |
|---|---|
| dataset | PersonaMem-v2 / ImplicitPersona, **text-only, 128K, MCQ** |
| row filter | `distance_from_related_snippet_to_query_128k > 0` — the evidence turn is strictly earlier in the history than the query |
| exchangeability unit | **persona_id** |
| split (Amendment A1) | 16 / 20 / 24 personas, 12 selected questions each |
| budgets | `B_mem = B_rec = 2048`, `B_out = 1024` |
| answerer | `llama-3.1-8b-instruct-local`, temperature 0, identical prompt/parser/option order on both routes |
| metric | released MCQ: `option_mapping[extract_final_answer(resp)] == correct_answer`. **No LLM judge, no external API.** |
| γ | 0.5 (binary correctness ⇒ `R = 1[correct]`) |
| option shuffle | released implementation, `PYTHONHASHSEED=13`, verified reproducible across fresh processes |

The specified filter named `distance_to_ref_in_blocks`; that column exists only in
PersonaMem-**v1**. The v2 equivalent is the token distance above, and the 32k and 128k
distance columns agree on the `>0` predicate for all 5,000 released rows.

## B. Ordering guarantee

`thresholds.json` was written **and hashed while `final_test.jsonl` did not exist**
(`final_test_existed_at_freeze: false`, asserted in code). `collect("final_test")` refuses to
run without a frozen threshold file, and `collect()` refuses to overwrite an existing split
log. Collection is resumable per persona: rows are appended and fsynced as one unit, then the
persona id is written atomically to a `.progress.json`.

## C. Hashes

```
parent split         25decf6c9afa2c3ddc8dc009a674e9c70def883146594b8d879593f7a6417e1d
Amendment A1         3b1565169561bf2561a4ac7ec6a8074d32043fd473f316f4505b8cbcc17c12d4
question selection   267554892adf0cfc3931190904b8d41affcde4628893c2aa819c675bf9ac288c
scorer               f3b9519da36838aa63ada40a1ab2bb860d5b3aa4d4947e959157b845633531c8
normalizer           7a6500a78bb4702fe5ae295347bc99caca2804535811061012e7c48972d98766
thresholds           6fb3081e36f0d065b2aee0455f4bdf4e70d943aba2fe39b5aec624578ffd3914
random scores        830aa45647ba09ba83f7bad03008f8585e222999a33bdc342e8b186d7ff3a040
predictor_train.jsonl 86eeb8d5dffccfaec251b391ec0b8ce9a88a511f5d414c2baeff44acab6880e8
calibration.jsonl    3c52fd211308226bfad323868fe0451cbcb459e713ee9431d4986d510c04c07b
final_test.jsonl     803e73c6d2273b423ff70010a7123cba308b34c048e42df6f6a07fda285d5908
benchmark.csv        95f2a8a324aab7baf2af937feae12731369e2abf7cad5ab3e170594cb25a3e52
dataset revision     0622e56d1cc6f1bc990a5100a6ec4022a60e66a6
v2 code commit       dd52429f83ced4394be46c3849186a423942b2a5
Mem0 commit          39bc02330563764e7d4465f1ecff5f002d94da1a
tokenizer / model    meta-llama/Llama-3.1-8B-Instruct snapshot 0e9e39f249a16976918f6564b8830bc894c89659
```

## D. Collected data

| split | personas | decisions | `R_mem` +/− | `R_rec` +/− | 00/01/10/11 | mem acc | rec acc |
|---|---|---|---|---|---|---|---|
| predictor_train | 16 | 192 | 55 / 137 | 75 / 117 | 97/40/20/35 | 0.286 | 0.391 |
| calibration | 20 | 238 | 72 / 166 | 69 / 169 | 130/36/39/33 | 0.303 | 0.290 |
| **final_test** | **24** | **286** | **81 / 205** | 106 / 180 | **146/59/34/47** | **0.283** | **0.371** |

Final-test per persona: history 93,252–130,856 tokens (median 127,510);
Mem0 store 110–243 memories; `E_mem` 948–2044 tokens; `E_rec` 2036–2048 tokens.
238 and 286 rather than 240 and 288 because three personas have fewer than 12 eligible
questions (296: 10, 259: 11, 332: 11), recorded in the frozen amendment.

## E. Hard invariants — all hold on all 716 decisions

`pair_valid` 716/716 · byte-identical `x_t` across branches · distinct state hash per decision
in every split · `B_mem`/`B_rec` never exceeded · **memory count unchanged across every query
phase** (the query phase calls only `Mem0.search`, never `add`) · **0 external API calls** ·
**0 LLM-judge calls** · **0 multimodal calls** · no gold leakage.

Parser failures: **1** of 1,432 branch calls (a single calibration-split call, scored
incorrect per released semantics; the parser was not loosened). Mem0 fact-extraction
malformed-JSON failures: **1280** — logged per persona, **not repaired**.

## F. Scorer

L2 logistic regression, `class_weight='balanced'`, C = 1.0, `max_iter` = 500, seed 13, trained
on the 16 predictor-train personas only, then frozen (save/load round-trip identical).

| split | π̂ (persona-equal) | AUROC | AUPRC |
|---|---|---|---|
| predictor_train (in-sample) | 0.2865 | 0.6483 | 0.4597 |
| calibration | 0.3025 | 0.5111 | 0.3183 |
| **final_test** | **0.2828** | **0.5657** | **0.3206** |

Three of the ten host-agnostic features are constant on this workload and carry zero weight
(`action_arg_support`, `support_count_norm`, `step_progress`). Unlike PrefEval,
`conflict_density_inv` is **not** constant here — the 128K histories do contain negation
patterns in the packed evidence — so seven features are active.

## G. Table 1 — canonical frozen final-test point estimates

Persona-equal weighting: losses are averaged over a persona's selected decisions first, then
equally across the 24 personas. FS and Cov. are frozen final-test point estimates; Exc. is the
200-resample persona-level exceedance frequency.

| Method | α | FS | Cov. | Exc. | τ |
|---|---|---|---|---|---|
| Always Trust | — | **0.717** | **1.000** | — | -Infinity |
| Always Recover | — | **0.000** | **0.000** | — | Infinity |
| Fixed-F1 | — | **0.685** | **0.961** | — | 0.2901 |
| Empirical-risk | 0.05 | **0.059** | **0.090** | 0.540 | 0.7166 |
|  | 0.10 | **0.104** | **0.153** | 0.535 | 0.6706 |
|  | 0.20 | **0.164** | **0.234** | 0.445 | 0.5995 |
| Random score + CRC | 0.05 | **0.003** | **0.003** | 0.000 | 0.9969 |
|  | 0.10 | **0.049** | **0.052** | 0.035 | 0.9299 |
|  | 0.20 | **0.192** | **0.237** | 0.145 | 0.7666 |
| ReCoverMem + marginal CRC | 0.05 | **0.000** | **0.000** | 0.000 | Infinity |
|  | 0.10 | **0.062** | **0.094** | 0.080 | 0.7080 |
|  | 0.20 | **0.143** | **0.209** | 0.255 | 0.6151 |

Sanity: Always Trust FS = 0.7172 = 1 − π̂ = 0.7172 ✓

`n_cal = 20` ⇒ marginal-CRC floor `1/(n+1) = 0.0476`. At α = .05 the criterion
`(20/21)·L̂ + 0.0476 ≤ 0.05` needs `L̂ ≤ 0.0025`, which only τ = +∞ attains — so **ReCoverMem +
CRC at α = .05 degenerates to Always Recover**. This was predicted before collection and no
rule was modified to raise coverage.

## H. Exceedance protocol

The frozen Table-1 convention, resampled at the **persona** level: pool = calibration +
final_test (44 personas, never the predictor's training personas), 200 repetitions,
`n_cal = 20` drawn disjointly per repetition, `base_seed = 13`, `mode = "split"`. The frozen
Uniform(0,1) random scores were generated once over all 716 formal decision keys and reused
across repetitions rather than redrawn.

## I. Runtime

| stage | hours |
|---|---|
| predictor_train collection | 1.77 |
| calibration collection | 2.17 |
| final_test collection | 2.67 |
| **total collection** | **6.61** |

Memory construction 4.75 h of that (285 min over 60 personas, ~5 min/persona),
1,432 answerer calls.

## J. Appendix — repeated-calibration stability (mean ± SD, 200 persona-level resamples)

Appendix only; must not be substituted for the main-table FS/Cov point estimates.

| Rule | α | FS mean ± SD | Cov mean ± SD | Exc. | frac. τ = +∞ |
|---|---|---|---|---|---|
| Empirical-risk | 0.05 | 0.056 ± 0.025 | 0.081 ± 0.032 | 0.540 | 0.000 |
| Random score + CRC | 0.05 | 0.001 ± 0.003 | 0.001 ± 0.003 | 0.000 | 0.740 |
| ReCoverMem + marginal CRC | 0.05 | 0.000 ± 0.004 | 0.001 ± 0.005 | 0.000 | 0.985 |
| Empirical-risk | 0.10 | 0.107 ± 0.039 | 0.152 ± 0.056 | 0.535 | 0.000 |
| Random score + CRC | 0.10 | 0.055 ± 0.018 | 0.068 ± 0.021 | 0.035 | 0.000 |
| ReCoverMem + marginal CRC | 0.10 | 0.061 ± 0.027 | 0.087 ± 0.034 | 0.080 | 0.000 |
| Empirical-risk | 0.20 | 0.203 ± 0.053 | 0.294 ± 0.075 | 0.445 | 0.000 |
| Random score + CRC | 0.20 | 0.160 ± 0.032 | 0.210 ± 0.039 | 0.145 | 0.000 |
| ReCoverMem + marginal CRC | 0.20 | 0.165 ± 0.048 | 0.239 ± 0.064 | 0.255 | 0.000 |

## K. Scientific caveats

1. **The scorer barely generalises.** Final-test AUROC 0.566 against 0.648 in-sample, and
   calibration AUROC 0.511 — essentially chance on the split that sets the threshold.
   FS control still holds because it comes from CRC, not from discrimination; what suffers is
   coverage. Read the Cov. column with that in mind.
2. **α = .05 is degenerate** for ReCoverMem + CRC at `n_cal = 20` (§G), and the appendix shows
   it selects τ = +∞ in 98.5% of resamples.
3. **Empirical-risk has no finite-sample correction and it shows**: Exc. 0.54 / 0.535 / 0.445
   across the three α. The CRC rows are 0.000 / 0.080 / 0.255 — the correction is doing exactly
   what it exists for.
4. **n = 24 test personas.** Every point estimate has wide uncertainty; the Exc. column and the
   appendix SDs are the honest description of it.
5. **Labels depend on a local 8B answerer.** `R_mem` and `R_rec` are properties of this
   backbone, not benchmark-intrinsic.
6. **Mem0 fact extraction is lossy here** — 1280 malformed-JSON extraction failures across 60
   personas, whose facts Mem0 silently dropped. Logged, not repaired.
7. **`B_out` 256 → 1024** was an infrastructure correction made pre-outcome and authorised;
   the budget audit was recomputed and `B_mem = B_rec = 2048` is unchanged under it.

## L. Artifacts

```
personamem_recovermem_outputs/formal/
  FORMAL_RUN_REPORT.md   formal_summary.json    TABLE1_LATEX.txt
  predictor_train.jsonl  calibration.jsonl      final_test.jsonl
  scorer.json            scorer_metrics.json    scorer_metrics_all_splits.json
  thresholds.json (+.sha256)  table1_rows.json  resampling_summary.json
  calibration_artifacts/random_scores.json      memory/<split>/persona<id>/
  *.progress.json  (per-persona resume state)
```
