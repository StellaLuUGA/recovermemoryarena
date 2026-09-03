# ALFWorld → ReCoverMem preflight report

**Question asked:** can ALFWorld serve as the third executable-agent domain for ReCoverMem?
**Answer:** the *environment* qualifies on every structural criterion; the *frozen agent* does not
clear the competence stopping rule.

```
ALFWORLD_PREFLIGHT = FAIL_SUFFIX_COMPETENCE
```

## Frozen configuration

| | |
|---|---|
| ALFWorld | 0.5.0 (`aaba687`), `/home/aristella/recoverappworld/alfworld` |
| Environment | `AlfredTWEnv` only — no AI2-THOR, no MaskRCNN, no visual ALFWorld |
| Split | `eval_out_of_distribution` = `valid_unseen` = 134 games |
| Python | `/home/aristella/miniconda3/envs/alfworld/bin/python`; textworld 1.7.0, jericho 3.3.1 |
| Data | `/home/aristella/.cache/alfworld` |
| Model | `llama-3.1-8b-instruct-local` @ `http://localhost:8123/v1`, temperature 0 |
| Seed | 13 |

## Gate-by-gate

| § | Gate | Requirement | Result | |
|---|---|---|---|---|
| 1 | structural validator exists | CASE 1 or CASE 2, no LLM judge, no step-count proxy | CASE 2 | **PASS** |
| 3 | 30-game structural census | ≥ 20/30 with `K_USABLE ≥ 2` | **30/30** | **PASS** |
| 4 | validator verified by expert execution | g₁ + g₂ detected, ordered, no false early | 3/3 games, 2 independent expert sources | **PASS** |
| 5 | state replay | 9/9 semantic matches | **9/9**, zero diff fields | **PASS** |
| 8 | native controlled reachability | W ≥ 5 | **W = 8/20** | **PASS** |
| 9 | next-subgoal suffix feasibility | B ≥ 2 | **B = 0/5** | **FAIL** |

## What passed, and why it matters

**Programmatic intermediate progress exists text-only.** The ALFRED `plan.high_pddl` reward
machinery (`alfworld/env/tasks.py` → `transition_reward`, `goal_idx`, `get_subgoal_idx`) is
unusable here — it is hard-bound to AI2-THOR event metadata and a THOR navigation graph, and
`get_task` is imported by `alfworld/env/thor_env.py` and nowhere else. But ALFWorld ships a
*second*, TextWorld-native official checker: `<TaskType>Policy.check_subgoal_completion` in
`alfworld/agents/expert/handcoded_expert.py`, with predicates computed from PDDL `facts` and
`admissible_commands` in `handcoded_expert_tw.py`. `AlfredTWEnv` instantiates it itself
(`AlfredExpert`), and `AlfredTWEnv.is_solvable` used it to decide which games ship at all. We run
it verbatim as a shadow monitor; nothing was re-implemented and no LLM judge is involved.
Full derivation, caveats and line references: `structural/SUBGOAL_SEMANTICS_AUDIT.md`.

**K_USABLE ≥ 2 everywhere.** 30/30 frozen games; K = 4 (`pick_and_place_simple`,
`look_at_obj_in_light`), 6 (heat/cool/clean), 8 (`pick_two_obj_and_place`); median 6, max 8.
Every index 0…K−1 is reachable by the checker (AST-verified per task type). The TW subgoal count
agrees with ALFRED's own `len(high_pddl) − 1` on 27/30 (the 3 exceptions have one fewer
`GotoLocation` because the ALFRED agent already started at the receptacle).

**The checker fires where it should.** Verified on 3 games against two *independent* upstream
gold executions — the handcoded `HandCodedTWAgent` and the PDDL planner plan exposed as
`EnvInfos.policy_commands`. All 6 runs win; g₁ and g₂ are detected in order; and the detector
never claims "object taken" before the raw PDDL fact `holds agent <object_target>` becomes true.

**Replay is exact.** 3 games × 3 reconstructions: observation text, admissible commands, PDDL
facts, subgoal rank, won/done all identical to the reference, with no normalisation beyond sorting
unordered collections. Section 9 independently reproduced the native rank in 5/5 replays. Exact
action-prefix reconstruction of a controlled state — the thing ReCoverMem's controlled branch
needs — works.

