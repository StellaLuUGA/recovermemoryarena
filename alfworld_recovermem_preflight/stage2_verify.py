"""Section 4: verify the harness-only subgoal checker against upstream expert execution."""
import os, sys, json, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pf_lib as L
from alfworld.agents.expert import HandCodedTWAgent

N_GAMES = 3
MAX_EXPERT_STEPS = 120


def facts_wo_ids(gs):
    f = [f"{fact.name} " + " ".join(n.strip() for n in fact.names) for fact in gs["facts"]]
    return f, [" ".join("".join(c for c in x if not c.isdigit()).split()) for x in f]


def anchors(gs, params):
    """INDEPENDENT ground-truth anchors read straight off PDDL facts.
    Used only to CHECK the upstream detector, never to replace it."""
    raw, clean = facts_wo_ids(gs)
    obj = params["object_target"]
    hold = f"holds agent {obj}" in clean
    held_ids = [" ".join(f.split()[2:3]) for f in raw
                if f.startswith("holds agent ") and obj in "".join(c for c in f if not c.isdigit())]
    held = held_ids[0] if held_ids else None
    prop = {}
    for p in ("ishot", "iscool", "isclean"):
        prop[p] = bool(held) and any(f.startswith(f"{p} {held}") for f in raw)
    inrecep = params.get("parent_target") and \
        f"inreceptacle {obj} {params['parent_target']}" in clean
    return {"hold": hold, **prop, "inreceptacle": bool(inrecep)}


PROP_FOR = {"pick_heat_then_place_in_recep": "ishot",
            "pick_cool_then_place_in_recep": "iscool",
            "pick_clean_then_place_in_recep": "isclean"}


def run_expert(game_file, source):
    """source: 'handcoded' -> upstream HandCodedTWAgent (the mechanism AlfredExpert
    wraps, alfred_tw_env.py:82-84).  'planner' -> upstream PDDL planner plan
    exposed as EnvInfos.policy_commands (alfred_tw_env.py:88)."""
    random.seed(L.SEED)   # upstream HandCodedAgent.act uses random.choice
    env = L.make_env([game_file], want_policy_commands=(source == "planner"))
    obs, infos = env.reset()
    gs = L.unbatch(obs, infos)

    mon = L.SubgoalMonitor(game_file)
    mon.reset_obs(gs)
    params = mon.agent.task_params

    trace = [{"step": 0, "action": None, "rank": 0, "won": bool(gs["won"]),
              "anchors": anchors(gs, params)}]

    if source == "handcoded":
        expert = HandCodedTWAgent(max_steps=MAX_EXPERT_STEPS)
        expert.reset(game_file)
        expert.observe(gs["feedback"])
        plan = None
    else:
        plan = list(gs["policy_commands"] or [])

    last = ""
    done = False
    for t in range(1, MAX_EXPERT_STEPS + 1):
        if source == "handcoded":
            try:
                cmd = expert.act(gs, 0, gs["won"], last)
            except Exception as e:
                trace.append({"step": t, "expert_error": f"{type(e).__name__}: {e}"})
                break
            if cmd not in gs["admissible_commands"]:
                cmd = "look"
        else:
            if not plan:
                break
            cmd = plan.pop(0)

        obs, _, dones, infos = env.step([cmd])
        gs = L.unbatch(obs, infos)
        rank = mon.update(gs, cmd, t)
        last = cmd
        done = bool(dones[0])
        trace.append({"step": t, "action": cmd, "rank": rank, "won": bool(gs["won"]),
                      "anchors": anchors(gs, params), "obs": obs[0][:160]})
        if source == "planner":
            plan = list(gs["policy_commands"] or []) if gs.get("policy_commands") else plan
        if done or gs["won"]:
            break
    env.close()

    return {"game_file": game_file, "source": source, "task_type": mon.task_type,
            "K": mon.K, "subgoals": mon.subgoal_spec, "won": bool(gs["won"]),
            "steps": len(trace) - 1, "monitor_error": mon.error,
            "max_rank": mon.max_rank, "trace": trace}


def first_step_where(trace, pred):
    for e in trace:
        if "rank" in e and pred(e):
            return e["step"]
    return None


def check(run):
    tt, K, tr = run["task_type"], run["K"], run["trace"]
    r1 = first_step_where(tr, lambda e: e["rank"] >= 1)
    r2 = first_step_where(tr, lambda e: e["rank"] >= 2)
    a_hold = first_step_where(tr, lambda e: e["anchors"]["hold"])
    res = {
        "g1_detected": r1 is not None,
        "g1_step": r1,
        "g2_applicable": K >= 2,
        "g2_detected": r2 is not None,
        "g2_step": r2,
        "monotone_first_hit_order": (r1 is not None and r2 is not None and r1 <= r2),
        "anchor_hold_step": a_hold,
        # detector must NOT claim "take done" before the PDDL fact says so
        "no_false_early_take": (r2 is None) or (a_hold is not None and r2 >= a_hold),
    }
    prop = PROP_FOR.get(tt)
    if prop:
        r4 = first_step_where(tr, lambda e: e["rank"] >= 4)
        a_p = first_step_where(tr, lambda e: e["anchors"][prop])
        res.update({f"anchor_{prop}_step": a_p, "r4_step": r4,
                    "no_false_early_prop": (r4 is None) or (a_p is not None and r4 >= a_p)})
    res["ok"] = all(v for k, v in res.items()
                    if k.startswith(("g1_detected", "g2_detected", "monotone", "no_false")))
    return res


def main():
    census = json.load(open(os.path.join(L.OUT, "structural", "STRUCTURAL_CENSUS.json")))
    eligible = [g for g in census["games"] if g["structurally_valid"]][:N_GAMES]

    out = {"n_games": len(eligible), "runs": []}
    path = os.path.join(L.OUT, "structural", "SUBGOAL_VALIDATOR_VERIFICATION.json")
    for g in eligible:
        for source in ("handcoded", "planner"):
            print(f"--- idx={g['idx']} {g['task_type']} source={source}")
            run = run_expert(g["game_file"], source)
            run["idx"] = g["idx"]
            run["checks"] = check(run)
            print("    won=%s steps=%s max_rank=%d/%d checks=%s" % (
                run["won"], run["steps"], run["max_rank"], run["K"],
                {k: v for k, v in run["checks"].items() if k in
                 ("g1_detected", "g2_detected", "no_false_early_take",
                  "no_false_early_prop", "ok")}))
            out["runs"].append(run)
            L.jdump(out, path)

    hc = [r for r in out["runs"] if r["source"] == "handcoded"]
    out["summary"] = {
        "handcoded_runs": len(hc),
        "handcoded_all_ok": all(r["checks"]["ok"] for r in hc),
        "handcoded_won": sum(r["won"] for r in hc),
        "planner_won": sum(r["won"] for r in out["runs"] if r["source"] == "planner"),
        "planner_no_false_early": all(r["checks"]["no_false_early_take"]
                                      for r in out["runs"] if r["source"] == "planner"),
        "verdict": "PASS" if all(r["checks"]["ok"] for r in hc) else "FAIL",
    }
    L.jdump(out, path)
    print("\nSUMMARY:", json.dumps(out["summary"], indent=2))


if __name__ == "__main__":
    main()
