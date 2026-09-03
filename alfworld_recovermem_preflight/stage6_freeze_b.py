"""Config B: build the disjoint frozen 20-game set, freeze the configuration,
run 3 action-format smoke calls.  No competence outcomes are collected here."""
import os, sys, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pf_lib as L
import agent_b as B

OUTD = os.path.join(L.OUT, "competence_b")
N = 20


def main():
    icl = json.load(open(os.path.join(L.OUT, "competence", "ICL_EXAMPLE.json")))

    # ---- 1. freeze the configuration (before ANY competence call) ----
    cfg = B.config_dict(icl)
    h = B.config_hash(cfg)
    cfg["config_sha256"] = h
    L.jdump(cfg, os.path.join(OUTD, "agent_config_b.json"))
    print("CONFIG_B_SHA256 =", h)

    # ---- 2. disjoint game set ----
    frozen30 = json.load(open(os.path.join(L.OUT, "structural", "FROZEN_30_GAMES.json")))
    excluded = {g["game_file"] for g in frozen30["games"]}
    # everything Config A touched lives inside the frozen 30; assert it explicitly
    native_a = {json.loads(l)["game_file"] for l in
                open(os.path.join(L.OUT, "competence", "native_20.jsonl"))}
    suffix_a = {r["game_file"] for r in
                json.load(open(os.path.join(L.OUT, "competence",
                                            "suffix_feasibility.json")))["runs"]}
    ver_a = {r["game_file"] for r in
             json.load(open(os.path.join(L.OUT, "structural",
                                         "SUBGOAL_VALIDATOR_VERIFICATION.json")))["runs"]}
    replay_a = {g["game_file"] for g in
                json.load(open(os.path.join(L.OUT, "replay", "replay_gate.json")))["games"]}
    assert native_a <= excluded and suffix_a <= excluded
    assert ver_a <= excluded and replay_a <= excluded
    excluded |= native_a | suffix_a | ver_a | replay_a

    ordering = L.frozen_order(L.collect_games())      # deterministic seed-13
    candidates = [g for g in ordering if g not in excluded]
    print(f"split games={len(ordering)}  excluded={len(excluded)}  candidates={len(candidates)}")

    picked, hasher = [], hashlib.sha256()
    for g in candidates:
        mon = L.SubgoalMonitor(g)                    # verified upstream checker
        if mon.K < 2:
            continue
        tr = L.load_traj(g)
        rec = {"rank_in_frozen_order": ordering.index(g), "game_file": g,
               "sha256": L.sha256_file(g), "task_type": tr["task_type"],
               "K_USABLE": mon.K,
               "alfred_num_subgoals_after_meta_removal": len(tr["plan"]["high_pddl"]) - 1,
               "tw_subgoals": mon.subgoal_spec}
        rec["idx"] = len(picked)
        picked.append(rec)
        hasher.update(g.encode()); hasher.update(rec["sha256"].encode())
        if len(picked) == N:
            break
    assert len(picked) == N

    frozen = {
        "config_id": "AGENT_CONFIG_B_ADMISSIBLE_COMMANDS",
        "split": L.SPLIT, "split_alias": "valid_unseen", "seed": L.SEED,
        "ordering_rule": ("AlfredTWEnv.collect_game_files() -> sorted() -> "
                          "random.Random(13).shuffle(); then EXCLUDE every game used "
                          "anywhere in the Config-A line (frozen structural-30, which is a "
                          "verified superset of Config-A native-20, suffix-5, replay-3 and "
                          "validator-3); then take the first 20 with K_USABLE >= 2"),
        "n_split_games": len(ordering), "n_excluded": len(excluded),
        "n_candidates": len(candidates),
        "structural_eligibility": "K_USABLE >= 2 via the verified upstream subgoal checker; no model outcomes involved",
        "disjoint_from_config_a": True,
        "config_sha256": h,
        "games": picked,
    }
    frozen["list_sha256"] = hasher.hexdigest()
    L.jdump(frozen, os.path.join(OUTD, "FROZEN_CONFIG_B_20.json"))
    print("CONFIG_B_20_HASH =", frozen["list_sha256"])
    for p in picked:
        print(f"  [{p['idx']:02d}] order={p['rank_in_frozen_order']:3d} "
              f"{p['task_type']:32s} K={p['K_USABLE']}")

    # ---- 3. three action-format smoke calls (format only, never task success) ----
    smoke = {"config_sha256": h, "criteria": ["output parses",
             "selected action is in admissible_commands",
             "entity numbers preserved exactly"], "calls": []}
    g = picked[0]["game_file"]
    env = L.make_env([g])
    obs, infos = env.reset()
    gs = L.unbatch(obs, infos)
    intro, history = obs[0], []
    for i in range(3):
        out = B.act(icl, intro, history, gs["admissible_commands"])
        cmd = out["command"]
        nums_model = [t for t in out["raw"].replace(":", " ").split() if t.isdigit()]
        nums_exec = [t for t in cmd.split() if t.isdigit()]
        rec = {"call": i, "raw": out["raw"], "command": cmd,
               "parsed": bool(cmd), "in_admissible": out["valid"],
               "entity_numbers_model": nums_model, "entity_numbers_executed": nums_exec,
               "entity_numbers_preserved": nums_model == nums_exec,
               "prompt_tokens": out["prompt_tokens"],
               "n_admissible": len(gs["admissible_commands"])}
        smoke["calls"].append(rec)
        print(f"  smoke {i}: raw={out['raw']!r} -> {cmd!r} adm={out['valid']} "
              f"nums {nums_model}->{nums_exec}")
        obs, _, dones, infos = env.step([cmd])
        gs = L.unbatch(obs, infos)
        history.append((cmd, obs[0]))
    env.close()
    smoke["all_parsed"] = all(c["parsed"] for c in smoke["calls"])
    smoke["all_admissible"] = all(c["in_admissible"] for c in smoke["calls"])
    smoke["all_entities_preserved"] = all(c["entity_numbers_preserved"] for c in smoke["calls"])
    smoke["verdict"] = "PASS" if (smoke["all_parsed"] and smoke["all_admissible"]
                                  and smoke["all_entities_preserved"]) else "FAIL"
    L.jdump(smoke, os.path.join(OUTD, "smoke_b.json"))
    print("SMOKE:", smoke["verdict"])


if __name__ == "__main__":
    main()
