# OBSERVABILITY_AUDIT.md — AppWorld

Recorded: 2026-08-27. Repo pin: a072b7a. Evidence: `../native_viability/native_results.jsonl`
(15/15 tasks, all fields populated), collector at `../native_viability/run_phase0.py:114-190`.

## What is observable to the CONTROLLER at decision time (no oracle)

| signal | source | verified |
|---|---|---|
| execution success/failure per step | `world.execute()` return string, `"Execution failed"` prefix | yes — 177/324 flagged across the run |
| full stdout/traceback per step | same return string | yes |
| API calls issued, per app | `logs/api_calls.jsonl` | yes — 0..352 per task |
| interaction count | `len(world.environment_io)` | yes |
| task-completed flag | `world.task_completed()` | yes — non-oracle, agent-driven |
| prompt tokens per turn / context growth | `logs/lm_calls.jsonl` usage | yes — per-turn series recorded for all 15 |
| context-limit hit | scan of lm_calls blob | yes — false for all 15 |

None of these require ground truth. The controller can be built on them without oracle leakage.

## What is NOT observable without the oracle

Requirement-level pass/fail (`TestTracker`) needs `task.ground_truth`. `AppWorld.evaluate()`
raises if the task has no ground truth (environment.py:1121). So the utility signal is
**PASS-2 / offline only** — same constraint as Gaia2's `are-benchmark judge`.

## Post-hoc completeness

Per task AppWorld writes `logs/environment_io.md`, `logs/api_calls.jsonl`,
`logs/lm_calls.jsonl`, and `dbs/` (full end-state). `AppWorld.parse_environment_io_log()`
round-trips the trajectory well enough to **replay it into a fresh world** — demonstrated by
`probes/replay_probe.py`, which reproduced all five solved tasks step-for-step and reached
identical final verdicts. Trajectory reconstruction is lossless for replay purposes.

## Classification

```
PASS
```

Decision-time observability is sufficient for a non-oracle controller; utility is
oracle-gated but obtainable offline; trajectories are replayable. No blocker.

## Caveat

`observable_history_tokens` is recorded as `max(prompt_tokens_by_turn)`, i.e. the largest
single prompt, not a true observable-history size. Adequate as a context-growth proxy;
do not read it as a memory-footprint measurement.
