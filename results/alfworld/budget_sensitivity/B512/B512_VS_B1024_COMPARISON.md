# ALFWorld half-budget compression sensitivity (B=512) vs canonical B=1024

This is a **budget-sensitivity experiment**, not the default, corrected, new, or
better-tuned ALFWorld setting. The canonical ALFWorld result remains the frozen
B=1024 run under `results/alfworld/final/`, which was read but never modified.

The only intervention relative to the canonical run is `B_mem`/`B_rec`
1024 -> 512 (ratio 0.5). Split identities,
host, Qwen, Mem0, features, horizons and seed are reused frozen.

| Metric | B=512 | B=1024 |
|---|---|---|
| B_mem | 512 | 1024 |
| B_rec | 512 | 1024 |
| final controlled decisions | 78 | 78 |
| R_mem prevalence (pi_hat) | 0.987 | 0.974 |
| R_mem-negative count | 1 | 2 |
| 01 count (recovery rescue) | 1 | 1 |
| Always Trust FS | 0.018 | 0.037 |
| Always Trust Cov | 1.000 | 1.000 |
| ReCoverMem+CRC(.10) FS | 0.018 | 0.037 |
| ReCoverMem+CRC(.10) Cov | 0.898 | 0.878 |
| Random+CRC(.10) FS | 0.000 | 0.018 |
| Random+CRC(.10) Cov | 0.943 | 0.943 |

## Canonical reference values verified from the artifact

The brief quoted canonical numbers; each was re-read from
`results/alfworld/final/table1/table1_alfworld.json` rather than copied.

| quantity | brief | artifact | match |
|---|---|---|---|
| pi_hat | 0.974 | 0.974 | YES |
| always_trust_FS | 0.037 | 0.037 | YES |
| always_trust_Cov | 1.0 | 1.000 | YES |
| random_FS | 0.018 | 0.018 | YES |
| random_Cov | 0.943 | 0.943 | YES |
| recovermem_FS | 0.037 | 0.037 | YES |
| recovermem_Cov | 0.878 | 0.878 | YES |

## Interpretation: CASE A

ALFWorld remains intrinsically low-memory-risk even under half budget: pi_hat stays >= .95 and memory-negative examples remain extremely rare.

Reported as a compression-severity intervention. B=512 is **not** declared
"better" for producing more failures, and does not replace canonical B=1024.

## Provenance

* B512 freeze sha256 `6a5c990e50654935ccb205fd44d6684719d22aaed6232ded741dc4f0295fef08`
* B512 thresholds sha256 `6d66ddeb40b3caf4683f76bed649c8817efbde54a411f6517a3337dbd79f94bf`
* B512 predictor sha256 `72ad3e440474bb1350a33d6c0fa8a8bb926d8566215c0f76b1d57e6f0ba1de49`
* B512 Table 1 json sha256 `ee3c4b241b98a6f68cbfd78bee8222a8a7a440c295704b766e949ac903dfe134`
* B512 Table 1 tex sha256 `035b5ddfd1448222101e789191ed8d8d4a1fd2b06d4397bb535ec88fd8d9acff`
* split manifests identical to canonical (hashes in `frozen_protocol/SPLIT_MIRROR.json`)
* Table 2 was deliberately NOT run at B=512.
