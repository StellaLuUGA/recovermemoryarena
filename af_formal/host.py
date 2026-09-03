"""Frozen Config-C host agent + ALFWorld environment plumbing for the formal run.

The action interface (system prompt, ICL example, admissible-command formatting,
history/observation serialisation, exact entity-preserving parser) is imported VERBATIM
from the frozen preflight modules; nothing is re-derived here.
"""
from __future__ import annotations

import json
from typing import Any

from af_formal.common import (LEDGER, MAX_BRANCH_ACTIONS, MAX_TOTAL_AGENT_ACTIONS,
                              PREFLIGHT, QWEN_BASE_URL, QWEN_MODEL, SEED, assert_local,
                              current_bucket, instrument_openai_client, sha256_text)

import pf_lib as L                      # frozen preflight harness
import agent_b as B                     # frozen Config-B interface
import agent_c as C                     # frozen Config-C backbone binding

from openai import OpenAI

# frozen, imported not restated
SYSTEM = C.SYSTEM
render_history = C._render
format_admissible = C.format_admissible
parse_action = C.parse_action
SubgoalMonitor = L.SubgoalMonitor
make_env = L.make_env
unbatch = L.unbatch

ICL = json.load(open(PREFLIGHT / "competence" / "ICL_EXAMPLE.json"))
_EX = render_history(ICL["intro"], [(s["action"], s["obs"]) for s in ICL["steps"]])

assert_local(QWEN_BASE_URL, "action agent")
_client = instrument_openai_client(OpenAI(base_url=QWEN_BASE_URL, api_key="EMPTY"))

USE_LOGPROBS = True     # frozen in agent_config_formal.json; does not affect temp-0 output


def _chat(messages, want_logprobs=False):
    kw = dict(model=QWEN_MODEL, messages=messages, temperature=C.TEMPERATURE, top_p=1.0,
              max_tokens=C.MAX_TOKENS, seed=SEED, stop=["\n"],
              extra_body={"chat_template_kwargs": {"enable_thinking": False}})
    if want_logprobs and USE_LOGPROBS:
        kw["logprobs"] = True
    resp = _client.chat.completions.create(**kw)
    ch = resp.choices[0]
    raw = (ch.message.content or "").strip()
    mlp = None
    lp = getattr(ch, "logprobs", None)
    toks = getattr(lp, "content", None) if lp else None
    if toks:
        vals = [t.logprob for t in toks if t.logprob is not None]
        if vals:
            mlp = sum(vals) / len(vals)
    return raw, mlp, resp.usage


# ---------------------------------------------------------------- prompts
def native_prompt(intro, history, admissible):
    """Config-C native prompt: full raw observable history."""
    hist = render_history(intro, history)
    user = ("Here is a complete example episode from a different game:\n\n"
            "=== EXAMPLE ===\n" + _EX + "\n=== END EXAMPLE ===\n\n"
            "--- New game ---\n" + hist + "\n\n" + format_admissible(admissible) + "\n>")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def common_state_text(task_instruction, observation, admissible):
    """x_t -- byte-identical for both branches. Benchmark-observable only."""
    return ("Task: " + task_instruction.strip() + "\n"
            "Current observation: " + observation.strip() + "\n"
            + format_admissible(admissible))


def branch_prompt(evidence_label, evidence_text, x_text, local_turns):
    """Branch prompt: x_t + selected evidence + the NEW local transcript only.

    The pre-S_t raw trajectory is deliberately absent; the branch sees the past only
    through its evidence source."""
    parts = ["Here is a complete example episode from a different game:\n\n"
             "=== EXAMPLE ===\n" + _EX + "\n=== END EXAMPLE ===\n",
             "--- Current game ---",
             f"{evidence_label}:\n{evidence_text.strip() or '(nothing retrieved)'}\n"]
    if local_turns:
        parts.append("Recent steps:\n" + "\n".join(
            f"> {a}\n{o.strip()}" for a, o in local_turns) + "\n")
    parts.append(x_text + "\n>")
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": "\n".join(parts)}]


# ---------------------------------------------------------------- actions
def act_native(intro, history, admissible, bucket="native"):
    msgs = native_prompt(intro, history, admissible)
    from af_formal.common import set_bucket
    set_bucket(bucket)
    raw, mlp, usage = _chat(msgs)
    cmd, valid = parse_action(raw, admissible)
    return {"raw": raw, "command": cmd, "valid": valid, "mean_logprob": mlp,
            "prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens}


def act_branch(evidence_label, evidence_text, x_text, local_turns, admissible,
               bucket, want_logprobs=False):
    msgs = branch_prompt(evidence_label, evidence_text, x_text, local_turns)
    from af_formal.common import set_bucket
    set_bucket(bucket)
    raw, mlp, usage = _chat(msgs, want_logprobs=want_logprobs)
    cmd, valid = parse_action(raw, admissible)
    return {"raw": raw, "command": cmd, "valid": valid, "mean_logprob": mlp,
            "prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens}


# ---------------------------------------------------------------- env
class Episode:
    """One ALFWorld game instance with its harness-only subgoal monitor."""

    def __init__(self, game_file):
        self.game_file = game_file
        self.env = make_env([game_file])
        obs, infos = self.env.reset()
        self.gs = unbatch(obs, infos)
        self.mon = SubgoalMonitor(game_file)
        self.mon.reset_obs(self.gs)
        self.intro = obs[0]
        self.task_instruction = _task_from_intro(self.intro)
        self.history: list[tuple[str, str]] = []
        self.t = 0
        self.done = False

    @property
    def K(self):
        return self.mon.K

    @property
    def rank(self):
        return self.mon.rank

    @property
    def admissible(self):
        return self.gs["admissible_commands"]

    @property
    def observation(self):
        return self.history[-1][1] if self.history else self.intro

    @property
    def won(self):
        return bool(self.gs["won"])

    def step(self, cmd):
        obs, _, dones, infos = self.env.step([cmd])
        self.gs = unbatch(obs, infos)
        self.t += 1
        rank = self.mon.update(self.gs, cmd, self.t)
        self.history.append((cmd, obs[0]))
        self.done = bool(dones[0]) or self.won
        return obs[0], rank, self.done

    def close(self):
        try:
            self.env.close()
        except Exception:
            pass

    def x_text(self):
        return common_state_text(self.task_instruction, self.observation, self.admissible)

    def history_messages(self):
        """Raw observable trajectory as chat turns, for recovery retrieval."""
        msgs = [{"role": "user", "content": self.intro.strip()}]
        for a, o in self.history:
            msgs.append({"role": "assistant", "content": f"action: {a}"})
            msgs.append({"role": "user", "content": f"observation: {o.strip()}"})
        return msgs


def _task_from_intro(intro: str) -> str:
    for line in intro.splitlines():
        if "Your task is to:" in line:
            return line.split("Your task is to:", 1)[1].strip()
    return intro.strip().splitlines()[-1]


def reconstruct(game_file, prefix):
    """Fresh reset + exact action-prefix replay. Returns a live Episode at S_t."""
    ep = Episode(game_file)
    for cmd in prefix:
        ep.step(cmd)
    return ep
