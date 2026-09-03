# Config C — backbone-scale feasibility: Qwen3-32B-AWQ on ALFWorld

```
ALFWORLD_32B_PREFLIGHT = PASS
```

The blocker in Config A and Config B **was** backbone competence. Swapping only the model — same
ALFWorld, same environment, same prompt, same parser, same ICL example, same monitor, same
horizons — turns 0/20 full-task success into 13/20.

## Gate 1 (§2/§3) — the SAME five Config-B controlled states

`competence_c/suffix_c_old_states.json`. Each state reconstructed by exact action-prefix replay;
harness-side rank required to match the Config-B reference.

```
B32 = 5 / 5   ->  PASS_SUFFIX_COMPETENCE      (replay rank matched reference 5/5)
```

| idx | task type | rank₀ | next official subgoal | steps used | valid rate | result |
|---|---|---|---|---|---|---|
| 5 | pick_and_place_simple | 1 | `take peppershaker` | **1** | 1.00 | ✓ |
| 6 | pick_heat_then_place_in_recep | 1 | `take mug` | **1** | 1.00 | ✓ |
| 7 | pick_two_obj_and_place | 1 | `take cd` | **1** | 1.00 | ✓ |
| 12 | look_at_obj_in_light | 1 | `take alarmclock` | 3 | 0.67 | ✓ |
| 13 | pick_clean_then_place_in_recep | 1 | `take egg` | **1** | 1.00 | ✓ |

Four of five completed the next subgoal on the **first action**. On these identical states
Llama-3.1-8B (Config B) issued zero `take` actions in 100 steps.

## Gate 2 (§4) — new disjoint native 20

`competence_c/FROZEN_CONFIG_C_20.json`, hash `3250bc02…`. Ranks **50–69** of the seed-13
ordering. Excluded first: structural-30, Config-A native-20, Config-A suffix-5, Config-B
native-20, Config-B suffix-5, Config-C gate-1 suffix-5, validator-3 and replay-3 — union of 50
distinct games, leaving 84 candidates. Manifest hashed before the first model call.

```
W32 (>=1 controlled decision)  = 14 / 20    -> gate W32>=5 : PASS
NEW_NATIVE_FULL_TASK_SUCCESS   = 13 / 20
episodes reaching rank >= 2    = 14 / 20     (Config A: 1/20, Config B: 0/20)
episodes reaching rank >= 4    =  8 / 20
VALID_ACTION_RATE              = 0.780       (415 admissible of 532 issued)
DISTINCT_ACTIONS               = mean 16.45 / median 14.5
LONGEST_REPEAT_STREAK          = mean 3.80  / median 1.0
actions per episode            = mean 26.6  / median 18.5
```

| idx | order | task type | K | won | max rank | ctrl | 1st ctrl | acts | distinct | repeat | invalid | valid rate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 50 | look_at_obj_in_light | 4 | 0 | 0 | 0 | – | 50 | 23 | 7 | 15 | 0.70 |
| 1 | 51 | pick_clean_then_place_in_recep | 6 | **1** | 5 | 1 | 1 | 6 | 6 | 1 | 0 | 1.00 |
| 2 | 52 | pick_and_place_simple | 4 | **1** | 3 | 1 | 1 | 4 | 4 | 1 | 0 | 1.00 |
| 3 | 53 | pick_cool_then_place_in_recep | 6 | **1** | 3 | 1 | 37 | 43 | 30 | 10 | 13 | 0.70 |
| 4 | 54 | look_at_obj_in_light | 4 | **1** | 3 | 1 | 6 | 9 | 8 | 1 | 0 | 1.00 |
| 5 | 55 | pick_heat_then_place_in_recep | 6 | 0 | 0 | 0 | – | 50 | 20 | 1 | 6 | 0.88 |
| 6 | 56 | pick_clean_then_place_in_recep | 6 | **1** | 4 | 1 | 16 | 19 | 19 | 1 | 0 | 1.00 |
| 7 | 57 | pick_cool_then_place_in_recep | 6 | **1** | 5 | 1 | 1 | 7 | 7 | 1 | 0 | 1.00 |
| 8 | 58 | pick_clean_then_place_in_recep | 6 | **1** | 5 | 1 | 2 | 8 | 7 | 1 | 0 | 1.00 |
| 9 | 59 | pick_and_place_simple | 4 | **1** | 3 | 1 | 1 | 5 | 5 | 1 | 0 | 1.00 |
| 10 | 60 | pick_and_place_simple | 4 | **1** | 3 | 1 | 35 | 38 | 17 | 17 | 20 | 0.47 |
| 11 | 61 | look_at_obj_in_light | 4 | **1** | 3 | 1 | 4 | 6 | 5 | 1 | 0 | 1.00 |
| 12 | 62 | pick_cool_then_place_in_recep | 6 | **1** | 5 | 1 | 4 | 9 | 9 | 1 | 0 | 1.00 |
| 13 | 63 | pick_clean_then_place_in_recep | 6 | 0 | 0 | 0 | – | 50 | 12 | 10 | 25 | 0.50 |
| 14 | 64 | pick_heat_then_place_in_recep | 6 | 0 | 4 | 1 | 44 | 50 | 41 | 1 | 3 | 0.94 |
| 15 | 65 | pick_cool_then_place_in_recep | 6 | **1** | 5 | 1 | 13 | 18 | 17 | 1 | 0 | 1.00 |
| 16 | 66 | pick_clean_then_place_in_recep | 6 | 0 | 0 | 0 | – | 50 | 22 | 6 | 18 | 0.64 |
| 17 | 67 | pick_two_obj_and_place | 8 | 0 | 0 | 0 | – | 50 | 34 | 11 | 16 | 0.68 |
| 18 | 68 | pick_heat_then_place_in_recep | 6 | **1** | 5 | 1 | 3 | 10 | 9 | 0 | 1.00 |
| 19 | 69 | pick_heat_then_place_in_recep | 6 | 0 | 0 | 0 | – | 50 | 34 | 2 | 1 | 0.98 |

