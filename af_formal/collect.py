"""Native logging trajectory + paired MEMORY/RECOVERY evaluation at controlled states."""
from __future__ import annotations

import json
import traceback
from pathlib import Path

from af_formal.common import (GAMMA, LEDGER, MAX_BRANCH_ACTIONS, MAX_TOTAL_AGENT_ACTIONS,
                              QWEN_MAX_MODEL_LEN, jdump, log, sha256_text, set_bucket)
from af_formal import host as H
from af_formal import memhost as M

from recovermem.scoring.features import (CandidateAction, DecisionState, extract_features)

PROBE_BUDGET = 32768          # audit-only: retrieve without effective truncation


def _n_tok(text: str) -> int:
    return M.COUNTER.count_text(text)


def run_branch(game_file, prefix, rank0, label, evidence_text, x_frozen, bucket,
               max_actions=MAX_BRANCH_ACTIONS, want_first_logprobs=False):
    """Reconstruct S_t exactly, hand the branch its evidence, run <= max_actions."""
    bep = H.reconstruct(game_file, prefix)
    recon_ok = (bep.rank == rank0)
    x_hash = sha256_text(x_frozen)
    local, steps = [], []
    first_action, first_mlp = None, None
    success = False
    try:
        for k in range(max_actions):
            x = x_frozen if k == 0 else bep.x_text()
            out = H.act_branch(label, evidence_text, x, local, bep.admissible, bucket,
                               want_logprobs=(k == 0 and want_first_logprobs))
            if k == 0:
                first_action, first_mlp = out["command"], out["mean_logprob"]
            obs, rank, done = bep.step(out["command"])
            local.append((out["command"], obs))
            steps.append({"k": k, "raw": out["raw"], "command": out["command"],
                          "valid": out["valid"], "rank": rank, "won": bep.won})
            if rank > rank0 or bep.won:
                success = True
                break
            if done:
                break
    finally:
        bep.close()
    return {"reconstruction_ok": recon_ok, "x_hash": x_hash, "success": bool(success),
            "n_steps": len(steps), "won": bep.won, "final_rank": bep.rank,
            "first_action": first_action, "first_mean_logprob": first_mlp,
            "steps": steps}


def evaluate_pair(ep, hostmem, decision_id, rank0, b_mem, b_rec, predictor=None):
    """One paired controlled decision. Branch state is always discarded."""
    x_frozen = ep.x_text()
    x_hash = sha256_text(x_frozen)
    prefix = [a for a, _ in ep.history]

    e_mem = hostmem.retrieve(x_frozen, b_mem)
    set_bucket("rec")
    e_rec = M.recover(x_frozen, ep.history_messages(), b_rec)

    mem = run_branch(ep.game_file, prefix, rank0, "Retrieved memory", e_mem.text,
                     x_frozen, "mem", want_first_logprobs=True)
    rec = run_branch(ep.game_file, prefix, rank0, "Recovered history", e_rec.text,
                     x_frozen, "rec")

    cand = CandidateAction(text=mem["first_action"] or "",
                           arguments={"command": mem["first_action"] or ""},
                           mean_logprob=mem["first_mean_logprob"])
    state = DecisionState(query=x_frozen, step_index=ep.t,
                          max_steps=MAX_TOTAL_AGENT_ACTIONS, tool_names=[],
                          state_hash=x_hash, state_tokens=_n_tok(x_frozen))
    feats = extract_features(state, e_mem, cand)
    score = float(predictor.predict_score(feats)) if predictor is not None else None

    hist_text = H.render_history(ep.intro, ep.history)
    budget_ok = (e_mem.tokens <= b_mem) and (e_rec.tokens <= b_rec)
    pair_valid = bool(mem["reconstruction_ok"] and rec["reconstruction_ok"]
                      and mem["x_hash"] == rec["x_hash"] == x_hash and budget_ok)

    u_mem = 1.0 if mem["success"] else 0.0
    u_rec = 1.0 if rec["success"] else 0.0
    return {
        "episode_id": ep.episode_id, "decision_id": decision_id,
        "decision_key": f"{ep.episode_id}::{decision_id}",
        "game_file": ep.game_file, "task_type": ep.task_type,
        "t": ep.t, "rank_at_S": rank0, "K": ep.K,
        "common_state_text": x_frozen, "common_state_tokens": _n_tok(x_frozen),
        "common_state_hash": x_hash,
        "memory_branch_common_state_hash": mem["x_hash"],
        "recovery_branch_common_state_hash": rec["x_hash"],
        "expected_common_state_hash": x_hash,
        "budget_mem": b_mem, "budget_rec": b_rec,
        "e_mem_tokens": e_mem.tokens, "e_mem_n_items": e_mem.n_packed,
        "e_mem_n_candidates": e_mem.n_candidates,
        "e_rec_tokens": e_rec.tokens, "e_rec_n_items": len(getattr(e_rec, "items", []) or []),
        "e_rec_truncated": bool(getattr(e_rec, "truncated", None)
                                if getattr(e_rec, "truncated", None) is not None
                                else e_rec.tokens >= b_rec),
        "history_tokens": _n_tok(hist_text), "n_prior_actions": len(ep.history),
        "n_memories": hostmem.n_memories(),
        "u_mem": u_mem, "u_rec": u_rec,
        "r_mem": int(u_mem >= GAMMA), "r_rec": int(u_rec >= GAMMA),
        "mem_steps": mem["n_steps"], "rec_steps": rec["n_steps"],
        "mem_won": mem["won"], "rec_won": rec["won"],
        "mem_first_action": mem["first_action"], "rec_first_action": rec["first_action"],
        "features": feats.to_log(), "score": score,
        "reconstruction_ok_mem": mem["reconstruction_ok"],
        "reconstruction_ok_rec": rec["reconstruction_ok"],
        "budget_ok": budget_ok, "pair_valid": pair_valid,
        "mem_branch_steps": mem["steps"], "rec_branch_steps": rec["steps"],
    }


