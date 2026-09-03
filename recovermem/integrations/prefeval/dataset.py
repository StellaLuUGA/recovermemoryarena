"""PrefEval classification instances, histories and deterministic partitions.

Everything here is metadata-only and outcome-blind: nothing in this module reads a model
response, a correctness label, or any ReCoverMem score.

Frozen primary setting (Phase-1 §1):

* preference form  : implicit, **choice-based**
* history length   : ``--inter_turns 300``
* metric           : the released programmatic MCQ comparison

The gold answer is ``classification_task_options[0]`` by positional convention -- PrefEval
ships no gold field. It is shuffled away by :meth:`PrefInstance.shuffled` before anything
reaches the memory host, the scorer or the reader.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

PREFEVAL_ROOT = Path("/home/aristella/recoverappworld/PrefEval")
DATA = PREFEVAL_ROOT / "benchmark_dataset"

#: Frozen: the first canonical implicit form under every ordering the repo exposes
#: (sorted directory listing, argparse default, and run_mcq_task.sh execution order).
PREF_FORM = "implicit_choice"
PREF_FORM_DIR = DATA / "implicit_preference" / "choice-based"
OPTIONS_DIR = DATA / "mcq_options"
FILLER_FILE = DATA / "filtered_inter_turns.json"

#: Frozen: raw history ~101.6k Llama tokens = 3.1x the 32,768-token answer context.
INTER_TURNS = 300

#: Unreferenced stray file in mcq_options/; excluded by exact name.
STRAY_OPTION_FILES = {"travel_hotel copy"}

LETTERS = ("A", "B", "C", "D")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ShuffledOptions:
    """Options as the reader sees them, with the gold letter kept OUT of the text.

    The shuffle is derived from the instance id, not from a global ``random.seed`` --
    upstream's ``benchmark_classification.py`` calls ``random.seed(41)`` without importing
    ``random`` and therefore cannot have produced any released ordering, so no upstream
    permutation exists to reproduce. Deriving it from the id makes the ordering exactly
    reproducible and independent of iteration order.
    """

    options: tuple[str, ...]
    gold_letter: str

    def rendered(self) -> str:
        return "\n".join(f"{LETTERS[i]}. {o}" for i, o in enumerate(self.options))


@dataclass
class PrefInstance:
    """One PrefEval classification instance under the frozen primary setting."""

    topic: str
    index: int
    question: str
    raw_options: list[str]          # options[0] is the gold -- PRIVATE
    conversation: dict[str, str]    # the 4-message implicit choice-based exchange
    preference: str                 # PRIVATE: never enters a prompt in the implicit form
    explanation: str                # PRIVATE

    @property
    def pair_id(self) -> str:
        return f"{self.topic}#{self.index:03d}"

    # -- the parts that may reach a model ---------------------------------

    def shuffled(self) -> ShuffledOptions:
        """Deterministic per-instance permutation of the four options."""
        import random as _random

        rng = _random.Random(f"prefeval-mcq-shuffle-v1::{self.pair_id}")
        gold = self.raw_options[0]
        order = list(self.raw_options)
        rng.shuffle(order)
        return ShuffledOptions(options=tuple(order), gold_letter=LETTERS[order.index(gold)])

    def conversation_messages(self) -> list[dict[str, str]]:
        """The implicit preference exchange, using upstream's role assignment.

        ``utils/implicit_utils.extract_conversation_to_messages`` maps ``query`` and
        ``user_selection`` to the user role and everything else to the assistant.
        """
        out: list[dict[str, str]] = []
        for key, content in self.conversation.items():
            role = "user" if key in ("query", "user_selection") else "assistant"
            out.append({"role": role, "content": str(content)})
        return out

    def history(self, filler: list[dict[str, str]], inter_turns: int = INTER_TURNS) -> list[dict[str, str]]:
        """H_i = implicit preference exchange ++ the fixed distractor prefix.

        Order mirrors ``get_implicit_question_prompt_mcq``: conversation first, then the
        inter-turn filler, then (outside this function) the query.
        """
        return self.conversation_messages() + filler[: 2 * inter_turns]

    def common_state_text(self) -> str:
        """x_i -- byte-identical for the MEMORY and RECOVERY branches.

        Reproduces ``get_mcq_question_format`` verbatim, including its indentation, so the
        released prompt wording is unchanged.
        """
        formatted = self.shuffled().rendered()
        return self.question + f"""
    I'm trying to decide on this and here are 4 options for my query: \n{formatted}\nNow, I'd like you to pick one of them as your top recommendation for me.
    Important instructions for your response:
    1. Choose only one option (A, B, C, or D) that best matches my preferences.
    2. Your answer must be one of these options.
    3. Don't say things like "I can't choose" or suggest alternatives not listed.
    4. Answer example: <choice>B</choice>. Give me your answer in this exact format, without any additional explanation:
       <choice>[A/B/C/D]</choice>
    """

    def state_hash(self) -> str:
        return _h(self.common_state_text())


def load_filler() -> list[dict[str, str]]:
    """The single global distractor pool, concatenated in file order.

    ``utils/common_utils.extract_multi_turn_conversation`` walks this list from the start
    and stops at ``2 * inter_turns``, with no sampling -- so every instance in a run sees
    the identical prefix and different ``--inter_turns`` values are strict prefixes of one
    another. Reproduced exactly.
    """
    payload = json.loads(FILLER_FILE.read_text())
    return [dict(m) for conv in payload for m in conv["conversation"]]


def load_instances() -> list[PrefInstance]:
    """Every classification instance of the frozen preference form, in file order."""
    topics = sorted(
        f[:-5] for f in os.listdir(PREF_FORM_DIR) if f.endswith(".json")
    )
    out: list[PrefInstance] = []
    for topic in topics:
        if topic in STRAY_OPTION_FILES:
            continue
        pref = json.loads((PREF_FORM_DIR / f"{topic}.json").read_text())
        opts = json.loads((OPTIONS_DIR / f"{topic}.json").read_text())
        if len(pref) != len(opts):
            raise RuntimeError(
                f"{topic}: preference form has {len(pref)} records but mcq_options has "
                f"{len(opts)}; upstream's positional index is not aligned"
            )
        for i, (p, o) in enumerate(zip(pref, opts)):
            options = list(o["classification_task_options"])
            if len(options) != 4:
                raise RuntimeError(f"{topic}#{i}: expected 4 options, got {len(options)}")
            out.append(
                PrefInstance(
                    topic=topic,
                    index=i,
                    question=o["question"],
                    raw_options=options,
                    conversation=dict(p["conversation"]),
                    preference=o["preference"],
                    explanation=o.get("explanation", ""),
                )
            )
    return out


def group_key_components(instances: Iterable[PrefInstance]) -> dict[str, str]:
    """Phase-0 group key: connected components over shared preference OR shared query.

    Both the mcq-file and preference-file wordings are used as preference edges so the 30
    paraphrase pairs land in one group. Returns ``pair_id -> group_id``, where the group id
    is the lexicographically smallest member.
    """
    items = list(instances)
    parent = {x.pair_id: x.pair_id for x in items}

    def find(a: str) -> str:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    explicit_dir = DATA / "explicit_preference"
    explicit_pref: dict[str, str] = {}
    for topic in sorted(f[:-5] for f in os.listdir(explicit_dir) if f.endswith(".json")):
        rows = json.loads((explicit_dir / f"{topic}.json").read_text())
        for i, r in enumerate(rows):
            explicit_pref[f"{topic}#{i:03d}"] = _norm(r["preference"])

    for key in ("pref_mcq", "pref_explicit", "question"):
        buckets: dict[str, list[str]] = {}
        for x in items:
            if key == "pref_mcq":
                k = _norm(x.preference)
            elif key == "pref_explicit":
                k = explicit_pref.get(x.pair_id, f"<missing::{x.pair_id}>")
            else:
                k = _norm(x.question)
            buckets.setdefault(k, []).append(x.pair_id)
        for members in buckets.values():
            for m in members[1:]:
                union(members[0], m)

    return {x.pair_id: find(x.pair_id) for x in items}


def deterministic_partition(
    instances: list[PrefInstance],
    sizes: dict[str, int],
    seed: int = 13,
) -> dict[str, list[str]]:
    """Group-disjoint deterministic slices of the unit pool.

    Groups (not instances) are permuted with a fixed seed and dealt out in the order the
    caller lists ``sizes``; one representative instance per group is returned. Because a
    whole group moves together, no preference or query can appear in two partitions.
    """
    import numpy as np

    groups = group_key_components(instances)
    members: dict[str, list[str]] = {}
    for pid, gid in groups.items():
        members.setdefault(gid, []).append(pid)
    ordered_groups = sorted(members)
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(ordered_groups))
    shuffled = [ordered_groups[i] for i in perm]

    out: dict[str, list[str]] = {}
    cursor = 0
    for name, n in sizes.items():
        take = shuffled[cursor : cursor + n]
        cursor += n
        # One representative per group: the lexicographically first member.
        out[name] = [sorted(members[g])[0] for g in take]
    return out
