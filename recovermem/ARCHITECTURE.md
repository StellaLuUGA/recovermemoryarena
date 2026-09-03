# ReCoverMem architecture (Table 1 / Mem0 configuration)

## Dataflow

```
                       tau^3-Bench Retail episode
                                  |
                                  v
                    immutable raw trajectory  H_t
                                  |
                +-----------------+------------------+
                |                                    |
                v                                    v
        Mem0 OSS  (host)                    Recovery backend
        native write/update                 bounded retrieval over H_t
                |                                    |
                v                                    |
        Mem0 store  M_t                              |
                |                                    |
        retrieve, pack <= B_mem              pack <= B_rec  (= B_mem)
                |                                    |
                v                                    v
        memory evidence  E_t                 recovered evidence  E_rec
                |                                    |
                |                                    |
                +---------> ReCoverMem <-------------+
                            |
                            |  feature extraction   f(x_t, E_t, a_mem)     <- E_rec NOT an input
                            |  recoverability score s = sigma(w.f + b)
                            |  CRC calibration      tau_hat  (episode-level)
                            |  TRUST / RECOVER routing
                            |  paired decision logging
                            v
                       action a_t
```

**Three-Layer Memory is NOT part of the Mem0 Table 1 configuration.** It is not
imported, referenced, or instantiated anywhere on this path. It exists only as
`hosts/three_layer_adapter.py`, an optional host for a later host-generality experiment,
reachable exclusively through `build_host("three_layer", ...)`.

## The leakage boundary

```
    scorer sees:      x_t          decision state (no history field)
                      E_t          host-retrieved evidence + retrieval statistics
                      a_mem        the candidate memory-route action

    scorer NEVER sees: H_t, E_rec, u_mem, u_rec, R_mem, task outcome
```

Enforced by the signature of `extract_features`, which raises `TypeError` on any
forbidden keyword. The old implementation violated this by conditioning the score on the
already-generated draft answer (`predictor.py:324-334`).

## Two operating modes

| | `collect` | `route` |
|---|---|---|
| Purpose | build the Table 1 dataset | deploy a calibrated policy |
| Branches run | **both**, from the same checkpointed state | one, selected by τ̂ |
| Needs τ̂ | no | yes |
| Needs a frozen predictor | no | yes (unfrozen raises) |
| Produces | `u_mem` and `u_rec` per decision | the routed action |

`collect` is what makes the paired comparison possible: `PairedEvaluator` captures the
pre-decision state, runs the memory branch, restores, runs the recovery branch, and sets
`pair_valid` only if all three state hashes agree.

## Calibration

Exchangeability unit is the **episode**. For episode *i* with T_i controlled decisions,
trusting iff s ≥ τ:

```
    L_i(tau) = (1/T_i) sum_t  1[ s_it >= tau  AND  R_mem_it == 0 ]
    Lhat_n(tau) = (1/n) sum_i L_i(tau)

    marginal CRC:   tau_hat = inf { tau : [n/(n+1)] Lhat_n(tau) + 1/(n+1) <= alpha }
```

`R_mem_it = 1[u_mem_it >= gamma]` is derived at analysis time from the continuously
logged utility, so γ is a free parameter.

Six rules share one exact breakpoint grid: Always Trust (τ = −∞), Always Recover
(τ = +∞), Fixed-F1, Empirical-risk, Random score + marginal CRC (frozen Uniform(0,1)
draw), and marginal CRC. Infeasibility (α < 1/(n+1)) is reported, never patched.

## Provenance recorded per run

`RunManifest` pins: seed, split, host, agent model, Mem0 LLM, embedding model, γ, B_ctx,
B_mem, B_rec, git commits for τ³-bench and Mem0, host metadata, feature schema version,
and a config hash derived from all of it.
