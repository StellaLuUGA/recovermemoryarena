# ALFWorld agent-configuration timeline

## Config A — `AGENT_CONFIG_A_MINIMAL` — CLOSED, PRESERVED

Frozen in `competence/AGENT_FREEZE.md` before any competence call. Definition:

* `admissible_commands` **not** shown to the model (OPTION-A of the section-6 contract);
* OPTION-A action parser with **digit-stripped unique-match snapping** enabled;
* otherwise: Llama-3.1-8B-Instruct, temperature 0, seed 13, one train-split ICL example,
  full raw history, `MAX_AGENT_STEPS = 50`, `MAX_NEXT_SUBGOAL_STEPS = 20`.

Observed outcomes (final, not to be reinterpreted):

```
AGENT_CONFIG_A_MINIMAL = FAIL_SUFFIX_COMPETENCE
  native controlled reachability = 8 / 20
  native full-task success       = 0 / 20
  suffix next-subgoal success    = 0 / 5
```

Disclosed defect of Config A, preserved as part of the record: the digit-stripped snapping rule
could **change a numbered entity the model explicitly named** — observed on frozen games 0, 3 and
16, where `go to desk 1` was executed as `go to desk 2`, 25 times per episode. This defect is why
Config A's parser is not reused.

Artifacts (unmodified, not deleted): `competence/AGENT_FREEZE.md`,
`competence/NATIVE_20_REPORT.md`, `competence/native_20.jsonl`,
`competence/SUFFIX_FEASIBILITY.md`, `competence/suffix_feasibility.json`,
`ALFWORLD_PREFLIGHT_REPORT.md`, `ALFWORLD_PREFLIGHT.json`.

## Ordering of events

1. Environment gates run and passed: structural census 30/30, subgoal-validator audit +
   expert-execution verification, replay gate 9/9.
2. Config A frozen (`competence/AGENT_FREEZE.md`), then executed: native-20, then suffix-5.
3. Config A **closed** at `FAIL_SUFFIX_COMPETENCE` and its artifacts written.
4. **Only then** was Config B created, on explicit instruction, as the single authorised
   follow-up configuration.

**At the moment Config B was created, no ReCoverMem outcome of any kind existed for ALFWorld.**
No Mem0 instance, no `B_mem`/`B_rec`, no `R_mem`/`R_rec`, no scorer, no AUROC, no CRC, no FS, no
coverage, no Table 1, no Table 2 had been produced for this domain. Config B was therefore not
selected against any ReCoverMem result.

## Config B — `AGENT_CONFIG_B_ADMISSIBLE_COMMANDS` — the final candidate

Exactly two authorised changes relative to Config A:

1. **entity-preserving exact parser** — all fuzzy/digit-stripped matching removed; the parser may
   normalise only whitespace, wrapping quotes, an optional `ACTION:` prefix, a trailing period and
   letter case. It can never alter an action verb, an object identity, a receptacle identity or a
   numeric suffix.
2. **`admissible_commands` shown to the model** at every step (OPTION-B of the section-6
   contract) — standard, benchmark-observable TextWorld interface information, not oracle
   information.

Everything else — model, temperature, seed, horizons, system prompt body, ICL example, history
and observation serialisation, inventory handling — is carried over unchanged.

Config B is evaluated on a **disjoint** 20-game set (see `FROZEN_CONFIG_B_20.json`); every game
used anywhere in the Config-A line (frozen structural-30, native-20, suffix-5, replay and
validator verification) is excluded. Config A and Config B are therefore **not** an ablation pair
and no statistical comparison between them is claimed.

If Config B fails, ALFWorld is closed as a main-table candidate. No Config C will be attempted in
this experiment line.
