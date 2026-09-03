# Frozen ALFWorld text agent — ReCoverMem preflight (written BEFORE the 20-game probe)

## Model
| | |
|---|---|
| model id | `llama-3.1-8b-instruct-local` (Meta Llama-3.1-8B-Instruct) |
| endpoint | OpenAI-compatible vLLM, `http://localhost:8123/v1` |
| max_model_len | 32768 |
| temperature | `0` |
| top_p | `1.0` |
| seed | `13` |
| max_tokens per action | `32` |
| stop | `["\n"]` |

## Environment
`AlfredTWEnv`, split `eval_out_of_distribution` (= valid_unseen), batch_size 1,
`domain_randomization=False`, env `max_episode_steps=200` (never the binding limit).

## Horizons (frozen)
```
MAX_AGENT_STEPS        = 50   # full native episode
MAX_NEXT_SUBGOAL_STEPS = 20   # section-9 controlled branch
```

## What the agent may see (benchmark-observable ONLY)
1. the task instruction, as it appears in the initial observation;
2. the initial room observation;
3. every prior action it issued and the environment's verbatim response;
4. the current observation;
5. the `inventory` **action** (part of the public grammar) and its observation — note that the
   `textworld.EnvInfos.inventory` *field* is `None` on ALFWorld games, so nothing is injected
   into the prompt; the agent must issue `inventory` itself if it wants to know;
6. the public action grammar (`textworld.EnvInfos.command_templates`, printed verbatim below);
7. one in-context example trajectory drawn **from the `train` split**.

## What the agent must NEVER see (harness-only)
`plan.high_pddl`, `traj_data.json`, PDDL `facts`, `policy_commands`, `extra.expert_plan`,
target object/receptacle ids not present in an observation, future subgoals, and the
subgoal-completion rank produced by `pf_lib.SubgoalMonitor`.

## `admissible_commands` policy — **OPTION A (frozen)**
`admissible_commands` is **never shown to the model**. It is used only as an
action-validity parser/checker, by this frozen rule, applied to the model's raw text:

1. take the first non-empty line; strip whitespace, a leading `>`, and wrapping
   quotes/backticks; lowercase; strip a trailing `.`;
2. if the result is in `admissible_commands` → issue it;
3. else compute the digit-stripped, whitespace-normalised form of the result and of every
   admissible command. If **exactly one** admissible command matches → issue that command and
   record `snapped = True` (e.g. `take mug from shelf 3` → `take mug 1 from shelf 3`);
4. else record `invalid_action = True` and issue the normalised string verbatim; TextWorld
   answers `Nothing happens.`

An empty model output is issued as `look`. This policy is frozen for the whole preflight
(native probe and section-9 suffix runs) and is not revisited after seeing results.

## In-context example (exactly one, frozen)
`competence/ICL_EXAMPLE.json` —
`train/pick_and_place_simple-SoapBottle-None-GarbageCan-407/trial_T20190908_063232_403749`,
9 steps, produced by the **upstream** `HandCodedTWAgent`.
Selection rule: train split → `sorted()` → `random.Random(13).shuffle()` → first
`pick_and_place_simple` game the upstream expert solves within 25 steps.
It is from `train`, so it leaks nothing about any `valid_unseen` game.

## Prompt (frozen)
`system`: role + action grammar (the 18 `command_templates` verbatim) + output contract
("reply with exactly one action and nothing else").
`user`: the in-context example transcript, then `--- New game ---`, then the current game's
intro, then the full `> action` / observation history, then `>`.
No truncation, no summarisation, no memory module. The whole raw history is always sent.

## Metrics recorded per episode
`won`, final/max subgoal rank, `K`, `REACHED_CONTROLLED`, first-controlled-decision step,
total actions, distinct actions, longest repeated-action streak, invalid-action count,
snapped-action count, and prompt/history token counts from the model's own tokenizer
(vLLM `POST /tokenize`).

## Pre-registered gates (section 8 / 9)
```
W  = # of 20 native episodes reaching >=1 controlled decision
      W >= 5      -> PASS
      W in {2,3,4}-> STOP_FOR_REVIEW
      W <= 1      -> FAIL_NATIVE_COMPETENCE

B  = # of 5 suffix attempts completing the NEXT official subgoal within 20 steps
      B >= 2      -> PASS
      B == 1      -> STOP_FOR_REVIEW
      B == 0      -> FAIL_SUFFIX_COMPETENCE
```
Model, prompt, horizons, game selection and the admissible-command policy are frozen here and
will not be changed after W or B is observed.
