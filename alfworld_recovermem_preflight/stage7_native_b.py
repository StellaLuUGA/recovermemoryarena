"""Config B sections 6/7/11: native 20-game probe on the disjoint frozen set."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pf_lib as L
import agent_b as B

JSONL = os.path.join(L.OUT, "competence_b", "native_b_20.jsonl")


def longest_streak(actions):
    best = cur = 0; prev = None
    for a in actions:
        cur = cur + 1 if a == prev else 1
        prev = a; best = max(best, cur)
    return best


def run_game(rec, icl):
    g = rec["game_file"]
    env = L.make_env([g])
    obs, infos = env.reset()
    gs = L.unbatch(obs, infos)
    mon = L.SubgoalMonitor(g)
    mon.reset_obs(gs)
    K = mon.K
    intro = obs[0]

    history, steps, controlled_states = [], [], []
    first_controlled = None
    invalid = 0

    for t in range(1, L.MAX_AGENT_STEPS + 1):
        out = B.act(icl, intro, history, gs["admissible_commands"])
        cmd = out["command"]
        invalid += int(out["invalid"])
        obs, _, dones, infos = env.step([cmd])
        gs = L.unbatch(obs, infos)
        rank = mon.update(gs, cmd, t)
        history.append((cmd, obs[0]))
        steps.append({"step": t, "raw": out["raw"], "command": cmd,
                      "valid": out["valid"], "invalid": out["invalid"],
                      "prompt_tokens": out["prompt_tokens"],
                      "obs": obs[0].strip()[:400], "rank": rank,
                      "won": bool(gs["won"])})
        if 1 <= rank < K:
            hist_text = B._render(intro, history)
            controlled_states.append({
                "step": t, "rank": rank, "K": K,
                "H_t_tokens": B.count_tokens(hist_text),
                "x_t_tokens": B.count_tokens(obs[0].strip()),
                "n_prior_actions": t, "n_prior_observations": t + 1})
            if first_controlled is None:
                first_controlled = t
        if gs["won"] or bool(dones[0]):
            break
    env.close()

    acts = [s["command"] for s in steps]
    n = len(acts)
    return {
        "config_id": "AGENT_CONFIG_B_ADMISSIBLE_COMMANDS",
        "idx": rec["idx"], "rank_in_frozen_order": rec["rank_in_frozen_order"],
        "game_file": g, "task_type": rec["task_type"], "K": K,
        "subgoals": mon.subgoal_spec,
        "won": bool(gs["won"]),
        "env_score": gs.get("score"), "env_max_score": gs.get("max_score"),
        "final_rank": mon.rank, "max_rank": mon.max_rank,
        "REACHED_CONTROLLED": int(first_controlled is not None),
        "first_controlled_step": first_controlled,
        "n_controlled_states": len(controlled_states),
        "total_actions": n, "distinct_actions": len(set(acts)),
        "longest_repeat_streak": longest_streak(acts),
        "invalid_actions": invalid,
        "valid_action_rate": (n - invalid) / n if n else None,
        "max_prompt_tokens": max((s["prompt_tokens"] or 0) for s in steps) if steps else None,
        "monitor_error": mon.error,
        "controlled_states": controlled_states, "steps": steps,
    }


def main():
    frozen = json.load(open(os.path.join(L.OUT, "competence_b", "FROZEN_CONFIG_B_20.json")))
    icl = json.load(open(os.path.join(L.OUT, "competence", "ICL_EXAMPLE.json")))
    done = {}
    if os.path.exists(JSONL):
        for line in open(JSONL):
            r = json.loads(line); done[r["idx"]] = r
    with open(JSONL, "a") as fh:
        for gme in frozen["games"]:
            if gme["idx"] in done:
                print(f"[{gme['idx']:02d}] cached"); continue
            r = run_game(gme, icl)
            done[gme["idx"]] = r
            fh.write(json.dumps(r) + "\n"); fh.flush()
            print(f"[{r['idx']:02d}] {r['task_type']:32s} won={int(r['won'])} "
                  f"rank={r['final_rank']}/max{r['max_rank']}/K{r['K']} "
                  f"ctrl={r['REACHED_CONTROLLED']}@{r['first_controlled_step']} "
                  f"acts={r['total_actions']} dist={r['distinct_actions']} "
                  f"rep={r['longest_repeat_streak']} inval={r['invalid_actions']} "
                  f"vrate={r['valid_action_rate']:.2f} tok={r['max_prompt_tokens']}")
    rs = [done[g["idx"]] for g in frozen["games"]]
    W = sum(r["REACHED_CONTROLLED"] for r in rs)
    print(f"\nW_B = {W}/{len(rs)}   full_task_success = {sum(r['won'] for r in rs)}/{len(rs)}")


if __name__ == "__main__":
    main()
