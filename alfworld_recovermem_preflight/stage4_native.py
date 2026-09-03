"""Sections 7/8/10: 20-game native competence probe with the frozen agent."""
import os, sys, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pf_lib as L
import agent as A

N_GAMES = 20
JSONL = os.path.join(L.OUT, "competence", "native_20.jsonl")


def longest_streak(actions):
    best = cur = 0
    prev = None
    for a in actions:
        cur = cur + 1 if a == prev else 1
        prev = a
        best = max(best, cur)
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

    history = []            # (action, observation)
    steps = []
    controlled_states = []
    first_controlled = None
    invalid = snapped = 0

    for t in range(1, L.MAX_AGENT_STEPS + 1):
        out = A.act(icl, intro, history, gs["admissible_commands"])
        cmd = out["command"]
        invalid += int(out["invalid"])
        snapped += int(out["snapped"])

        obs, _, dones, infos = env.step([cmd])
        gs = L.unbatch(obs, infos)
        rank = mon.update(gs, cmd, t)
        history.append((cmd, obs[0]))

        steps.append({"step": t, "raw": out["raw"], "command": cmd,
                      "snapped": out["snapped"], "invalid": out["invalid"],
                      "prompt_tokens": out["prompt_tokens"],
                      "obs": obs[0].strip()[:400], "rank": rank,
                      "won": bool(gs["won"])})

        if 1 <= rank < K:
            hist_text = A._render(intro, history)
            x_text = obs[0].strip()
            cs = {"step": t, "rank": rank, "K": K,
                  "H_t_tokens": A.count_tokens(hist_text),
                  "x_t_tokens": A.count_tokens(x_text),
                  "n_prior_actions": t,
                  "n_prior_observations": t + 1}
            controlled_states.append(cs)
            if first_controlled is None:
                first_controlled = t

        if gs["won"] or bool(dones[0]):
            break
    env.close()

    acts = [s["command"] for s in steps]
    return {
        "idx": rec["idx"], "game_file": g, "task_type": rec["task_type"], "K": K,
        "subgoals": mon.subgoal_spec,
        "won": bool(gs["won"]),
        "env_score": gs.get("score"), "env_max_score": gs.get("max_score"),
        "final_rank": mon.rank, "max_rank": mon.max_rank,
        "completed_official_subgoals_final": mon.rank,
        "completed_official_subgoals_max": mon.max_rank,
        "REACHED_CONTROLLED": int(first_controlled is not None),
        "first_controlled_step": first_controlled,
        "n_controlled_states": len(controlled_states),
        "total_actions": len(acts), "distinct_actions": len(set(acts)),
        "longest_repeat_streak": longest_streak(acts),
        "invalid_actions": invalid, "snapped_actions": snapped,
        "final_prompt_tokens": steps[-1]["prompt_tokens"] if steps else None,
        "max_prompt_tokens": max((s["prompt_tokens"] or 0) for s in steps) if steps else None,
        "monitor_error": mon.error,
        "controlled_states": controlled_states,
        "steps": steps,
    }


def main():
    census = json.load(open(os.path.join(L.OUT, "structural", "STRUCTURAL_CENSUS.json")))
    eligible = [g for g in census["games"] if g["structurally_valid"]][:N_GAMES]
    icl = json.load(open(os.path.join(L.OUT, "competence", "ICL_EXAMPLE.json")))

    done = {}
    if os.path.exists(JSONL):
        for line in open(JSONL):
            r = json.loads(line)
            done[r["idx"]] = r

    with open(JSONL, "a") as fh:
        for g in eligible:
            if g["idx"] in done:
                print(f"[{g['idx']:02d}] cached"); continue
            r = run_game(g, icl)
            done[g["idx"]] = r
            fh.write(json.dumps(r) + "\n"); fh.flush()
            print(f"[{r['idx']:02d}] {r['task_type']:32s} won={int(r['won'])} "
                  f"rank={r['final_rank']}/max{r['max_rank']}/K{r['K']} "
                  f"ctrl={r['REACHED_CONTROLLED']}@{r['first_controlled_step']} "
                  f"acts={r['total_actions']} inval={r['invalid_actions']} "
                  f"snap={r['snapped_actions']} rep={r['longest_repeat_streak']} "
                  f"tok={r['max_prompt_tokens']}")

    rs = [done[g["idx"]] for g in eligible]
    W = sum(r["REACHED_CONTROLLED"] for r in rs)
    print(f"\nW = {W}/{len(rs)}   full_task_success = {sum(r['won'] for r in rs)}/{len(rs)}")


if __name__ == "__main__":
    main()
