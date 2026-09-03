# MAB-AR structural feasibility gate — **FAILED** (brief §7)

**Decision: STOP before any formal outcome collection.** No memory was built, no model
call was made on any AR query, and no route outcome was inspected before this document.

## The number

MemoryAgentBench Accurate Retrieval supplies **7 independent source histories**, not 72.

| source | independent source histories | queries |
|---|---|---|
| EventQA (`eventqa_full`) | 5 | 500 |
| RULER QA1 (`ruler_qa1_197K`) | 1 | 100 |
| RULER QA2 (`ruler_qa2_421K`) | 1 | 100 |
| **total** | **7** | **700** |

The preferred formal target is `predictor_train = 24`, `calibration = 24`,
`final_test = 24` — **72 independent source histories**. The deficit is 65.

There is no larger pool hiding in the split. `Accurate_Retrieval` holds 22 samples in
total; 5 are LongMemEval (excluded by design) and 10 are `eventqa_131072` /
`eventqa_65536`, which the audit verified to be **strict character prefixes of the same
five EventQA books**. Counting a truncation as an extra history would place one book in
two partitions — the exact leakage the brief forbids. RULER QA1 and QA2 each contain
exactly one haystack.

## Maximum valid disjoint split sizes

With 7 histories and all three partitions required to be non-empty, the largest balanced
3-way disjoint split is **3 / 2 / 2**. Every allocation, ranked by the best (lowest)
marginal-CRC floor `1/(n_cal + 1)` it can reach:

| train | calibration | test | CRC floor `1/(n_cal+1)` | smallest α that could ever be feasible |
|---|---|---|---|---|
| 1 | 5 | 1 | 0.167 | α ≥ 0.167 |
| 1 | 4 | 2 | 0.200 | α ≥ 0.200 |
| 2 | 4 | 1 | 0.200 | α ≥ 0.200 |
| 3 | 2 | 2 | 0.333 | α ≥ 0.333 |
| 2 | 2 | 3 | 0.333 | α ≥ 0.333 |

## Is α = .05 statistically feasible? **No.**

Three independent reasons, any one of which is disqualifying:

1. **The brief's own floor.** §7 requires ≥ 20 non-empty calibration histories for
   α = .05. The maximum obtainable is 7, and that only if `predictor_train` and
   `final_test` are both empty — not a valid design. Under the best real allocation it
   is 5.

2. **Marginal CRC is analytically infeasible.** The rule selects
   `tau_hat = inf { tau : [n/(n+1)]·L̂_n(tau) + 1/(n+1) ≤ α }`. At the most conservative
   threshold `L̂ = 0`, so the criterion floors at `1/(n+1)`. Feasibility therefore needs
   `n_cal ≥ ⌈1/α − 1⌉`:

   | α | required `n_cal` | available `n_cal` (best allocation) | feasible |
   |---|---|---|---|
   | .05 | 19 | 5 | **no** |
   | .10 | 9 | 5 | **no** |
   | .20 | 4 | 4–5 | only degenerately — see below |

   `recovermem/calibration/marginal_crc.py` already reports this as `feasible=False` and
   falls back to Always Recover rather than patching it. At α = .20 with `n_cal = 4` the
   condition reduces to `0.8·L̂ + 0.2 ≤ 0.2`, i.e. `L̂ ≤ 0` — satisfiable *only* at
   τ = +∞. The rule would "pass" by collapsing onto the Always Recover row and would
   report nothing about the scorer.

3. **The predictor cannot be fitted.** `predictor_train` would hold 1–3 histories, i.e.
   1–3 independent draws of the long-memory source. All 100 queries inside a history share
   one context, so the effective sample size for a 10-feature logistic regression is the
   number of histories, not the number of queries. Two of the three sources contribute
   exactly **one** history each, so any split either omits a source from training entirely
   or leaves calibration/test with none of it — stratification by
   `{EventQA, RULER QA1, RULER QA2}` is impossible at 3 partitions × 3 sources with 1+1
   singleton sources.

`Exc.` over 200 history-level calibration resamples is likewise not estimable: resampling
5 histories into cal/held-out subsets yields at most a handful of distinct partitions, so
the 200 repetitions would be near-duplicates rather than an independent variability
estimate.

## What was NOT done, deliberately

- **No fallback to query-level splitting.** Splitting the 700 queries would put queries
  from one book into `predictor_train`, `calibration` and `final_test` simultaneously.
  Since all 100 queries in a history are answered from the same injected context, the
  calibration guarantee would be computed over 700 non-exchangeable units and the reported
  FS/Exc. would be optimistic by an unquantified amount. §7 and §29 forbid it, and the
  numbers it produced would be worse than no numbers.
- **No relaxation of α**, no change to `gamma`, no change to the budget rule, and no
  broadening of MAB-AR's source list to reach a history count.
- **No route outcomes inspected.** Nothing about memory-route or recovery-route accuracy
  is known at the time of this decision.

## Options that would restore feasibility

These change scientific semantics, so they are reported rather than taken:

1. **Report MAB-AR as a fixed-threshold transfer setting, not a calibration setting.**
   Calibrate τ on the τ³ setting (which has the history counts), freeze it, and report
   FS/Cov on MAB-AR's 7 histories as out-of-distribution *transfer*. No Exc. column; the
   `Empirical-risk` / `CRC` rows become "τ imported from τ³".
2. **Enlarge the AR history pool from the upstream generators.** RULER QA1/QA2 are
   synthetic — the upstream RULER generator can produce many additional independent
   haystacks at 197K/421K. That is a data-generation task outside this checkout, and the
   resulting histories would no longer be byte-identical to the published MAB release.
3. **Redefine the AR statistical unit** (e.g. treat each of EventQA's five books as
   several disjoint sub-histories with disjoint query sets). This changes what the paper's
   MAB-AR row means and needs to be an explicit, stated design choice.
4. **Accept α = .20 only**, with `Empirical-risk` and `Fixed-F1` rows reported and the CRC
   rows marked infeasible. This yields a 3-row-degenerate Table 1 whose CRC entries are
   Always Recover by construction.

Option 1 preserves both the paper's MAB-AR definition and the calibration guarantee, and is
the recommendation.

## State of the work at the stop point

Completed and reusable:

- `results/mab_ar/` output tree (isolated; nothing written to `MemoryAgentBench/outputs/`).
- `results/mab_ar/preflight/ENVIRONMENT.md` — minimal MABench 3.10.16 environment,
  `pip check` clean, `/home/aristella/.pipenv-venv` untouched.
- `results/mab_ar/preflight/STRUCTURAL_AUDIT.md` + `structural_audit.json` — all 14 audit
  items.
- `recovermem/integrations/memoryagentbench/{upstream,datasets,structural_audit}.py` —
  MAB imported as a library, with a hard assertion that `mem0` resolves to the pinned
  `/home/aristella/recoverappworld/mem0` checkout and never to `MemoryAgentBench/mem0/`.
  Upstream MemoryAgentBench is **unmodified** by this integration.

Not started, pending the decision above: local-Llama adapter wiring, budget audit, smoke,
cost gate, pilot, formal collection, predictor, calibration, tables.
