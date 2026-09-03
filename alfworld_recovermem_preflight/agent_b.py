"""AGENT_CONFIG_B_ADMISSIBLE_COMMANDS — final ALFWorld preflight agent.

Exactly two changes vs Config A (agent.py):
  1. entity-preserving EXACT parser  (no digit-stripping, no fuzzy match)
  2. admissible_commands shown to the model every step
Everything else is carried over verbatim from agent.py.
"""
import os, re, sys, json, hashlib
import requests
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pf_lib as L
import agent as A_CONFIG_A          # reuse Config A's serialisation verbatim

BASE_URL = A_CONFIG_A.BASE_URL
TOKENIZE_URL = A_CONFIG_A.TOKENIZE_URL
MODEL = A_CONFIG_A.MODEL
TEMPERATURE = A_CONFIG_A.TEMPERATURE      # 0.0
SEED = A_CONFIG_A.SEED                    # 13
MAX_TOKENS = A_CONFIG_A.MAX_TOKENS        # 32

_client = OpenAI(base_url=BASE_URL, api_key="EMPTY")

# --- Config A's system prompt, with ONLY the output contract adapted to the
# --- admissible-command list (change 2).  Body text is otherwise identical.
SYSTEM = (
    A_CONFIG_A.SYSTEM
    + "\n\nAt every step you are given the list of admissible commands for the current state. "
      "Choose exactly ONE command from that list and copy it verbatim, including its numbers. "
      "Reply in the form:\nACTION: <command>"
)

count_tokens = A_CONFIG_A.count_tokens
_render = A_CONFIG_A._render              # identical history/observation serialisation


def format_admissible(admissible):
    return "Admissible commands:\n" + "\n".join("- " + c for c in admissible)


def build_prompt(icl, intro, history, admissible):
    ex = _render(icl["intro"], [(s["action"], s["obs"]) for s in icl["steps"]])
    hist = _render(intro, history)
    user = ("Here is a complete example episode from a different game:\n\n"
            "=== EXAMPLE ===\n" + ex + "\n=== END EXAMPLE ===\n\n"
            "--- New game ---\n" + hist + "\n\n"
            + format_admissible(admissible) + "\n>")
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": user}], hist


# ---------------------------------------------------------------- EXACT parser
_ACTION_PREFIX = re.compile(r"^\s*action\s*:\s*", re.IGNORECASE)
_WRAP = re.compile(r"^[>\s\"'`*]+|[\s\"'`*]+$")


def parse_action(raw, admissible):
    """ENTITY-PRESERVING EXACT parser.

    Normalises ONLY: leading '>' / whitespace, an optional 'ACTION:' prefix,
    wrapping quotes/backticks/asterisks, a single trailing period, and letter case.
    It never alters the verb, an object or receptacle identity, or a numeric suffix,
    and it never substitutes a different admissible command.

    Returns (command, valid).
    """
    line = next((l for l in raw.splitlines() if l.strip()), "")
    a = _ACTION_PREFIX.sub("", line)
    a = _WRAP.sub("", a).strip()
    if a.endswith("."):
        a = a[:-1].rstrip()
    a = a.lower()
    if not a:
        return "look", False
    return a, (a in admissible)


def act(icl, intro, history, admissible):
    msgs, hist_text = build_prompt(icl, intro, history, admissible)
    resp = _client.chat.completions.create(
        model=MODEL, messages=msgs, temperature=TEMPERATURE, top_p=1.0,
        max_tokens=MAX_TOKENS, seed=SEED, stop=["\n"],
    )
    raw = (resp.choices[0].message.content or "").strip()
    cmd, valid = parse_action(raw, admissible)
    usage = resp.usage
    return {"raw": raw, "command": cmd, "valid": valid, "invalid": not valid,
            "snapped": False,
            "prompt_tokens": usage.prompt_tokens if usage else None,
            "history_text": hist_text}


def config_dict(icl):
    return {
        "config_id": "AGENT_CONFIG_B_ADMISSIBLE_COMMANDS",
        "model": MODEL, "endpoint": BASE_URL, "temperature": TEMPERATURE,
        "top_p": 1.0, "seed": SEED, "max_tokens_per_action": MAX_TOKENS,
        "stop": ["\n"],
        "MAX_AGENT_STEPS": L.MAX_AGENT_STEPS,
        "MAX_NEXT_SUBGOAL_STEPS": L.MAX_NEXT_SUBGOAL_STEPS,
        "env": "AlfredTWEnv", "split": L.SPLIT, "env_max_episode_steps": L.MAX_ENV_STEPS,
        "system_prompt": SYSTEM,
        "user_prompt_template": ("Here is a complete example episode from a different game:\n\n"
                                 "=== EXAMPLE ===\n{example}\n=== END EXAMPLE ===\n\n"
                                 "--- New game ---\n{history}\n\n"
                                 "Admissible commands:\n- {cmd}\n- ...\n>"),
        "admissible_command_formatting": "one per line, prefixed '- ', verbatim from info['admissible_commands'][0], in engine order",
        "history_serialization": "identical to Config A: intro, then '> {action}\\n{observation}' per step",
        "inventory": "EnvInfos.inventory is None on ALFWorld games; nothing injected. The agent may issue the 'inventory' action itself.",
        "parser": {
            "kind": "entity-preserving exact match",
            "normalises": ["leading '>' and whitespace", "optional 'ACTION:' prefix",
                           "wrapping quotes/backticks/asterisks", "one trailing period",
                           "letter case"],
            "never_modifies": ["action verb", "object identity", "receptacle identity",
                               "numeric suffix"],
            "fuzzy_or_digit_stripped_matching": False,
            "on_invalid": "issue the normalised string verbatim; TextWorld answers 'Nothing happens.'",
            "on_empty_output": "issue 'look', counted as invalid",
            "source": "agent_b.py::parse_action",
        },
        "icl_examples": [{
            "game_file": icl["game_file"], "split": icl["split"],
            "task_type": icl["task_type"], "n_steps": len(icl["steps"]),
            "selection_rule": icl["selection_rule"],
        }],
        "agent_visible": ["task instruction", "current text observation",
                          "prior actions and environment responses",
                          "current admissible_commands"],
        "harness_only": ["plan.high_pddl", "traj_data.json", "PDDL facts",
                         "policy_commands", "extra.expert_plan", "subgoal rank"],
    }


def config_hash(cfg):
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()
