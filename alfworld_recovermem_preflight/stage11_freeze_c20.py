"""Config C section 4: build + hash the new disjoint 20-game manifest (no model calls)."""
import os, sys, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pf_lib as L

OUTD = os.path.join(L.OUT, "competence_c")
N = 20


def main():
    excluded, prov = set(), {}
    def add(name, paths):
        s = set(paths); prov[name] = len(s); excluded.update(s)

    add("structural_30", [g["game_file"] for g in json.load(
        open(os.path.join(L.OUT, "structural", "FROZEN_30_GAMES.json")))["games"]])
    add("config_a_native_20", [json.loads(l)["game_file"] for l in
        open(os.path.join(L.OUT, "competence", "native_20.jsonl"))])
    add("config_a_suffix", [r["game_file"] for r in json.load(
        open(os.path.join(L.OUT, "competence", "suffix_feasibility.json")))["runs"]])
    add("validator_verification", [r["game_file"] for r in json.load(
        open(os.path.join(L.OUT, "structural", "SUBGOAL_VALIDATOR_VERIFICATION.json")))["runs"]])
    add("replay_verification", [g["game_file"] for g in json.load(
        open(os.path.join(L.OUT, "replay", "replay_gate.json")))["games"]])
    add("config_b_native_20", [g["game_file"] for g in json.load(
        open(os.path.join(OUTD, "..", "competence_b", "FROZEN_CONFIG_B_20.json")))["games"]])
    add("config_b_suffix", [r["game_file"] for r in json.load(
        open(os.path.join(L.OUT, "competence_b", "suffix_b.json")))["runs"]])
    add("config_c_gate1_suffix", [r["game_file"] for r in json.load(
        open(os.path.join(OUTD, "suffix_c_old_states.json")))["runs"]])

    ordering = L.frozen_order(L.collect_games())
    candidates = [g for g in ordering if g not in excluded]
    print("excluded:", prov, "-> union", len(excluded), "| candidates", len(candidates))

    picked, hasher = [], hashlib.sha256()
    for g in candidates:
        mon = L.SubgoalMonitor(g)
        if mon.K < 2:
            continue
        tr = L.load_traj(g)
        rec = {"idx": len(picked), "rank_in_frozen_order": ordering.index(g),
               "game_file": g, "sha256": L.sha256_file(g), "task_type": tr["task_type"],
               "K_USABLE": mon.K, "tw_subgoals": mon.subgoal_spec}
        picked.append(rec)
        hasher.update(g.encode()); hasher.update(rec["sha256"].encode())
        if len(picked) == N:
            break
    assert len(picked) == N

    cfg = json.load(open(os.path.join(OUTD, "agent_config_c.json")))
    frozen = {
        "config_id": "AGENT_CONFIG_C_QWEN32B", "config_sha256": cfg["config_sha256"],
        "split": L.SPLIT, "split_alias": "valid_unseen", "seed": L.SEED,
        "ordering_rule": ("AlfredTWEnv.collect_game_files() -> sorted() -> "
                          "random.Random(13).shuffle(); exclude every game used by "
                          "structural-30, Config-A native-20, Config-A suffix, Config-B "
                          "native-20, Config-B suffix, Config-C gate-1 suffix, validator "
                          "verification and replay verification; then first 20 with K_USABLE>=2"),
        "excluded_provenance": prov, "n_excluded_union": len(excluded),
        "n_split_games": len(ordering), "n_candidates": len(candidates),
        "disjoint_from_all_prior_runs": True, "games": picked,
    }
    frozen["list_sha256"] = hasher.hexdigest()
    L.jdump(frozen, os.path.join(OUTD, "FROZEN_CONFIG_C_20.json"))
    print("CONFIG_C_20_HASH =", frozen["list_sha256"])
    for p in picked:
        print(f"  [{p['idx']:02d}] order={p['rank_in_frozen_order']:3d} "
              f"{p['task_type']:32s} K={p['K_USABLE']}")


if __name__ == "__main__":
    main()
