# Upstream MemoryAgentBench modifications (brief §4)

Base commit: `fe1735d`.

## The MAB-AR integration itself modifies nothing

`recovermem/integrations/memoryagentbench/` imports MemoryAgentBench as a **library**
(`load_eval_data`, `chunk_text_into_sentences`, `post_process`, `get_template`) and calls
it verbatim. No upstream file is patched, monkey-patched, or shadowed on the MAB-AR path.

The MAB checkout root is **appended** to `sys.path`, never inserted at position 0, because
the checkout vendors `mem0/`, `letta/` and `cognee/` at its repository root. Inserting it
first would make `import mem0` resolve to MemoryAgentBench's vendored copy instead of the
pinned Mem0 OSS checkout. `upstream.py` asserts, before and after loading MAB, that `mem0`
resolves inside `/home/aristella/recoverappworld/mem0`.

## Pre-existing working-tree changes (from the earlier local-Llama bring-up)

These predate the MAB-AR work and are **not used by the MAB-AR execution path**, which
bypasses `AgentWrapper` entirely. They are recorded here because they are live in the tree.

### `agent.py` — 15 insertions, 2 deletions, 3 hunks

The model name `llama-3.1-8b-instruct-local` is **not** disguised as a GPT name; an
explicit local OpenAI-compatible provider branch was added instead, which is the
brief §4 preference.

1. **After `_create_oai_client` (new, +11 lines)** — two helpers:
   - `_is_local_model(self)` → `"local" in self.model.lower()`
   - `_create_local_client(self)` → `OpenAI(base_url=$LOCAL_LLM_BASE_URL, api_key=$LOCAL_LLM_API_KEY)`
2. **`_initialize_long_context_agent` (+2 / −1)** — a new first branch
   `if self._is_local_model(): self.client = self._create_local_client()`, placed before
   the existing `elif "gpt" in self.model or "o4" in self.model:`.
3. **`_query_long_context_agent` (+1 / −1)** — dispatch condition widened from
   `if "gpt" in self.model:` to `if self._is_local_model() or "gpt" in self.model:`,
   routing local models to the same `chat.completions.create` call.

No other line of `agent.py` is touched. Behaviour for `gpt` / `o4` / `claude` / `gemini`
model names is byte-identical to upstream.

### Untracked files added (no upstream file modified)

- `configs/agent_conf/Long_Context_Agents/Long_context_agent_llama-3.1-8b-instruct-local.yaml`
- `bash_files/configs/local_llama_agents.txt`
- `bash_files/sh/run_memagent_local_llama.sh`
- `.env` (git-ignored; `LOCAL_LLM_BASE_URL`, no real cloud keys)

### Untracked outputs

`MemoryAgentBench/outputs/llama-3.1-8b-instruct-local/Conflict_Resolution/` holds a
3-query bring-up smoke from the earlier session. It is **not** MAB-AR data, it is not
Accurate Retrieval, and no MAB-AR artifact is written under `MemoryAgentBench/outputs/`.
All MAB-AR outputs live under `results/mab_ar/`.
