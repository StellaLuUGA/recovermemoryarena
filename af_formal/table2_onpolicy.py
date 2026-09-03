"""Table 2: TRUE on-policy deployment. No replay of the Table-1 logging trajectory."""
from __future__ import annotations

import json
import math
import statistics
import traceback
from pathlib import Path

from af_formal.common import (LEDGER, MAX_BRANCH_ACTIONS, MAX_TOTAL_AGENT_ACTIONS, RESULTS,
                              SEED, jdump, jload, log, set_bucket, sha256_json, sha256_text)
from af_formal import host as H
from af_formal import memhost as M

from recovermem.calibration.random_crc import generate_random_scores
from recovermem.scoring.features import CandidateAction, DecisionState, extract_features
from recovermem.scoring.predictor import RecoverabilityPredictor

T2 = RESULTS / "table2"
POLICIES = ("always_trust", "always_recover", "empirical_risk_0.10",
            "random_crc_0.10", "recovermem_crc_0.10", "raw_history_only")
MAIN_ROWS = [("Always Trust", "always_trust"), ("Always Recover", "always_recover"),
             ("Empirical-risk (.10)", "empirical_risk_0.10"),
             ("Random + CRC (.10)", "random_crc_0.10"),
             ("ReCoverMem + CRC (.10)", "recovermem_crc_0.10")]
NEEDS_SCORE = {"empirical_risk_0.10", "recovermem_crc_0.10"}
NEEDS_MEM = {"always_trust", "always_recover", "empirical_risk_0.10",
             "random_crc_0.10", "recovermem_crc_0.10"}


def _tau(v):
    if isinstance(v, str):
        return math.inf if v == "Infinity" else -math.inf
    return float(v)


def rollout(game_rec, policy, thresholds, predictor, b_mem, b_rec, run_tag):
    game_file, episode_id = game_rec["game_file"], game_rec["episode_id"]
    LEDGER.reset()
    ep = H.Episode(game_file)
    ep.episode_id, ep.task_type = episode_id, game_rec["task_type"]
    uses_mem = policy in NEEDS_MEM
    hostmem = None
    if uses_mem:
        hostmem = M.Mem0Host(f"{run_tag}/{policy}")
        hostmem.reset(episode_id)
        hostmem.write_task(ep.task_instruction, ep.intro)

    tau = _tau(thresholds["rules"][policy]["tau"]) if policy in thresholds["rules"] else None
    routes, steps, err = [], [], None
    max_rank = ep.rank

    def native_step():
        out = H.act_native(ep.intro, ep.history, ep.admissible, bucket="native")
        obs, rank, done = ep.step(out["command"])
        if uses_mem:
            hostmem.write_turn(out["command"], obs)
        steps.append({"t": ep.t, "phase": "native", "command": out["command"],
                      "valid": out["valid"], "rank": rank, "won": ep.won})
        return rank, done

    try:
        # -- phase 1: frozen Config-C native full-history policy until first boundary --
        while ep.t < MAX_TOTAL_AGENT_ACTIONS and not ep.done:
            rank, done = native_step()
            if rank > max_rank:
                max_rank = rank
                if rank < ep.K:
                    break

        # raw-history-only reference never routes: it stays on the native policy.
        if policy == "raw_history_only":
            while ep.t < MAX_TOTAL_AGENT_ACTIONS and not ep.done:
                native_step()
        else:
            # -- phase 2: on-policy routing at every controlled boundary --
            while ep.t < MAX_TOTAL_AGENT_ACTIONS and not ep.done and max_rank < ep.K:
                x = ep.x_text()
                rank0 = ep.rank
                e_mem = hostmem.retrieve(x, b_mem)
                set_bucket("rec")
                e_rec = M.recover(x, ep.history_messages(), b_rec)

                score, reused = None, None
                if policy in NEEDS_SCORE:
                    cand_out = H.act_branch("Retrieved memory", e_mem.text, x, [],
                                            ep.admissible, "ctrl", want_logprobs=True)
                    feats = extract_features(
                        DecisionState(query=x, step_index=ep.t,
                                      max_steps=MAX_TOTAL_AGENT_ACTIONS,
                                      state_hash=sha256_text(x)),
                        e_mem,
                        CandidateAction(text=cand_out["command"],
                                        arguments={"command": cand_out["command"]},
                                        mean_logprob=cand_out["mean_logprob"]))
                    score = float(predictor.predict_score(feats))
                    reused = cand_out
                elif policy.startswith("random_crc"):
                    key = f"{episode_id}::{len(routes)}"
                    score = generate_random_scores([key], seed=SEED)[key]

                if policy == "always_trust":
                    route = "MEMORY"
                elif policy == "always_recover":
                    route = "RECOVERY"
                else:
                    route = "MEMORY" if score >= tau else "RECOVERY"

                label, ev_text, bucket = (("Retrieved memory", e_mem.text, "mem")
                                          if route == "MEMORY"
                                          else ("Recovered history", e_rec.text, "rec"))
                routes.append({"decision_index": len(routes), "t": ep.t, "rank": rank0,
                               "score": score, "tau": (None if tau is None else
                                                       ("Infinity" if math.isinf(tau) and tau > 0
                                                        else "-Infinity" if math.isinf(tau)
                                                        else round(tau, 6))),
                               "route": route,
                               "e_mem_tokens": e_mem.tokens, "e_rec_tokens": e_rec.tokens})

                local, seg_ok = [], False
                for k in range(MAX_BRANCH_ACTIONS):
                    if ep.t >= MAX_TOTAL_AGENT_ACTIONS or ep.done:
                        break
                    if k == 0 and route == "MEMORY" and reused is not None:
                        out = reused          # the scorer's candidate IS the first action
                    else:
                        out = H.act_branch(label, ev_text, x if k == 0 else ep.x_text(),
                                           local, ep.admissible, bucket)
                    obs, rank, done = ep.step(out["command"])
                    if uses_mem:
                        hostmem.write_turn(out["command"], obs)
                    local.append((out["command"], obs))
                    steps.append({"t": ep.t, "phase": f"route:{route}",
                                  "decision_index": routes[-1]["decision_index"],
                                  "command": out["command"], "valid": out["valid"],
                                  "rank": rank, "won": ep.won})
                    if rank > rank0 or ep.won:
                        seg_ok = True
                        max_rank = max(max_rank, rank)
                        break
                    if done:
                        break
                routes[-1]["segment_success"] = seg_ok
                routes[-1]["segment_actions"] = len(local)
                # state is NOT restored: it is this policy's own on-policy state
    except Exception as e:
        err = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1200:]}"
        log(f"  !! {policy}/{episode_id}: {err.splitlines()[0]}")
    finally:
        n_rec = sum(1 for r in routes if r["route"] == "RECOVERY")
        result = {
            "policy": policy, "episode_id": episode_id, "game_file": game_file,
            "task_type": game_rec["task_type"], "K": ep.K,
            "task": int(ep.won), "final_rank": ep.rank, "max_rank": max_rank,
            "n_actions": ep.t, "n_route_decisions": len(routes),
            "n_recovery_routes": n_rec,
            "rec_frac": (n_rec / len(routes)) if routes else 0.0,
            "zero_route": len(routes) == 0,
            "mem0_instantiated": bool(uses_mem),
            "n_memories": hostmem.n_memories() if uses_mem else 0,
            "tokens": LEDGER.snapshot(), "routes": routes, "steps": steps, "error": err,
        }
        ep.close()
        if hostmem:
            hostmem.close()
    return result


