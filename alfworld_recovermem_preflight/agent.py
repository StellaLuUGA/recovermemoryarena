"""Frozen Llama-3.1-8B ALFWorld text agent (see competence/AGENT_FREEZE.md)."""
import os, re, json, sys
import requests
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pf_lib as L

BASE_URL = "http://localhost:8123/v1"
TOKENIZE_URL = "http://localhost:8123/tokenize"
MODEL = "llama-3.1-8b-instruct-local"
TEMPERATURE = 0.0
SEED = 13
MAX_TOKENS = 32

_client = OpenAI(base_url=BASE_URL, api_key="EMPTY")

TEMPLATES = [
    "clean {obj} with {recep}", "close {recep}", "cool {obj} with {recep}",
    "examine {obj}", "examine {recep}", "go to {recep}", "heat {obj} with {recep}",
    "help", "inventory", "look", "move {obj} to {recep}", "open {recep}",
    "put {obj} in {recep}", "slice {obj} with {knife}",
    "take {obj} from {recep}", "use {obj}",
]

SYSTEM = (
    "You are an agent solving a text-based household task in the ALFWorld TextWorld "
    "environment.\n\n"
    "Each turn you get the environment's latest response and you reply with exactly ONE "
    "action, and nothing else. No explanations, no numbering, no quotes.\n\n"
    "Objects and receptacles are always referred to with their number, e.g. 'cabinet 2', "
    "'mug 1'. The available action forms are:\n"
    + "\n".join("  " + t for t in TEMPLATES) +
    "\n\nHints: you must 'go to' a receptacle before interacting with things there; you may "
    "need to 'open' a closed receptacle to see inside; you can carry only one object at a "
    "time; 'clean X with sinkbasin', 'heat X with microwave', 'cool X with fridge' work only "
    "while you are holding X and standing at that receptacle; 'use X' turns on a lamp; the "
    "'inventory' action tells you what you are carrying.\n"
    "Do not repeat an action that produced 'Nothing happens.'"
)


def count_tokens(text):
    r = requests.post(TOKENIZE_URL, json={"model": MODEL, "prompt": text}, timeout=60)
    r.raise_for_status()
    return r.json()["count"]


def _render(intro, history):
    """history: list of (action, observation)."""
    parts = [intro.strip()]
    for a, o in history:
        parts.append(f"> {a}\n{o.strip()}")
    return "\n".join(parts)


def build_prompt(icl, intro, history):
    ex = _render(icl["intro"], [(s["action"], s["obs"]) for s in icl["steps"]])
    hist = _render(intro, history)
    user = ("Here is a complete example episode from a different game:\n\n"
            "=== EXAMPLE ===\n" + ex + "\n=== END EXAMPLE ===\n\n"
            "--- New game ---\n" + hist + "\n>")
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": user}], hist


_STRIP = re.compile(r"^[>\s\"'`*\-]+|[\s\"'`*.]+$")
_DIGITS = re.compile(r"\d")


def _canon(s):
    return " ".join(_DIGITS.sub("", s).split())


def parse_action(raw, admissible):
    """Frozen OPTION-A parser. Returns (command, snapped, invalid)."""
    line = next((l for l in raw.splitlines() if l.strip()), "")
    a = _STRIP.sub("", line).strip().lower()
    if not a:
        return "look", False, True
    if a in admissible:
        return a, False, False
    ca = _canon(a)
    cands = [c for c in admissible if _canon(c) == ca]
    if len(cands) == 1:
        return cands[0], True, False
    return a, False, True


def act(icl, intro, history, admissible):
    msgs, hist_text = build_prompt(icl, intro, history)
    resp = _client.chat.completions.create(
        model=MODEL, messages=msgs, temperature=TEMPERATURE, top_p=1.0,
        max_tokens=MAX_TOKENS, seed=SEED, stop=["\n"],
    )
    raw = (resp.choices[0].message.content or "").strip()
    cmd, snapped, invalid = parse_action(raw, admissible)
    usage = resp.usage
    return {
        "raw": raw, "command": cmd, "snapped": snapped, "invalid": invalid,
        "prompt_tokens": usage.prompt_tokens if usage else None,
        "history_text": hist_text,
    }
