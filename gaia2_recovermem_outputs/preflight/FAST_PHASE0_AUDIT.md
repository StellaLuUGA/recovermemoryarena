# Gaia2 / ARE — fast Phase-0 eligibility audit for ReCoverMem

Static audit only. **No model inference, no external API, no LLM judge, no ReCoverMem
outcome inspected.** The upstream Meta ARE repository was not modified; every artifact is
under `gaia2_recovermem_outputs/`.

- Repo: `https://github.com/facebookresearch/meta-agents-research-environments.git`
- **Commit `87ebd38f31aafae0f11e14f55617903196236cfb`** (2026-08-26)
- Dataset: `meta-agents-research-environments/gaia2`, local HF cache, fingerprint
  `78ea3bdbdeec2bdcd6afa5420915d8a22f23ed99`, 2.3 GB, **nothing downloaded**
- Machine-readable: `fast_phase0_audit.json`

## Decision

```
MAIN_TABLE_DECISION = FAIL
```

Blocking condition: **`HARD_AND_CLEAR_SCENARIOS = 0`** against a requirement of 72, because
**every multi-turn Gaia2 scenario requires the LLM judge**.

## What counts as a turn and a decision

From `are/simulation/scenarios/scenario.py:298 build_event_id_to_turn_idx`:

> the turn of an event is the number of `send_message_to_user` events among its ancestors

So a **turn boundary is literally an `AgentUserInterface.send_message_to_user` event**.
`nb_turns` = max turn index + 1.

A **scored decision** is one `OracleEvent` of `event_type=AGENT`, which the judge
(`GraphPerEventJudge._match_agent_oracle_event`) tries to match to an agent event under a
causality constraint. ReAct/reasoning steps are neither turns nor scored decisions and were
not counted as such.

## A. Multi-turn census

Configs loaded: `adaptability`, `ambiguity`, `execution`, `search`, `time` — 160 scenarios
each, split `validation`. `mini` (160 rows) is a subset drawn from those five and was
**excluded to avoid double-counting**; `demo` is tutorial content.

```
TOTAL_SCENARIOS        = 800     (800 unique scenario_id, 800 unique content hashes)
1-turn                 = 576
2-turn                 = 206
3-turn                 =  18
MULTITURN_SCENARIOS    = 224
```

User messages per scenario: 1 in 799 scenarios, 2 in one. Multi-turn structure therefore
comes from the agent's own `send_message_to_user` boundaries, not from repeated user input.

Multi-turn by capability: **adaptability 160, time 63, ambiguity 1** — `execution` and
`search` contribute **zero** multi-turn scenarios.

Oracle AGENT events: 5,342 in total across 800 scenarios.

## B. Hard-verifier census — the blocker

`validation/tool_judge.MildToolJudge.compare` runs the hard judge first, then:

```python
hard_comparison = self.hard_judge(agent_event, oracle_event, **kwargs)
if not hard_comparison or self.soft_judge.no_arg_to_check:
    return hard_comparison
return self.soft_judge(agent_event, oracle_event, **kwargs)   # LLM
```

and `SoftToolJudge.no_arg_to_check` is True **iff no argument of that tool is registered as
`CheckerType.llm_checker`**. So a scored decision is PROGRAMMATIC_HARD exactly when its tool
has no `llm_checker` argument.

Of the 89 tools in `TOOL_ARG_CHECKER_TYPE_REGISTRY`: **61 programmatic-hard, 28 LLM-judged**.
Default judge engine is `meta-llama/Meta-Llama-3.3-70B-Instruct` through LiteLLM with
provider `huggingface` — an **external API**.

Scored-event totals over all 800 scenarios:

| class | count |
|---|---|
| PROGRAMMATIC_HARD | 2,412 |
| LLM_JUDGE | 2,930 |
| HYBRID | 0 (the mild judge is hard-then-soft per tool, so a tool is one or the other) |
| UNKNOWN | **0** (every oracle tool is in the registry) |

