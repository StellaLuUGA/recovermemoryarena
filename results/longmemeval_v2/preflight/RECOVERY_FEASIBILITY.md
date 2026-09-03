# Bounded raw-history recovery feasibility (§8)

Audit only; nothing implemented. Token figures use the **exact Llama-3.1-8B-Instruct
tokenizer** from snapshot `0e9e39f249a16976918f6564b8830bc894c89659`.

## The raw-history representation

`SCHEMA.md`, confirmed against a fetched record (`trajectories.jsonl` byte range 0–3 MB,
trajectory `00332982`, enterprise/workarena, 101 states, 1.34 MB of JSON):

| trajectory field | present | note |
|---|---|---|
| `id` | yes | stable trajectory id, the natural slice namespace |
| `domain`, `environment` | yes | web/enterprise; environment family |
| `goal` | yes | task goal text |
| `outcome` | yes | `success` / `failure` |
| `start_url` | yes | first state URL |
| `states` | yes | **ordered** list |

| state field | present | note |
|---|---|---|
| `state_index` | yes | zero-based, gives total order |
| `step` | yes | original step number |
| `url` | yes | text |
| `action` | yes | text, `null` on the initial state |
| `thought` | yes | agent thought text when available |
| `accessibility_tree` | yes | **the observation**, ~12k chars in the sampled state |
| `screenshot` | yes | a **path** (`screenshots/<traj_id>/<step>.png`), not bytes |

Answering the audited points directly:

- **Text fields per step:** `url`, `action`, `thought`, `accessibility_tree` — the state is
  fully readable without any image.
- **State/action/result:** yes; actions are attached to destination states (documented in
  `agentrunbook_r._build_note_generation_messages`), so `state[i].action` is the transition
  *into* state *i*.
- **Note fields:** not in the released data. Notes (`procedure_note`, `hint_note`) are
  *generated* by the baselines with an LLM at insert time. Original data carries no notes,
  which is the right property: recovery reads the raw history, not a derived summary.
- **Timestamps / order:** no wall-clock timestamps; `state_index` and `step` give a total
  order within a trajectory, and haystack lists are **ordered** arrays, giving a
  deterministic order across trajectories.
- **Trajectory ids:** stable and unique (`load_trajectories` rejects duplicates).
- **Independently indexable slices:** yes — `(trajectory_id, state_index)` addresses a
  state, and `entry_id = f"{traj_id}:raw_state:{center_index:04d}"` is the upstream
  convention for exactly this.
- **Screenshots referenceable by path:** yes, and only by path, so a text-only recovery
  operator never needs the 5.92 GB of tarballs.

## Does the official RAG baseline already provide a raw-slice index? **Yes.**

`rag_query_to_slice` (`memory_modules/rag.py`) borrows
`AgentRunbookR._build_raw_state_entries`, which for every state *c* of every trajectory
emits one entry:

```python
start = max(0, c - raw_state_slice_radius)          # radius default 1
end   = min(len(states), c + raw_state_slice_radius + 1)
{ "entry_id": f"{traj_id}:raw_state:{c:04d}",
  "trajectory_id": ..., "goal": ..., "center_state_index": c,
  "slice_state_indexes": [...], "slice_urls": [...],
  "slice_action_sequence": ..., "full_action_sequence": ...,
  "slice_axtree_text": _slice_axtree_text(slice_states) }
```

So the benchmark itself defines a raw-state slice unit over the original trajectories,
independent of any memory store, retrieved by embedding similarity against
`slice_axtree_text`. This is precisely the substrate a bounded recovery operator needs, and
ReCoverMem's existing `TrajectoryRetriever` (IDF-weighted lexical, deterministic, no LLM)
can score the same slice list without importing the baseline's Qwen embedder.

**Verdict: bounded raw-history recovery is constructible from original trajectory slices,
fully independent of Mem0. PASS.**

Note the caveat required by the brief: `_build_raw_state_context_items` — the *renderer*
the baselines use — appends the center state's **screenshot** after each text slice. A
ReCoverMem recovery operator must render text-only and must not reuse that renderer
verbatim, or RECOVERY would carry an evidence channel MEMORY does not have.

## Scale: why the bound is not optional

Measured on trajectory `00332982` (101 states), rendering each state as
`State/URL/Action/AXTree`:

| quantity | exact Llama tokens |
|---|---|
| one state (min / median / max) | 205 / 3,166 / 7,173 |
| one full trajectory | **306,963** |
| a 100-trajectory small haystack (this rate) | ~30.7 M |
| a 500-trajectory medium haystack (this rate) | ~153 M |

Against `B_ctx = 32,768`:

- one **state slice** at radius 1 ≈ 9.5k tokens — already ~29% of the entire window;
- one **trajectory** ≈ 9.4× the window;
- one **small haystack** ≈ 937× the window;
- one **medium haystack** ≈ 4,684× the window.

This is consistent with the README's "up to 115M tokens in the largest haystacks". Placing
a haystack — or even a single trajectory — in the reader prompt is impossible, not merely
undesirable, so the `|ρ(x,H)| ≤ B_rec` bound is enforced by physics here as well as by
protocol.

Two consequences for budget design (to be settled by the standard two-stage rule, not now):

- With `B_ctx = 32,768` and the standard ladder, `B_mem = B_rec` will land at **4,096 or
  8,192**. At 4,096 a single radius-1 slice does not fit; the recovery operator would have
  to emit radius-0 slices or truncate, which changes what "a slice" means. This is a real
  design decision, not a formality.
- The harness default `--memory-context-max-tokens = 200,000` is designed for a
  long-context reader and is ~6× our window. It must be lowered to at most the reader
  window, which is itself a departure from the official operating point.

## Hard rules restated for the eventual implementation

- RECOVERY must retrieve over the retained original `trajectory` dicts, **never** by a
  second `Mem0.search`.
- RECOVERY must not receive a larger evidence budget than MEMORY (`B_rec = B_mem`).
- RECOVERY must render text-only, not reuse the baseline renderer's screenshot append.
- The full raw haystack must never reach the reader prompt.
