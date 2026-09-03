# ALFWorld — formal ReCoverMem results

## A. Reproducibility

| | |
|---|---|
| ALFWorld | 0.5.0 `aaba687`, `AlfredTWEnv`, split `eval_out_of_distribution` (valid_unseen) |
| Python | `/home/aristella/miniconda3/envs/alfworld/bin/python` (3.10) |
| Action backbone | **Qwen3-32B-AWQ**, `enable_thinking = false`, T=0, seed 13, AWQ 4-bit / awq_marlin, fp16, vLLM 0.18.0, `max_model_len` 16384, `kv_cache_dtype` auto, RTX 5090 |
| Mem0 | OSS pinned `39bc02330563764e7d4465f1ecff5f002d94da1a`, internal LLM = the same Qwen3-32B-AWQ server |
| Embedding | `all-MiniLM-L6-v2`, 384-d, CPU |
| Tokenizer | Qwen3-32B-AWQ (exact, server tokenizer) |
| code hash | `7c11c87a2d4c80fcb3c1e8dffb4c13020d157e42ecc840c8a6507a6e35f8200a` |
| exclusion manifest | `b3283d99343c6e79c89ea8f2b8a80617939a51987cf08d4208e291bd0cffd468` |
| CLEAN_64 / TRAIN / CAL / TEST | `4183cb627d9c716a` / `0236ef7af6127806` / `8a4a95035a284f74` / `2941a3d9592288ca` |
| budget freeze | `6df85870e9240b851a0ff8272a62e6673f125ac1b71e1e766eb65998005c574f` |
| predictor | `1be2ffa0acb62d9f73b9e079648528a6da3e7af3d1d2d5b14c5fadcd2e746159` |
| thresholds | `ebad38b0a206f913065bc79a2eb5773c34a7b6714dadba8b896ea65dc1bed12a` |
| Table-2 manifest | `56aef2aeec3f8e45ad976bcae5c5b2411c1a8bf9a69867945115eef244748650` |

Stack label: **ALFWorld Qwen3-32B stack configuration** (Mem0's internal LLM is the same
Qwen3-32B-AWQ as the action agent — the 5090 cannot hold two models).

## B. Formal sample counts

Authorised split deviation: **16 / 24 / 24**, not 20/32/32 — only 64 clean games exist
(the brief's 84 came from a stale figure of mine; see `frozen_protocol/SPLIT_FREEZE.md`).

| split | episodes | non-empty | controlled decisions |
|---|---|---|---|
| predictor_train | 16 | 7 | 36 |
| calibration | 24 | 18 | 66 |
| final_test | 24 | 18 | 78 |

## C. Data quality

| | |
|---|---|
| paired records | 180 |
| `pair_valid` | 180 (1.0) |
| reconstruction violations | 0 |
| common-state hash violations (leakage) | 0 |
| budget violations | 0 |
| external API attempts | 0 |

## D. Recoverability diagnostics

| split | R_mem (dec.) | R_rec (dec.) | 00 / 01 / 10 / 11 | mean E_mem tok | mean E_rec tok |
|---|---|---|---|---|---|
| train | 0.9444 | 0.9722 | 1 / 1 / 0 / 34 | 207.8 | 575.8 |
| cal | 0.9545 | 0.9091 | 3 / 0 / 3 / 60 | 210.1 | 534.5 |
| test | 0.9744 | 0.9615 | 1 / 1 / 2 / 74 | 267.6 | 610.8 |

## E. Predictor

train AUROC = 0.9559, AUPRC = 0.9975 ·
final-test AUROC = 0.3882, AUPRC = 0.9761.
Diagnostics only; no refit was performed.

## F. Calibration

Non-empty calibration episodes = 18 / 24.
CRC floor 1/(n+1) = 0.05263 — alpha below this cannot be satisfied by
any threshold and falls to the pre-specified Always-Recover boundary.
All frozen thresholds: `calibration/thresholds.json`.

## G. TABLE 1

| Policy | FS | Cov. | Exc. |
|---|---|---|---|
| Always Trust | 0.037 | 1.000 | -- |
| Always Recover | 0.000 | 0.000 | -- |
| Fixed-F1 | 0.037 | 0.981 | -- |
| Empirical-risk alpha=.05 | 0.037 | 0.878 | 0.000 |
| Empirical-risk alpha=.10 | 0.037 | 1.000 | 0.000 |
| Empirical-risk alpha=.20 | 0.037 | 1.000 | 0.000 |
| Random+CRC alpha=.05 | 0.000 | 0.000 | 0.000 |
| Random+CRC alpha=.10 | 0.018 | 0.943 | 0.000 |
| Random+CRC alpha=.20 | 0.037 | 1.000 | 0.000 |
| ReCoverMem+CRC alpha=.05 | 0.000 | 0.000 | 0.000 |
| ReCoverMem+CRC alpha=.10 | 0.037 | 0.878 | 0.000 |
| ReCoverMem+CRC alpha=.20 | 0.037 | 1.000 | 0.000 |

FS/Cov are canonical frozen final-test point estimates; Exc. is the 200-resample
exceedance frequency (episode-level resampling). Resampling mean±SD live in
`table1/resampling_summary.json`, never in the main table.

Sanity: Always Trust FS = 0.037 vs
episode-weighted mean(1 - R_mem) = 0.037.

## H. TABLE 2

| Policy | Task | Rec. | Cost |
|---|---|---|---|
| Always Trust | 0.800 | 0.000 | 9.394 |
| Always Recover | 0.800 | 0.800 | 12.705 |
| Empirical-risk (.10) | 0.800 | 0.000 | 9.394 |
| Random + CRC (.10) | 0.800 | 0.000 | 9.394 |
| ReCoverMem + CRC (.10) | 0.800 | 0.110 | 9.790 |

Raw-history-only reference: Task = 0.800, Cost = 1.000 (definition).
120 / 120 rollouts completed.
Conditional-on-route Rec. and zero-route counts: `table2/table2_alfworld.json` → `appendix`.

## I. Caveats

ALFWorld is a SHORT-HORIZON executable-agent environment. It is included to test interactive-agent generality with a native programmatic intermediate progress signal, NOT to demonstrate extreme long-context pressure. Raw observable histories at controlled states are hundreds of tokens, orders of magnitude below MemoryArena.

Mem0's internal LLM is the same Qwen3-32B-AWQ server as the action agent; this is a stack
constraint of the single 32 GB GPU, declared rather than hidden.

Elapsed: 0.0 h.
