"""Fast-path audit: is exact server-reported usage already in the formal logs?"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path("/home/aristella/recoverappworld/personamem_recovermem_outputs")
FORMAL, OUT = ROOT / "formal", ROOT / "table2"
SRC = Path("/home/aristella/recoverappworld/recovermem")

rows = [json.loads(l) for l in (FORMAL / "final_test.jsonl").read_text().splitlines() if l.strip()]
keys = set(rows[0])

runner_src = (SRC / "integrations/personamem_v2/runner.py").read_text()
adapter_src = (SRC / "hosts/mem0_adapter.py").read_text()
answerer_src = (SRC / "integrations/prefeval/answerer.py").read_text()

need = {
    "C_write.server_reported_usage": {
        "present": False,
        "evidence": [
            "Mem0Adapter.write() records only counter.count_messages(messages) into "
            "write_prompt_tokens -- a LOCAL TOKENIZER count of the add() input, not "
            "server-reported usage, and it excludes every Mem0 extraction/update "
            "completion token and every update-call prompt.",
            "V2Runner.build_memory() returns write_prompt_tokens but formal.collect() "
            "never writes it into the row: no write-cost field exists in final_test.jsonl.",
        ],
        "fields_in_log": sorted(k for k in keys if "write" in k),
    },
    "MEMORY.prompt_tokens": {
        "present": "memory_prompt_tokens" in keys,
        "evidence": ["V2Answerer.answer() reads resp.usage.prompt_tokens (server-reported) "
                     "and V2Runner.run_instance persists it as memory_prompt_tokens."],
        "n_rows_with_value": sum(1 for r in rows if isinstance(r.get("memory_prompt_tokens"), int)),
    },
    "MEMORY.completion_tokens": {
        "present": "memory_completion_tokens" in keys,
        "evidence": ["AnswerResult carries completion_tokens from resp.usage, but "
                     "V2Runner.run_instance() persists only prompt_tokens; the "
                     "completion-token field is dropped before logging."],
    },
    "RECOVERY.prompt_tokens": {
        "present": "recovery_prompt_tokens" in keys,
        "evidence": ["Same server-reported path as the memory branch."],
        "n_rows_with_value": sum(1 for r in rows if isinstance(r.get("recovery_prompt_tokens"), int)),
    },
    "RECOVERY.completion_tokens": {
        "present": "recovery_completion_tokens" in keys,
        "evidence": ["Dropped by V2Runner.run_instance(), same as the memory branch."],
    },
}

have = [k for k, v in need.items() if v["present"]]
missing = [k for k, v in need.items() if not v["present"]]
status = "COMPLETE" if not missing else ("MISSING" if not have else "PARTIAL")

audit = {
    "cost_fast_path": status,
    "have": have,
    "missing": missing,
    "requirements": need,
    "cost_convention": (
        "Exact server-reported usage (resp.usage.prompt_tokens + resp.usage.completion_tokens) "
        "for every LLM call. Tokenizer-derived estimates are NOT admissible for Table 2."
    ),
    "minimal_replay_plan": {
        "replay_1_c_write": {
            "why": "no server-reported Mem0 extraction/update usage was ever recorded",
            "what": "rebuild Mem0 ONCE per final-test persona into a scratch store root, "
                    "with every openai chat.completions.create call instrumented",
            "n_mem0_rebuilds": len({r["persona_id"] for r in rows}),
            "n_answer_calls": 0,
            "writes_to_formal": False,
        },
        "replay_2_branch_usage": {
            "why": "server-reported completion tokens for both branches were dropped at log time",
            "what": "bind the EXISTING frozen final-test Mem0 store read-only (via a scratch "
                    "copy), reproduce the frozen retrieval and the frozen recovery retrieval, "
                    "and re-issue each branch answer call once to read resp.usage",
            "n_mem0_rebuilds": 0,
            "n_answer_calls": 2 * len(rows),
            "equivalence_check": "replayed prompt_tokens must equal the formal, already "
                                 "server-reported memory_prompt_tokens / recovery_prompt_tokens",
            "writes_to_formal": False,
        },
        "not_done": "five independent policy executions (5 x 286) -- unnecessary, routing has "
                    "no persistent state effect on this workload",
    },
    "n_rows": len(rows),
    "n_personas": len({r["persona_id"] for r in rows}),
    "row_schema": sorted(keys),
}
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "cost_fast_path_audit.json").write_text(json.dumps(audit, indent=2))
print("COST_FAST_PATH =", status)
print("have   :", have)
print("missing:", missing)
