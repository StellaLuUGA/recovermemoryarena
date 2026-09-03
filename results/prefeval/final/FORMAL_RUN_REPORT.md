# PrefEval formal ReCoverMem run — Table 1

Completed 2026-08-28T15:53:58Z. Every scientific choice was frozen before collection;
nothing below was tuned on an observed outcome.

## A. Frozen setting

| | |
|---|---|
| preference form | implicit choice-based |
| history | `--inter_turns 300` → 604 messages, ~104k Llama tokens (3.2× the answer context) |
| budgets | `B_mem = B_rec = 2048` |
| answerer | `llama-3.1-8b-instruct-local`, temperature 0, identical prompt/parser/ordering on both routes |
| metric | released programmatic MCQ metric only; **no LLM judge**, no external API |
| γ | 0.5 (binary correctness ⇒ `R = 1[correct]`) |
| split | 24 / 24 / 24 group-disjoint units, seed 13, reserved in Phase 1 |

## B. Ordering guarantee

`thresholds.json` was written **and hashed while `final_test.jsonl` did not exist** — asserted
in code, not by discipline. `collect()` refuses to overwrite an existing split log, and the
final-test collector refuses to start without a frozen threshold file.

## C. Hashes

```
config / frozen split   0e96a2902f272b1207c547f36c79ec64db98da560b6b53451e4da939cafc651d
scorer                  e2e19ff5469d389f6bfe199b10eb605d174ccdcdb9bfd537545c6b7557e272d0
normalizer              70a46724b29230f78e8e78d7240fd908a2c1dd51053dacb5464df31db549ccfa
thresholds              f9c1bc575ec6a45642464d49485b67b38960216ea5fb2cce9fca1a74bd6e36e6
random scores           82c3ca070bd6dbec1a93faa271ed37754e51d61749e559d5779e04308ac47103
predictor_train.jsonl   5275a6b5a279905645542f54c01859f9c5c3ed36dec8a1136609897013119028
calibration.jsonl       8a3480ab672a88dfc9553fd13ab620c01680bcf6662898321fcff11be7c4b09c
final_test.jsonl        5da3acee6f22dda0325b474f1a1353e9aad92314f5667579214576a23d8894b4
tokenizer / model       /home/aristella/.cache/huggingface/hub/models--meta-llama--Llama-3.1-8B-Instruct/snapshots/0e9e39f249a16976918f6564b8830bc894c89659
PrefEval commit         50795054b5ff5f418d2b768a331d71e480f93331
Mem0 commit             39bc02330563764e7d4465f1ecff5f002d94da1a
feature schema          recovermem-features-v1
```

## D. Collected data

| split | units | `R_mem` +/− | `R_rec` +/− | 00/01/10/11 | mem acc | rec acc | longest-opt |
|---|---|---|---|---|---|---|---|
| predictor_train | 24 | 9 / 15 | 11 / 13 | 12/3/1/8 | 0.375 | 0.458 | 0.542 |
| calibration | 24 | 9 / 15 | 15 / 9 | 9/6/0/9 | 0.375 | 0.625 | 0.500 |
| **final_test** | 24 | **10 / 14** | 15 / 9 | **8/6/1/9** | **0.417** | **0.625** | 0.542 |

Per split: history 604 messages / ~104k tokens; Mem0 store 85–148 memories;
`E_mem` 1160–2035 tokens; `E_rec` 2036–2048 tokens.

## E. Hard invariants — all hold on all 72 units

`pair_valid` 72/72 · 24 distinct `x_i` hashes per split · `B_mem`/`B_rec` never exceeded ·
memory count unchanged across every query phase · **0 external API calls** · **0 LLM-judge
calls** · no gold leakage (options shuffled before exposure; pre-shuffle order never stored
on a result). Mem0 fact-extraction JSON parse failures: **176** across 72 units —
logged per unit, **not repaired**, as required.

## F. Scorer

