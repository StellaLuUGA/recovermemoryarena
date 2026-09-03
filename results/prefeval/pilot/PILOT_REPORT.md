# PrefEval fast viability pilot (Phase-1 §8)

8 independent units, IDs frozen **before** inference in `PRIMARY_SETTING.json` (seed-13
group permutation) and **disjoint from the smoke and budget-audit slices** — asserted in
code before the run started. `B_mem = B_rec = 2048`, frozen before any outcome.

Machine-readable: `pilot_summary.json`.

## Viability gate — **PASS**

```
rule:  PASS if R_mem positives >= 2 AND R_mem negatives >= 2 AND both classes present
       R_mem positives = 2   >= 2   OK
       R_mem negatives = 6   >= 2   OK
       both classes present         OK
```

The recoverability label is non-degenerate. The gate was fixed before the run and was not
adjusted after seeing outcomes.

## Results

| quantity | value |
|---|---|
| total pilot units | 8 |
| `R_mem` positives / negatives | **2 / 6** |
| `R_rec` positives / negatives | 4 / 4 |
| `pi_hat` (unit-equal) | 0.250 |
| memory-route accuracy | 0.250 |
| recovery-route accuracy | 0.500 |
| longest-option heuristic **on these 8 instances** | 0.500 |
| random-choice baseline | 0.250 |
| longest-option structural baseline (Phase 0, all 1000) | **0.446** |
| parser failures | 1 (memory route, `professional_work_location_style#008`) |

```
00 / 01 / 10 / 11  =  3 / 3 / 1 / 1
```

Per unit:

| unit | gold | mem | rec | `R_mem` | `R_rec` | `E_mem` | `E_rec` | Mem0 memories | build |
|---|---|---|---|---|---|---|---|---|---|
| `travel_hotel#002` | A | B | C | 0 | 0 | 1,740 | 2,046 | 122 | 140.7 s |
| `travel_activities#007` | C | D | D | 0 | 0 | 1,384 | 2,047 | 108 | 132.5 s |
| `pet_ownership#006` | D | A | D | 0 | 1 | 1,709 | 2,048 | 90 | 140.3 s |
| `professional_work_location_style#008` | A | none | A | 0 | 1 | 1,212 | 2,047 | 128 | 132.7 s |
| `shop_home#043` | B | A | B | 0 | 1 | 1,419 | 2,046 | 120 | 142.5 s |
| `entertain_sports#007` | B | B | A | 1 | 0 | 1,733 | 2,043 | 114 | 140.3 s |
| `lifestyle_dietary#012` | B | A | A | 0 | 0 | 1,672 | 2,045 | 107 | 129.2 s |
| `shop_fashion#033` | A | A | A | 1 | 1 | 1,656 | 2,045 | 107 | 125.4 s |

Integrity: `pair_valid` 8/8, `B_mem` respected 8/8, `B_rec` respected 8/8, 8 distinct `x_i`
hashes, memory count unchanged across every query phase, 16 answerer calls (2 per unit),
0 external API calls, 0 judge calls.

## Runtime

| quantity | value |
|---|---|
| memory construction | 1,083.7 s total, **135.5 s / unit** |
| query evaluation (both routes, 16 calls) | 3.92 s total |
| total | 1,106.9 s = **18.4 min** for 8 units |

Memory construction is 98% of wall clock: 27 sequential `Mem0.add()` calls per unit, each
doing fact extraction plus update decisions against one local 8B server. Projected for the
intended 24/24/24 formal protocol (72 units): **≈ 2.7 h**.

## Interpretation — deliberately limited

At n = 8 nothing here is a measurement of method quality, and none of it was used to change
a frozen setting. Three things are worth flagging, all as *observations for the formal run*
rather than conclusions:

- **`pi_hat` = 0.25 sits exactly at the random-choice baseline**, and memory-route accuracy
  (0.250) is below the structural longest-option floor of 0.446. On this small sample the
  memory route is not beating the no-memory heuristic. That is precisely the regime where a
  recoverability signal is interesting, but it also means the formal run must report both
  baselines prominently.
- **The longest-option heuristic scores 0.500 on these 8 instances** versus 0.446 over all
  1000 — sampling noise at n = 8, not a property of the selection, which was frozen before
  any outcome.
- **`01` = 3 and `10` = 1** (recovery right where memory was wrong, three times as often as
  the reverse). Not required by the gate, and not evidence at this sample size, but the
  label is at least varying in the direction the method targets.

## What was NOT done

No predictor was trained. No CRC threshold was calibrated. No final-test unit was inspected
— the 24/24/24 reserved slices in `PRIMARY_SETTING.json` remain untouched. No frozen setting
was altered: preference form, `--inter_turns`, `B_mem`/`B_rec`, γ, the recovery operator, the
option parser and the instance selection are all exactly as frozen before the smoke run.

**Gate result: PASS. Stopping here as instructed.**
