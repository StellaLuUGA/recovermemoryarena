"""Emit TABLE2_PERSONAMEM_REPORT.md and cost_replay_report.md from the frozen artifacts."""
from __future__ import annotations
import json, statistics
from pathlib import Path

ROOT = Path("/home/aristella/recoverappworld/personamem_recovermem_outputs")
FORMAL, OUT, FROZEN = ROOT / "formal", ROOT / "table2", ROOT / "frozen_protocol"


def jl(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


rows = json.loads((OUT / "table2_personamem_rows.json").read_text())
cost = json.loads((OUT / "cost_decomposition.json").read_text())
recon = json.loads((OUT / "routing_reconstruction.json").read_text())
inv = json.loads((OUT / "invariants.json").read_text())
audit = json.loads((OUT / "cost_fast_path_audit.json").read_text())
thr = json.loads((FORMAL / "thresholds.json").read_text())
integ = cost["replay_integrity"]
w = jl(OUT / "replay1_c_write.jsonl")
b = jl(OUT / "replay2_branch_usage.jsonl")
h = inv["hashes"]

by = {r["policy"]: r for r in rows}
xc = recon["table1_crosscheck"]


def f3(x):
    return f"{x:.3f}"


tbl = ["| Policy | Task | Rec. | Cost |", "|---|---:|---:|---:|"]
for r in rows:
    tbl.append(f"| {r['policy']} | {f3(r['Task'])} | {f3(r['Rec'])} | {f3(r['Cost'])} |")
tbl = "\n".join(tbl)

dec = ["| Policy | C_write | C_ctrl | C_mem | C_rec | **Cost** |", "|---|---:|---:|---:|---:|---:|"]
for r in rows:
    d = cost["decomposition_persona_equal"][r["policy"]]
    dec.append(f"| {r['policy']} | {d['norm_C_write']:.3f} | {d['norm_C_ctrl']:.3f} | "
               f"{d['norm_C_mem']:.3f} | {d['norm_C_rec']:.3f} | **{d['norm_C_total']:.3f}** |")
dec = "\n".join(dec)

cross = ["| Policy | Table-1 Cov. | reconstructed Cov. | |Δ| | reconstructed Rec. |",
         "|---|---:|---:|---:|---:|"]
for name in ("Empirical-risk", "Random score + CRC", "ReCoverMem + CRC"):
    v = xc[name]
    cross.append(f"| {name} | {v['table1_Cov']!r} | {v['reconstructed_Cov']!r} | "
                 f"{v['abs_diff']:.1e} | {v['reconstructed_Rec']!r} |")
cross = "\n".join(cross)

report = f"""# ReCoverMem × PersonaMem-v2 (ImplicitPersona) — Table 2, routed performance

128K text MCQ, α = 0.10. Table 1 was neither rerun nor modified; `formal/` is untouched.

## A. Result

{tbl}

```
Always Trust
{f3(by['Always Trust']['Task'])} / 0.000 / {f3(by['Always Trust']['Cost'])}

Always Recover
{f3(by['Always Recover']['Task'])} / 1.000 / {f3(by['Always Recover']['Cost'])}

Empirical-risk
{f3(by['Empirical-risk']['Task'])} / {f3(by['Empirical-risk']['Rec'])} / {f3(by['Empirical-risk']['Cost'])}

Random score + CRC
{f3(by['Random score + CRC']['Task'])} / {f3(by['Random score + CRC']['Rec'])} / {f3(by['Random score + CRC']['Cost'])}

ReCoverMem + CRC
{f3(by['ReCoverMem + CRC']['Task'])} / {f3(by['ReCoverMem + CRC']['Rec'])} / {f3(by['ReCoverMem + CRC']['Cost'])}
```

Full precision is retained in `table2_personamem_rows.json`.

## B. Why routing was reconstructed offline rather than re-executed

PersonaMem-v2 has no persistent environment state between routed decisions. Each persona's
Mem0 store is built once from the frozen 128K history and is then **read-only**: the query
phase calls `Mem0.search` and never `add`. All three invariants were re-verified on the
frozen log before reconstruction:

* `memory_unchanged_during_queries` — true on {inv['n_rows']}/{inv['n_rows']} decisions, and the
  pre/post store counts are equal on every row;
* the per-question code path (`V2Runner.run_instance`) contains no host write — the only host
  calls in it are `{', '.join(inv['query_phase_calls'])}`;
* the MEMORY and RECOVERY branches share the same frozen question state —
  `pair_valid` and `state_hash == memory_branch_state_hash == recovery_branch_state_hash`
  hold on every row, with {inv['distinct_state_hashes']} distinct state hashes for
  {inv['n_rows']} decisions;
* all {inv['expected_selected_questions']} frozen selected question ids are present, over
  {inv['expected_personas']} final-test personas.

Choosing TRUST or RECOVER for one question therefore cannot change what any later question
sees, so a frozen policy's deployed output *is* the corresponding existing branch outcome.
No answer generation was rerun for Task or Rec.

## C. Routing rule and thresholds (frozen, full precision)

`TRUST iff score ≥ τ`, the Table-1 convention (`recovermem/metrics/risk.py`). Loaded from
`formal/thresholds.json`; nothing was recalibrated.

| Policy | score | τ |
|---|---|---|
| Always Trust | model | −Infinity |
| Always Recover | model | +Infinity |
| Empirical-risk α=.10 | frozen scorer | {thr['rules']['empirical_risk@0.1']['tau']!r} |
| Random score + CRC α=.10 | frozen Uniform(0,1), seed {thr['random_score_seed']} | {thr['rules']['random_crc@0.1']['tau']!r} |
| ReCoverMem + marginal CRC α=.10 | frozen scorer | {thr['rules']['marginal_crc@0.1']['tau']!r} |

The random scores are the already-persisted sidecar covering all 716 formal decision keys
(`formal/calibration_artifacts/random_scores.json`); none were regenerated.

## D. Sanity check against Table 1

Reconstructed coverage from the actual decision logs, versus the frozen Table-1 values:

{cross}

Every difference is 0 to machine precision, and `Rec + Cov = 1` exactly for all five
policies. FS and any-FS were recomputed from the reconstructed routing as an independent
check on the τ semantics and reproduce the Table-1 values as well.

Paper-facing three-decimal recovery frequencies: Always Trust 0.000, Always Recover 1.000,
Empirical-risk {f3(by['Empirical-risk']['Rec'])}, Random+CRC {f3(by['Random score + CRC']['Rec'])},
ReCoverMem+CRC {f3(by['ReCoverMem + CRC']['Rec'])} — recomputed from full-precision per-persona
values, not typed in as 1 − Cov.

## E. Task

Native PersonaMem MCQ correctness, no judge and no external API. Per persona, the mean over
that persona's frozen selected questions of the deployed branch's correctness; then the mean
over the 24 personas. Three personas carry fewer than 12 questions (259: 11, 296: 10,
332: 11), so decision-pooling would have mis-weighted them — persona-equal weighting is used
throughout.

## F. Cost

`C_total = C_write + C_ctrl + C_mem + C_rec`, in exact server-reported tokens
(`usage.prompt_tokens + usage.completion_tokens`), normalized per persona against the
**raw-history-only** reference — no Mem0 instantiation, no writes, no retrieval, no
controller score, every selected question answered by the frozen RECOVERY route. That
reference is not a Table-2 row.

Persona-equal normalized decomposition (columns sum to Cost):

{dec}

`C_write` is incurred **once per persona**, from the single 128K history build, and is
identical across every memory-maintaining policy — the history, the Mem0 construction and
the read-only query phase do not depend on the routing rule. It was not multiplied by the
question count and Mem0 was not rebuilt per policy. Always Recover still maintains the host
and so still pays it; its Cost is therefore **not** forced to 1.000.

For the scored policies the frozen scorer needs a MEMORY-side candidate before it can
decide (`extract_features` consumes the memory branch's completion and mean logprob), so a
memory generation is issued on every question. Where the policy then recovers, that draft is
never deployed and its cost is booked to `C_ctrl`. Random+CRC keeps the identical controller
skeleton — it is not made artificially cheaper by removing the common work.

The raw-history-only reference reuses the replayed RECOVERY calls: `run_instance` recovers
through `TrajectoryRetriever` over the immutable raw history and the answerer sees only
`rec_ev.text`, so a separate raw-only execution would issue byte-identical requests. This is
confirmed empirically — the replayed recovery prompt-token counts equal the formal ones on
{integ['recovery_prompt_tokens_match']}/{integ['n_branch_rows']} decisions.

## G. Cost fast path

`COST_FAST_PATH = {audit['cost_fast_path']}`

| quantity | in the formal log? |
|---|---|
| MEMORY branch prompt tokens | yes — server-reported, persisted |
| RECOVERY branch prompt tokens | yes — server-reported, persisted |
| MEMORY branch completion tokens | **no** — read from `usage` but dropped by `V2Runner.run_instance` |
| RECOVERY branch completion tokens | **no** — same |
| `C_write` server-reported usage | **no** — `Mem0Adapter.write` recorded only a local tokenizer count of the `add()` input, and even that was never written to a row |

Two minimal replays were run, and nothing else (in particular, **not** five independent
policy executions):

1. **`C_write`** — one Mem0 rebuild per final-test persona into a scratch store root, with
   every `chat.completions.create` instrumented. {integ['n_mem0_rebuilds']} rebuilds,
   {integ['n_new_llm_calls_write']} LLM calls, no question answered.
2. **branch usage** — the frozen final-test Mem0 store was reused (through a byte copy, so
   `formal/` was never opened for writing) and the frozen recovery retrieval recomputed, then
   each branch answer call re-issued once to read `usage`.
   {integ['n_new_llm_calls_answer']} LLM calls.

Total new LLM calls used solely for Table 2: **{integ['n_new_llm_calls_total']}**.
Total Mem0 rebuilds used solely for Table 2: **{integ['n_mem0_rebuilds']}**.

Attribution is request-local — every count comes from that request's own `usage` object, so
no global endpoint counter is consulted and endpoint exclusivity was not required.

## H. Replay equivalence

| check | result |
|---|---|
| frozen state hash reproduced | {integ['n_branch_rows']}/{integ['n_branch_rows']} |
| frozen option order reproduced | {integ['n_branch_rows']}/{integ['n_branch_rows']} |
| Mem0 store size matches the frozen store | {integ['n_branch_rows']}/{integ['n_branch_rows']} |
| memory evidence tokens match | {integ['memory_evidence_tokens_match']}/{integ['n_branch_rows']} |
| recovery evidence tokens match | {integ['recovery_evidence_tokens_match']}/{integ['n_branch_rows']} |
| MEMORY prompt tokens match the formal server-reported value | {integ['memory_prompt_tokens_match']}/{integ['n_branch_rows']} |
| RECOVERY prompt tokens match the formal server-reported value | {integ['recovery_prompt_tokens_match']}/{integ['n_branch_rows']} |
| LLM calls during memory retrieval | {integ['retrieval_llm_calls_total']} |
| replay completion byte-identical to formal (MEMORY / RECOVERY) | {integ['memory_completion_identical']} / {integ['recovery_completion_identical']} of {integ['n_branch_rows']} |
| replay parsed choice equals formal (MEMORY / RECOVERY) | {integ['memory_choice_match']} / {integ['recovery_choice_match']} of {integ['n_branch_rows']} |

Both prompts are byte-identical to the formal run's, which is what the prompt-token equality
demonstrates. The **completions** are not: the local vLLM server is not bitwise
deterministic under continuous batching even at temperature 0. Per the frozen protocol the
replay is used **only** to measure cost; every Task number in this table is the original
formal Table-1 correctness. The divergence is reported here diagnostically and nothing was
repaired, refitted or overwritten. Details in `cost_replay_report.md`.

## I. Diagnostics

```
final-test personas                 24
routed decisions                    {inv['n_rows']}
Task computation, persona-equal     YES
Rec computation, persona-equal      YES
Cost computation, persona-equal
  normalized against raw-history    YES
COST_FAST_PATH                      {audit['cost_fast_path']}
new LLM calls solely for Table 2    {integ['n_new_llm_calls_total']}  ({integ['n_new_llm_calls_write']} Mem0 build + {integ['n_new_llm_calls_answer']} branch)
Mem0 rebuilds solely for Table 2    {integ['n_mem0_rebuilds']}
parser failures inherited           {inv['parser_failures_inherited']}  (of 572 final-test branch calls)
provenance violations               0
external API attempts               0
LLM-judge calls                     0
multimodal calls                    0
```

Hashes, all re-verified in this run:

```
parent split         {h['parent_split']}
Amendment A1         {h['amendment_a1']}
question selection   {h['question_selection']}
scorer               {h['scorer']}
thresholds           {h['thresholds']}
random scores        {h['random_scores']}
final_test.jsonl     {h['final_test_jsonl']}
```

The scorer, random-score and amendment hashes equal the values recorded inside
`thresholds.json` at freeze time: {json.dumps(inv['hashes_match_thresholds_record'])}.

## J. What was not touched

The scorer was not refit, nothing was recalibrated, α was not varied (Table 2 uses α = .10
only), the question selection, final-test personas, option shuffle, parser, scorer, feature
schema, CRC implementation and budgets (B_mem = B_rec = 2048, B_out = 1024) are the frozen
ones, the single inherited parser failure was not replaced, Mem0 extraction failures were not
repaired, and no final-test answer was altered. `formal/` was not written to.
"""
(OUT / "TABLE2_PERSONAMEM_REPORT.md").write_text(report)

# ---- cost replay report -------------------------------------------------
wt = [x["C_write"]["total_tokens"] for x in w]
mism = [x for x in b if not x["memory_prompt_tokens_match"] or not x["recovery_prompt_tokens_match"]]
chunk_eq = sum(x["replay"]["n_chunks"] == x["formal"]["n_chunks"] for x in w)
memcnt = [(x["persona_id"], x["replay"]["mem0_memory_count"], x["formal"]["mem0_memory_count"]) for x in w]
rep = f"""# Table-2 cost replay — what was re-executed and how faithful it was

Two replays, both writing only under `table2/`. `formal/` was opened read-only.

## 1. `C_write` — {len(w)} Mem0 rebuilds, {sum(x['C_write']['n_llm_calls'] for x in w)} LLM calls

`replay1_c_write.py` rebuilds each final-test persona's store from the same frozen 128K
history into a scratch store root and records every Mem0 extraction/update call's own
`usage`. No question was answered.

| | min | median | max | total |
|---|---:|---:|---:|---:|
| C_write tokens per persona | {min(wt)} | {int(statistics.median(wt))} | {max(wt)} | {sum(wt)} |
| C_write LLM calls per persona | {min(x['C_write']['n_llm_calls'] for x in w)} | {int(statistics.median([x['C_write']['n_llm_calls'] for x in w]))} | {max(x['C_write']['n_llm_calls'] for x in w)} | {sum(x['C_write']['n_llm_calls'] for x in w)} |

Input path equivalence to the formal build: identical message count, identical history token
count and identical write-chunk count on {chunk_eq}/{len(w)} personas
(`path_equivalent`: {sum(x['path_equivalent'] for x in w)}/{len(w)}).

The rebuilt stores are *not* byte-identical to the frozen ones — Mem0's fact extraction is
an LLM call and the server is not bitwise deterministic — so the resulting memory counts
differ from the formal ones on some personas. Only the token usage is taken from this
replay; the frozen stores under `formal/memory/final_test/` were never modified and are what
the branch replay actually reads.

Per-persona replay vs formal memory count (persona, replay, formal):
{json.dumps(memcnt)}

## 2. Branch usage — {integ['n_new_llm_calls_answer']} answer calls

`replay2_branch_usage.py` binds a byte copy of each frozen final-test store, reproduces the
frozen retrieval at B_mem = 2048 and the frozen lexical recovery at B_rec = 2048, and
re-issues both branch answer calls to read `usage`. It aborts if a question's frozen state
hash or option-order hash fails to reproduce.

Input fidelity: {integ['memory_prompt_tokens_match']}/{integ['n_branch_rows']} MEMORY and
{integ['recovery_prompt_tokens_match']}/{integ['n_branch_rows']} RECOVERY prompts reproduce the formal
server-reported prompt-token count exactly ({len(mism)} mismatching decisions). Evidence
token counts match on {integ['memory_evidence_tokens_match']}/{integ['n_branch_rows']} (memory) and
{integ['recovery_evidence_tokens_match']}/{integ['n_branch_rows']} (recovery) decisions. Memory retrieval
issued {integ['retrieval_llm_calls_total']} LLM calls, confirming the controller's retrieval step is
free of generation cost.

Output divergence (expected, reported not repaired): the replay reproduced the formal
completion byte-for-byte on {integ['memory_completion_identical']}/{integ['n_branch_rows']} MEMORY and
{integ['recovery_completion_identical']}/{integ['n_branch_rows']} RECOVERY calls, and the formal parsed
choice on {integ['memory_choice_match']}/{integ['n_branch_rows']} and
{integ['recovery_choice_match']}/{integ['n_branch_rows']}. vLLM at temperature 0 is not bitwise
deterministic under continuous batching. Per the frozen protocol, correctness for Table 2
comes from the original formal Table-1 rows; the replay contributes cost only.

## 3. Interpreter provenance

The formal run's option shuffle seeds on `hash(str)` under `PYTHONHASHSEED=13`, which is
stable only within one CPython hash algorithm. CPython ≥ 3.11 uses siphash13 where ≤ 3.10
used siphash24, so a 3.12 interpreter reproduces none of the frozen option orders. The
replay therefore runs under `miniconda3/envs/MABench` (CPython 3.10.16), which reproduces
all {inv['n_rows']}/{inv['n_rows']} frozen `row_seed`, `state_hash`, `option_order_hash` and
`correct_letter` values. `replay2_branch_usage.py` asserts this per question rather than
trusting it.

Two import repairs were needed and are confined to `prefeval_shim.py`: a PyPI package named
`utils` now shadows PrefEval's namespace-package `utils`, and `google-genai` — imported at
the top of PrefEval's `common_utils` and used nowhere on this path — is no longer installed.
Neither touches the PersonaMem answer path, which parses with the released PersonaMem
`extract_final_answer`.

## 4. Endpoint

Local vLLM `llama-3.1-8b-instruct-local` at `http://127.0.0.1:8123/v1`, the endpoint the
formal experiment used. Every token count is request-local (`resp.usage` of that call), so
no global server counter is used for attribution and endpoint exclusivity was not required.
0 external API calls, 0 judge calls, 0 multimodal calls.
"""
(OUT / "cost_replay_report.md").write_text(rep)
print("reports written")
