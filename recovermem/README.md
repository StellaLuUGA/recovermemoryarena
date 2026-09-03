# ReCoverMem (clean implementation)

Host-agnostic recoverability scoring, episode-level calibration, and TRUST/RECOVER
routing for executable-agent environments. Built for the τ³-Bench Retail Table 1
experiment with **Mem0 OSS as the host memory**.

## Running things

> **Always run from the project root:**
>
> ```bash
> cd /home/aristella/RecoverMemMinimal/update_replicate
> python3 -m pytest recovermem/tests/ -q
> ```
>
> **Do not run Python with the working directory set to
> `update_replicate/recovermem`.** Python puts the current directory on `sys.path`, so
> from inside the package the submodule `recovermem/logging/` is importable as top-level
> `logging` and **shadows the standard library's `logging` module**. pytest itself fails
> to start under that cwd (`ImportError: cannot import name 'LogRecord' from 'logging'`).
> The package name matches the structure the brief specifies and is being kept; from the
> supported project-root invocation there is no problem, and renaming it is deferred as
> cosmetic until Table 1 is done.

## Layout

| Package | Contents |
|---|---|
| `interfaces/` | `HostMemoryAdapter`, `RecoveryBackend` — the only surfaces the controller touches |
| `hosts/` | `mem0_adapter.py` (**Table 1**), `three_layer_adapter.py` (optional, inactive) |
| `scoring/` | host-agnostic `features.py`, `normalizer.py`, `predictor.py` |
| `calibration/` | `marginal_crc`, `empirical_risk`, `fixed_f1`, `random_crc`, `resample`, `threshold_grid`, `episode_loss` |
| `metrics/` | `risk.py` (episode-equal-weighted FS/Cov/π̂), `weighting.py`, `discrimination.py` |
| `recovery/` | `trajectory_retriever.py` — bounded retrieval over H_t |
| `control/` | `controller.py` — TRUST/RECOVER routing and record assembly |
| `logging/` | `schema.py`, `paired_decision_log.py`, `trajectory_log.py` |
| `checkpoint/` | `state_checkpoint.py` (same-state pairing), `replay.py` |
| `integrations/tau3/` | τ³-Bench Retail wiring and the smoke runner |
| `configs/` | frozen run configurations |

## The invariants this package enforces structurally

These are not conventions; each one is a raised exception or a lazy import.

1. **The scorer is blind to H_t.** `extract_features(state, evidence, candidate)` takes
   three arguments and raises `TypeError` on any keyword in `FORBIDDEN_INPUTS`
   (`history`, `recovered`, `u_mem`, `u_rec`, `r_mem`, `reward`, `outcome`, `label`, …).
   `DecisionState` has no history field.
2. **Both routes are budgeted.** `MemoryEvidence` and `RecoveredEvidence` raise on
   construction if `tokens > budget_tokens`. B_rec = B_mem for the main experiment.
3. **Recorded tokens equal the real prompt.** Packing measures the *joined* text, so
   `record.tokens.memory_evidence_tokens == counter.count_text(evidence.text)` holds by
   construction. See the duplicate-evidence note below.
4. **Risk is episode-weighted.** Every risk functional is defined over
   `EpisodeDecisions`; there is no code path that pools decisions IID.
5. **γ stays free.** Continuous `u_mem`/`u_rec` are logged, never only the binary
   `R_mem`, so γ-sensitivity is a re-analysis rather than a re-run.
6. **Pairs are proven, not assumed.** `pair_valid` defaults to `False` and is set only
   after the state hashes entering both branches are verified equal.
7. **cal ∩ test = ∅.** `threshold_grid.assert_disjoint` refuses to report otherwise.
8. **Mem0 path never touches Three-Layer Memory.** `build_host` imports lazily, so
   `host="mem0"` does not even load the module.
9. **Local only.** A non-localhost LLM endpoint raises before Mem0 is constructed.
10. **B_mem must be frozen.** Constructing a controller with `B_mem=None` raises.

## Duplicate evidence (regression, fixed)

Packing originally selected items by rank and then rebuilt the kept list by matching
strings, so duplicate candidate texts — identical tool results, a memory retrieved under
two ids — were all reintroduced. `tokens` stayed correct while `text` exceeded the
budget, meaning the log would have recorded a compliant budget for an over-budget prompt.
Packing is now by **index**, and the token count is **re-measured on the joined text**.
Pinned by `tests/test_duplicate_evidence.py` at three levels: packer, Mem0 host, recovery
backend.

## Tests

`python3 -m pytest recovermem/tests/ -q` → 49 tests, covering all 14 required checks
(brief §17) plus duplicate-evidence and pairing regressions.
