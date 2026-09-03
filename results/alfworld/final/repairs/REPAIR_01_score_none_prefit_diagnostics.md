# Infrastructure repair 01 — pre-fit diagnostics required a recoverability score

Date: 2026-08-31. Infrastructure only. No scientific label, budget, split, prompt,
model, horizon or memory setting was changed.

## A. Split audit (run BEFORE any repair or fit)

The resume brief restated the ORIGINAL intent 84 / 20 / 32 / 32. That premise is the
stale one: it was already retracted before collection, in `SPLIT_FREEZE.md`.

Verified from the persisted manifests:

| partition | manifest | n | list_sha256 recomputed from records |
|---|---|---|---|
| clean | `CLEAN_64.json` | 64 | `4183cb62…` MATCH |
| predictor_train | `PREDICTOR_TRAIN_16.json` | 16 | `0236ef7a…` MATCH |
| calibration | `CALIBRATION_24.json` | 24 | `8a4a9503…` MATCH |
| final_test | `FINAL_TEST_24.json` | 24 | `2941a3d9…` MATCH |

* `16 + 24 + 24 = 64`; the three partitions are pairwise disjoint and their union is
  exactly `CLEAN_64`; contiguous index blocks 0–15 / 16–39 / 40–63 of the frozen
  seed-13 clean order; identical `exclusion_manifest_sha256` on all four.
* `af_formal/common.py:49` — `N_PREDICTOR_TRAIN, N_CALIBRATION, N_FINAL_TEST = 16, 24, 24`.
* The runtime loop ran `16 / 16`, which is the frozen manifest, not a truncation.

**Verdict: NOT an infrastructure split bug, and NOT `FORMAL_SPLIT_FREEZE_MISMATCH`.**
Only 64 clean games exist (exclusion union 70 of 134), so 20/32/32 is arithmetically
infeasible. `protocol.py:60` stopped the run with `FORMAL_SPLIT_INTEGRITY_FAILURE`
before freezing anything, and the resize to 16/24/24 was an explicit, pre-collection,
user-authorised decision recorded in `SPLIT_FREEZE.md`. No 4 "missing" predictor-train
games exist to collect: taking any would have to come out of calibration or final test
and would corrupt the frozen split.

## B. Validation of the already-collected predictor-train episodes

All 16 frozen games, in manifest order, `error=None`, 36 controlled decisions.
Every one of the 36 records passes: `pair_valid`, `reconstruction_ok_mem`,
`reconstruction_ok_rec`, `budget_ok`, `common_state_hash == expected_common_state_hash`
(exact state replay), memory- and recovery-branch common-state hashes equal to the
common state (common-state equality), `budget_mem = budget_rec = 1024`,
`e_mem_tokens <= 1024`, `e_rec_tokens <= 1024`, `r_mem`/`r_rec` binary, `score is None`,
10-dim host-agnostic features present, `u_mem`/`u_rec` present, `episode_id` in the
frozen manifest, `decision_key` unique.

Fresh stores: `Mem0Host.reset()` `rmtree`s the per-episode store root before each
episode; `n_memories` per episode is non-monotonic
(12, 20, 15, 41, 5, 17, 42, 16, 36, 37, 33, 12, 38, 19, 38, 11), i.e. no carry-over.
No external API: `assert_local` is installed globally on `openai.OpenAI.__init__`;
the only endpoint is `http://localhost:8124/v1`.

**All 16 kept. 0 re-collected.**

## C. The bug

`fit_predictor` → `diagnostics` → `episodes_of` → `group_by_episode` →
`float(row["score"])` raised `TypeError` because predictor-train collection writes
`score = None` — correct, since no predictor exists yet.

Fix (`af_formal/stages.py`): added `LabelOnlyEpisode` + `group_by_episode_labels`, and
`episodes_of` / `diagnostics` take `require_score` (default `True`). `fit_predictor`'s
pre-fit diagnostics and `run_all.final_report`'s predictor-train diagnostics pass
`require_score=False` and group on `episode_id` + `r_mem` only.

* No score is fabricated. `LabelOnlyEpisode` has **no** `scores` attribute at all, so
  any threshold quantity (FS, coverage) raises rather than reading a stand-in.
* `recovermem.metrics.weighting.group_by_episode` and the whole shared final-evaluation
  weighting/risk path are **unchanged**; scored calibration/final-test records still use
  them exactly as before.
* None of the reported diagnostics depend on the score, so the numbers are identical
  under either grouping (asserted by test).
* Zero-decision episodes stay legitimate units: still counted, still reported in
  `empty_episode_ids`, still excluded from per-episode means by the shared `drop_empty`.

Regression test: `af_formal/tests/test_prefit_diagnostics.py`, 14 tests, all pass,
including one over the real frozen `predictor_train.jsonl`.

Code hash before repair `7b999284f0d3ee73…`, after repair `9da7a3a7b9f5cc31…`.

## D. Recorded in advance, not patched

Predictor-train yielded 7 non-empty / 9 zero-decision episodes (44% non-empty) and a
decision-level `R_mem` prevalence of 0.944 (joint cells 00:1, 01:1, 10:0, 11:34).
`SPLIT_FREEZE.md` pre-recorded that CRC at alpha=.05 needs >= 19 non-empty of the 24
calibration episodes (79%); at the observed rate that is unlikely to hold and alpha=.05
would fall to the pre-specified Always-Recover boundary. That outcome is to be reported,
never patched by raising alpha, dropping hard games, or altering the host, Qwen,
horizon 50, branch horizon 20, Mem0, B=1024 or the subgoal monitor.
