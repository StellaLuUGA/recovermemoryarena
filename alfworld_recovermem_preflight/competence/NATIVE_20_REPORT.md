# Section 7/8/10 — 20-game native competence probe

Agent frozen in `competence/AGENT_FREEZE.md` **before** this run.
Games: the first 20 structurally eligible games in frozen seed-13 order (frozen idx 0–19).
No cherry-picking by task type or difficulty. Horizon 50 steps, `AlfredTWEnv`, valid_unseen.

## Headline

```
W (>=1 controlled decision reached) = 8 / 20    -> pre-registered gate W>=5  : PASS
NATIVE_FULL_TASK_SUCCESS            = 0 / 20    (reported, not gated)
episodes reaching rank >= 2 (object actually in hand) = 1 / 20
episodes reaching rank >= 3                           = 1 / 20
```

`REACHED_CONTROLLED_i = 1` iff the harness-only upstream checker reports
`1 <= rank < K` at some step, i.e. at least one official high-level subgoal completed and at
least one still remaining.

`env_score` / `env_max_score` are `None` for every episode — ALFWorld TextWorld games carry no
scored quest, which is exactly why the upstream subgoal checker (not the env score) is the
progress signal.

## Per-episode

| idx | task type | K | won | final rank | max rank | ctrl | 1st ctrl step | #ctrl states | acts | distinct | longest repeat | invalid | snapped | max prompt tok |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | look_at_obj_in_light | 4 | 0 | 1 | 1 | 1 | 1 | 50 | 50 | 2 | 1 | 0 | 25 | 3452 |
| 1 | pick_and_place_simple | 4 | 0 | 0 | 0 | 0 | – | 0 | 50 | 3 | 48 | 47 | 0 | 1471 |
| 2 | pick_and_place_simple | 4 | 0 | 0 | 0 | 0 | – | 0 | 50 | 3 | 48 | 47 | 0 | 1451 |
| 3 | look_at_obj_in_light | 4 | 0 | 0 | 0 | 0 | – | 0 | 50 | 2 | 1 | 0 | 25 | 3232 |
| 4 | pick_clean_then_place_in_recep | 6 | 0 | 0 | 1 | 1 | 1 | 12 | 50 | 4 | 36 | 47 | 0 | 1417 |
| 5 | pick_clean_then_place_in_recep | 6 | 0 | 0 | 0 | 0 | – | 0 | 50 | 2 | 49 | 48 | 0 | 1468 |
| 6 | pick_clean_then_place_in_recep | 6 | 0 | 0 | 1 | 1 | 1 | 11 | 50 | 3 | 39 | 48 | 0 | 1407 |
| 7 | pick_cool_then_place_in_recep | 6 | 0 | 0 | 0 | 0 | – | 0 | 50 | 2 | 49 | 48 | 0 | 1472 |
| 8 | pick_cool_then_place_in_recep | 6 | 0 | 0 | 0 | 0 | – | 0 | 50 | 3 | 46 | 45 | 0 | 1560 |
| 9 | pick_clean_then_place_in_recep | 6 | 0 | 0 | 0 | 0 | – | 0 | 50 | 3 | 48 | 47 | 0 | 1537 |
| 10 | pick_cool_then_place_in_recep | 6 | 0 | 1 | 1 | 1 | 2 | 49 | 50 | 2 | 49 | 48 | 0 | 1531 |
| 11 | pick_clean_then_place_in_recep | 6 | 0 | 0 | 0 | 0 | – | 0 | 50 | 2 | 19 | 38 | 0 | 1763 |
| 12 | pick_two_obj_and_place | 8 | 0 | 0 | 0 | 0 | – | 0 | 50 | 2 | 49 | 48 | 0 | 1385 |
| 13 | pick_clean_then_place_in_recep | 6 | 0 | 0 | 1 | 1 | 1 | 16 | 50 | 3 | 34 | 48 | 0 | 1480 |
| 14 | pick_clean_then_place_in_recep | 6 | 0 | 0 | 0 | 0 | – | 0 | 50 | 3 | 46 | 47 | 0 | 1518 |
| 15 | pick_heat_then_place_in_recep | 6 | 0 | **3** | **3** | 1 | 1 | 50 | 50 | 4 | 46 | 46 | 0 | 1498 |
| 16 | look_at_obj_in_light | 4 | 0 | 0 | 1 | 1 | 1 | 25 | 50 | 2 | 1 | 0 | 25 | 2957 |
| 17 | pick_and_place_simple | 4 | 0 | 0 | 0 | 0 | – | 0 | 50 | 3 | 46 | 45 | 0 | 1529 |
| 18 | pick_heat_then_place_in_recep | 6 | 0 | 0 | 1 | 1 | 1 | 3 | 50 | 2 | 45 | 44 | 0 | 1596 |
| 19 | pick_heat_then_place_in_recep | 6 | 0 | 0 | 0 | 0 | – | 0 | 50 | 2 | 19 | 38 | 0 | 1825 |