The decisive fact:

> **`AgentUserInterface__send_message_to_user` is registered with an `llm_checker` argument,
> and it is also the turn delimiter.**

Therefore every multi-turn scenario contains at least one LLM-judged scored event — verified
directly: **224 / 224 multi-turn scenarios contain a `send_message_to_user` oracle event.**

```
scenarios with ZERO LLM-judged scored events            =  13   (all 1-turn: 11 execution, 2 time)
multi-turn with >= 2 PROGRAMMATIC_HARD decisions        = 173
  ... and ZERO LLM-judged decisions                     =   0
multi-turn with hard decisions spread over >= 2 turns   =  91
  ... and ZERO LLM-judged decisions                     =   0
```

LLM-judged events per multi-turn scenario: min 1, median 6, max 11.

## C. Scenario independence / reset — **INDEPENDENT_RESET**

Each benchmark scenario is rebuilt from its own released JSON row
(`scenario_imported_from_json`), so no mutable state is shared between formal scenarios.
The explicit reset is `Scenario.soft_reset()` (`scenarios/scenario.py:181`):

1. `app.reset()` per app (which reseeds `random.Random(self.seed)`),
2. `app.load_state(json.loads(self._initial_apps[name]["serialized_state"]))`,
3. `apply_augmentation_configs()`,
4. `app.set_seed(self.seed)` per app.

`Environment.reset_app_states()` (`environment.py:361`) calls `app.reset()` across the board.
Concrete `get_state`/`load_state` exist for calendar, contacts, email_client, messaging,
shopping, cab, city, apartment_listing and virtual_file_system.

Mechanism kind: **in-process state reload** (scenario reconstruction from JSON is also
available and would be equally clean, just slower).

## D. Checkpoint / restore — **RESTORE_SUPPORTED**

Cheapest valid mechanism: **per-app `get_state()` / `load_state()` snapshot**, optionally
with `Environment.get_state()` (`environment.py:337`), which serializes apps + `event_log` +
`event_queue` + `current_time`. `App._skip_deepcopy_fields` shows apps are deepcopy-safe, so
an in-process snapshot/restore around a controlled decision is feasible.

Alternative: `are/simulation/replay.py::replay_logs(world_logs, env)` — deterministic replay
from the world log.

Caveats recorded, not resolved:

- the environment runs a time-based loop on a background thread; a checkpoint must
  `pause()` first;
- `app.reset()` reseeds from `app.seed`, so RNG-dependent apps restore correctly only if the
  seed is restored with the state;
- **replay determinism was not empirically verified** — Phase 0 did not run the environment.

## E. Observable-history boundary — **OBSERVABLE_BOUNDARY_CLEAN**

`Environment.process_event` (`environment.py:646`):

```python
if type(event) is OracleEvent:
    if self.oracle_mode:
        ...
    else:
        logger.debug(f"Oracle event {event.event_id} ignored as oracle_mode = False")
```

`EnvironmentConfig.oracle_mode` defaults to `False`, and `dump_dir` / `queue_based_loop` are
rejected outright unless oracle mode is on. In agent mode oracle events are neither executed
nor logged, so the gold solution never enters the agent's observation stream.

`H_t` for ReCoverMem would be `Environment.get_world_logs()` plus AUI messages and tool
observations. The oracle events, the oracle graph and the judge state live in a separate
object graph under `are/simulation/validation/` and are structurally separable. No leakage
shortcut would be needed.

## F. Cross-turn memory dependence

Structural classification only — token overlap between argument/message strings introduced
in earlier turns and those required in a later turn, plus DAG ancestry of a later-turn oracle
event on a non-boundary earlier-turn event. No agent correctness, no ReCoverMem output.

```
CLEAR_CROSS_TURN_DEPENDENCE     = 224 / 224
POSSIBLE_CROSS_TURN_DEPENDENCE  =   0
NO_CROSS_TURN_DEPENDENCE        =   0
```