L2 logistic regression, `class_weight='balanced'`, C = 1.0, seed 13, trained on the 24
predictor-train units only, then frozen.

| split | π̂ | AUROC | AUPRC |
|---|---|---|---|
| predictor_train (in-sample) | 0.3750 | 0.8148 | 0.7666 |
| calibration | 0.3750 | 0.7037 | 0.5532 |
| **final_test** | **0.4167** | **0.6714** | **0.5920** |

Four of the ten host-agnostic features are **constant on this workload** and therefore carry
zero weight: `action_arg_support` (no tool arguments in an MCQ), `support_count_norm` (all 50
Mem0 candidates always fit under `B_mem`), `conflict_density_inv` (no negation conflicts in
the packed evidence), `step_progress` (single-step decision). Six features do the work. This
is the pre-specified host-agnostic schema applied unchanged to a static QA workload, not a
schema edited for PrefEval.

## G. Table 1 — canonical frozen final-test point estimates

FS and Cov. are frozen final-test point estimates; Exc. is the repeated-calibration
exceedance frequency over 200 resamples. Unit-equal weighting (each unit contributes one
decision, so unit-equal and decision-equal coincide numerically while the independent-unit
count stays 24).

| Rule | α | FS | Cov. | Exc. | τ | feasible |
|---|---|---|---|---|---|---|
| Always Trust | — | **0.583** | **1.000** | — | -Infinity | True |
| Always Recover | — | **0.000** | **0.000** | — | Infinity | True |
| Fixed-F1 | — | **0.167** | **0.333** | — | 0.4924 | True |
| Empirical-risk | 0.05 | **0.083** | **0.125** | 0.370 | 0.7309 | True |
| Empirical-risk | 0.10 | **0.083** | **0.125** | 0.425 | 0.6082 | True |
| Empirical-risk | 0.20 | **0.167** | **0.333** | 0.320 | 0.4924 | True |
| Random score + CRC | 0.05 | **0.000** | **0.000** | 0.265 | 0.9805 | True |
| Random score + CRC | 0.10 | **0.042** | **0.083** | 0.250 | 0.9104 | True |
| Random score + CRC | 0.20 | **0.125** | **0.250** | 0.395 | 0.7203 | True |
| ReCoverMem + marginal CRC | 0.05 | **0.000** | **0.000** | 0.085 | Infinity | True |
| ReCoverMem + marginal CRC | 0.10 | **0.083** | **0.125** | 0.255 | 0.7309 | True |
| ReCoverMem + marginal CRC | 0.20 | **0.167** | **0.333** | 0.320 | 0.4924 | True |

Sanity check: Always Trust FS = 0.5833 = 1 − π̂ = 0.5833 ✓

`n_cal = 24` ⇒ marginal-CRC floor `1/(n+1) = 0.0400`. At α = .05 the criterion
`(24/25)·L̂ + 0.04 ≤ 0.05` needs `L̂ ≤ 0.0104`, while the lowest non-zero calibration risk
available is 0.0417 — so ReCoverMem + CRC at α = .05 can only satisfy it by selecting
τ = +∞, i.e. **it degenerates to Always Recover** (FS 0, Cov 0). This was predicted before
collection and no rule was modified to raise coverage.

## H. Exceedance protocol

