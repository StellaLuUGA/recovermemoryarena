# Section 9 — next-subgoal suffix feasibility

```
B = 0 / 5   -> pre-registered gate: FAIL_SUFFIX_COMPETENCE
```

## Protocol
The **first 5** native episodes in frozen order that reached a genuine controlled decision:
frozen idx **0, 4, 6, 10, 13**. Each episode's first controlled state was reconstructed by exact
action-prefix replay, then the *same frozen agent* was resumed from it with the **full observable
raw history prefix**, no Mem0 and no compression, for at most `MAX_NEXT_SUBGOAL_STEPS = 20` steps.
Success iff the harness-only upstream checker reports completion of the **next** official
high-level subgoal (rank ≥ rank₀ + 1).

Replay integrity: in **5/5** cases the reconstructed state reproduced the native subgoal rank
(`replay_rank_matches_native = true`), independently corroborating the section-5 replay gate.

## Results

| idx | task type | prefix | rank₀ | next official subgoal | target rank | steps used | success |
|---|---|---|---|---|---|---|---|
| 0 | look_at_obj_in_light | `go to desk 1` | 1 | `take mug` | 2 | 20 | ✗ |
| 4 | pick_clean_then_place_in_recep | `go to countertop 1` | 1 | `take soapbar` | 2 | 20 | ✗ |
| 6 | pick_clean_then_place_in_recep | `go to countertop 1` | 1 | `take soapbar` | 2 | 20 | ✗ |
| 10 | pick_cool_then_place_in_recep | `go to cabinet 1 → go to countertop 1` | 1 | `take mug` | 2 | 20 | ✗ |
| 13 | pick_clean_then_place_in_recep | `go to cabinet 1` | 1 | `take bowl` | 2 | 20 | ✗ |

In all five the next subgoal is a **single admissible action away** (`take <obj> from <recep>`,
with the object named in the observation the agent is looking at). The agent never issued a
`take` in any of the 100 suffix steps. Command distributions:

* idx 0 — `go to desk 2` ×10, `go to desk 1` ×10 (the parser-snap oscillation described in
  `NATIVE_20_REPORT.md`); 0 invalid.
* idx 4 — `examine soapbar 1` ×11 (inadmissible), `go to cabinet 1` ×8, `open cabinet 1` ×1; 18 invalid.
* idx 6 — `examine soapbar 1` ×10, `go to cabinet 1` ×10; 19 invalid.
* idx 10 — `go to countertop 1` ×20 while already at countertop 1; 20 invalid.
* idx 13 — `examine bowl 1` ×15, `go to countertop 1` ×5; 19 invalid.

## Interpretation

B = 0 is a **frozen viability stopping rule**, not evidence that deeper ALFWorld subgoals are
unreachable in principle. What it does establish, on this frozen configuration:

* the environment, the replay mechanism and the upstream subgoal checker all behave correctly —
  the target subgoal is one legal action away and would have been detected instantly;
* the binding constraint is the **frozen agent**: greedy temperature-0 Llama-3.1-8B-Instruct with
  a zero/one-shot prompt and no admissible-command exposure degenerates into action repetition
  and never emits `take`.

The two changes most likely to move B, both of which would require an explicit **re-freeze**
before any further outcome collection, are (a) fixing the parser-snap defect so it can never
substitute a different entity number, and (b) the admissible-command policy — option B of the
section-6 contract (showing the admissible command list to the model) is the standard ALFWorld
configuration in the literature and directly addresses repetition of inadmissible actions.
Neither was applied here, because both were pre-registered and W and B have now been observed.

Raw record: `competence/suffix_feasibility.json`.
