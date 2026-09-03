# Why one path is excluded from the canonical read-only check

`results/alfworld/final/logs/vllm_qwen3_formal.log` is excluded from
`CANONICAL_B1024_SNAPSHOT.sha256`.

It is the **vLLM server's own stdout log**, not a B=1024 experiment artifact. The server
was launched during setup with its output redirected into that path, and it appends to it
continuously for as long as it runs. Section 14 of the brief requires reusing that healthy
server rather than starting a second one, so the file necessarily keeps growing while the
B=512 experiment runs.

No B=512 code writes to it: the B=512 runner's own stdout/stderr go to
`results/alfworld/budget_sensitivity/B512/logs/B512_run.log`, and every B=512 artifact path
is asserted to resolve outside the canonical tree before collection starts.

Every other file under `results/alfworld/final/` -- all 917 of them, including every
manifest, threshold, predictor, Table 1 and Table 2 artifact and the formal run logs -- is
hashed and verified byte-identical in the final invariant check.
