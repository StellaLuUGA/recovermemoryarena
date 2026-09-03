# Table-2 cost replay — what was re-executed and how faithful it was

Two replays, both writing only under `table2/`. `formal/` was opened read-only.

## 1. `C_write` — 24 Mem0 rebuilds, 757 LLM calls

`replay1_c_write.py` rebuilds each final-test persona's store from the same frozen 128K
history into a scratch store root and records every Mem0 extraction/update call's own
`usage`. No question was answered.

| | min | median | max | total |
|---|---:|---:|---:|---:|
| C_write tokens per persona | 313635 | 435837 | 461210 | 10001281 |
| C_write LLM calls per persona | 24 | 33 | 35 | 757 |

Input path equivalence to the formal build: identical message count, identical history token
count and identical write-chunk count on 24/24 personas
(`path_equivalent`: 24/24).

The rebuilt stores are *not* byte-identical to the frozen ones — Mem0's fact extraction is
an LLM call and the server is not bitwise deterministic — so the resulting memory counts
differ from the formal ones on some personas. Only the token usage is taken from this
replay; the frozen stores under `formal/memory/final_test/` were never modified and are what
the branch replay actually reads.

Per-persona replay vs formal memory count (persona, replay, formal):
[[901, 150, 110], [265, 171, 210], [259, 198, 168], [995, 269, 233], [72, 148, 131], [235, 159, 179], [137, 128, 148], [737, 160, 229], [741, 244, 197], [76, 146, 163], [521, 234, 206], [604, 202, 243], [199, 162, 162], [332, 213, 213], [277, 186, 186], [716, 236, 236], [721, 163, 163], [351, 151, 151], [184, 151, 151], [527, 149, 149], [816, 188, 188], [209, 175, 175], [213, 152, 152], [800, 193, 193]]

## 2. Branch usage — 572 answer calls

`replay2_branch_usage.py` binds a byte copy of each frozen final-test store, reproduces the
frozen retrieval at B_mem = 2048 and the frozen lexical recovery at B_rec = 2048, and
re-issues both branch answer calls to read `usage`. It aborts if a question's frozen state
hash or option-order hash fails to reproduce.

Input fidelity: 286/286 MEMORY and
286/286 RECOVERY prompts reproduce the formal
server-reported prompt-token count exactly (0 mismatching decisions). Evidence
token counts match on 286/286 (memory) and
286/286 (recovery) decisions. Memory retrieval
issued 0 LLM calls, confirming the controller's retrieval step is
free of generation cost.

Output divergence (expected, reported not repaired): the replay reproduced the formal
completion byte-for-byte on 38/286 MEMORY and
21/286 RECOVERY calls, and the formal parsed
choice on 224/286 and
225/286. vLLM at temperature 0 is not bitwise
deterministic under continuous batching. Per the frozen protocol, correctness for Table 2
comes from the original formal Table-1 rows; the replay contributes cost only.

## 3. Interpreter provenance

The formal run's option shuffle seeds on `hash(str)` under `PYTHONHASHSEED=13`, which is
stable only within one CPython hash algorithm. CPython ≥ 3.11 uses siphash13 where ≤ 3.10
used siphash24, so a 3.12 interpreter reproduces none of the frozen option orders. The
replay therefore runs under `miniconda3/envs/MABench` (CPython 3.10.16), which reproduces
all 286/286 frozen `row_seed`, `state_hash`, `option_order_hash` and
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
