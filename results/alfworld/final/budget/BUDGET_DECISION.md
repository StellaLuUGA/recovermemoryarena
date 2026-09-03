# ALFWorld budget decision (scorer-independent)

Measured on the **16 PREDICTOR_TRAIN episodes only**, with the exact Qwen3-32B tokenizer, before
any paired utility label existed. No R_mem, R_rec, scorer, AUROC, FS or coverage quantity was
computed or inspected.

| quantity | median | q90 | max |
|---|---|---|---|
| current state x_t | 245.5 | 279.5 | 409 |
| native Mem0 serialized evidence | 235.5 | 349.0 | 516 |
| raw observable history | 503.5 | 737.5 | 1060 |
| available serving evidence capacity | 15084.5 | 15163.0 | 15172 |

Two-stage rule (identical in form to tau3):

```
B_cap  = largest ladder budget <= Q0.05(available capacity) = 8192
B_host = smallest ladder budget >= max native Mem0 evidence (516) = 1024
B_mem  = min(B_cap, B_host) = 1024
B_rec  = B_mem = 1024
```

Ladder: [256, 512, 1024, 2048, 4096, 8192, 16384].

Binding behaviour: raw observable history exceeds `B_rec` at **5.6%** of controlled
states (so recovery evidence is genuinely truncated there); native Mem0 evidence exceeds `B_mem`
at 0.0%. Whether or not the budget binds, it is frozen here and is not retuned after
labels are seen.

`BUDGET_FREEZE.json` sha256 `6df85870e9240b851a0ff8272a62e6673f125ac1b71e1e766eb65998005c574f`.
