# ALFWorld 0.5.0 — Subgoal Semantics Audit (source-only, no model calls)

Pinned source: `/home/aristella/recoverappworld/alfworld/` @ `aaba687` (v0.5.0)
Environment under audit: **`AlfredTWEnv`** (text-only). AI2-THOR / MaskRCNN excluded by construction.

---

## A. Game → ALFRED trajectory metadata mapping

**Official and exact.** Each TextWorld game is `<trial_dir>/game.tw-pddl`; the ALFRED trajectory is its
sibling `<trial_dir>/traj_data.json`.

| Evidence | Location |
|---|---|
| Collector pairs `traj_data.json` with `game.tw-pddl` in the same `root` | `alfworld/agents/environment/alfred_tw_env.py:156-193` |
| `AlfredInfos` wrapper surfaces the game path at runtime as `state["extra.gamefile"]` | `alfworld/agents/environment/alfred_tw_env.py:38-51` |
| `init_env` requests that extra | `alfworld/agents/environment/alfred_tw_env.py:254` |
| Upstream itself derives traj_data from the gamefile: `os.path.join(os.path.dirname(game), 'traj_data.json')` | `alfworld/agents/expert/handcoded_expert.py:549-552` |

So the mapping is not inferred by us — it is the mapping upstream uses. Harness helper: `pf_lib.traj_data_path()`.

## B. Where `plan.high_pddl` lives and how subgoals are represented

`traj_data.json → ["plan"]["high_pddl"]`: an ordered list of
`{"high_idx": int, "discrete_action": {"action", "args"}, "planner_action": {...}}`.
Low-level actions link back via `low_actions[i]["high_idx"]` (`scripts/augment_trajectories.py:164`).

Verified example (`look_at_obj_in_light-Mug-None-DeskLamp-308`):
`['GotoLocation', 'PickupObject', 'GotoLocation', 'ToggleObject', 'NoOp']`.

The **only** entry upstream itself identifies as non-task bookkeeping is the trailing `NoOp`/`End`:

```python
# alfworld/env/tasks.py:22
self.num_subgoals = len(self.traj['plan']['high_pddl']) - 1  # ignore end noop
```

No hand-pruning beyond that rule is performed anywhere in this preflight.

## C. Does `AlfredTWEnv` expose a programmatic intermediate-subgoal signal?

**Not directly.** `AlfredTWEnv.init_env` requests only
`textworld.EnvInfos(won=True, admissible_commands=True, extras=["gamefile"])`
(`alfworld/agents/environment/alfred_tw_env.py:254`). Measured on a live game:

* `won` — terminal boolean only.
* `score` / `max_score` — **`None`** on ALFWorld games (no scored TextWorld quest ⇒ no native staged reward).
* `intermediate_reward` — a TextWorld per-move "closer/further to a winning state" scalar, **not** an
  ALFRED high-level-subgoal index. Rejected as the subgoal signal.
* `facts` — full PDDL world state, available on request; upstream itself turns it on for the handcoded
  expert (`alfred_tw_env.py:96`).
* `policy_commands` — the PDDL planner's gold plan from the current state (`alfred_tw_env.py:88`).

Symbol sweep results:

| Symbol | Where | Reachable from `AlfredTWEnv`? |
|---|---|---|
| `high_pddl` | `alfworld/env/tasks.py:22,75`; `traj_data.json` | file-side only (harness) |
| `goal_idx`, `num_subgoals`, `finished`, `get_subgoal_idx`, `transition_reward` | `alfworld/env/tasks.py:22-124`, `alfworld/env/thor_env.py:213-235` | **NO — THOR only** |
| `goal_condition_success_rate` | `alfworld/agents/eval/evaluate_*.py` | populated by `AlfredThorEnv` only |
| `facts`, `admissible_commands` | `textworld.EnvInfos` | **YES** |
| `check_subgoal_completion` | `alfworld/agents/expert/handcoded_expert.py:108,347,379,414,444,478,512` | **YES (TextWorld-native)** |

### Why the ALFRED `high_pddl` reward machinery is unusable here

`BaseTask.transition_reward` / `get_subgoal_idx` (`alfworld/env/tasks.py:63-124`) is the canonical
high-level-subgoal tracker, but it is hard-bound to AI2-THOR:

* it consumes `state.metadata` / `state.pose_discrete` AI2-THOR events (`alfworld/env/reward.py:31-52`);
* it needs a THOR navigation graph `graph_obj.Graph(use_gt=True, scene_id=...)` (`tasks.py:49-55`);
* heat/cool/clean predicates read `self.env.heated_objects / cooled_objects / cleaned_objects`, which are
  populated only inside `ThorEnv.step` (`alfworld/env/thor_env.py:195-209`);
