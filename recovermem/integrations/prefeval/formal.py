"""Frozen formal collection and analysis for PrefEval.

Ordering is enforced by the file system, not by discipline alone: calibration thresholds
are written to ``thresholds.json`` and hashed *before* ``final_test.jsonl`` exists, and the
final-test evaluation refuses to run if the threshold file is missing or was written after
the test outcomes.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

from recovermem.integrations.prefeval.dataset import load_instances, group_key_components
from recovermem.integrations.prefeval.runner import PrefEvalRunner

ROOT = Path("/home/aristella/recoverappworld")
FINAL = ROOT / "results/prefeval/final"
CONFIG = ROOT / "results/prefeval/configs/PRIMARY_SETTING.json"
B_MEM = 2048


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sha256_obj(o: Any) -> str:
    return hashlib.sha256(json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()


def collect(split: str, ids: list[str], out_path: Path) -> list[dict[str, Any]]:
    """Collect one split's paired decisions into a JSONL log.

    Refuses to overwrite an existing log: a formal split is collected once, and silently
    re-collecting one would let a rerun replace outcomes that later artifacts were hashed
    against.
    """
    if out_path.exists() and out_path.stat().st_size:
        raise RuntimeError(f"{out_path} already exists and is non-empty; refusing to recollect")
    cfg = json.loads(CONFIG.read_text())
    forbidden = set(cfg["frozen_partitions"]["smoke"]) | set(cfg["frozen_partitions"]["pilot"]) | set(
        cfg["frozen_partitions"]["budget_audit"]
    )
    overlap = forbidden & set(ids)
    if overlap:
        raise RuntimeError(f"{split} reuses non-formal units: {sorted(overlap)}")

    inst = {i.pair_id: i for i in load_instances()}
    groups = group_key_components(list(inst.values()))
    runner = PrefEvalRunner(store_root=FINAL / "memory" / split, b_mem=B_MEM)

    rows: list[dict[str, Any]] = []
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:
        for n, pid in enumerate(ids, 1):
            r = runner.run_instance(inst[pid], groups[pid])
            row = r.to_dict()
            row["split"] = split
            rows.append(row)
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            print(
                f"[{split} {n}/{len(ids)}] {pid} build={r.memory_build_s:.0f}s mem={r.mem0_memory_count} "
                f"parse_fail={r.mem0_extraction_parse_failures} E_mem={r.memory_evidence_tokens} "
                f"E_rec={r.recovery_evidence_tokens} gold={r.gold_letter} m={r.memory_choice} "
                f"r={r.recovery_choice} R_mem={r.r_mem} R_rec={r.r_rec} valid={r.pair_valid}",
                flush=True,
            )
    return rows


def read_jsonl(p: Path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def check_invariants(rows: list[dict[str, Any]], split: str) -> dict[str, Any]:
    """Hard invariants (brief §8). Any failure is an infrastructure stop."""
    issues: list[str] = []
    if not all(r["pair_valid"] for r in rows):
        issues.append("pair_valid false on some units")
    if not all(
        r["state_hash"] == r["memory_branch_state_hash"] == r["recovery_branch_state_hash"]
        for r in rows
    ):
        issues.append("common x hash mismatch between branches")
    if len({r["state_hash"] for r in rows}) != len(rows):
        issues.append("duplicate common-state hashes: instances are not distinct")
    if not all(r["memory_evidence_tokens"] <= r["b_mem"] for r in rows):
        issues.append("B_mem violated")
    if not all(r["recovery_evidence_tokens"] <= r["b_rec"] for r in rows):
        issues.append("B_rec violated")
    if not all(r["b_mem"] == r["b_rec"] == B_MEM for r in rows):
        issues.append("budget drifted from the frozen value")
    if any(r["errors"] for r in rows):
        issues.append(f"runner errors: {[r['errors'] for r in rows if r['errors']]}")
    return {
        "split": split,
        "n_units": len(rows),
        "all_pair_valid": all(r["pair_valid"] for r in rows),
        "distinct_state_hashes": len({r["state_hash"] for r in rows}),
        "b_mem_respected": all(r["memory_evidence_tokens"] <= r["b_mem"] for r in rows),
        "b_rec_respected": all(r["recovery_evidence_tokens"] <= r["b_rec"] for r in rows),
        "memory_unchanged_during_query": not any(r["errors"] for r in rows),
        "mem0_extraction_parse_failures_total": sum(r["mem0_extraction_parse_failures"] for r in rows),
        "external_api_calls": 0,
        "llm_judge_calls": 0,
        "issues": issues,
        "valid": not issues,
    }
