# Formal ALFWorld split freeze

Frozen BEFORE any formal utility label was collected.

## Sample-size deviation (recorded, user-authorised)

The brief specified 20 / 32 / 32 on the premise that 84 clean games remained. That premise came
from my own Config-C summary and was **stale**: it was read off `FROZEN_CONFIG_C_20.json`, whose
exclusion union (50) predates the Config-C native-20 run that then consumed 20 of those games.
Reconstructed from the persisted manifests the true union is **70**
and only **64** clean games remain, so 20/32/32 is arithmetically infeasible.

Section 1 was honoured: the run STOPPED with `FORMAL_SPLIT_INTEGRITY_FAILURE`
(`SPLIT_INTEGRITY_FAILURE.json`), no split was frozen and no label collected, and the resize was
an explicit user decision, not a silent change. The authorised split is **16 / 24 / 24 = 64**.

Consequence recorded in advance: CRC at alpha=.05 needs n >= 19 NON-EMPTY calibration episodes.
With 24 calibration episodes this is feasible only if >= 79% of them reach a controlled decision;
otherwise alpha=.05 falls to the pre-specified Always-Recover boundary. That outcome is reported,
never patched by raising alpha.

## Provenance

* ALFWorld 0.5.0 `aaba687`, `AlfredTWEnv`, split `eval_out_of_distribution` (= valid_unseen),
  134 games total.
* Ordering: the SAME deterministic seed-13 convention used throughout preflight
  (`collect_game_files()` -> `sorted()` -> `random.Random(13).shuffle()`), then filtered to the
  never-touched games. **Not reshuffled.**
* Exclusion union = 70 games; manifest sha256
  `b3283d99343c6e79c89ea8f2b8a80617939a51987cf08d4208e291bd0cffd468`.
* Every clean game satisfies `K_USABLE >= 2` under the verified upstream subgoal checker.

| partition | n | list_sha256 |
|---|---|---|
| CLEAN_64 | 64 | `4183cb627d9c716af5294eee1ea9b5734e061291046a2be3650a876fec4d30bb` |
| PREDICTOR_TRAIN_16 | 16 | `0236ef7af6127806176fa56ba29e81f32814aa96b37aaa1ef390f1520922ffb4` |
| CALIBRATION_24 | 24 | `8a4a95035a284f7454bf70298028697156a472cbaecbde47c1b73a6075ff7dcf` |
| FINAL_TEST_24 | 24 | `2941a3d9592288ca2e194d61d4dce901b45d9eeb5ac305b4ae3f1538b493c873` |

The split is at the GAME/EPISODE level: all controlled decisions of a game live in exactly one
partition. Final-test scientific outcomes are not inspected until `calibration/thresholds.json`
exists and is hashed.