**Controlled decisions are reachable natively.** 8/20 episodes reached a state with ≥ 1 official
subgoal complete and ≥ 1 remaining, above the pre-registered W ≥ 5.

## What failed

**B = 0/5.** From each reconstructed controlled state, with the full raw observable history and no
memory module, the frozen agent completed the next official subgoal in 0 of 5 attempts within 20
steps — even though in all five cases that subgoal was a *single admissible action* away
(`take <obj> from <recep>`, object visible in the current observation). The agent never emitted a
`take` in 100 suffix steps.

The cause is agent competence, not environment structure. Across the native probe the mean number
of *distinct* actions per 50-step episode is 2.6 and the mean longest repeated-action streak is
36: greedy temperature-0 Llama-3.1-8B-Instruct locks onto one action (typically
`go to <receptacle it is already at>` → `Nothing happens.`) and never escapes. Native full-task
success is 0/20, and only 1/20 episodes ever got the object into its hand.

**Harness defect, disclosed not repaired.** The frozen OPTION-A parser's rule 3 (digit-stripped
unique match) can substitute a *different numbered entity* than the model named — on the three
`look_at_obj_in_light` games it turned `go to desk 1` into `go to desk 2` 25 times per episode,
making the agent oscillate. This is a harness bug. It was left in place because the
admissible-command policy was pre-registered in `competence/AGENT_FREEZE.md` and W had already
been observed; silently repairing it and re-running would be exactly the outcome-driven retuning
the freeze exists to prevent. It did not manufacture any of the 8 controlled decisions — each
arises from a verbatim, unsnapped model action.

## History-length diagnostic (not a gate)

Over all 216 controlled states, raw observable history `H_t`: median 553.5, p75 831.8, p90 1875.5,
max 2762 tokens (Llama-3.1-8B tokenizer); at each episode's *first* controlled state, median
201.5, max 275. Current-state `x_t` median 4 tokens. Full prompts peak at 3452 tokens against a
32 768-token window. As pre-registered this is not grounds for rejection — ALFWorld's value to
ReCoverMem would be executable-agent generality with a native programmatic intermediate-progress
signal, not long-context pressure. It does mean ALFWorld would exercise a very different regime
from MemoryArena.

## Recommendation

Nothing about ALFWorld the *environment* blocks it: the validator, the census, and the replay
gate all pass cleanly, and controlled decisions are reachable. The blocker is that
Llama-3.1-8B-Instruct at temperature 0, under this deliberately minimal frozen agent, is not
competent enough to advance one subgoal from a genuine controlled state.

Before any formal ReCoverMem collection, section 6 would need an explicit **re-freeze** and
sections 7–9 a clean re-run. The two changes with the clearest mechanical link to B are:

1. fix parser rule 3 so a snap can never change an entity number the model wrote;
2. reconsider the admissible-command policy — option B of the section-6 contract (showing the
   admissible command list to the model) is the standard ALFWorld configuration in the literature
   and directly targets the observed repetition of inadmissible actions.

Both are pre-registration decisions, not something to decide from these outcomes. No such re-run
was performed here.

## Not run, by design

No Mem0, no `B_mem`/`B_rec`, no `R_mem`/`R_rec`, no scorer training, no AUROC, no CRC, no FS, no
coverage, no Table 1, no Table 2.

## Artifacts

```
structural/SUBGOAL_SEMANTICS_AUDIT.md          source audit, line-referenced
structural/FROZEN_30_GAMES.json                frozen list + per-file sha256 + list hash
structural/STRUCTURAL_CENSUS.json              per-game K_USABLE, reachable ranks, summary
structural/SUBGOAL_VALIDATOR_VERIFICATION.json section-4 expert traces + checks
replay/REPLAY_GATE.md, replay/replay_gate.json
competence/AGENT_FREEZE.md                     written before the probe
competence/ICL_EXAMPLE.json                    the one train-split in-context example
competence/NATIVE_20_REPORT.md, competence/native_20.jsonl
competence/SUFFIX_FEASIBILITY.md, competence/suffix_feasibility.json
ALFWORLD_PREFLIGHT_REPORT.md, ALFWORLD_PREFLIGHT.json
logs/                                          stdout of each stage
pf_lib.py, agent.py, make_icl.py, stage1..stage5*.py
```
