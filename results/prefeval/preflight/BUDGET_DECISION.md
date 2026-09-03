# PrefEval budget decision — FROZEN

```
B_mem = 2048
B_rec = 2048
```

Frozen before any ReCoverMem route outcome was observed, by the two-stage
scorer-independent rule in `BUDGET_AUDIT.md`.

| stage | quantity | value |
|---|---|---|
| 1 | `Q_0.05(B_avail)` over all 1000 instances | 31,983 |
| 1 | `B_cap` = largest standard budget ≤ Q₀.₀₅ | 16,384 |
| 2 | max uncapped native Mem0 evidence, 3 frozen audit units | 1,978 |
| 2 | `B_host` = smallest standard budget ≥ that | **2,048** |
| — | `B_mem = min(B_cap, B_host)` | **2,048** |
| — | `B_rec = B_mem` | **2,048** |

Binding stage: **`B_host`**. Not inherited from τ³ Retail's 1,024 — the mechanical rule
chose 2,048 here on its own, and 1,024 would have truncated ~48% of Mem0's native evidence.

`B_rec` is binding on **100%** of instances (median raw history 104,122 tokens = 50.8 ×
`B_rec`, and 3.2 × the whole 32,768-token answer context).

No correctness, FS, coverage, AUROC or scorer output was inspected in reaching this. The
value is frozen for smoke, pilot and any later formal collection.
