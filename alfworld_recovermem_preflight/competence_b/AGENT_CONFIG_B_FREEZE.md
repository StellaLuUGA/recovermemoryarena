# `AGENT_CONFIG_B_ADMISSIBLE_COMMANDS` — frozen BEFORE any competence outcome

```
config_sha256    = 1555ae8d557106e563ea981c4fdf1c0b9937b9c900a3e520d80c33810386086e
CONFIG_B_20_HASH = b56fa6534768489cf66d555cfc7dfd08aa4bef121d2d38f43498c2c13d248276
```

Machine-readable copy: `competence_b/agent_config_b.json` (full prompt text, parser spec,
ICL provenance). Game set: `competence_b/FROZEN_CONFIG_B_20.json`.

## Unchanged from Config A (§0, §3)

| | |
|---|---|
| ALFWorld | 0.5.0 `aaba687`, `/home/aristella/recoverappworld/alfworld` |
| Python | `/home/aristella/miniconda3/envs/alfworld/bin/python` |
| `ALFWORLD_DATA` | `/home/aristella/.cache/alfworld` |
| Environment | `AlfredTWEnv`, `eval_out_of_distribution` (= valid_unseen, 134 games) |
| Model | `llama-3.1-8b-instruct-local` @ `http://localhost:8123/v1` |
| Temperature / top_p / seed | `0` / `1.0` / `13` |
| max_tokens per action / stop | `32` / `["\n"]` |
| `MAX_AGENT_STEPS` | `50` |
| `MAX_NEXT_SUBGOAL_STEPS` | `20` |
| ICL example | the same single **train-split** trajectory (`competence/ICL_EXAMPLE.json`), 9 steps, produced by the upstream `HandCodedTWAgent` |
| History serialisation | identical (`agent_b._render is agent._render`): intro, then `> {action}\n{observation}` per step, full raw history, no truncation or summarisation |
| Inventory | `EnvInfos.inventory` is `None` on ALFWorld games, so nothing is injected; the agent may issue the `inventory` action itself |
| System prompt body | Config A's verbatim, including its `Do not repeat an action that produced 'Nothing happens.'` line (carried over, **not** a new anti-loop hint) |

Nothing was added: no ReAct demonstrations, no expert demonstrations, no chain-of-thought
exemplars, no task-specific rules, no failure-specific hints, no anti-loop heuristics, no forced
exploration, no repetition penalties, no temperature change, no action blacklists.

## Change 1 — entity-preserving exact parser

`agent_b.py::parse_action`. All fuzzy / digit-stripped matching from Config A is **deleted**.

Normalises only: leading `>` and whitespace · an optional `ACTION:` prefix (case-insensitive) ·
wrapping quotes/backticks/asterisks · one trailing period · letter case (ALFWorld commands are
lowercase).

Never modifies: the **action verb**, **object identity**, **receptacle identity**, or any
**numeric suffix**. It can never substitute a different admissible command, so
`go to desk 1 → go to desk 2` is structurally impossible.

If the normalised string is not in `admissible_commands`, it is issued **verbatim** and counted as
an invalid action; TextWorld answers `Nothing happens.` An empty model output is issued as `look`
and counted invalid.

## Change 2 — `admissible_commands` shown to the model

At every step the user message ends with `info["admissible_commands"][0]`, rendered verbatim in
engine order, one per line prefixed `- `, under the header `Admissible commands:`, followed by
`>`. The system prompt gains exactly one paragraph:

> At every step you are given the list of admissible commands for the current state. Choose
> exactly ONE command from that list and copy it verbatim, including its numbers. Reply in the
> form:
> ACTION: \<command\>

No planning hints, no pointers to which command to pick.

## Agent-visible vs harness-only

**Visible:** task instruction · current text observation · prior actions and environment
responses · current `admissible_commands`.

**Harness-only, never in any prompt:** `plan.high_pddl`, `traj_data.json`, PDDL `facts`,
`policy_commands`, `extra.expert_plan`, the shadow monitor's subgoal rank, target predicates,
future subgoals.

`admissible_commands` is part of the public standard TextWorld interface
(`AlfredTWEnv.init_env` requests it upstream at `alfred_tw_env.py:254`). It is **not** oracle
information: it enumerates legal actions in the current state and carries no information about
which action serves the task.

## Game set (§5) — disjoint from Config A

Deterministic seed-13 ordering (`collect_game_files()` → `sorted()` → `Random(13).shuffle()`),
then **exclude** every game used anywhere in the Config-A line — the frozen structural-30, which
is a verified superset of Config-A's native-20, suffix-5, replay-3 and validator-3 (asserted in
`stage6_freeze_b.py`) — then take the **first 20 with `K_USABLE ≥ 2`**, eligibility decided by
the already-verified upstream subgoal checker with no model outcomes involved.

104 candidates remained; the 20 selected are ranks 30–49 of the seed-13 ordering. Task mix:
6 × `pick_and_place_simple`, 4 × `pick_two_obj_and_place` (K=8), 3 × `look_at_obj_in_light`,
3 × `pick_clean_…`, 3 × `pick_cool_…`, 1 × `pick_heat_…`. No replacements after outcomes.

## Pre-registered gates (unchanged from Config A)

```
W_B >= 5       -> native reachability PASS
W_B in {2,3,4} -> STOP_FOR_REVIEW
W_B <= 1       -> FAIL_NATIVE_COMPETENCE

B_B >= 2       -> ALFWORLD_CONFIG_B_PREFLIGHT = PASS
B_B == 1       -> STOP_FOR_REVIEW
B_B == 0       -> FAIL_SUFFIX_COMPETENCE
```

If Config B fails, ALFWorld is closed as a main-table candidate. No Config C.

## Smoke calls (§4) — format only, 3 calls, `competence_b/smoke_b.json`

| criterion | result |
|---|---|
| output parses | **3/3 PASS** (incl. one `ACTION: …` prefixed reply, stripped correctly) |
| entity numbers preserved exactly | **3/3 PASS** |
| selected action ∈ `admissible_commands` | **1/3** — calls 2 and 3 repeated `go to cabinet 1` while already at cabinet 1 |

The prompt was dumped and inspected directly: the `Admissible commands:` block was present with
17 entries including `open cabinet 1`, and the parser reproduced the model's string exactly. The
2/3 miss is therefore **model non-compliance, not a prompt or parser defect**.

Proceeding to the native-20 probe: the admissibility criterion measures model compliance, which
is precisely what the 20-game probe is designed to measure, and halting on a 3-call sample would
pre-empt the pre-registered experiment. **No configuration change was made in response to the
smoke result.** This paragraph was written before the first native-probe model call.
