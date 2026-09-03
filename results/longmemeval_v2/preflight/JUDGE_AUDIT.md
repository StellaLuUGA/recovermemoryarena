# LongMemEval-V2 judge / correctness audit (§5)

Audited from released code (`evaluation/qa_eval_metrics.py`, `evaluation/harness.py`,
`evaluation/run_eval.py`), not from README wording. **No judge was called.**

Machine-readable: `judge_audit.json`.

## Classification: **HYBRID**

295 / 451 questions (65.4%) are scored by a purely programmatic function.
156 / 451 (34.6%) are **OFFICIAL_JUDGE_DEPENDENT**.

## Scoring table

| question type | count | scoring function | programmatic? | LLM judge required? | binary correctness available? |
|---|---|---|---|---|---|
| static-environment | 116 | `norm_phrase_set_match` | yes | no | yes |
| static-environment | 12 | `mc_choice_match` | yes | no | yes |
| static-environment | 5 | `norm_phrase_set_match_ordered` | yes | no | yes |
| static-environment | 1 | `mc_choice_set_match` | yes | no | yes |
| dynamic-environment | 59 | `norm_phrase_set_match` | yes | no | yes |
| dynamic-environment | 21 | `mc_choice_match` | yes | no | yes |
| dynamic-environment | 6 | `norm_phrase_set_match_ordered` | yes | no | yes |
| procedure | 35 | `mc_choice_match` | yes | no | yes |
| procedure | 24 | `norm_phrase_set_match` | yes | no | yes |
| procedure | 15 | `norm_phrase_set_match_ordered` | yes | no | yes |
| errors-gotchas | 1 | `norm_phrase_set_match` | yes | no | yes |
| **static-environment-abs** | **55** | `llm_abstention_checker` | no | **yes** | yes (judge-produced) |
| **dynamic-environment-abs** | **41** | `llm_abstention_checker` | no | **yes** | yes (judge-produced) |
| **procedure-abs** | **32** | `llm_abstention_checker` | no | **yes** | yes (judge-produced) |
| **errors-gotchas** | **28** | `llm_gotchas_checker` | no | **yes** | yes (judge-produced) |

The mapping is one-to-one with the memory-ability categories: every `-abs`
(premise-awareness / abstention) question and all but one `errors-gotchas` question is
judge-scored; every non-abstention factual question is programmatic. `harness.py` enforces
this with `require("-abs" in qtype)` for `llm_abstention_checker`.

## Answers to the audited questions

1. **What computes correctness.** `harness.score_prediction` → `eval_from_spec(row["eval_function"], …)`,
   dispatching by name into `qa_eval_metrics`. The `eval_function` string is a per-question
   field in `questions.jsonl`, so the split above is data, not configuration.
2. **Kind.** Hybrid: normalized phrase-set match (order-free and ordered), multiple-choice
   letter match and letter-set match are pure string/regex operations; abstention and
   gotchas grading is a reference-conditioned LLM call.
3. **Programmatic correctness without a judge?** For 295 questions yes, fully. For the
   remaining 156 there is **no** released non-LLM fallback — the functions raise if
   `evaluator_model` is unset.
4. **Does the judge see the gold answer?** **Yes.** Both prompts embed
   `Reference answer:\n{answer_text}` together with the question, the model's full
   response and the extracted `\boxed{}` answer, and ask for `{"label": 0|1, "reason": …}`.
   It is a reference-grounded grader, not an open-ended rater.
5. **All 451 or only some?** Only the 156 above. The other 295 never touch the evaluator.
6. **Cached official judge labels released?** **No.** The HF dataset contains
   `questions.jsonl`, `trajectories.jsonl`, haystacks and screenshots only — no reference
   predictions and no cached judgements. There is no way to obtain the official labels for
   the 156 questions without running the judge.
7. **Is leaderboard accuracy fundamentally judge-based?** Partly. `aggregate_metrics`
   reports per-category accuracy over all seven categories and LAFS is computed from the
   combined accuracy, so the headline number is 34.6% judge-produced. The four
   non-abstention categories (`static`, `dynamic`, `procedure`, `gotchas` minus its 28
   judged items) can be reported without any judge.

## Additional finding: the UNKNOWN override

`score_prediction` applies, *after* the eval function returns:

```python
if row["is_unknown"]:
    score_bool = False
```

Any reader output whose `\boxed{}` content is exactly `UNKNOWN` is scored 0 regardless of
question type — including abstention questions, where the judge prompt separately grades a
bare UNKNOWN as 0. Both domain system prompts instruct the reader to emit
`\boxed{UNKNOWN}` when unsure. This is a benchmark-level abstention penalty and interacts
directly with ReCoverMem's TRUST/RECOVER semantics: a route that declines to answer is
scored identically to a wrong answer.

## What OFFICIAL_JUDGE_DEPENDENT means for ReCoverMem

For the 156 judge-scored questions, `R_mem` and `R_rec` would be **labels produced by
`gpt-5.2`**, not an independently programmatic task reward. Consequences:

- A CRC guarantee calibrated on those labels controls false-safe rate *with respect to the
  judge's labelling function*. It is a valid conformal statement about a stochastic
  labeller, but it is not the same object as the τ³ programmatic reward, and the paper must
  not present them as interchangeable.
- Judge calls cost money and reach a paid API. The current constraint set forbids that, so
  those 156 questions cannot be labelled at all under Phase-0 rules.
- The endpoint **is** redirectable: `harness.py` accepts `--evaluator-base-url`, and the
  judge functions fall back to `api_key="EMPTY"` when a base URL is given, so pointing the
  judge at `127.0.0.1:8123` would technically work. **This was not done and must not be
  done silently** — substituting Llama-3.1-8B for gpt-5.2 changes the labelling function and
  therefore the meaning of every reported number. Note also that `run_eval.py` does *not*
  forward `--evaluator-base-url`, so the wrapper path always targets the OpenAI cloud; only
  a direct `harness.py` invocation can be redirected.
- A **defensible judge-free subset exists**: the 295 programmatic questions. It drops the
  premise-awareness ability entirely (all 128 `-abs` questions) and 28 of 29 gotchas, i.e.
  2 of the benchmark's 5 advertised memory abilities. That is a scope change to be decided
  explicitly, not a workaround.
