# Config B — native 20-game probe (sections 6, 7, 11)

`AGENT_CONFIG_B_ADMISSIBLE_COMMANDS`, frozen in `AGENT_CONFIG_B_FREEZE.md` before the first
model call. Disjoint 20-game set (`FROZEN_CONFIG_B_20.json`, ranks 30–49 of the seed-13
ordering); no game overlaps the Config-A line.

```
config_sha256    = 1555ae8d557106e563ea981c4fdf1c0b9937b9c900a3e520d80c33810386086e
CONFIG_B_20_HASH = b56fa6534768489cf66d555cfc7dfd08aa4bef121d2d38f43498c2c13d248276
```

## Headline

```
W_B (>=1 controlled decision) = 6 / 20     -> pre-registered gate W_B>=5 : PASS
NATIVE_FULL_TASK_SUCCESS      = 0 / 20
episodes reaching rank >= 2   = 0 / 20      (no episode ever got an object in hand)
VALID_ACTION_RATE             = 0.073       (73 admissible of 1000 issued actions)
DISTINCT_ACTIONS              = mean 1.65 / median 2.0   (out of 50 actions)
LONGEST_REPEAT_STREAK         = mean 45.6  / median 49.0
```

`env_score` / `env_max_score` are `None` throughout (ALFWorld games carry no scored quest);
progress is tracked solely by the verified harness-only shadow monitor, whose output is never
exposed to the agent.

## Per-episode

| idx | seed-13 rank | task type | K | won | final rank | max rank | ctrl | 1st ctrl step | acts | distinct | longest repeat | invalid | valid rate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 30 | pick_and_place_simple | 4 | 0 | 0 | 0 | 0 | – | 50 | 1 | 50 | 49 | 0.02 |
| 1 | 31 | pick_clean_then_place_in_recep | 6 | 0 | 0 | 0 | 0 | – | 50 | 1 | 50 | 49 | 0.02 |
| 2 | 32 | pick_cool_then_place_in_recep | 6 | 0 | 0 | 0 | 0 | – | 50 | 3 | 20 | 31 | 0.38 |
| 3 | 33 | pick_clean_then_place_in_recep | 6 | 0 | 0 | 0 | 0 | – | 50 | 1 | 50 | 49 | 0.02 |
| 4 | 34 | pick_cool_then_place_in_recep | 6 | 0 | 0 | 0 | 0 | – | 50 | 3 | 38 | 47 | 0.06 |
| 5 | 35 | pick_and_place_simple | 4 | 0 | 1 | 1 | **1** | 1 | 50 | 2 | 35 | 35 | 0.30 |
| 6 | 36 | pick_heat_then_place_in_recep | 6 | 0 | 1 | 1 | **1** | 1 | 50 | 1 | 50 | 49 | 0.02 |
| 7 | 37 | pick_two_obj_and_place | 8 | 0 | 1 | 1 | **1** | 2 | 50 | 2 | 49 | 48 | 0.04 |
| 8 | 38 | pick_and_place_simple | 4 | 0 | 0 | 0 | 0 | – | 50 | 2 | 49 | 48 | 0.04 |
| 9 | 39 | pick_two_obj_and_place | 8 | 0 | 0 | 0 | 0 | – | 50 | 1 | 50 | 49 | 0.02 |
| 10 | 40 | pick_two_obj_and_place | 8 | 0 | 0 | 0 | 0 | – | 50 | 2 | 49 | 48 | 0.04 |
| 11 | 41 | look_at_obj_in_light | 4 | 0 | 0 | 0 | 0 | – | 50 | 1 | 50 | 49 | 0.02 |
| 12 | 42 | look_at_obj_in_light | 4 | 0 | 1 | 1 | **1** | 1 | 50 | 1 | 50 | 49 | 0.02 |
| 13 | 43 | pick_clean_then_place_in_recep | 6 | 0 | 1 | 1 | **1** | 1 | 50 | 1 | 50 | 49 | 0.02 |
| 14 | 44 | look_at_obj_in_light | 4 | 0 | 0 | 0 | 0 | – | 50 | 1 | 50 | 49 | 0.02 |
| 15 | 45 | pick_and_place_simple | 4 | 0 | 0 | 0 | 0 | – | 50 | 2 | 46 | 46 | 0.08 |
| 16 | 46 | pick_heat_then_place_in_recep | 6 | 0 | 0 | 0 | 0 | – | 50 | 2 | 48 | 48 | 0.04 |
| 17 | 47 | pick_cool_then_place_in_recep | 6 | 0 | 0 | 0 | 0 | – | 50 | 2 | 48 | 48 | 0.04 |
| 18 | 48 | pick_and_place_simple | 4 | 0 | 0 | 0 | 0 | – | 50 | 2 | 49 | 48 | 0.04 |
| 19 | 49 | pick_two_obj_and_place | 8 | 0 | 1 | 1 | **1** | 1 | 50 | 2 | 31 | 39 | 0.22 |

## Failure mode

Identical in kind to Config A and, on this set, more extreme. The model issues its first action,
usually a valid `go to <receptacle>`, and then re-issues that **same** command for the remaining
49 steps even though it is no longer in the admissible list and the environment answers
`Nothing happens.` every time. Nine of twenty episodes have `distinct_actions == 1`.

The parser and the prompt were verified directly, not inferred: a step-2 prompt was dumped in
full and the `Admissible commands:` block was present with 17 entries including the obviously
correct `open cabinet 1`; the parser reproduced the model's string byte-for-byte, and the
`ACTION:` prefix was stripped correctly whenever the model emitted it. **The repetition is model
non-compliance with the supplied list, not a harness defect.** No entity-number substitution is
possible in Config B by construction, and none occurred.

## Aggregate behaviour vs Config A — DIAGNOSIS ONLY

The two configurations ran on **disjoint game sets** and this is **not** an ablation; no
statistical claim of improvement or regression is made in either direction.

| aggregate | Config A | Config B |
|---|---|---|
| valid action rate | 0.221 | 0.073 |
| distinct actions (mean / median) | 2.60 / 2.5 | 1.65 / 2.0 |
| longest repeat streak (mean / median) | 35.95 / 46.0 | 45.60 / 49.0 |
| W | 8/20 | 6/20 |
| full-task success | 0/20 | 0/20 |

Showing the admissible-command list did not reduce inadmissible-action repetition. These
diagnostics were not used to tune Config B in any way.

## Section 11 — history-length diagnostic (DIAGNOSTIC ONLY)

Llama-3.1-8B tokenizer (vLLM `POST /tokenize`), over all **223 controlled states** across the 6
episodes that reached one. `H_t` = full raw observable history (task instruction + every prior
action and environment response); `x_t` = current observation alone.

| quantity | median | p75 | p90 | max |
|---|---|---|---|---|
| **H_t (tokens)** | **469.0** | **613.5** | **693.8** | **977** |
| x_t (tokens) | 4.0 | 4.0 | 4.0 | 53 |
| prior actions | 26.0 | 39.0 | 46.0 | 50 |

At each episode's **first** controlled state (6 states): median 223.0, p75 234.8, p90 238.0,
max 238. Full prompts peak at 1535–1932 tokens against a 32 768-token window.

As pre-registered, short histories are **not** a rejection criterion. (The `x_t` median of 4
tokens is itself a symptom: most observations are the four-token `Nothing happens.`)

Raw records: `competence_b/native_b_20.jsonl`, one JSON object per episode, flushed after each game.