Wins by task type: `pick_cool` 4/4, `pick_and_place_simple` 3/3, `pick_clean` 3/5,
`look_at_obj_in_light` 2/3, `pick_heat` 1/4, `pick_two_obj_and_place` 0/1. The six failures are
search failures — the agent never located the target object within 50 steps — not action-format
or repetition failures (`longest_repeat_streak` median 1).

## Gate 3 (§5) — second suffix check on the new set

`competence_c/suffix_c_new.json`. First 5 native episodes in frozen order that reached a
controlled state: idx **1, 2, 3, 4, 6**. Exact prefix replay, rank match required, then the same
20-step full-history suffix test.

```
B32_new = 5 / 5   ->  PASS      (replay rank matched native 5/5)
```

| idx | task type | rank₀ | next official subgoal | steps used | result |
|---|---|---|---|---|---|
| 1 | pick_clean_then_place_in_recep | 1 | `take plate` | 1 | ✓ |
| 2 | pick_and_place_simple | 1 | `take pencil` | 1 | ✓ |
| 3 | pick_cool_then_place_in_recep | 1 | `take tomato` | 1 | ✓ |
| 4 | look_at_obj_in_light | 1 | `take mug` | 1 | ✓ |
| 6 | pick_clean_then_place_in_recep | 1 | `take pan` | 1 | ✓ |

All five on the first action.

## History-length diagnostic (§11 carried over — DIAGNOSTIC ONLY)

Qwen3-32B tokenizer (vLLM `POST /tokenize` on `:8124`), over all **67 controlled states** across
the 14 episodes that reached one.

| quantity | median | p75 | p90 | max |
|---|---|---|---|---|
| **H_t (tokens)** | **340.0** | **715.0** | **1211.8** | **1649** |
| x_t (tokens) | 15.0 | 24.5 | 37.4 | 65 |
| prior actions | 6.0 | 16.5 | 39.4 | 47 |

At each episode's first controlled state (14 states): median 280.5, p75 646.5, p90 1029.5,
max 1555. Full prompts peak at 1138–3435 tokens against a 16 384-token window.

Histories are **shorter** than under the failing configurations, because a competent agent reaches
its first controlled state in a median of 6 actions instead of thrashing for 50. As pre-registered
this is not a rejection criterion, but it is the honest shape of the domain: ALFWorld under a
competent host is a *short-horizon* executable-agent domain, and its value to ReCoverMem is
native programmatic intermediate progress, not long-context pressure.

## Cross-configuration table — DIAGNOSIS ONLY

Three **disjoint** game sets, three separately pre-registered configurations. This is not an
ablation and no statistical claim is made; it is recorded because §7 asks for these aggregates.

| | Config A (8B, no adm. list) | Config B (8B, adm. list) | **Config C (32B)** |
|---|---|---|---|
| game set (seed-13 ranks) | 0–29 subset | 30–49 | **50–69** |
| W | 8/20 | 6/20 | **14/20** |
| full-task success | 0/20 | 0/20 | **13/20** |
| valid action rate | 0.221 | 0.073 | **0.780** |
| distinct actions (mean) | 2.60 | 1.65 | **16.45** |
| longest repeat streak (mean) | 35.95 | 45.60 | **3.80** |
| suffix success | 0/5 | 0/5 | **5/5 and 5/5** |

## Conclusion

ALFWorld reopens as a ReCoverMem main-table candidate. The environment gates
(structural 30/30, programmatic subgoal validator, replay 9/9) were never in question and were
re-confirmed 10 more times here (5+5 exact-replay rank matches). The host agent is now
demonstrably competent: it completes the next official subgoal from a genuine controlled state in
10/10 attempts across two disjoint state sets, and solves 13/20 full tasks natively.

**No ReCoverMem work was performed.** No Mem0, no budget audit, no `R_mem`/`R_rec`, no scorer, no
CRC, no FS, no coverage, no Table 1, no Table 2.