def run_episode(game_rec, run_tag, b_mem=None, b_rec=None, collect_pairs=True,
                predictor=None, audit=False):
    """One formal episode: native Config-C logging trajectory + optional paired records."""
    game_file, episode_id = game_rec["game_file"], game_rec["episode_id"]
    LEDGER.reset()
    ep = H.Episode(game_file)
    ep.episode_id, ep.task_type = episode_id, game_rec["task_type"]
    hostmem = M.Mem0Host(run_tag)
    hostmem.reset(episode_id)
    hostmem.write_task(ep.task_instruction, ep.intro)

    records, native_steps, audit_rows = [], [], []
    max_rank, decision_id, err = ep.rank, 0, None
    try:
        while ep.t < MAX_TOTAL_AGENT_ACTIONS and not ep.done:
            out = H.act_native(ep.intro, ep.history, ep.admissible)
            obs, rank, done = ep.step(out["command"])
            hostmem.write_turn(out["command"], obs)
            native_steps.append({"t": ep.t, "raw": out["raw"], "command": out["command"],
                                 "valid": out["valid"], "rank": rank, "won": ep.won,
                                 "prompt_tokens": out["prompt_tokens"]})
            if rank > max_rank:
                max_rank = rank
                if rank < ep.K:
                    if audit:
                        x = ep.x_text()
                        probe = hostmem.retrieve(x, PROBE_BUDGET)
                        set_bucket("rec")
                        rprobe = M.recover(x, ep.history_messages(), PROBE_BUDGET)
                        audit_rows.append({
                            "episode_id": episode_id, "t": ep.t, "rank": rank, "K": ep.K,
                            "x_tokens": _n_tok(x),
                            "native_mem_evidence_tokens": probe.tokens,
                            "native_mem_n_candidates": probe.n_candidates,
                            "raw_history_tokens": _n_tok(H.render_history(ep.intro, ep.history)),
                            "recover_probe_tokens": rprobe.tokens,
                            "base_prompt_tokens": M.COUNTER.count_messages(
                                H.branch_prompt("Retrieved memory", "", x, [])),
                            "n_memories": hostmem.n_memories()})
                    elif collect_pairs:
                        records.append(evaluate_pair(ep, hostmem, decision_id, rank,
                                                     b_mem, b_rec, predictor))
                        decision_id += 1
    except Exception as e:
        err = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1500:]}"
        log(f"  !! {episode_id}: {err.splitlines()[0]}")
    finally:
        result = {
            "episode_id": episode_id, "game_file": game_file,
            "task_type": game_rec["task_type"], "K": ep.K,
            "n_actions": ep.t, "won": ep.won, "final_rank": ep.rank,
            "max_rank": max_rank, "n_controlled_decisions": len(records) or len(audit_rows),
            "n_memories": hostmem.n_memories(),
            "tokens": LEDGER.snapshot(), "error": err,
            "native_steps": native_steps,
            "records": records, "audit_rows": audit_rows,
        }
        ep.close(); hostmem.close()
    return result


def run_partition(manifest_path, out_jsonl, run_tag, b_mem=None, b_rec=None,
                  collect_pairs=True, predictor=None, audit=False):
    """Resumable partition run; one JSON line per episode, flushed immediately."""
    games = json.loads(Path(manifest_path).read_text())["games"]
    out = Path(out_jsonl); out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        for line in out.open():
            try:
                done.add(json.loads(line)["episode_id"])
            except Exception:
                pass
    with out.open("a") as fh:
        for i, g in enumerate(games):
            if g["episode_id"] in done:
                continue
            r = run_episode(g, run_tag, b_mem, b_rec, collect_pairs, predictor, audit)
            fh.write(json.dumps(r, default=str) + "\n"); fh.flush()
            log(f"  [{i+1}/{len(games)}] {g['episode_id'][:46]:46s} "
                f"acts={r['n_actions']:2d} won={int(r['won'])} maxrank={r['max_rank']}/{r['K']} "
                f"dec={r['n_controlled_decisions']} tok={r['tokens']['total_tokens']}")
    return out
