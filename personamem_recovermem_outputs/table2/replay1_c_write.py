"""Replay 1 -- exact server-reported C_write_i, one Mem0 build per final-test persona.

Nothing under formal/ is read for writing or overwritten: the rebuild goes to a scratch
store root and only its token usage is kept. No question is answered here.
"""
from __future__ import annotations

import json, os, sys, time
from pathlib import Path

ROOT = Path("/home/aristella/recoverappworld/personamem_recovermem_outputs")
OUT = ROOT / "table2"
sys.path.insert(0, "/home/aristella/recoverappworld")
sys.path.insert(0, str(OUT))

import prefeval_shim
SHIM = prefeval_shim.install()

import usage_meter
usage_meter.install()

from recovermem.integrations.personamem_v2.runner import V2Runner

FROZEN = ROOT / "frozen_protocol"
LOG = OUT / "replay1_c_write.jsonl"
PROG = OUT / "replay1_c_write.progress.json"


def done_set():
    return set(json.loads(PROG.read_text())["completed"]) if PROG.exists() else set()


def mark(pid):
    d = sorted(done_set() | {int(pid)})
    tmp = PROG.with_suffix(".tmp"); tmp.write_text(json.dumps({"completed": d}))
    os.replace(tmp, PROG)


def main():
    amend = json.loads((FROZEN / "AMENDMENT_A1.json").read_text())
    personas = [int(p) for p in amend["persona_subsets"]["final_test"]]
    formal = {}
    for l in (ROOT / "formal" / "final_test.jsonl").read_text().splitlines():
        if l.strip():
            r = json.loads(l)
            formal.setdefault(r["persona_id"], r)

    r = V2Runner(store_root=OUT / "replay1_write_stores", b_mem=2048)
    done = done_set()
    for n, pid in enumerate(personas, 1):
        if pid in done:
            continue
        t0 = time.perf_counter()
        with usage_meter.phase("write"):
            m = r.build_memory(pid)
        w = usage_meter.drain("write")
        f = formal[pid]
        rec = {
            "persona_id": pid,
            "C_write": {"n_llm_calls": w["n_calls"], "prompt_tokens": w["prompt_tokens"],
                        "completion_tokens": w["completion_tokens"],
                        "total_tokens": w["total_tokens"],
                        "all_usage_reported": w["all_usage_reported"]},
            "replay": {"n_chunks": m["n_chunks"], "n_messages": m["n_messages"],
                       "history_tokens": m["history_tokens"],
                       "mem0_memory_count": m["mem0_memory_count"],
                       "mem0_parse_failures": m["mem0_parse_failures"],
                       "build_s": m["build_s"], "wall_s": time.perf_counter() - t0},
            "formal": {"n_chunks": f["n_write_chunks"], "n_messages": f["n_history_messages"],
                       "history_tokens": f["history_tokens"],
                       "mem0_memory_count": f["mem0_memory_count"],
                       "mem0_parse_failures": f["mem0_extraction_parse_failures"],
                       "build_s": f["memory_build_s"]},
        }
        rec["path_equivalent"] = (rec["replay"]["n_chunks"] == rec["formal"]["n_chunks"]
                                  and rec["replay"]["n_messages"] == rec["formal"]["n_messages"]
                                  and rec["replay"]["history_tokens"] == rec["formal"]["history_tokens"])
        with LOG.open("a") as fh:
            fh.write(json.dumps(rec) + "\n"); fh.flush(); os.fsync(fh.fileno())
        mark(pid)
        print(f"[write {n}/{len(personas)}] persona{pid} calls={w['n_calls']} "
              f"tok={w['total_tokens']} ({w['prompt_tokens']}in/{w['completion_tokens']}out) "
              f"chunks={m['n_chunks']}/{f['n_write_chunks']} mem={m['mem0_memory_count']}/"
              f"{f['mem0_memory_count']} {time.perf_counter()-t0:.0f}s", flush=True)
    print("REPLAY1 DONE", flush=True)


if __name__ == "__main__":
    main()
