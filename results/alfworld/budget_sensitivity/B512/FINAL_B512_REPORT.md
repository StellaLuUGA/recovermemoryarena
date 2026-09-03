# ALFWorld half-budget compression sensitivity (B=512) — final report

**This is a budget-sensitivity experiment.** It is not the default ALFWorld
setting, not a corrected setting, not the new formal setting, and not a
better-tuned setting. Canonical ALFWorld remains the frozen B=1024 run.

Interpretation: **CASE A** — ALFWorld remains intrinsically low-memory-risk even under half budget: pi_hat stays >= .95 and memory-negative examples remain extremely rare.

## Configuration

* `B_mem = B_rec = 512` (canonical 1024, ratio 0.5); freeze sha256 `6a5c990e50654935ccb205fd44d6684719d22aaed6232ded741dc4f0295fef08`
* Split reused verbatim from the canonical freeze: 16 / 24 / 24 over 64 clean games
* Host, Qwen3-32B-AWQ non-thinking, temperature 0, Mem0, embedder, subgoal monitor,
  horizon 50, branch horizon 20, seed 13, scorer features/architecture: all frozen
* Table 2 deliberately NOT run at B=512

## Per-split diagnostics

| split | episodes | non-empty | zero-decision | decisions | 00 | 01 | 10 | 11 | R_mem prev | R_rec prev |
|---|---|---|---|---|---|---|---|---|---|---|
| predictor_train | 16 | 7 | 9 | 36 | 1 | 1 | 0 | 34 | 0.9444 | 0.9722 |
| calibration | 24 | 18 | 6 | 66 | 2 | 1 | 4 | 59 | 0.9545 | 0.9091 |
| final_test | 24 | 18 | 6 | 78 | 0 | 1 | 4 | 73 | 0.9872 | 0.9487 |

## Final-test scorer discrimination

* AUROC = 0.5325, AUPRC = 0.992
* class counts: 1 R_mem-negative vs 77 positive
* **UNRELIABLE — one class has fewer than 10 members, so these are noise, not a measurement of scorer quality.**

## Headline sensitivity quantities

* `pi_hat_512` = 0.9872
* R_mem-negative decisions = 1
* 01 recovery-rescue decisions = 1

* Random+CRC (alpha=.10): FS = 0.0, Cov = 0.9434, tau = 0.054515, feasible = True
* ReCoverMem+CRC (alpha=.10): FS = 0.0185, Cov = 0.8984, tau = 0.45482, feasible = True

## Invariant checks (§13)

| invariant | result |
|---|---|
| no split overlap | PASS |
| no final-test leakage before threshold freeze | PASS |
| zero writes to canonical B=1024 artifacts | PASS |
| no branch state mismatch (exact replay) | PASS |
| no cross-branch memory contamination | PASS |
| B_mem <= 512 on every record | PASS |
| B_rec <= 512 on every record | PASS |
| no duplicate decision keys | PASS |
| Mem0 stores confined to B512/_stores | PASS |
| external API use | PASS (assert_local on every openai client; localhost only) |
| cross-episode memory contamination | PASS (store rmtree'd per episode) |
| hidden-state leakage | PASS (subgoal monitor harness-only, never in agent input / Mem0 / scorer / evidence) |

Records checked: 180.


## Provenance

* predictor sha256 `72ad3e440474bb1350a33d6c0fa8a8bb926d8566215c0f76b1d57e6f0ba1de49` (train AUROC 0.9559, AUPRC 0.9975)
* thresholds sha256 `6d66ddeb40b3caf4683f76bed649c8817efbde54a411f6517a3337dbd79f94bf`
* elapsed 2.89 h