* `get_task()` is imported in exactly one place — `alfworld/env/thor_env.py:14` (verified by grep).

⇒ **CASE 2 via `env/tasks.py` is impossible text-only.** Not adopted.

## D. Does an official programmatic high-level-subgoal checker exist for TextWorld?

**Yes — and it is what we adopt (CASE 2).**

`alfworld/agents/expert/handcoded_expert.py` defines, per ALFRED task type, an ordered high-level subgoal
list and a **state-based** completion checker; `alfworld/agents/expert/handcoded_expert_tw.py` supplies the
TextWorld specialisation of its predicates, computed from **PDDL `facts` + `admissible_commands`**.

| Task type | `subgoals` (source) | `check_subgoal_completion` |
|---|---|---|
| `pick_and_place_simple` | `handcoded_expert.py:340-345` (K=4) | `:347-358` |
| `pick_two_obj_and_place` | `:368-377` (K=8) | `:379-398` |
| `look_at_obj_in_light` | `:407-412` (K=4) | `:414-425` |
| `pick_heat_then_place_in_recep` | `:435-442` (K=6) | `:444-459` |
| `pick_cool_then_place_in_recep` | `:469-476` (K=6) | `:478-493` |
| `pick_clean_then_place_in_recep` | `:502-509` (K=6) | `:512-529` |
| TextWorld predicates for all six | `handcoded_expert_tw.py:11-113` | — |

Predicates are PDDL/engine-level, e.g.
`"holds agent {obj}" in facts_wo_num_ids`, `"ishot {obj}" in facts`, `"iscool …"`, `"isclean …"`,
`"inreceptacle {obj} {parent}" in facts_wo_num_ids`, and admissible-command membership
(`"clean {obj} with sinkbasin"`, `"heat {obj} with microwave"`, `"move {obj} to {parent}"`).

`check_subgoal_completion` returns the index of the **next** subgoal to execute, i.e. the number of
completed subgoals ∈ `[0, K-1]`.

This checker is not a side artifact: `AlfredTWEnv` itself instantiates it via
`AlfredExpert` (`alfred_tw_env.py:60-110, 97`), and `AlfredTWEnv.is_solvable`
(`:216-243`) used it to decide which games ship in the dataset at all.

### Adopted validator (harness-only)

`pf_lib.SubgoalMonitor` runs a **second, shadow** `HandCodedTWAgent` instance and replays *verbatim* the
state-update block of upstream `BasePolicy.act`:

```python
# handcoded_expert.py:200   p.update_state_tracking(game_state, last_action)
# handcoded_expert.py:203   p.observe(game_state["feedback"])
# handcoded_expert.py:206   p.subgoal_idx = p.check_subgoal_completion(game_state)
```

Only upstream's *heuristic action selection* (lines 207+) is omitted — it is not part of the checker, and it
is the sole part that consumes RNG and can raise. Intro observation is seeded exactly as
`AlfredExpert.reset` does (`alfred_tw_env.py:105-110`). Nothing is re-implemented.

**Honest limitations (recorded, not worked around):**

1. The checker is *state-based*, so its rank can decrease (e.g. the agent puts the target object back
   down). We log the raw rank; a controlled decision is defined on the **raw current** rank, which is the
   genuine post-`g_j` state ReCoverMem needs. `max_rank` is logged separately for diagnostics only.
2. Two of its predicates (`is_obj_in_obs`, `at_right_recep`) come from upstream's own observation
   bookkeeping (`observe`, `update_state_tracking`) rather than from PDDL facts. This is upstream code used
   unmodified — but it means the checker is "upstream programmatic", not "pure PDDL entailment". It is
   neither an LLM judge nor a step-count proxy, the two disallowed constructions.
3. `K_USABLE` is therefore defined on the **TextWorld** subgoal list (`len(policy.subgoals)`), which is the
   granularity the checker can decide. The ALFRED `len(high_pddl) - 1` count is recorded alongside for
   cross-validation; the two agree on 27/30 frozen games (the 3 exceptions have one fewer `GotoLocation`
   because the ALFRED agent already started at the receptacle).

## Verdict

```
STRUCTURAL_VALIDATOR_GATE = PASS   (CASE 2)
implementation = alfworld/agents/expert/handcoded_expert.py::<TaskType>Policy.check_subgoal_completion
                 + alfworld/agents/expert/handcoded_expert_tw.py::<TaskType>TWPolicy.get_predicates
driver         = pf_lib.SubgoalMonitor (verbatim replay of handcoded_expert.py:200-206)
signal source  = textworld.EnvInfos(facts=True, admissible_commands=True)  [harness-only]
```

Harness-only, never in the agent prompt: `high_pddl`, `traj_data.json`, `facts`, `policy_commands`,
`extra.expert_plan`, subgoal ranks.
