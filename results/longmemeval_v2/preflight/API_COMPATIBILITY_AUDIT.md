# LongMemEval-V2 memory-API compatibility audit (§7)

Read from `memory_modules/memory.py`, `no_retrieval.py`, `rag.py`, `agentrunbook_r.py`,
`evaluation/harness.py`, `evaluation/run_eval.py`, `tests/test_query_privacy.py`.
No implementation was written.

## The two contracts

```python
class Memory(ABC):
    memory_type: str = ""
    def __init__(self, memory_params: dict[str, object]) -> None: ...

    @abstractmethod
    def insert(self, trajectory: dict[str, object]) -> None: ...

    @abstractmethod
    def query(self, query: str, query_image: str | None = None) -> list[MemoryContextItem]: ...
```

`MemoryContextItem = {"type": Literal["text","image"], "value": str}`. `validate_memory_context_items`
requires non-empty strings and, for images, an existing path. Registration is
`@register_memory` on a class with a unique `memory_type`; construction goes through
`build_memory(config)` from a `{"memory_type", "memory_params"}` JSON file passed as
`--memory-config-path`.

Optional hooks: `configure_runtime(**kwargs)`, `post_query_hook(...)`,
`_save_backend(dir)` / `_load_backend(dir)`, `reconcile_loaded_memory_config(...)`.

`insert` receives **the full trajectory object** — `id`, `domain`, `environment`, `goal`,
`outcome`, `start_url`, and the complete ordered `states` list. This is the entire raw
observable history, handed to the backend directly.

## Does the harness leak benchmark-private metadata to the backend? **No — verified.**

The README claim holds in code:

- `build_prompt_row` calls `memory.set_query_context(query_invocation_id=item["query_invocation_id"])`,
  where the id is a fresh `uuid.uuid4().hex` per question, then calls
  `memory.query(item["question_text"], query_image=item["question_image"])` and finally
  `memory.clear_query_context()` in a `finally`.
- `Memory.set_query_context` takes **only** the keyword `query_invocation_id`; any other
  keyword is a `TypeError`.
- `get_query_context()` returns `{"query_invocation_id": ...}` and nothing else, from a
  `threading.local`, so it is also per-worker isolated.
- The question id, `question_type`, `eval_function`, `answer`, the raw question record and
  the evaluator config stay in `prepared_questions` inside the harness and are never passed
  to the backend.
- `tests/test_query_privacy.py::test_all_backends_receive_only_opaque_query_context`
  asserts exactly this for all six released backends, and
  `test_query_context_api_rejects_benchmark_metadata` asserts the `TypeError`.

This matches ReCoverMem's leakage boundary: the scorer must never see the gold answer or
the label, and here the *host* cannot see them either.

## Can ReCoverMem be added as a backend without changing upstream semantics?

**Yes — a new registered class, no upstream edit.** The intended shape maps cleanly:

| ReCoverMem concept | LongMemEval-V2 hook |
|---|---|
| fresh host per memory source | one backend instance per haystack; `insert` called once per trajectory in haystack order |
| `Mem0Adapter.write(messages)` | called from `insert(trajectory)` with the trajectory's states rendered as turns |
| immutable raw history `H_i` | the same `trajectory` dicts, retained by the backend in its own store |
| `x_t` (common state) | the `query` string (+ `query_image` path), byte-identical for both routes |
| `E_t` = Mem0 evidence ≤ `B_mem` | text items returned by `query` |
| `ρ(x, H)` ≤ `B_rec` | text items produced from retained raw slices, never from Mem0 |
| reader | the harness's own reader call, same model and settings for both routes |

Three integration facts worth recording:

1. **Paired collection needs two passes, not a modified harness.** `query()` returns one
   evidence payload per call, so MEMORY and RECOVERY are naturally two runs of the same
   harness over the same questions with two backend configs — identical `x`, identical
   reader, differing only in evidence source. `--shuffle-questions-seed` must be left unset
   (or fixed) so both passes see the same order. No upstream file needs changing.
2. **The official token budget is not ReCoverMem's budget.** `truncate_memory_context`
   enforces `--memory-context-max-tokens` (default **200,000**) counted with
   `AutoProcessor.from_pretrained("Qwen/Qwen3.5-9B")`. ReCoverMem's `B_mem`/`B_rec` must be
   enforced *inside* `query()` with the exact Llama tokenizer; the harness cap then becomes
   a non-binding outer guard, which must be set at or below the reader window so it never
   silently truncates. Two tokenizers disagreeing is acceptable only in that direction.
3. **Reader-side control is limited.** The harness owns prompt construction
   (`build_messages` fixes the `### Memory context:` / `### Question to answer:` layout and
   the domain system prompt) and generation parameters come from CLI flags. That is good
   for fairness — both routes get the identical wrapper — but ReCoverMem cannot request
   logprobs through it, so the `action_confidence` feature would fall back to its
   pre-defined neutral 0.5 unless the reader call is made outside the harness.

**Verdict: PASS** for the memory API itself; the only structural gap is (3), which affects
one of ten scorer features and is handled by the schema's existing neutral value.