def run_all(manifest, thresholds, predictor, b_mem, b_rec, run_tag, out_jsonl):
    games = manifest["games"]
    out = Path(out_jsonl); out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        for line in out.open():
            try:
                r = json.loads(line); done.add((r["policy"], r["episode_id"]))
            except Exception:
                pass
    with out.open("a") as fh:
        for policy in POLICIES:
            for i, g in enumerate(games):
                if (policy, g["episode_id"]) in done:
                    continue
                r = rollout(g, policy, thresholds, predictor, b_mem, b_rec, run_tag)
                fh.write(json.dumps(r, default=str) + "\n"); fh.flush()
                log(f"  [{policy:20s} {i+1:2d}/{len(games)}] task={r['task']} "
                    f"acts={r['n_actions']:2d} routes={r['n_route_decisions']} "
                    f"rec={r['rec_frac']:.2f} tok={r['tokens']['total_tokens']}")
    return out


def summarize(rollouts_jsonl):
    rows = [json.loads(l) for l in Path(rollouts_jsonl).open()]
    by = {}
    for r in rows:
        by.setdefault(r["policy"], {})[r["episode_id"]] = r
    raw = by["raw_history_only"]
    jdump({"policy": "raw_history_only",
           "task": round(statistics.fmean(v["task"] for v in raw.values()), 4),
           "per_episode_tokens": {k: v["tokens"]["total_tokens"] for k, v in raw.items()},
           "cost": 1.0, "mem0_instantiated": any(v["mem0_instantiated"] for v in raw.values())},
          T2 / "raw_only_reference.json")

    table, appendix = [], {}
    for label, pol in MAIN_ROWS:
        eps = by[pol]
        ids = sorted(eps)
        task = statistics.fmean(eps[i]["task"] for i in ids)
        rec = statistics.fmean(eps[i]["rec_frac"] for i in ids)
        routed = [eps[i]["rec_frac"] for i in ids if eps[i]["n_route_decisions"] > 0]
        cost = statistics.fmean(
            eps[i]["tokens"]["total_tokens"] / max(1, raw[i]["tokens"]["total_tokens"])
            for i in ids)
        table.append({"policy": label, "key": pol, "Task": round(task, 4),
                      "Rec": round(rec, 4), "Cost": round(cost, 4)})
        appendix[pol] = {
            "rec_conditional_on_route": round(statistics.fmean(routed), 4) if routed else None,
            "n_zero_route_episodes": sum(1 for i in ids if eps[i]["zero_route"]),
            "n_episodes": len(ids),
            "mean_route_decisions": round(statistics.fmean(eps[i]["n_route_decisions"] for i in ids), 3),
            "mean_actions": round(statistics.fmean(eps[i]["n_actions"] for i in ids), 2),
            "token_buckets": {b: sum(eps[i]["tokens"][b]["prompt"] + eps[i]["tokens"][b]["completion"]
                                     for i in ids) for b in ("ctrl", "mem", "rec", "write", "native")},
            "mean_final_env_rank": round(statistics.fmean(eps[i]["final_rank"] for i in ids), 3),
        }
    out = {"table": table, "appendix": appendix,
           "raw_history_only": {"Task": round(statistics.fmean(v["task"] for v in raw.values()), 4),
                                "Cost": 1.0},
           "n_rollouts": len(rows), "n_expected": 120}
    jdump(out, T2 / "table2_alfworld.json")
    lines = [r"\begin{tabular}{lrrr}", r"\toprule",
             r"Policy & Task & Rec. & Cost \\", r"\midrule"]
    for r in table:
        lines.append(f"{r['policy']} & {r['Task']:.3f} & {r['Rec']:.3f} & {r['Cost']:.3f} \\\\")
    lines += [r"\midrule",
              f"Raw-history-only & {out['raw_history_only']['Task']:.3f} & -- & 1.000 \\\\",
              r"\bottomrule", r"\end{tabular}"]
    (T2 / "table2_alfworld.tex").write_text("\n".join(lines) + "\n")
    return out
