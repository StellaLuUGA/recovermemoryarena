# LongMemEval-V2 Phase-0 structural audit (§3–§4)

Zero-LLM except one local text-vs-image capability probe (§10). No benchmark run, no Mem0
build, no paid API, no route outcome inspected.

- Repo: `https://github.com/xiaowu0162/LongMemEval-V2.git` @ `2cc8c540bdb87fe6761629b585e727e1c4704520` (2026-08-09)
- HF dataset: `xiaowu0162/longmemeval-v2` @ `f152293e235517d504809563c833d7190b8c713b`
- Downloaded in Phase 0 (~5.2 MB): `questions.jsonl`, both haystack files, `SCHEMA.md`, `DATA_CARD.md`, `README.md`, `checksums.sha256`
- **Not** downloaded: `trajectories.jsonl` (1.196 GB), screenshot tarballs (5.92 GB)
- Machine-readable: `structural_audit.json`

## Questions

451 questions, one JSON object per line, fields
`id, domain, environment, question_type, question, image, answer, eval_function`.

| axis | breakdown |
|---|---|
| domain | web 240, enterprise 211 |
| environment | workarena 211, webarena-reddit 91, webarena-cms 83, webarena-onestopshop 66 |
| question_type | static-environment 134, dynamic-environment 86, procedure 74, static-environment-abs 55, dynamic-environment-abs 41, procedure-abs 32, errors-gotchas 29 |
| `image != null` | **29** (all of them `errors-gotchas`; 15 web / 14 enterprise) |

`environment` nests strictly inside `domain`: workarena ⊂ enterprise; the three webarena
families ⊂ web.

## Haystacks — the decisive finding

`SCHEMA.md` states it and the data confirms it:

> `haystacks/lme_v2_small.json`: … **Within each domain, all questions share one 100-trajectory haystack.**

| | small | medium |
|---|---|---|
| question entries | 451 | 451 |
| **unique ordered trajectory lists** | **2** | 447 |
| unique trajectory sets (order-insensitive) | **2** | 433 |
| haystack sizes | 100 × 451 | 500 × 428, plus 387/411/441/458/471/477/479/481/487 for 23 web questions |
| distinct trajectories used | 200 (web 100, enterprise 100) | 1,473 (web 599, enterprise 874) |
| questions per unique haystack | 240 (web), 211 (enterprise) | median 1, max 2 |

The harness reacts to exactly this. `all_haystacks_shared()` is True per domain on the
small tier, so `evaluation/harness.py` prints *"All questions share the same haystack,
building shared memory once for all questions"* and reuses one memory object for all 240
(or 211) questions. On the medium tier it takes the per-question branch and rebuilds
memory for every question.

### The medium tier's 447 haystacks are not 447 independent memory sources

They are 447 different ~500-element draws from a domain pool of only 599 / 874:

| domain | n questions | pairwise Jaccard min / median / max | median \|A ∩ B\| | trajectories used by exactly 1 question | used by all questions |
|---|---|---|---|---|---|
| web | 240 | 0.442 / **0.835** / 1.000 | 455 | **0** of 599 | 1 |
| enterprise | 211 | 0.370 / **0.761** / 0.934 | 432 | 19 of 874 | 20 |

Two arbitrary web questions share ~84% of their injected trajectory history, and **no web
trajectory belongs to only one question**. Assigning such questions to different
partitions would put the same trajectories — hence very nearly the same Mem0 store — into
`predictor_train`, `calibration` and `final_test` simultaneously. That is the leakage the
protocol forbids, restated at 84% rather than 100%.

### Tier relationship

- Both tiers contain the **same 451 question ids**. The tiers differ only in haystack depth.
- The small pool (200 trajectories) is a **subset of the medium pool** (1,473).
- But **small ⊄ medium per question**: for 0 of 451 questions is `small[q] ⊆ medium[q]`.
  Coverage of the small 100-set inside the same question's medium haystack ranges
  0.53–0.96 (web, mean 0.87) and 0.52–0.74 (enterprise, mean 0.59).
- So the tiers are neither independent samples nor nested; they are two overlapping draws
  from one pool. Counting a question once per tier would double-count it.

## Exchangeability unit (§4)

Candidate units, evaluated against "no injected trajectory may appear in two partitions":

| candidate unit | count | defensible? |
|---|---|---|
| question | 451 | **No.** All questions in a domain share one haystack (small) or ~76–84% of it (medium). |
| haystack (small tier) | 2 | Yes, but n = 2. |
| haystack (medium tier) | 447 | **No.** Haystacks overlap by construction; only 0/19 trajectories are question-exclusive. |
| customized environment | 4 | **No.** Each web haystack draws ~500 of the 599 web trajectories, so a reddit question's memory also contains cms and onestopshop trajectories. `environment` labels the question, not a disjoint trajectory pool. |
| **domain / trajectory pool** | **2** | **Yes.** `validate_public_data` forbids cross-domain trajectories in a haystack, so web and enterprise pools are provably disjoint (200 = 100 + 100; 1,473 = 599 + 874). |

```
n_independent = 2      (web, enterprise)
```

This holds for both tiers and does not improve by combining them: the same two disjoint
trajectory pools underlie both.

## Structural feasibility

| target | requirement | available | verdict |
|---|---|---|---|
| 24 / 24 / 24 | ≥ 72 independent units | 2 | **FAIL** (deficit 70) |
| 30 / 30 / remainder | ≥ 61 independent units | 2 | **FAIL** |
| α = .05 calibration | ≥ 20 non-empty calibration units | ≤ 1 (a 3-way split of 2 units is impossible) | **FAIL** |

With `n_independent = 2` a disjoint three-way split does not exist at all: one of
`predictor_train`, `calibration`, `final_test` must be empty. Marginal CRC needs
`n_cal ≥ ⌈1/α − 1⌉` = 19 / 9 / 4 for α = .05 / .10 / .20; the maximum obtainable `n_cal`
is 1, whose CRC floor is `1/(1+1) = 0.5`. Every α in the Table-1 family is analytically
infeasible, and the predictor cannot be fitted on a single unit.

No model correctness outcome was inspected in reaching this conclusion.

## What a query-level split would hide

Splitting the 451 questions 24/24/24 or 150/150/151 is arithmetically easy and
scientifically void here: on the small tier the memory object handed to a test question is
the *identical Python object* that produced the training features, and on the medium tier
it shares ~84% of its source trajectories. FS and Exc. computed that way would describe
resubstitution error on one memory, not out-of-sample risk control.
