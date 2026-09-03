# LongMemEval-V2 — Phase-0 classification (§12)

Based only on structural / protocol facts. No ReCoverMem outcome, no benchmark run, no
judge call, no paid API. Repo `2cc8c54`, dataset sha `f152293e`.

| axis | verdict | basis |
|---|---|---|
| **A. Independent unit count** | **FAIL** | `n_independent = 2` (web pool, enterprise pool). Small tier: 2 haystacks for all 451 questions. Medium tier: 447 haystacks but median pairwise Jaccard 0.835 (web) / 0.761 (enterprise), and 0 of 599 web trajectories belong to a single question. |
| **B. 24/24/24 CRC feasibility** | **FAIL** | Needs ≥ 72 units; 2 available. A disjoint 3-way split does not exist — one partition must be empty. 30/30/rest also fails. |
| **C. α = .05 calibration feasibility** | **FAIL** | Needs ≥ 20 calibration units; max obtainable `n_cal` = 1, CRC floor `1/(n+1)` = 0.5. α = .10 and .20 fail identically. |
| **D. Official correctness** | **HYBRID** | 295/451 programmatic (`norm_phrase_set_match`, `_ordered`, `mc_choice_match`, `mc_choice_set_match`); 156/451 (34.6%) require `gpt-5.2` via `llm_abstention_checker` (128) / `llm_gotchas_checker` (28). No cached official judge labels are released. |
| **E. Multimodal compatibility** | **PARTIAL** (blocking for one type) | 29 questions have a required query screenshot — exactly the 29 `errors-gotchas`. Official RAG/AgentRunbook evidence is multimodal. Our local Llama server returns HTTP 400 *"is not a multimodal model"*, so those 29 and every official multimodal baseline are hard-blocked. 422 questions are text-clean. |
| **F. Memory API compatibility** | **PASS** | `insert(trajectory)` hands over the complete raw trajectory; `query(query, query_image)` returns typed context items. Backends receive only an opaque `query_invocation_id` — verified in `memory.py` and enforced by `tests/test_query_privacy.py`. A registered ReCoverMem backend needs **no upstream edit**. |
| **G. Bounded raw recovery** | **PASS** | States carry `url`/`action`/`thought`/`accessibility_tree`; screenshots are path references. Slices are addressable as `(trajectory_id, state_index)`, and upstream already defines exactly this unit (`_build_raw_state_entries`, `entry_id = "<traj>:raw_state:<c>"`). Recovery can read original slices with no Mem0 call. |
| **H. Local Llama reader** | **PARTIAL** | `READER_BASE_URL` / `READER_MODEL` swap the reader with no semantic change. But text-only blocks 29 questions + all multimodal baselines, and the 32,768 window is ~6.7× below the official 200,000-token memory-context default. |
| **I. Data / disk practicality** | **CAUTION** | Disk is fine: 5 MB metadata (fetched), 1.2 GB text, 7.12 GB full, 131 GB free. Compute is not: the medium tier rebuilds memory per question — 451 × ~500 ≈ **225,500 `insert()` calls** with Mem0 `infer=True`, ≈ 63 h per route at 1 s/trajectory on one local 8B server. The small tier is cheap (200 inserts) but has `n_independent = 2`. |

## Final classification

```
APPENDIX_ONLY
```

**Why not `MAIN_TABLE_CANDIDATE` or `TRANSFER_ONLY_CANDIDATE`.** Axis A is the binding
constraint and it is structural, not a resourcing problem. A Table-1 row needs
history-level calibration; LongMemEval-V2 supplies two disjoint memory sources, so
`predictor_train`, `calibration` and `final_test` cannot all be non-empty, and every α in
the Table-1 family is analytically infeasible. Transfer-only (import τ from τ³, report
FS/Cov here) is *closer* to viable — it needs no calibration units — but the FS/Cov point
estimate would still be an average over **two** exchangeable units, which is not a
reportable risk estimate, and 34.6% of its labels would come from a paid judge we cannot
call. `REJECT` is too strong: the memory API, the query-privacy boundary and the raw-slice
substrate are all genuinely well-suited to ReCoverMem, and a descriptive appendix result on
the judge-free, text-only subset would be honest and informative.

**What an appendix result would look like** (not selected, not run):

```
pool:      image == null  AND  eval_function programmatic   ->  294 of 451 questions
tier:      small (2 shared haystacks, 200 inserts, tractable)
abilities: static state recall, dynamic state tracking, workflow knowledge
lost:      environment gotchas (image + judge), premise awareness (judge)
reader:    llama-3.1-8b-instruct-local, identical for MEMORY and RECOVERY
reported:  memory-route vs recovery-route accuracy, AUROC, risk-coverage curve
NOT reported: FS / Cov / Exc. as calibrated quantities (n_independent = 2)
```

## Comparison with the MAB-AR gate

| | MAB-AR | LongMemEval-V2 |
|---|---|---|
| independent units | 7 | **2** |
| queries | 700 | 451 |
| correctness | fully programmatic (`substring_exact_match`) | 65% programmatic, 35% `gpt-5.2` |
| multimodal | none | 29 image-required questions |
| raw-history recovery substrate | plain text context | **richer** (indexed state slices) |
| memory-build cost | 7 histories | 200 (small) or ~225,500 (medium) inserts |
| verdict | gate FAIL, transfer-only recommended | **APPENDIX_ONLY** |

Both benchmarks fail the same axis for the same reason: they are built for
"inject once, query many times", which maximises question count per memory source — the
opposite of what history-level conformal calibration needs. This is now a documented
pattern across two independent long-memory benchmarks and is itself worth a sentence in the
paper's limitations.

## Artifacts

```
results/longmemeval_v2/preflight/STRUCTURAL_AUDIT.md          structural_audit.json
results/longmemeval_v2/preflight/JUDGE_AUDIT.md               judge_audit.json
results/longmemeval_v2/preflight/MULTIMODAL_AUDIT.md
results/longmemeval_v2/preflight/API_COMPATIBILITY_AUDIT.md
results/longmemeval_v2/preflight/RECOVERY_FEASIBILITY.md
results/longmemeval_v2/preflight/DATA_SIZE_AUDIT.md
results/longmemeval_v2/preflight/READER_COMPATIBILITY.md
results/longmemeval_v2/PHASE0_CLASSIFICATION.md
LongMemEval-V2/data/longmemeval-v2/                            5.2 MB metadata only
```

Untouched as required: `/home/aristella/.pipenv-venv`, the running vLLM server, the
LongMemEval-V2 source tree (read-only; the only write is the `data/longmemeval-v2/`
metadata download its own `download_data.py` targets). No LongMemEval-V2 conda environment
was created — Phase 0 needed none.
