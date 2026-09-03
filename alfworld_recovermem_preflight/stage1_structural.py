"""Section 3: 30-game structural census. No model calls, no env stepping."""
import os, sys, ast, json, inspect, hashlib, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pf_lib as L
from alfworld.agents.expert import handcoded_expert as HE


def reachable_ranks(policy):
    """Static AST analysis of the pinned upstream check_subgoal_completion:
    which subgoal indices can it ever return?  K = len(policy.subgoals)."""
    cls = type(policy)
    # the checker lives on the ALFRED base policy, not the TW subclass
    fn = cls.check_subgoal_completion
    src = inspect.getsource(fn)
    tree = ast.parse(src.lstrip().replace("\n    ", "\n"))  # dedent-ish
    K = len(policy.subgoals)
    vals = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and node.value is not None:
            v = node.value
            if isinstance(v, ast.Constant) and isinstance(v.value, int):
                vals.add(v.value)
            elif isinstance(v, ast.BinOp) and isinstance(v.op, ast.Sub):
                # len(self.subgoals) - N
                if isinstance(v.right, ast.Constant):
                    vals.add(K - v.right.value)
    return sorted(vals), K


def main():
    games = L.frozen_order(L.collect_games())
    frozen = games[:L.N_FROZEN]

    frozen_rec = {
        "split": L.SPLIT,
        "split_alias": "valid_unseen",
        "alfworld_version": "0.5.0",
        "environment": "AlfredTWEnv",
        "ordering_rule": ("AlfredTWEnv.collect_game_files() -> sorted() -> "
                          "random.Random(13).shuffle() -> first 30"),
        "seed": L.SEED,
        "n_split_games": len(games),
        "games": [],
    }
    hasher = hashlib.sha256()
    for i, g in enumerate(frozen):
        gh = L.sha256_file(g)
        hasher.update(g.encode())
        hasher.update(gh.encode())
        frozen_rec["games"].append({
            "idx": i, "game_file": g, "sha256": gh,
            "traj_data": L.traj_data_path(g),
        })
    frozen_rec["list_sha256"] = hasher.hexdigest()
    L.jdump(frozen_rec, os.path.join(L.OUT, "structural", "FROZEN_30_GAMES.json"))

    census = {"games": []}
    for i, g in enumerate(frozen):
        tr = L.load_traj(g)
        mon = L.SubgoalMonitor(g)
        ranks, K = reachable_ranks(mon.policy)
        hp = tr["plan"]["high_pddl"]
        hp_actions = [h["discrete_action"]["action"] for h in hp]
        # upstream meta-removal rule: alfworld/env/tasks.py:22 "ignore end noop"
        K_alfred = len(hp) - 1
        all_checkable = (set(ranks) == set(range(K)))
        rec = {
            "idx": i,
            "game_file": g,
            "task_type": tr["task_type"],
            "pddl_params": tr["pddl_params"],
            "alfred_high_pddl_len": len(hp),
            "alfred_high_pddl_actions": hp_actions,
            "alfred_num_subgoals_after_meta_removal": K_alfred,
            "tw_subgoals": mon.subgoal_spec,
            "K_USABLE": K,
            "reachable_ranks": ranks,
            "all_intermediate_programmatically_checkable": all_checkable,
            "structurally_valid": bool(all_checkable and K >= 2),
            "K_USABLE_ge_2": bool(K >= 2),
        }
        census["games"].append(rec)
        L.jdump(census, os.path.join(L.OUT, "structural", "STRUCTURAL_CENSUS.json"))
        print(f"[{i:02d}] {tr['task_type']:34s} K_USABLE={K} alfred={K_alfred} "
              f"ranks={ranks} ok={rec['structurally_valid']}")

    ks = [r["K_USABLE"] for r in census["games"]]
    ks_s = sorted(ks)
    def pct(p):
        k = (len(ks_s) - 1) * p
        f, c = int(k), min(int(k) + 1, len(ks_s) - 1)
        return ks_s[f] + (ks_s[c] - ks_s[f]) * (k - f)
    summary = {
        "n": len(ks),
        "structurally_valid": sum(r["structurally_valid"] for r in census["games"]),
        "K_USABLE_ge_2": sum(r["K_USABLE_ge_2"] for r in census["games"]),
        "all_checkable": sum(r["all_intermediate_programmatically_checkable"]
                             for r in census["games"]),
        "K_min": min(ks), "K_median": statistics.median(ks),
        "K_mean": sum(ks) / len(ks), "K_p75": pct(0.75), "K_p90": pct(0.90),
        "K_max": max(ks),
        "task_type_counts": {},
    }
    for r in census["games"]:
        summary["task_type_counts"][r["task_type"]] = \
            summary["task_type_counts"].get(r["task_type"], 0) + 1
    census["summary"] = summary
    census["frozen_list_sha256"] = frozen_rec["list_sha256"]
    L.jdump(census, os.path.join(L.OUT, "structural", "STRUCTURAL_CENSUS.json"))
    print("\nSUMMARY:", json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
