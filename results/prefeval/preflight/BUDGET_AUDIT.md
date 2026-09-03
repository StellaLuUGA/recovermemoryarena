# PrefEval two-stage budget audit (Phase-1 §5)

Applied **before any ReCoverMem route outcome was observed**. No correctness, FS, coverage
or scorer output was consulted in selecting B. All token counts use the exact
`meta-llama/Llama-3.1-8B-Instruct` tokenizer, snapshot `0e9e39f2…`.

Machine-readable: `budget_audit.json`.

## Inputs

| symbol | value | source |
|---|---|---|
| `B_ctx` | 32,768 | the running vLLM server's `--max-model-len` |
| `B_out` | 8 | PrefEval `config.yaml` sets `max_mcq_tokens: 5`; 8 leaves room for the closing `</choice>` under our assistant prefill |
| `B_safe` | 512 | fixed reserve for chat-template overhead not captured by per-message counting |
| ladder | 1K, 2K, 4K, 8K, 16K, 32K | `recovermem.tokens.STANDARD_BUDGETS` |

## Stage 1 — `B_cap`, from the answerer's own context

Computed structurally over **all 1000 classification instances**; no model call, no memory.
`B_base` is the mandatory prompt: system turn + the full `x_i` (question + the four
shuffled options + the released instruction block) + the `<choice>` assistant prefill.

| quantity | min | median | max |
|---|---|---|---|
| `B_base` | 207 | 239 | 363 |
| `B_avail = B_ctx − B_base − B_out − B_safe` | 31,885 | 32,010 | 32,041 |

`Q_0.05(B_avail) = 31,983`

```
B_cap = largest standard budget <= 31,983 = 16,384
```

PrefEval's query block is tiny, so the answerer's context is barely a constraint — the
whole 32k window is essentially free for evidence.

## Stage 2 — `B_host`, from native uncapped Mem0 evidence

Audit subset: the 3 frozen `budget_audit` units from `PRIMARY_SETTING.json`, selected by
seed-13 group permutation **before** any outcome and **disjoint** from smoke and pilot.
For each, a fresh Mem0 store ingests the full 604-message history, then a single
decision-time `search` is issued with the budget set to 10⁹ so packing is a no-op and the
number reported is the host's own uncapped output.

Write granularity: 4,096 tokens per `Mem0.add()`, never splitting a message (the same
streaming convention MemoryAgentBench uses).

| unit | history msgs | history tokens | write chunks | build time | Mem0 memories | **uncapped evidence** | candidates | largest candidate |
|---|---|---|---|---|---|---|---|---|
| `lifestyle_beauty#010` | 604 | 104,132 | 27 | 141.3 s | 115 | 1,537 | 50 | 209 |
| `shop_technology#001` | 604 | 104,120 | 27 | 134.6 s | 128 | 1,477 | 50 | 209 |
| `professional_work_location_style#011` | 604 | 104,127 | 27 | 140.9 s | 89 | 1,978 | 50 | 326 |

```
max uncapped Mem0 evidence = 1,978
B_host = smallest standard budget >= 1,978 = 2,048
```

## Frozen decision

```
B_mem = min(B_cap, B_host) = min(16384, 2048) = 2048
B_rec = B_mem            = 2048
```

**`B_host` is the binding stage.** 1,024 was *not* forced from τ³ Retail; the ladder rule
selected 2,048 independently here because Mem0's native uncapped evidence (1,978 tokens)
exceeds 1,024. Had the τ³ value been imposed, ~48% of the host's own retrieved evidence
would have been discarded before the comparison even started.

## Is `B_rec` binding?

**Yes, overwhelmingly.**

| raw 300-turn history tokens | min | median | max |
|---|---|---|---|
| | 104,079 | 104,122 | 104,224 |

- fraction of instances whose raw history exceeds `B_rec`: **100.0 %**
- median raw history / `B_rec` = **50.8×**

Recovery sees at most 1/50th of the history it retrieves over, so the RECOVERY route is a
genuinely bounded retrieval problem rather than a disguised full-context read. The raw
history is also 3.2× the entire answer context, so passing it directly is impossible in any
case.

## Observations recorded, not acted on

1. **Mem0 fact-extraction JSON parse failures.** Building the three audit memories produced
   6 `Error parsing extraction response` messages (malformed JSON from the 8B extractor).
   Mem0 skips those chunks' facts. This is a host-quality property of running Mem0 on a
   local 8B model and it applies identically to every instance; it is reported, not
   patched, and it does not enter the budget rule.
2. **A `snapshot()` reporting bug was fixed in ReCoverMem, not upstream.** Mem0's
   `get_all` defaults to `top_k=20` (`mem0/memory/main.py:1259`), a display cap.
   `Mem0Adapter.snapshot()` inherited it and reported exactly "20 memories" for every
   store. The adapter now passes `top_k=100_000`; the corrected counts are 89–128. The
   audit was re-run after the fix and **the budget decision is unchanged** (`B_cap` and
   `B_host` are computed from `B_avail` and evidence tokens, neither of which the bug
   touched).
3. **Cost.** ~140 s of memory construction per instance, dominated by 27 sequential
   `Mem0.add()` calls each doing fact extraction plus update decisions against one local 8B
   server. Retrieval is ~0.02 s. Budget for ~2.5 min per instance of collection.