The τ³-Retail protocol, unchanged: pool = calibration + final_test (48 units, never the
predictor's training units), 200 repetitions, `n_cal = 24` drawn disjointly per repetition,
`base_seed = 13`, `mode = "split"`. The frozen Uniform(0,1) random scores are reused across
repetitions rather than redrawn.

## I. No-memory diagnostic (§7)

Same 24 final-test queries, same answerer / option ordering / prompt / tokenizer /
temperature / parser. **No Mem0 evidence, no raw-history recovery, no benchmark metadata.**
Not used for training, calibration, `R_mem`, or thresholds.

| quantity | value |
|---|---|
| random-choice baseline | 0.250 |
| global longest-option heuristic (all 1000 instances) | 0.446 |
| final-test longest-option accuracy | **0.542** |
| **no-memory Llama accuracy** | **0.333** |
| memory-route accuracy | **0.417** |
| recovery-route accuracy | **0.625** |

Reading: on this final-test sample the memory route (0.417) beats the no-memory answerer
(0.333) by 8.4 points but sits **below the longest-option shortcut** (0.542). The recovery
route (0.625) is the only condition that clears the shortcut. Memory is contributing
something, but on 24 units none of these gaps is separable from noise, and the shortcut
number means 0.25 must never be quoted as the sole floor.

## J. Runtime

Memory construction 3.24 h total, 162 s/unit (27 sequential `Mem0.add()` calls
per unit against one local 8B server) — ~98% of wall clock. 168 answerer calls total
(2 per unit × 72, plus 24 for the diagnostic); the diagnostic itself took 2.1 s.

## K. Appendix — repeated-calibration stability (mean ± SD, 200 resamples)

Appendix only. These must not be substituted for the main-table FS/Cov point estimates.

| Rule | α | FS mean ± SD | Cov mean ± SD | Exc. | frac. τ = +∞ |
|---|---|---|---|---|---|
| Empirical-risk | 0.05 | 0.059 ± 0.074 | 0.096 ± 0.112 | 0.370 | 0.000 |
| Empirical-risk | 0.10 | 0.104 ± 0.084 | 0.188 ± 0.142 | 0.425 | 0.000 |
| Empirical-risk | 0.20 | 0.166 ± 0.102 | 0.345 ± 0.158 | 0.320 | 0.000 |
| Random score + CRC | 0.05 | 0.030 ± 0.054 | 0.042 ± 0.081 | 0.265 | 0.385 |
| Random score + CRC | 0.10 | 0.067 ± 0.066 | 0.118 ± 0.102 | 0.250 | 0.000 |
| Random score + CRC | 0.20 | 0.168 ± 0.106 | 0.321 ± 0.134 | 0.395 | 0.000 |
| ReCoverMem + marginal CRC | 0.05 | 0.014 ± 0.047 | 0.017 ± 0.062 | 0.085 | 0.475 |
| ReCoverMem + marginal CRC | 0.10 | 0.059 ± 0.074 | 0.096 ± 0.112 | 0.255 | 0.000 |
| ReCoverMem + marginal CRC | 0.20 | 0.166 ± 0.102 | 0.345 ± 0.158 | 0.320 | 0.000 |

## L. Scientific caveats

1. **n = 24 per split.** Every point estimate here has wide uncertainty; the Exc. column and
   the appendix SDs are the honest description of that.
2. **Final-test AUROC 0.671** versus 0.815 in-sample — the scorer generalises
   weakly. FS control still holds because it comes from CRC, not from discrimination.
3. **α = .05 is degenerate** for ReCoverMem + CRC at this calibration size (see §G).
4. **The task has a structural shortcut** (§I). Accuracy comparisons must be read against
   0.446/0.542, not 0.250.
5. **Labels depend on a local 8B answerer.** `R_mem` and `R_rec` are properties of this
   backbone; they are not benchmark-intrinsic.
6. **Mem0 fact extraction is lossy here** — 176 malformed-JSON extraction failures across
   72 units, whose facts were silently dropped by Mem0. Logged, not repaired.

## M. Artifacts

```
results/prefeval/final/FORMAL_RUN_REPORT.md      formal_summary.json
                       predictor_train.jsonl     calibration.jsonl      final_test.jsonl
                       thresholds.json (+.sha256) scorer_metrics.json   scorer_metrics_all_splits.json
                       table1_rows.json          resampling_summary.json
                       no_memory_diagnostic.json predictor/scorer.json
                       calibration/random_scores.json
                       memory/<split>/<unit>/    (per-unit Mem0 stores)
```
