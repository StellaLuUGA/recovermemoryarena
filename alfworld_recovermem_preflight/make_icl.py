"""Build the ONE frozen in-context example, from the TRAIN split only.
Deterministic: train games sorted -> Random(13).shuffle -> first
pick_and_place_simple game the upstream handcoded expert solves in <=25 steps.
Contains no information about any valid_unseen game."""
import os, sys, json, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pf_lib as L
from alfworld.agents.environment import get_environment
from alfworld.agents.expert import HandCodedTWAgent

OUTP = os.path.join(L.OUT, "competence", "ICL_EXAMPLE.json")


def solve(game_file, cap=25):
    random.seed(L.SEED)
    env = L.make_env([game_file])
    obs, infos = env.reset()
    gs = L.unbatch(obs, infos)
    ex = HandCodedTWAgent(max_steps=200)
    ex.reset(game_file)
    ex.observe(gs["feedback"])
    steps, last = [], ""
    intro = obs[0]
    for _ in range(cap):
        try:
            cmd = ex.act(gs, 0, gs["won"], last)
        except Exception:
            env.close(); return None
        if cmd not in gs["admissible_commands"]:
            cmd = "look"
        obs, _, dones, infos = env.step([cmd])
        gs = L.unbatch(obs, infos)
        steps.append({"action": cmd, "obs": obs[0].strip()})
        last = cmd
        if gs["won"]:
            env.close()
            return {"game_file": game_file, "intro": intro.strip(), "steps": steps}
        if dones[0]:
            break
    env.close()
    return None


def main():
    config = L.load_config()
    tw = get_environment("AlfredTWEnv")(config, train_eval="train")
    files = sorted(tw.game_files)
    random.Random(L.SEED).shuffle(files)
    for g in files:
        tr = L.load_traj(g)
        if tr["task_type"] != "pick_and_place_simple":
            continue
        r = solve(g)
        if r:
            r["task_type"] = tr["task_type"]
            r["split"] = "train"
            r["selection_rule"] = ("train split, sorted, Random(13).shuffle, first "
                                   "pick_and_place_simple solved by upstream "
                                   "HandCodedTWAgent within 25 steps")
            L.jdump(r, OUTP)
            print("ICL example:", g, "steps:", len(r["steps"]))
            return
    raise SystemExit("no example found")


if __name__ == "__main__":
    main()
