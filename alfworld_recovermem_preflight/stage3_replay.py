"""Section 5: state replay gate. 3 games x 3 reconstructions = 9 comparisons."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pf_lib as L

N_GAMES, N_REPLAYS = 3, 3


def norm_facts(gs):
    return sorted(f"{f.name} " + " ".join(n.strip() for n in f.names) for f in gs["facts"])


def snapshot(gs, rank, done):
    return {
        "feedback": gs["feedback"],
        "inventory": gs["inventory"],
        "location": gs["location"],
        "admissible_commands": sorted(gs["admissible_commands"]),
        "facts_sorted": norm_facts(gs),
        "n_facts": len(gs["facts"]),
        "rank": rank,
        "won": bool(gs["won"]),
        "done": bool(done),
    }


def execute(game_file, prefix):
    """Fresh reset + replay `prefix` exactly; snapshot the terminal state."""
    env = L.make_env([game_file])
    obs, infos = env.reset()
    gs = L.unbatch(obs, infos)
    mon = L.SubgoalMonitor(game_file)
    mon.reset_obs(gs)
    rank, done = 0, False
    for t, cmd in enumerate(prefix, start=1):
        obs, _, dones, infos = env.step([cmd])
        gs = L.unbatch(obs, infos)
        rank = mon.update(gs, cmd, t)
        done = bool(dones[0])
    env.close()
    return snapshot(gs, rank, done)


FIELDS = ["feedback", "inventory", "location", "admissible_commands",
          "facts_sorted", "rank", "won", "done"]


def main():
    ver = json.load(open(os.path.join(L.OUT, "structural",
                                      "SUBGOAL_VALIDATOR_VERIFICATION.json")))
    runs = [r for r in ver["runs"] if r["source"] == "handcoded"][:N_GAMES]

    out = {"n_games": len(runs), "n_replays_per_game": N_REPLAYS, "games": [],
           "matches": 0, "comparisons": 0}
    path = os.path.join(L.OUT, "replay", "replay_gate.json")

    for r in runs:
        K = r["K"]
        # first genuine controlled decision along the frozen expert trajectory
        b = next(e for e in r["trace"] if 1 <= e["rank"] < K)
        prefix = [e["action"] for e in r["trace"][1:b["step"] + 1]]
        assert all(a is not None for a in prefix)

        ref = execute(r["game_file"], prefix)
        rec = {"idx": r["idx"], "game_file": r["game_file"], "task_type": r["task_type"],
               "K": K, "boundary_step": b["step"], "boundary_rank": b["rank"],
               "prefix": prefix, "reference_rank": ref["rank"], "replays": []}

        for i in range(N_REPLAYS):
            s = execute(r["game_file"], prefix)
            diffs = [f for f in FIELDS if s[f] != ref[f]]
            out["comparisons"] += 1
            ok = not diffs
            out["matches"] += int(ok)
            rec["replays"].append({"replay": i, "match": ok, "diff_fields": diffs,
                                  "rank": s["rank"], "won": s["won"]})
            print(f"  idx={r['idx']} replay {i}: match={ok} rank={s['rank']} diffs={diffs}")
        rec["all_match"] = all(x["match"] for x in rec["replays"])
        out["games"].append(rec)
        L.jdump(out, path)

    out["verdict"] = "PASS" if out["matches"] == out["comparisons"] == N_GAMES * N_REPLAYS else "FAIL"
    L.jdump(out, path)
    print(f"\nREPLAY_GATE = {out['matches']}/{out['comparisons']} -> {out['verdict']}")


if __name__ == "__main__":
    main()
