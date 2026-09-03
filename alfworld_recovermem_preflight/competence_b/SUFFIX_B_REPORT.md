# Config B — next-subgoal suffix feasibility (section 8)

```
B_B = 0 / 5   ->  ALFWORLD_CONFIG_B_PREFLIGHT = FAIL_SUFFIX_COMPETENCE
```

## Protocol
Six games reached a controlled state (idx 5, 6, 7, 12, 13, 19); the **first 5 in frozen order**
were used: idx **5, 6, 7, 12, 13**.
Each game's action prefix was frozen at its **first genuine controlled state**, the game was
fresh-reset, the prefix replayed exactly, and the harness-side subgoal rank required to match.

**Replay integrity: 5/5 exact rank matches** (`replay_rank_matches_native = true`), independently
re-confirming the environment-level replay gate.

Config B was then resumed from that state with the current observable state, the full observable
raw history, and the current `admissible_commands` — no Mem0, no compression, no ReCoverMem
scorer — for at most `MAX_NEXT_SUBGOAL_STEPS = 20`. Success iff the next official subgoal is
completed according to the verified harness-only monitor.

## Results

| idx | task type | prefix | rank₀ | next official subgoal | target | steps | invalid | success |
|---|---|---|---|---|---|---|---|---|
| 5 | pick_and_place_simple | `go to cabinet 1` | 1 | `take peppershaker` | 2 | 20 | 19/20 | ✗ |
| 6 | pick_heat_then_place_in_recep | `go to cabinet 1` | 1 | `take mug` | 2 | 20 | 20/20 | ✗ |
| 7 | pick_two_obj_and_place | `go to desk 1 → go to desk 2` | 1 | `take cd` | 2 | 20 | 20/20 | ✗ |
| 12 | look_at_obj_in_light | `go to desk 1` | 1 | `take alarmclock` | 2 | 20 | 20/20 | ✗ |
| 13 | pick_clean_then_place_in_recep | `go to countertop 1` | 1 | `take egg` | 2 | 20 | 20/20 | ✗ |

Commands issued across the 100 suffix steps:

* idx 5 — `go to cabinet 2` ×19, `go to cabinet 1` ×1
* idx 6 — `go to cabinet 1` ×20
* idx 7 — `go to desk 2` ×20
* idx 12 — `go to desk 1` ×20
* idx 13 — `go to countertop 1` ×20

In every case the required action (`take <obj> from <recep>`) was **present in the admissible
command list shown to the model at every one of those 20 steps**, and the object was named in the
observation immediately above. The agent issued **zero** `take` actions in 100 suffix steps; 99
of 100 actions were inadmissible repetitions.

## Interpretation

The environment, the exact-replay mechanism and the upstream subgoal checker all behaved
correctly — the target subgoal was one legal, explicitly-listed action away and would have been
detected the instant it fired. Nothing here indicates that deeper ALFWorld subgoals are
unreachable in principle; `B_B = 0` is a frozen viability stopping rule, and it is the agent that
stops.

Config B was the single authorised follow-up configuration. Per the pre-registered rule it fails,
and **ALFWorld is closed as a ReCoverMem main-table candidate**. No Config C is attempted: no
backbone change, no temperature change, no anti-loop prompting, no expert actions.

Raw record: `competence_b/suffix_b.json`.
