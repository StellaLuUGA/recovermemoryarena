# PrefEval — Phase-0 decision (§12)

Structural / protocol facts only. No model inference, no Mem0, no scorer, no calibration,
no outcome inspected. `requirements.txt` was not installed. The PrefEval tree was not
modified. Repo `50795054`.

| axis | verdict | basis |
|---|---|---|
| **A. Independent-unit count** | **PASS** | `n_independent = 985` group-key components over 1000 classification instances (997 unique preference-query pairs, merged for 9 reused preferences / 6 reused queries / 3 reused pairs). |
| **B. 24/24/24 feasibility** | **PASS** | Needs 72; 985 available — 13.7× headroom. 30/30/rest also passes with final_test = 925. Deterministic stratification by the 20 topics (31–61 groups each) is available without splitting a group. |
| **C. α = .05 calibration feasibility** | **PASS** | Needs ≥ 20 non-empty calibration units and `n_cal ≥ 19` for marginal CRC; 985 available. α = .10 and .20 likewise. 200 history-level resamples draw genuinely distinct subsets. |
| **D. Correctness** | **PROGRAMMATIC** | `1[extract_choice(response) == ["A","B","C","D"][correct_idx]]`. Pure BeautifulSoup + regex + string equality. No LLM judge anywhere on the classification path; no API needed for scoring. Malformed output → `None` → deterministically incorrect. |
| **E. Memory-sufficiency semantics** | **PASS** (one PARTIAL) | Preference lives only in the history (62.9% zero content-word overlap with the query, p90 0.167); `x_i` identical for both routes; no gold needed to build either evidence route. PARTIAL: choosing the longest option scores 44.6% with no memory (chance 25%), so that is the real no-memory floor. |
| **F. Bounded raw-history recovery** | **PASS** | History is a list of atomic `{role, content}` messages. ReCoverMem's existing `TrajectoryRetriever` consumes that shape unchanged — no new backend. `B_rec = B_mem` is enforceable at message granularity with no mid-unit truncation. |
| **G. Duplication / leakage risk** | **MANAGEABLE** | The distractor background is a single global object shared by all instances, and `--inter_turns` settings are strict prefixes of it. But the *evidence* — the preference — is unique in 990/1000. The 14 multi-member groups are handled by the group key. Gold is the positional convention `options[0]`, which must be shuffled away before anything reaches the host or scorer. |

## Final classification

```
MAIN_TABLE_CANDIDATE
```

PrefEval is the first of the three audited long-memory benchmarks that clears the
structural gate. It clears it on the axis that killed the other two — independent units —
and it does so while also giving programmatic correctness, which LongMemEval-V2 could not.

### Why it clears the gate the others failed

| | MAB-AR | LongMemEval-V2 | **PrefEval** |
|---|---|---|---|
| independent units | 7 | 2 | **985** |
| what is shared across instances | the answer-bearing context | the answer-bearing haystack | only answer-irrelevant filler |
| memory rebuilt per instance? | no (one per book) | no (one per domain) | **yes, necessarily** |
| correctness | programmatic | 65% programmatic / 35% `gpt-5.2` | **100% programmatic** |
| multimodal blockers | none | 29 image-required questions | none |
| history size vs our 32k window | 6–23× | 900–4,700× | 0.03–3.3×, tunable |
| verdict | gate FAIL | APPENDIX_ONLY | **MAIN_TABLE_CANDIDATE** |

MAB-AR and LongMemEval-V2 both maximise *questions per memory source*. PrefEval inverts
that: one query per preference, one preference per instance, a fixed shared background. The
background sharing is a controlled experimental constant, not a leaked evidence source — the
distinction is argued in full in `EXCHANGEABILITY_AUDIT.md`.

### Conditions this candidacy depends on

These are structural obligations, not discovered problems:

1. **Freeze one preference form and one `--inter_turns` value** for the whole experiment.
   The three forms are variants of one pair and the turn settings are prefixes of one
   source; neither may vary within a run or be counted as extra units.
2. **Use the group key** from `EXCHANGEABILITY_AUDIT.md`, not raw row order — 14 groups have
   2–3 members.
3. **Shuffle options before exposure.** `classification_task_options[0]` is the gold by
   positional convention only; it must never reach the memory host, the scorer or the log's
   feature block.
4. **Report the 44.6% length-cue floor** alongside any accuracy, not 25%.
5. **Pick `--inter_turns` so the history exceeds the reader window**, otherwise memory is
   unnecessary and `R_mem` is uninformative. The crossing point is ≈100 inter-turns
   (34,849 tokens ≈ 1.06 × B_ctx); 300 gives 101,588 tokens ≈ 3.1×. Below ~50 the whole
   history fits in context and the task degenerates.
6. **Pin `pref_generation` if the explicit form is used** — the assistant's acknowledgement
   is LLM-generated at construction time and must be produced once per instance and reused
   byte-identically by both routes. The implicit forms avoid this entirely and are the
   cleaner choice.

### Upstream defect to work around

`classification_task/benchmark_classification.py` calls `random.seed(41)` and
`shuffle_options` (which uses `random.sample`) **without importing `random`** — as released
it raises `NameError` before doing any work. Irrelevant to our plan, since a ReCoverMem
runner would replace this driver, but it means no published classification number can have
come from this file revision and the shuffle seed behind published results is unknown.
Documented in `CORRECTNESS_AUDIT.md`; the PrefEval tree was **not** patched.

## Artifacts

```
results/prefeval/preflight/STRUCTURAL_AUDIT.md        structural_audit.json
results/prefeval/preflight/CORRECTNESS_AUDIT.md
results/prefeval/preflight/EXCHANGEABILITY_AUDIT.md
results/prefeval/preflight/RECOVERY_COMPATIBILITY.md
results/prefeval/preflight/PHASE0_CLASSIFICATION.md
```

Stopping here as instructed. No smoke, no pilot, no formal collection.
