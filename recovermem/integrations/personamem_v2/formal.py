"""Frozen formal collection for PersonaMem-v2 128K text MCQ.

Resumability is per persona: each persona's rows are appended and fsynced as one unit and
its id is recorded in a sidecar ``.progress.json``. An interrupted run re-enters and skips
completed personas rather than restarting, and a persona is never half-written.

Ordering is enforced by the file system: ``collect_final_test`` refuses to run unless
``thresholds.json`` already exists, so final-test outcomes cannot be generated before the
thresholds are frozen and hashed.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

from recovermem.integrations.personamem_v2.dataset import V2Bench
from recovermem.integrations.personamem_v2.runner import V2Runner

ROOT = Path("/home/aristella/recoverappworld/personamem_recovermem_outputs")
FORMAL = ROOT / "formal"
FROZEN = ROOT / "frozen_protocol"
B_MEM = 2048


def sha256_file(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _progress_path(out: Path) -> Path:
    return out.with_suffix(".progress.json")


def _load_progress(out: Path) -> list[int]:
    p = _progress_path(out)
    return json.loads(p.read_text())["completed_personas"] if p.exists() else []


def _mark_done(out: Path, pid: int) -> None:
    p = _progress_path(out)
    done = _load_progress(out)
    done.append(int(pid))
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"completed_personas": done}, indent=1))
    os.replace(tmp, p)  # atomic


def collect(split: str, runner: Optional[V2Runner] = None) -> list[dict[str, Any]]:
    """Collect one frozen split, persona by persona, resumable."""
    amend = json.loads((FROZEN / "AMENDMENT_A1.json").read_text())
    personas = amend["persona_subsets"][split]
    selected = amend["selected_questions"][split]
    out = FORMAL / f"{split}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)

    if split == "final_test" and not (FORMAL / "thresholds.json").exists():
        raise RuntimeError(
            "thresholds.json does not exist; final-test outcomes must not be generated "
            "before the calibration thresholds are frozen and hashed."
        )

    r = runner or V2Runner(store_root=FORMAL / "memory" / split, b_mem=B_MEM)
    b = r.bench
    done = set(_load_progress(out))
    if done:
        print(f"[{split}] resuming, {len(done)}/{len(personas)} personas already complete", flush=True)

    for n, pid in enumerate(personas, 1):
        if pid in done:
            continue
        keep = set(selected[str(pid)]["selected_question_ids"])
        m = r.build_memory(pid)
        pre = int((r.host.snapshot().get("n_memories") or 0))
        rows = []
        for inst in b.instances_for(pid):
            if inst.question_id not in keep:
                continue
            row = r.run_instance(inst, m["history"])
            row.update(split=split, n_history_messages=m["n_messages"],
                       history_tokens=m["history_tokens"], n_write_chunks=m["n_chunks"],
                       memory_build_s=m["build_s"], mem0_memory_count=pre,
                       mem0_extraction_parse_failures=m["mem0_parse_failures"],
                       memory_parse_ok=row["memory_choice"] is not None,
                       recovery_parse_ok=row["recovery_choice"] is not None)
            rows.append(row)
        post = int((r.host.snapshot().get("n_memories") or 0))
        for row in rows:
            row["mem0_memory_count_after_queries"] = post
            row["memory_unchanged_during_queries"] = (pre == post)
        if len(rows) != len(keep):
            raise RuntimeError(f"persona {pid}: expected {len(keep)} selected rows, got {len(rows)}")

        with out.open("a") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        _mark_done(out, pid)
        print(f"[{split} {n}/{len(personas)}] persona{pid} build={m['build_s']:.0f}s "
              f"mem={pre}->{post} rows={len(rows)} parse_fail="
              f"{sum(1 for x in rows if not x['memory_parse_ok'] or not x['recovery_parse_ok'])} "
              f"R_mem={sum(x['r_mem'] for x in rows)}/{len(rows)}", flush=True)

    return read_jsonl(out)


def read_jsonl(p) -> list[dict[str, Any]]:
    p = Path(p)
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def check_invariants(rows: list[dict[str, Any]], split: str) -> dict[str, Any]:
    issues: list[str] = []
    if not all(r["pair_valid"] for r in rows):
        issues.append("pair_valid false somewhere")
    if not all(r["state_hash"] == r["memory_branch_state_hash"] == r["recovery_branch_state_hash"] for r in rows):
        issues.append("common x hash mismatch between branches")
    if len({r["state_hash"] for r in rows}) != len(rows):
        issues.append("duplicate common-state hashes")
    if not all(r["memory_evidence_tokens"] <= B_MEM for r in rows):
        issues.append("B_mem violated")
    if not all(r["recovery_evidence_tokens"] <= B_MEM for r in rows):
        issues.append("B_rec violated")
    if not all(r["b_mem"] == r["b_rec"] == B_MEM for r in rows):
        issues.append("budget drifted")
    if not all(r["memory_unchanged_during_queries"] for r in rows):
        issues.append("memory count changed during the query phase")
    pf = sum(1 for r in rows if not r["memory_parse_ok"]) + sum(1 for r in rows if not r["recovery_parse_ok"])
    return {
        "split": split, "n_personas": len({r["persona_id"] for r in rows}), "n_decisions": len(rows),
        "all_pair_valid": all(r["pair_valid"] for r in rows),
        "distinct_state_hashes": len({r["state_hash"] for r in rows}),
        "b_mem_respected": all(r["memory_evidence_tokens"] <= B_MEM for r in rows),
        "b_rec_respected": all(r["recovery_evidence_tokens"] <= B_MEM for r in rows),
        "memory_unchanged_during_queries": all(r["memory_unchanged_during_queries"] for r in rows),
        "parser_failures": pf,
        "mem0_extraction_parse_failures_total": sum(
            r["mem0_extraction_parse_failures"] for r in rows if r["question_id"] == next(
                x["question_id"] for x in rows if x["persona_id"] == r["persona_id"])),
        "external_api_calls": 0, "llm_judge_calls": 0, "multimodal_calls": 0,
        "issues": issues, "valid": not issues,
    }
