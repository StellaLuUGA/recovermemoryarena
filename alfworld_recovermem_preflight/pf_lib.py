"""ReCoverMem ALFWorld preflight -- shared harness library.

Frozen constants and thin wrappers around pinned ALFWorld 0.5.0 upstream code.
NOTHING in here invents a new subgoal validator: the subgoal signal is the
upstream `<TaskType>Policy.check_subgoal_completion` from
alfworld/agents/expert/handcoded_expert.py, specialised for TextWorld by
alfworld/agents/expert/handcoded_expert_tw.py.
"""
import os
import json
import random
import hashlib
from os.path import join as pjoin

import yaml
import textworld
import textworld.gym

from alfworld.agents.environment import get_environment
from alfworld.agents.environment.alfred_tw_env import AlfredDemangler, AlfredInfos
from alfworld.agents.expert import HandCodedTWAgent

# ---------------------------------------------------------------- frozen cfg
SEED = 13
REPO = "/home/aristella/recoverappworld/alfworld"
CONFIG_PATH = pjoin(REPO, "configs", "base_config.yaml")
OUT = "/home/aristella/recoverappworld/alfworld_recovermem_preflight"
SPLIT = "eval_out_of_distribution"          # == valid_unseen
MAX_ENV_STEPS = 200                          # env truncation; > any agent budget
MAX_AGENT_STEPS = 50                         # frozen, section 6
MAX_NEXT_SUBGOAL_STEPS = 20                  # frozen, section 6
N_FROZEN = 30


def load_config():
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    config["env"]["type"] = "AlfredTWEnv"
    config["dataset"]["eval_id_data_path"] = None
    return config


def collect_games():
    """Official game collection via AlfredTWEnv.collect_game_files()."""
    config = load_config()
    tw = get_environment("AlfredTWEnv")(config, train_eval=SPLIT)
    return tw.game_files


def frozen_order(game_files, seed=SEED):
    """Deterministic seed-13 ordering: lexicographic sort (filesystem-order
    independent) then random.Random(seed).shuffle."""
    files = sorted(game_files)
    rng = random.Random(seed)
    rng.shuffle(files)
    return files


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def traj_data_path(game_file):
    """Official mapping game.tw-pddl -> ALFRED traj_data.json.
    Same rule as HandCodedAgent.reset (handcoded_expert.py:549-551)."""
    return pjoin(os.path.dirname(game_file), "traj_data.json")


def load_traj(game_file):
    with open(traj_data_path(game_file)) as f:
        return json.load(f)


# ------------------------------------------------------------------- env
def make_env(game_files, batch_size=1, want_policy_commands=False,
             max_episode_steps=MAX_ENV_STEPS):
    """Replicates AlfredTWEnv.init_env (alfred_tw_env.py:245-278) for the
    eval split (domain_randomization forced False there), with request_infos
    extended by HARNESS-ONLY fields (facts / inventory / location / score).
    Those never reach the agent prompt."""
    wrappers = [AlfredDemangler(shuffle=False), AlfredInfos]
    request_infos = textworld.EnvInfos(
        won=True,
        admissible_commands=True,
        extras=["gamefile"],
        # harness-only below
        facts=True,
        inventory=True,
        location=True,
        score=True,
        max_score=True,
        policy_commands=want_policy_commands,
    )
    env_id = textworld.gym.register_games(
        game_files, request_infos,
        batch_size=batch_size,
        asynchronous=False,
        max_episode_steps=max_episode_steps,
        wrappers=wrappers,
    )
    return textworld.gym.make(env_id)


def unbatch(obs, infos, idx=0):
    """textworld.gym batch env -> single game_state dict shaped like the
    textworld.core.GameState that upstream expert code expects."""
    gs = {k: v[idx] for k, v in infos.items()}
    gs["feedback"] = obs[idx]
    return gs


# --------------------------------------------------- upstream subgoal monitor
class SubgoalMonitor:
    """HARNESS-ONLY monitor. Runs the pinned upstream ALFWorld TextWorld
    handcoded policy's state tracking + subgoal checker, verbatim:

        handcoded_expert.py:200  self.update_state_tracking(game_state, last_action)
        handcoded_expert.py:203  self.observe(obs)
        handcoded_expert.py:206  self.subgoal_idx = self.check_subgoal_completion(game_state)

    i.e. exactly BasePolicy.act's state-update block, minus upstream's
    heuristic *action selection* (which we do not need and which is the only
    part that can raise / consume RNG).

    `subgoal_idx` is upstream's index of the NEXT subgoal to execute, so it
    equals the number of completed subgoals in `policy.subgoals`.
    """

    def __init__(self, game_file, max_steps=10 ** 6):
        self.game_file = game_file
        agent = HandCodedTWAgent(max_steps=max_steps)
        agent.reset(game_file)            # loads traj_data -> task_params -> policy
        self.agent = agent
        self.policy = agent.policy
        self.K = len(self.policy.subgoals)
        self.task_type = agent.task_params["task_type"]
        self.subgoal_spec = [dict(s) for s in self.policy.subgoals]
        self.rank = 0
        self.max_rank = 0
        self.history = []                 # (step, action, rank)
        self.error = None

    def reset_obs(self, game_state):
        """Mirror AlfredExpert.reset (alfred_tw_env.py:105-110): feed the intro
        observation to the policy before any command has been issued."""
        self.policy.observe(game_state["feedback"])
        self.rank = 0
        self.max_rank = 0
        self.history = []

    def update(self, game_state, last_action, step):
        p = self.policy
        try:
            p.update_state_tracking(game_state, last_action)
            p.observe(game_state["feedback"])
            p.subgoal_idx = p.check_subgoal_completion(game_state)
            self.rank = int(p.subgoal_idx)
        except Exception as e:                       # never abort an episode
            self.error = f"{type(e).__name__}: {e}"
        self.max_rank = max(self.max_rank, self.rank)
        self.history.append({"step": step, "action": last_action, "rank": self.rank})
        return self.rank


def jdump(obj, path):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2, sort_keys=False)
    os.replace(tmp, path)