Every multi-turn Gaia2 scenario is genuinely cross-turn memory dependent. **This axis passes
completely** — the benchmark is well designed for exactly the property ReCoverMem targets.

## Final tally

| quantity | value |
|---|---|
| TOTAL_SCENARIOS | 800 |
| MULTITURN_SCENARIOS | 224 |
| HARD_MULTITURN_SCENARIOS (≥2 hard decisions, loose) | 173 |
| HARD_MULTITURN_SCENARIOS (…and no LLM judge, strict) | **0** |
| CLEAR_MEMORY_DEPENDENT_SCENARIOS | 224 |
| **HARD_AND_CLEAR_SCENARIOS** | **0** (required ≥ 72) |

| PASS condition | status |
|---|---|
| HARD_AND_CLEAR ≥ 72 | **FAIL** (0) |
| valid independent reset | PASS |
| checkpoint/restore or deterministic replay | PASS |
| observable-history boundary clean | PASS |
| no mandatory external API for the selected subset | PASS for the environment; **FAIL** for validation |
| no mandatory LLM judge for the selected subset | **FAIL** |

```
MAIN_TABLE_DECISION = FAIL
```

## The exact structural blocker

Gaia2 defines a turn as the interval between `send_message_to_user` calls, and it scores that
very call with an LLM checker on its free-text `content`. Multi-turn-ness and LLM judging are
therefore the **same** structural feature, not two independent properties that happen to
co-occur. There is no subset of the released benchmark that is simultaneously multi-turn and
judge-free, and no amount of scenario filtering can create one.

Three things were deliberately **not** done to rescue it:

1. **No local Llama judge substituted for the released 70B judge.** That would change the
   labelling function, and the brief forbids manufacturing a hard-verifiable subset this way.
2. **No scoring of only the hard sub-events.** One could define `R` over just the
   PROGRAMMATIC_HARD oracle events inside a multi-turn scenario (173 scenarios qualify with
   ≥2 such events). That is a *derived* per-decision label, not Gaia2's released validation
   semantics — the released judge requires the whole oracle graph to match, turn boundary
   included. Adopting it would be altering validation semantics to make the experiment pass.
3. **No lowering of the 72-scenario requirement.**

## Is Gaia2 still useful to ReCoverMem?

**Yes — as an appendix / qualitative executable-agent setting, not for the main table.**

What it uniquely offers, all verified above: a clean per-scenario reset, real
checkpoint/restore, a genuinely clean observable/oracle boundary, and 224 scenarios with
*universal* clear cross-turn memory dependence. That is a better executable-agent substrate
than anything else audited so far — the failure is purely in how correctness is measured.

Ranked options:

1. **Appendix, hard-sub-event protocol (recommended if Gaia2 is wanted at all).** Restrict
   scoring to PROGRAMMATIC_HARD oracle events inside multi-turn scenarios — 173 scenarios,
   ≥2 hard decisions each, all CLEAR cross-turn. Fully local, no judge, no external API. It
   must be labelled explicitly as a **derived** metric that is not Gaia2's released
   validation, and reported in the appendix only.
2. **Transfer-only.** Import τ from another domain, report FS/Cov on Gaia2 without in-domain
   calibration. Does not avoid the judge problem for computing `R_mem`, so it only helps if
   combined with option 1.
3. **Qualitative example.** Use one or two scenarios to illustrate the TRUST/RECOVER
   mechanism in an executable agent, with no calibration claim.
4. **Full formal with the released judge.** Would require ~2,930 calls to a 70B judge over an
   external API. Out of scope under the current constraints.

Not recommended: any variant that presents a derived hard-sub-event score as Gaia2's official
accuracy.

## Stop

Per the brief, Phase 0 FAIL ⇒ **stop**. No smoke was run, no split frozen, no scorer trained,
no scientific route outcome inspected. `candidate_scenarios.json` records the 173-scenario
option-1 pool for reference only; it is **not** a frozen formal split.
