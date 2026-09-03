# UTILITY_GRANULARITY_AUDIT.md — AppWorld

Recorded: 2026-08-27. Repo pin: a072b7a (see REPO_PIN.md).
Probes: `probes/util_gran_probe.py`, `probes/replay_probe.py`; results in `probes/results/replay_*.json`.

## Candidates examined

| candidate | present in AppWorld? | evidence |
|---|---|---|
| 1. per-action verifier/checker | **no** | no per-execution verdict exists anywhere |
| 2. per-milestone state predicate | **yes, mechanically** | `TestTracker` returns N independent requirement-level assertions (`passes` / `failures`), N = 2..10 in the pilot |
| 3. write-action verifier | **no** (not separate) | writes are judged only through end-state predicates |
| 4. app-state mutation vs expected state | **yes** | `evaluate_task` (evaluator.py:452) builds a `ModelCollectionPair(start, end)` and asserts over the diff |
| 5. explicit DAG node completion | **no** | requirements are unordered assertions, not a DAG |
| 6. only final episode verifier | **no — readable at any step** | `AppWorld.evaluate()` (environment.py:1115) runs against the *live* DB; verified working mid-episode |

## Classification

```
MIXED — decision-level in mechanism, EPISODE-LEVEL in practice
```

## The mechanism genuinely is per-decision

`evaluate_task` compares task-initial DB against **current** DB. It does not require the
episode to be finished. Probed directly (`util_gran_probe.py`, task 50e1ac9_1): `world.evaluate()`
called at steps 0/1/2/3 of a live environment returned a valid per-requirement verdict every
time, no exception, no episode-end requirement. This is strictly better than Gaia2, where
only an aggregate `Judgment.success` is exposed.

## The catch, and it is the same catch as Gaia2

Readable at every boundary is not the same as *discriminating* at every boundary. All five
tasks the native agent solved were replayed step-by-step with the evaluator read after each
step (`replay_probe.py`). Utility curve = number of passing requirements after each step:

| task | steps | tests | distinct levels | transitions | curve |
|---|---|---|---|---|---|
| 23cf851_3 | 7 | 2 | 2 | **1** | `1,1,1,1,1,1,1,2` |
| 6bdbc26_3 | 8 | 2 | 2 | **1** | `1,1,1,1,1,1,1,1,2` |
| d4e9306_2 | 10 | 6 | 3 | **2** | `1,1,1,1,1,1,1,1,1,5,6` |
| 68ee2c9_1 | 10 | 5 | 3 | **2** | `1,1,1,1,1,1,1,1,1,4,5` |
| 6c2c621_3 | 12 | 8 | 2 | **1** | `1,1,1,1,1,1,1,1,1,1,1,1,8` |

**Mean controlled decisions per episode: 1.4 (range 1–2).**

The cause is mechanical, not incidental. The `simplified_react_code_agent` spends the
episode issuing *read* APIs (`show_*`), then performs every state mutation in one or two
terminal code blocks. Because the only utility AppWorld ships is an end-state predicate,
every read step is utility-invisible: the curve is flat at its floor for 85–92% of the
episode and then jumps once.

The floor is not zero (`passes = 1` from step 0) — one requirement is satisfied by the
initial state before the agent acts at all, so even the floor is not a clean "nothing done yet".

## Consequence for ReCoverMem

This is the same failure mode documented for Gaia2 in
`RecoverMemMinimal/update_replicate/ARE_outputs/phase0/UTILITY_GRANULARITY_AUDIT.md`
(72% of scenarios = 1 turn), reached by a different route. The FS/Cov machinery assumes
`T_i` controlled Trust/Recover decisions per episode. AppWorld delivers `T_i ∈ {1,2}`,
mean 1.4 — thinner than MemoryArena Bundled Shopping's 5-by-construction, and no better
than the Gaia2 multi-turn subset that was already judged "workable but thin".

Raising `T_i` would require making the agent mutate state incrementally (a prompt/agent
change) — explicitly out of scope for Phase 0, and it would break the byte-for-byte native
baseline.

## Sample caveat

n = 5 (every task the native agent solved). Failed tasks were not replayed: their curves
cannot rise to success and so cannot bound `T_i` from below in a meaningful way. The five
agree in both shape and mechanism, and the mechanism explains the shape, but 5 is 5.
