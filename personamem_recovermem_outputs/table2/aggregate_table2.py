"""Table-2 assembly: Task / Rec. / Cost, persona-equal, from the frozen routing
reconstruction plus the exact server-reported cost replay."""
from __future__ import annotations

import json, statistics, sys
from pathlib import Path

ROOT = Path("/home/aristella/recoverappworld/personamem_recovermem_outputs")
FORMAL, OUT = ROOT / "formal", ROOT / "table2"
POLICIES = ["Always Trust", "Always Recover", "Empirical-risk",
            "Random score + CRC", "ReCoverMem + CRC"]


def jl(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def main():
    routed = jl(OUT / "routed_decisions.jsonl")
    write = {r["persona_id"]: r for r in jl(OUT / "replay1_c_write.jsonl")}
    branch = {(r["persona_id"], r["question_id"]): r for r in jl(OUT / "replay2_branch_usage.jsonl")}
    recon = json.loads((OUT / "routing_reconstruction.json").read_text())

    personas, by_p = [], {}
    for d in routed:
        p = d["persona_id"]
        if p not in by_p:
            by_p[p] = []
            personas.append(p)
        by_p[p].append(d)

    # ---- replay integrity -------------------------------------------------
    miss = [f"{p}::{d['question_id']}" for p in personas for d in by_p[p]
            if (p, d["question_id"]) not in branch]
    if miss or set(write) != set(personas):
        raise SystemExit(f"incomplete replay: {len(miss)} branch rows missing, "
                         f"{len(set(personas) - set(write))} write rows missing")
    b = list(branch.values())
    integrity = {
        "n_branch_rows": len(b),
        "n_write_rows": len(write),
        "state_hash_matches_formal": all(x["state_hash_matches_formal"] for x in b),
        "option_order_hash_matches_formal": all(x["option_order_hash_matches_formal"] for x in b),
        "mem0_memory_count_matches_formal": all(
            x["mem0_memory_count_replay"] == x["mem0_memory_count_formal"] for x in b),
        "memory_evidence_tokens_match": sum(
            x["memory_evidence_tokens_replay"] == x["memory_evidence_tokens_formal"] for x in b),
        "recovery_evidence_tokens_match": sum(
            x["recovery_evidence_tokens_replay"] == x["recovery_evidence_tokens_formal"] for x in b),
        "memory_prompt_tokens_match": sum(x["memory_prompt_tokens_match"] for x in b),
        "recovery_prompt_tokens_match": sum(x["recovery_prompt_tokens_match"] for x in b),
        "retrieval_llm_calls_total": sum(x["mem_retrieval_llm_calls"] for x in b),
        "memory_choice_match": sum(x["memory_choice_match"] for x in b),
        "recovery_choice_match": sum(x["recovery_choice_match"] for x in b),
        "memory_completion_identical": sum(x["memory_completion_identical"] for x in b),
        "recovery_completion_identical": sum(x["recovery_completion_identical"] for x in b),
        "n_new_llm_calls_answer": sum(x["C_mem_branch"]["n_llm_calls"] + x["C_rec_branch"]["n_llm_calls"]
                                      for x in b),
        "n_new_llm_calls_write": sum(w["C_write"]["n_llm_calls"] for w in write.values()),
        "n_mem0_rebuilds": len(write),
        "write_path_equivalent": all(w["path_equivalent"] for w in write.values()),
        "all_usage_server_reported": all(w["C_write"]["all_usage_reported"] for w in write.values()),
    }
    integrity["n_new_llm_calls_total"] = (integrity["n_new_llm_calls_answer"]
                                          + integrity["n_new_llm_calls_write"])

    # ---- per-persona cost -------------------------------------------------
    cost = {p: {} for p in personas}
    for p in personas:
        w = write[p]["C_write"]
        rows = [(d, branch[(p, d["question_id"])]) for d in by_p[p]]
        c_raw = sum(x["C_rec_branch"]["total_tokens"] for _, x in rows)
        cost[p]["C_write"] = w["total_tokens"]
        cost[p]["C_write_in"] = w["prompt_tokens"]
        cost[p]["C_write_out"] = w["completion_tokens"]
        cost[p]["C_write_calls"] = w["n_llm_calls"]
        cost[p]["C_raw"] = c_raw
        cost[p]["T_i"] = len(rows)
        cost[p]["policies"] = {}
        for name in POLICIES:
            c_ctrl = c_mem = c_rec = 0
            for d, x in rows:
                m = x["C_mem_branch"]["total_tokens"]
                r = x["C_rec_branch"]["total_tokens"]
                route = d["policies"][name]["route"]
                if name == "Always Trust":
                    c_mem += m
                elif name == "Always Recover":
                    c_rec += r
                else:                       # frozen scorer needs the MEMORY-side draft first
                    if route == "TRUST":
                        c_mem += m
                    else:
                        c_ctrl += m         # draft computed, not deployed
                        c_rec += r
            total = w["total_tokens"] + c_ctrl + c_mem + c_rec
            cost[p]["policies"][name] = {
                "C_write": w["total_tokens"], "C_ctrl": c_ctrl, "C_mem": c_mem,
                "C_rec": c_rec, "C_total": total, "normalized_cost": total / c_raw,
                "norm_C_write": w["total_tokens"] / c_raw, "norm_C_ctrl": c_ctrl / c_raw,
                "norm_C_mem": c_mem / c_raw, "norm_C_rec": c_rec / c_raw,
            }

    # ---- table ------------------------------------------------------------
    rows_out, decomposition = [], {}
    for name in POLICIES:
        n = len(personas)
        norm = [cost[p]["policies"][name]["normalized_cost"] for p in personas]
        rows_out.append({
            "policy": name,
            "alpha": (None if name in ("Always Trust", "Always Recover") else 0.10),
            "tau": recon["taus"][name],
            "Task": recon["results"][name]["Task"],
            "Rec": recon["results"][name]["Rec"],
            "Cost": sum(norm) / n,
            "Cov_reconstructed": recon["results"][name]["Cov_reconstructed"],
            "n_recover_decisions": recon["results"][name]["n_recover_decisions"],
            "n_test_personas": n,
            "Cost_sd_over_personas": statistics.pstdev(norm),
            "Cost_min": min(norm), "Cost_max": max(norm),
        })
        decomposition[name] = {
            k: sum(cost[p]["policies"][name][k] for p in personas) / n
            for k in ("norm_C_write", "norm_C_ctrl", "norm_C_mem", "norm_C_rec")
        }
        decomposition[name]["norm_C_total"] = sum(norm) / n
        decomposition[name]["tokens_total_summed_over_personas"] = sum(
            cost[p]["policies"][name]["C_total"] for p in personas)

    raw_ref = {
        "definition": "raw-history-only: no Mem0 instantiation, no writes, no retrieval, no "
                      "controller score; every selected question answered by the frozen "
                      "RECOVERY route. C_write = C_ctrl = C_mem = 0.",
        "is_a_table2_row": False,
        "C_raw_per_persona": {str(p): cost[p]["C_raw"] for p in personas},
        "C_raw_total": sum(cost[p]["C_raw"] for p in personas),
        "reuse_justification": (
            "The RECOVERY branch calls TrajectoryRetriever over the immutable raw history and "
            "never touches the Mem0 store (V2Runner.run_instance calls self.recovery.recover, "
            "and the answerer sees only rec_ev.text), so a separate raw-only execution would "
            "issue byte-identical requests. The replayed recovery prompt token counts equal the "
            "formal ones on every decision, which confirms it empirically."),
    }

    payload = {
        "unit": "exact server-reported LLM tokens (usage.prompt_tokens + usage.completion_tokens)",
        "alpha": 0.10,
        "weighting": "persona-equal; normalized per persona against that persona's raw-history-only cost",
        "cost_fast_path": json.loads((OUT / "cost_fast_path_audit.json").read_text())["cost_fast_path"],
        "replay_integrity": integrity,
        "raw_history_only_reference": raw_ref,
        "per_persona": {str(p): cost[p] for p in personas},
        "decomposition_persona_equal": decomposition,
    }
    (OUT / "cost_decomposition.json").write_text(json.dumps(payload, indent=2))
    (OUT / "table2_personamem_rows.json").write_text(json.dumps(rows_out, indent=2))

    lines = ["| Policy | Task | Rec. | Cost |", "|---|---:|---:|---:|"]
    for r in rows_out:
        lines.append(f"| {r['policy']} | {r['Task']:.3f} | {r['Rec']:.3f} | {r['Cost']:.3f} |")
    table = "\n".join(lines)
    block = "\n\n".join(f"{r['policy']}\n{r['Task']:.3f} / {r['Rec']:.3f} / {r['Cost']:.3f}"
                        for r in rows_out)
    (OUT / "TABLE2_PERSONAMEM.txt").write_text(table + "\n\n" + block + "\n")
    print(table)
    print()
    print(block)
    print()
    print("integrity:", json.dumps(integrity, indent=1))


if __name__ == "__main__":
    main()