Aggregates: mean invalid actions 39.0/50, mean longest repeated-action streak 36.0,
mean distinct actions 2.6, mean snapped actions 3.8.

## Section 10 — history-length / memory-need diagnostic (DIAGNOSTIC ONLY)

Measured with the model's own tokenizer (vLLM `POST /tokenize`, `llama-3.1-8b-instruct-local`)
over **all 216 controlled states** observed across the 8 episodes that reached one.
`H_t` = the full raw observable history transcript (task instruction + every prior action and
environment response) at that state; `x_t` = the current observation alone. The system prompt and
the single in-context example are excluded.

| quantity | median | p75 | p90 | max |
|---|---|---|---|---|
| **H_t (tokens)** | **553.5** | **831.8** | **1875.5** | **2762** |
| x_t (tokens) | 4.0 | 43.0 | 50.0 | 56 |
| prior actions | 19.5 | 35.0 | 44.0 | 50 |
| prior observations | 20.5 | 36.0 | 45.0 | 51 |

Restricted to each episode's **first** controlled state (8 states): H_t median 201.5, p75 234.2,
p90 249.1, max 275.

Full prompts (system + in-context example + history) peak at 1385–3452 tokens, far inside the
32 768-token window. As pre-registered, this is **not** grounds to reject ALFWorld — ALFWorld's
role would be executable-agent generality with a native programmatic intermediate-progress
signal, not long-context pressure.

## Observed failure mode (honest characterisation)

Full-task success is 0/20 and the dominant cause is a **greedy temperature-0 repetition lock**:
in 17/20 episodes the agent emits one action 19–49 times consecutively, usually after arriving
somewhere and then re-issuing `go to <that same receptacle>`, which is no longer admissible and
returns `Nothing happens.` forever. Mean distinct actions per 50-step episode is 2.6.

### Threat to validity — the frozen action snapper

On the three `look_at_obj_in_light` episodes (idx 0, 3, 16) the frozen OPTION-A parser rule 3
(digit-stripped unique match) fires 25 times per episode and **substitutes a different numbered
entity than the model named**: the model says `go to desk 1` while standing at desk 1 (not
admissible), the digit-stripped form `go to desk` matches exactly one admissible command
`go to desk 2`, and the harness issues that instead. The agent then oscillates desk 1 ↔ desk 2.

This is a defect in the harness's parser, not model behaviour. It is reported rather than
repaired because the admissible-command policy was pre-registered and W has now been observed;
changing it post hoc is precisely what the freeze forbids. For any re-freeze, rule 3 should be
narrowed to reject candidates whose entity numbers differ from those the model wrote.

It did **not** manufacture the reported W: every one of the 8 controlled decisions arises from an
unsnapped, verbatim model action (`go to <receptacle>` reaching the receptacle holding the target
object, or in idx 15 an actual `take`).

Raw records: `competence/native_20.jsonl` (one JSON object per episode, written after each game).
