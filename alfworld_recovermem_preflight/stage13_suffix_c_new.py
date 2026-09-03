"""Config B section 8: next-subgoal suffix feasibility (disjoint frozen set)."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pf_lib as L
import agent_c as A

N = 5
OUTP = os.path.join(L.OUT, "competence_c", "suffix_c_new.json")


def run(rec, icl):
    g = rec["game_file"]
    cut = rec["first_controlled_step"]
    prefix = [s["command"] for s in rec["steps"][:cut]]

    env = L.make_env([g])
    obs, infos = env.reset()
    gs = L.unbatch(obs, infos)
    mon = L.SubgoalMonitor(g)
    mon.reset_obs(gs)
    intro = obs[0]
    history = []

    # --- exact action-prefix replay to the first genuine controlled state ---
    for t, cmd in enumerate(prefix, start=1):
        obs, _, dones, infos = env.step([cmd])
        gs = L.unbatch(obs, infos)
        rank = mon.update(gs, cmd, t)
        history.append((cmd, obs[0]))
    rank0 = mon.rank
    replay_ok = (rank0 == rec["steps"][cut - 1]["rank"])
    target = rank0 + 1
    K = mon.K

    steps = []
    success = False
    for t in range(cut + 1, cut + 1 + L.MAX_NEXT_SUBGOAL_STEPS):
        out = A.act(icl, intro, history, gs["admissible_commands"])
        cmd = out["command"]
        obs, _, dones, infos = env.step([cmd])
        gs = L.unbatch(obs, infos)
        rank = mon.update(gs, cmd, t)
        history.append((cmd, obs[0]))
        steps.append({"step": t, "raw": out["raw"], "command": cmd,
                      "valid": out["valid"], "invalid": out["invalid"],
                      "obs": obs[0].strip()[:300], "rank": rank,
                      "prompt_tokens": out["prompt_tokens"]})
        if rank >= target:
            success = True
            break
        if gs["won"] or bool(dones[0]):
            break
    env.close()

    return {"config_id": "AGENT_CONFIG_C_QWEN32B", "idx": rec["idx"], "game_file": g, "task_type": rec["task_type"], "K": K,
            "subgoals": mon.subgoal_spec,
            "controlled_step": cut, "prefix_len": len(prefix),
            "prefix": prefix,
            "rank_at_controlled_state": rank0,
            "replay_rank_matches_native": bool(replay_ok),
            "target_rank": target,
            "next_subgoal": mon.subgoal_spec[rank0] if rank0 < K else None,
            "success": bool(success), "steps_used": len(steps),
            "max_rank_reached": mon.max_rank, "steps": steps}


def main():
    native = [json.loads(l) for l in open(os.path.join(L.OUT, "competence_c", "native_c_20.jsonl"))]
    native.sort(key=lambda r: r["idx"])
    picked = [r for r in native if r["REACHED_CONTROLLED"]][:N]
    icl = json.load(open(os.path.join(L.OUT, "competence", "ICL_EXAMPLE.json")))

    out = {"n": len(picked), "max_steps": L.MAX_NEXT_SUBGOAL_STEPS, "runs": []}
    for rec in picked:
        r = run(rec, icl)
        out["runs"].append(r)
        L.jdump(out, OUTP)
        print(f"[{r['idx']:02d}] {r['task_type']:32s} rank0={r['rank_at_controlled_state']} "
              f"target={r['target_rank']} next={r['next_subgoal']} "
              f"success={r['success']} steps={r['steps_used']} "
              f"replay_ok={r['replay_rank_matches_native']}")

    B = sum(r["success"] for r in out["runs"])
    out["B32_new"] = B
    out["verdict"] = ("PASS" if B >= 2 else "STOP_FOR_REVIEW" if B == 1
                      else "FAIL_SUFFIX_COMPETENCE")
    L.jdump(out, OUTP)
    print(f"\nB32_new = {B}/{len(out['runs'])} -> {out['verdict']}")


if __name__ == "__main__":
    main()
