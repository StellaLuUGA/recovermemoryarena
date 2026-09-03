# Section 5 — ALFWorld state replay gate

**Result: `REPLAY_GATE = 9 / 9` semantic matches → PASS.**

## Protocol
Games: the first 3 structurally eligible games in frozen seed-13 order (frozen indices 0, 1, 2).

For each game the action prefix is the frozen upstream-expert trajectory from section 4,
truncated at its **first genuine controlled decision** — the first step where the harness-only
upstream checker reports `1 ≤ rank < K`, i.e. at least one official high-level subgoal complete
and at least one remaining.

Each game is then **fresh-reset and the identical prefix replayed 3 times** (3 × 3 = 9
reconstructions), each compared field-by-field against a reference execution of the same prefix.

## Compared at the boundary state
`feedback` (observation text) · `inventory` · `location` · `admissible_commands` ·
PDDL `facts` · harness subgoal rank · `won` · `done`

Only normalisation applied: `admissible_commands` and `facts` are compared as **sorted**
collections (TextWorld does not guarantee emission order). Observation text is compared **byte
for byte, unnormalised**. `inventory`/`location` are `None` on ALFWorld games for every run
(the fields are not populated by these PDDL games) and therefore match trivially — this is
recorded rather than counted as evidence.

## Per-game results

| frozen idx | task type | K | prefix len | boundary rank | matches |
|---|---|---|---|---|---|
| 0 | `look_at_obj_in_light` | 4 | 3 | 1 | 3/3 |
| 1 | `pick_and_place_simple` | 4 | 18 | 1 | 3/3 |
| 2 | `pick_and_place_simple` | 4 | 11 | 1 | 3/3 |

Prefixes (verbatim):

* idx 0 — `go to shelf 1 | go to shelf 2 | go to shelf 3`
* idx 1 — `go to shelf 1 | go to shelf 2 | go to shelf 3 | go to drawer 1 | open drawer 1 | close drawer 1 | go to drawer 2 | open drawer 2 | close drawer 2 | go to drawer 3 | open drawer 3 | close drawer 3 | go to countertop 1 | go to countertop 2 | go to countertop 3 | go to cabinet 1 | go to cabinet 2 | open cabinet 2`
* idx 2 — `go to sidetable 1 | go to shelf 1 | go to shelf 2 | look | go to drawer 2 | open drawer 2 | close drawer 2 | go to shelf 3 | go to shelf 4 | go to shelf 5 | go to shelf 6`

**No diffs in any field on any of the 9 reconstructions** (`diff_fields == []` throughout).
Prefix replay is therefore an exact state-reconstruction mechanism for ALFWorld TextWorld games,
which is what ReCoverMem's controlled-branch design requires.

Raw record: `replay/replay_gate.json`.
