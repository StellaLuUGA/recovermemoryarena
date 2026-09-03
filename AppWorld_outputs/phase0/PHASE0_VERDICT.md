# PHASE0_VERDICT.md — AppWorld

Recorded: 2026-08-27. Repo pin: a072b7a (clean). Model: Qwen3-32B-AWQ, local vLLM.

## Gate summary

| gate | verdict | evidence |
|---|---|---|
| native competence | **PASS** | TGC 5/15 = 33.3% (`../native_viability/official_metrics.json`) |
| task-dependence | **PASS (weak)** | `task_dependency_audit.json` |
| state-restore | **PASS (conditional)** | `probes/results/*_a.json`, `*_b.json` |
| observability | **PASS** | `OBSERVABILITY_AUDIT.md` |
| utility-granularity | **FAIL (degenerate)** | `UTILITY_GRANULARITY_AUDIT.md` |

## Verdict

```
DO NOT PROCEED to the 3-task paired ReCoverMem smoke.
```

The precondition "all structural gates pass" is not met. The utility-granularity gate fails
on the same axis Gaia2 failed, so the AppWorld substitution does not buy what it was meant
to buy.

## Gate detail

### task-dependence — PASS (weak)

13/15 pilot tasks have `max_substantive_span >= 2` (median 3, max 8). Two do not:
b119b1f_1 (span 0, 0 edges — genuinely shallow, and it scored 0/6) and 23cf851_3 (span 1).

Weakness: **0/15 tasks have a multi-source accumulator**, and `accumulator_feeds_answer` is
false for all 15. The audit's second qualifying criterion never fires; every task qualifies
on span alone. Median `answer_span` is 0 — for 11/15 tasks the *answer* does not sit at the
end of a long dependency chain even where the *actions* do.

### state-restore — PASS, conditional on fresh-process protocol

Protocol B (restore into a fresh process), 4/4 tasks, all checks pass:
`fresh_restore_matches_checkpoint_db`, `fresh_replay_matches_original_mutation_db`,
`fresh_replay_matches_original_output`, `frozen_datetime_correct`, `python_namespace_is_clean`.

Protocol A (in-process restore), 4/4 tasks, two consistent failures:
- `interaction_counter_rolled_back: FAIL` — counter is monotonic (2 → 4), survives restore
- `python_namespace_rolled_back: FAIL` — the interpreter namespace is not rolled back

DB restore itself is exact and replay is deterministic under both protocols.

Two hard operational constraints:
1. **One AppWorld instance per process.** Constructing a second in the same process raises
   `IndexError: pop from empty list` from freezegun (`common/time.py:118`) — global
   time-freezer state leaks. The original single-process probe run died on exactly this.
2. `world.close()` always raises `AttributeError: '_freeze_time' object has no attribute
   'fake_names'`. Cosmetic (teardown only, after state is flushed) but must be caught.

Note: 0b9a2f6_1 was in the probe target list but does not exist in the dataset — the probe
covers 4 tasks, not 5.

### utility-granularity — FAIL (degenerate)

`world.evaluate()` is readable against the live DB at any step — mechanically decision-level,
better than Gaia2. But replaying all five solved tasks shows the utility is **flat for
85–92% of the episode and moves only at the last 1–2 steps**: mean 1.4 transitions per
episode, range 1–2.

Cause: the native ReAct code-agent reads for most of the episode and mutates state in one
terminal burst; AppWorld's only shipped utility is an end-state predicate, so read steps are
utility-invisible.

`T_i ∈ {1,2}` does not support the FS/Cov machinery any better than the Gaia2 multi-turn
subset already judged "workable but thin".

## What is frozen regardless

The 15-task run stands as **pilot-only** and is not a headline number: n=15, CI ≈ ±12pp.
Manifest `frozen_before_any_model_run_on_dev: true` holds; nothing was tuned, removed, or
resampled.

## Open decision (not taken here)

Either (a) accept `T_i ≈ 1.4` and reformulate at episode level — the same concession Gaia2
forced, or (b) find a benchmark whose shipped utility moves with intermediate decisions.
Making the agent mutate incrementally would raise `T_i` but is a prompt/agent change and
would void the native baseline.
