"""Config C section 2/3 (gate 1): rerun the SAME five Config-B controlled states."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pf_lib as L
import agent_c as C

OUTP = os.path.join(L.OUT, "competence_c", "suffix_c_old_states.json")


def run(ref, icl):
    g = ref["game_file"]
    prefix = ref["prefix"]
    env = L.make_env([g])
    obs, infos = env.reset()
    gs = L.unbatch(obs, infos)
    mon = L.SubgoalMonitor(g)
    mon.reset_obs(gs)
    intro, history = obs[0], []
    for t, cmd in enumerate(prefix, start=1):
        obs, _, dones, infos = env.step([cmd])
        gs = L.unbatch(obs, infos)
        mon.update(gs, cmd, t)
        history.append((cmd, obs[0]))
    rank0 = mon.rank
    replay_ok = (rank0 == ref["rank_at_controlled_state"])
    target, K = rank0 + 1, mon.K
    cut = ref["controlled_step"]

    steps, success = [], False
    for t in range(cut + 1, cut + 1 + L.MAX_NEXT_SUBGOAL_STEPS):
        out = C.act(icl, intro, history, gs["admissible_commands"])
        cmd = out["command"]
        obs, _, dones, infos = env.step([cmd])
        gs = L.unbatch(obs, infos)
        rank = mon.update(gs, cmd, t)
        history.append((cmd, obs[0]))
        steps.append({"step": t, "raw": out["raw"], "command": cmd,
                      "valid": out["valid"], "invalid": out["invalid"],
                      "reasoning_content": out["reasoning_content"],
                      "obs": obs[0].strip()[:300], "rank": rank,
                      "prompt_tokens": out["prompt_tokens"]})
        if rank >= target:
            success = True
            break
        if gs["won"] or bool(dones[0]):
            break
    env.close()
    n = len(steps)
    return {"config_id": "AGENT_CONFIG_C_QWEN32B", "gate": "old_config_b_states",
            "idx": ref["idx"], "game_file": g, "task_type": ref["task_type"], "K": K,
            "subgoals": mon.subgoal_spec, "controlled_step": cut, "prefix": prefix,
            "rank_at_controlled_state": rank0,
            "reference_rank_config_b": ref["rank_at_controlled_state"],
            "replay_rank_matches_reference": bool(replay_ok),
            "target_rank": target, "next_subgoal": mon.subgoal_spec[rank0] if rank0 < K else None,
            "success": bool(success), "steps_used": n,
            "max_rank_reached": mon.max_rank, "won": bool(gs["won"]),
            "invalid_actions": sum(s["invalid"] for s in steps),
            "valid_action_rate": (n - sum(s["invalid"] for s in steps)) / n if n else None,
            "steps": steps}


def main():
    refs = json.load(open(os.path.join(L.OUT, "competence_b", "suffix_b.json")))["runs"]
    icl = json.load(open(os.path.join(L.OUT, "competence", "ICL_EXAMPLE.json")))
    out = {"n": len(refs), "max_steps": L.MAX_NEXT_SUBGOAL_STEPS,
           "states_source": "competence_b/suffix_b.json (identical five controlled states)",
           "runs": []}
    for ref in refs:
        r = run(ref, icl)
        out["runs"].append(r)
        L.jdump(out, OUTP)
        print(f"[{r['idx']:02d}] {r['task_type']:32s} rank0={r['rank_at_controlled_state']} "
              f"target={r['target_rank']} next={r['next_subgoal']} success={r['success']} "
              f"steps={r['steps_used']} vrate={r['valid_action_rate']:.2f} "
              f"replay_ok={r['replay_rank_matches_reference']} maxrank={r['max_rank_reached']}")
    B32 = sum(r["success"] for r in out["runs"])
    out["B32"] = B32
    out["verdict"] = ("PASS_SUFFIX_COMPETENCE" if B32 >= 2 else
                      "STOP_FOR_REVIEW" if B32 == 1 else "FAIL_SUFFIX_COMPETENCE")
    L.jdump(out, OUTP)
    print(f"\nB32 = {B32}/{len(out['runs'])} -> {out['verdict']}")


if __name__ == "__main__":
    main()
