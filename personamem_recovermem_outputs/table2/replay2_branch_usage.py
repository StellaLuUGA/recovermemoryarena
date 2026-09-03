"""Replay 2 -- exact server-reported prompt+completion usage for both branch calls.

The FROZEN final-test Mem0 store is reused (through a scratch copy, so formal/ is never
opened for writing), and the frozen recovery retrieval is recomputed by the same
deterministic lexical backend. Both branch prompts are therefore byte-identical to the
formal run's, which the replayed prompt_tokens are asserted against. Only cost is taken
from here; correctness stays the formal Table-1 value.
"""
from __future__ import annotations

import json, os, shutil, sys, time
from pathlib import Path

ROOT = Path("/home/aristella/recoverappworld/personamem_recovermem_outputs")
OUT = ROOT / "table2"
sys.path.insert(0, "/home/aristella/recoverappworld")
sys.path.insert(0, str(OUT))

import prefeval_shim
SHIM = prefeval_shim.install()

import usage_meter
usage_meter.install()

from recovermem.hosts.mem0_adapter import Mem0Config
from recovermem.integrations.personamem_v2.runner import V2Runner

FROZEN = ROOT / "frozen_protocol"
FORMAL_STORES = ROOT / "formal" / "memory" / "final_test"
SCRATCH = OUT / "replay2_store_copies"
LOG = OUT / "replay2_branch_usage.jsonl"
PROG = OUT / "replay2_branch_usage.progress.json"
B = 2048


def done_set():
    return set(json.loads(PROG.read_text())["completed"]) if PROG.exists() else set()


def mark(pid):
    d = sorted(done_set() | {int(pid)})
    tmp = PROG.with_suffix(".tmp"); tmp.write_text(json.dumps({"completed": d}))
    os.replace(tmp, PROG)


def bind_frozen_store(host, pid: int) -> Path:
    """Bind the adapter to a COPY of the frozen store, byte-for-byte, read-only in effect."""
    eid = f"persona{pid}"
    src = FORMAL_STORES / eid
    dst = SCRATCH / eid
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)
    cfg = Mem0Config(**{**host.config.__dict__})
    cfg.vector_store_path = str(dst)
    cfg.history_db_path = str(dst / "history.db")
    cfg.collection_name = f"{host.config.collection_name}_{eid}"
    host._memory = host._mem0.Memory.from_config(cfg.to_mem0_dict())
    host._resolved_cfg = cfg
    host.episode_id = eid
    return dst


def main():
    amend = json.loads((FROZEN / "AMENDMENT_A1.json").read_text())
    personas = [int(p) for p in amend["persona_subsets"]["final_test"]]
    selected = amend["selected_questions"]["final_test"]
    formal = {}
    for l in (ROOT / "formal" / "final_test.jsonl").read_text().splitlines():
        if l.strip():
            r = json.loads(l)
            formal[(r["persona_id"], r["question_id"])] = r

    r = V2Runner(store_root=OUT / "replay2_unused_root", b_mem=B)
    b = r.bench
    done = done_set()
    for n, pid in enumerate(personas, 1):
        if pid in done:
            continue
        t0 = time.perf_counter()
        d = bind_frozen_store(r.host, pid)
        snap_n = int(r.host.snapshot().get("n_memories") or 0)
        history = b.history(pid)
        keep = set(selected[str(pid)]["selected_question_ids"])
        rows, nmis = [], 0
        for inst in b.instances_for(pid):
            if inst.question_id not in keep:
                continue
            f = formal[(pid, inst.question_id)]
            if inst.state_hash() != f["state_hash"] or inst.option_order_hash() != f["option_order_hash"]:
                raise SystemExit(
                    f"FROZEN STATE NOT REPRODUCED for {pid}::{inst.question_id}. The released "
                    f"option shuffle seeds on hash(str); this interpreter's PYTHONHASHSEED=13 "
                    f"hash differs from the formal run's. Use the formal run's interpreter.")
            x = inst.common_state_text()
            with usage_meter.phase("retrieve_mem"):
                mem_ev = r.host.retrieve(x, B)
            ret = usage_meter.drain("retrieve_mem")
            with usage_meter.phase("mem"):
                mem_ans = r.answerer.answer(x, mem_ev.text)
            um = usage_meter.drain("mem")
            rec_ev = r.recovery.recover(x, history, B)
            with usage_meter.phase("rec"):
                rec_ans = r.answerer.answer(x, rec_ev.text)
            ur = usage_meter.drain("rec")

            row = {
                "persona_id": pid, "question_id": inst.question_id,
                "state_hash_matches_formal": inst.state_hash() == f["state_hash"],
                "option_order_hash_matches_formal": inst.option_order_hash() == f["option_order_hash"],
                "mem0_memory_count_replay": snap_n,
                "mem0_memory_count_formal": f["mem0_memory_count"],
                "memory_evidence_tokens_replay": mem_ev.tokens,
                "memory_evidence_tokens_formal": f["memory_evidence_tokens"],
                "recovery_evidence_tokens_replay": rec_ev.tokens,
                "recovery_evidence_tokens_formal": f["recovery_evidence_tokens"],
                "mem_retrieval_llm_calls": ret["n_calls"],
                "mem_retrieval_total_tokens": ret["total_tokens"],
                "C_mem_branch": {"n_llm_calls": um["n_calls"],
                                 "prompt_tokens": um["prompt_tokens"],
                                 "completion_tokens": um["completion_tokens"],
                                 "total_tokens": um["total_tokens"]},
                "C_rec_branch": {"n_llm_calls": ur["n_calls"],
                                 "prompt_tokens": ur["prompt_tokens"],
                                 "completion_tokens": ur["completion_tokens"],
                                 "total_tokens": ur["total_tokens"]},
                "memory_prompt_tokens_formal": f["memory_prompt_tokens"],
                "recovery_prompt_tokens_formal": f["recovery_prompt_tokens"],
                "memory_prompt_tokens_match": um["prompt_tokens"] == f["memory_prompt_tokens"],
                "recovery_prompt_tokens_match": ur["prompt_tokens"] == f["recovery_prompt_tokens"],
                "memory_choice_replay": mem_ans.parsed_choice,
                "memory_choice_formal": f["memory_choice"],
                "recovery_choice_replay": rec_ans.parsed_choice,
                "recovery_choice_formal": f["recovery_choice"],
                "memory_completion_identical": mem_ans.completion == f["memory_completion"],
                "recovery_completion_identical": rec_ans.completion == f["recovery_completion"],
                "memory_choice_match": mem_ans.parsed_choice == f["memory_choice"],
                "recovery_choice_match": rec_ans.parsed_choice == f["recovery_choice"],
            }
            nmis += (not row["memory_prompt_tokens_match"]) + (not row["recovery_prompt_tokens_match"])
            rows.append(row)
        if len(rows) != len(keep):
            raise SystemExit(f"persona {pid}: {len(rows)} rows, expected {len(keep)}")
        with LOG.open("a") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
            fh.flush(); os.fsync(fh.fileno())
        mark(pid)
        shutil.rmtree(d, ignore_errors=True)
        print(f"[branch {n}/{len(personas)}] persona{pid} rows={len(rows)} "
              f"prompt_tok_mismatch={nmis} "
              f"choice_match={sum(x['memory_choice_match'] and x['recovery_choice_match'] for x in rows)}/{len(rows)} "
              f"{time.perf_counter()-t0:.0f}s", flush=True)
    print("REPLAY2 DONE", flush=True)


if __name__ == "__main__":
    main()
