"""Frozen PersonaMem-v2 128K text instances.

Nothing in this module reads a model response or a correctness label.

The two pieces of benchmark semantics are imported from the released evaluator rather than
reimplemented: ``create_mcq_options`` (option order and the correct letter) and
``extract_final_answer`` (answer parsing). Both are used unmodified, and the option shuffle
is reproducible only when the process runs with ``PYTHONHASHSEED=13`` -- which
:func:`assert_hashseed` refuses to proceed without, because the released seed is
``hash(str)`` and would otherwise differ per process.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pandas as pd

DATA = Path("/home/aristella/recoverappworld/personamem_recovermem_outputs/_data_v2")
CODE = Path("/home/aristella/recoverappworld/personamem_recovermem_outputs/_code_v2")
FROZEN = Path("/home/aristella/recoverappworld/personamem_recovermem_outputs/frozen_protocol/FROZEN_SPLIT.json")
BENCHMARK_CSV = DATA / "benchmark/text/benchmark.csv"

#: Appended by the released evaluator to every user query before shuffling/answering.
RECALL_SUFFIX = " Please recall my related preferences from our conversation history to give personalized responses."


def assert_hashseed() -> None:
    if os.environ.get("PYTHONHASHSEED") != "13":
        raise RuntimeError(
            "PYTHONHASHSEED=13 must be set BEFORE the interpreter starts. The released "
            "option shuffle seeds on hash(str), which Python randomises per process; "
            "without the fixed seed the frozen option order cannot be reproduced."
        )


def _upstream():
    """Lift the released evaluator's two pure helpers out of its source, unmodified.

    ``inference.py`` imports API clients at module load (``query_llm`` -> ``timeout_decorator``,
    litellm, ...), so importing it would drag in a dependency chain this audit has no use for
    and no right to install. Instead the exact source text of ``create_mcq_options`` and
    ``extract_final_answer`` is extracted with ``ast`` and executed on its own. Both are
    self-contained -- they read only their arguments -- so this is the released implementation
    verbatim, not a reimplementation.
    """
    import ast as _ast
    import textwrap

    src = (CODE / "inference.py").read_text()
    tree = _ast.parse(src)
    wanted = {"create_mcq_options", "extract_final_answer"}
    ns: dict[str, Any] = {"random": __import__("random"), "re": __import__("re"),
                          "List": list, "Dict": dict, "Tuple": tuple, "Any": object}
    found = {}
    for node in _ast.walk(tree):
        if isinstance(node, _ast.FunctionDef) and node.name in wanted:
            body = textwrap.dedent(_ast.get_source_segment(src, node))
            exec(compile(body, f"<pm2:{node.name}>", "exec"), ns)
            found[node.name] = ns[node.name]
    missing = wanted - set(found)
    if missing:
        raise RuntimeError(f"released evaluator no longer defines {sorted(missing)}")

    class _Upstream:
        create_mcq_options = staticmethod(found["create_mcq_options"])
        extract_final_answer = staticmethod(found["extract_final_answer"])

    return _Upstream


@dataclass
class V2Instance:
    """One frozen benchmark row, bound to its persona's history."""

    persona_id: int
    question_id: str
    user_query_content: str
    correct_answer: str
    incorrect_answers: list[str]
    chat_history_128k_link: str
    pref_type: str
    conversation_scenario: str
    topic_query: str
    who: str
    updated: bool
    total_tokens_128k: int
    distance_to_snippet_128k: int

    # filled by freeze_options()
    option_order: list[str] = field(default_factory=list)
    correct_letter: str = ""
    mcq_instruction: str = ""
    row_seed: int = 0

    @property
    def query_with_recall(self) -> str:
        return self.user_query_content + RECALL_SUFFIX

    def common_state_text(self) -> str:
        """x_i -- byte-identical for both branches. Released wording, unmodified."""
        if not self.mcq_instruction:
            raise RuntimeError("call freeze_options() first")
        return self.query_with_recall + "\n\n" + self.mcq_instruction

    def state_hash(self) -> str:
        return hashlib.sha256(self.common_state_text().encode()).hexdigest()

    def option_order_hash(self) -> str:
        return hashlib.sha256("\x00".join(self.option_order).encode()).hexdigest()


class V2Bench:
    def __init__(self) -> None:
        assert_hashseed()
        self._cls = _upstream()
        self.frozen = json.loads(FROZEN.read_text())
        self.df = pd.read_csv(BENCHMARK_CSV)
        self.df = self.df[self.df.distance_from_related_snippet_to_query_128k > 0].copy()
        self.df["question_id"] = [
            "q_" + hashlib.sha256(
                f"{r.persona_id}\x00{r.user_query}\x00{r.correct_answer}".encode()
            ).hexdigest()[:16]
            for r in self.df.itertuples()
        ]

    # -- option freezing --------------------------------------------------

    def freeze_options(self, inst: V2Instance) -> V2Instance:
        """Apply the released shuffle verbatim and record the resulting order."""
        content = inst.query_with_recall
        inst.row_seed = hash(f"{inst.persona_id}_{content}") % 2**32
        mcq_instruction, option_mapping = self._cls.create_mcq_options(
            None, inst.correct_answer, list(inst.incorrect_answers), seed=inst.row_seed
        )
        inst.mcq_instruction = mcq_instruction
        inst.option_order = [option_mapping[chr(65 + i)] for i in range(len(option_mapping))]
        inst.correct_letter = next(
            l for l, a in option_mapping.items() if a == inst.correct_answer
        )
        return inst

    def extract_answer(self, response: str) -> str:
        return self._cls.extract_final_answer(None, response)

    def is_correct(self, response: str, inst: V2Instance) -> bool:
        letter = self.extract_answer(response)
        mapping = {chr(65 + i): o for i, o in enumerate(inst.option_order)}
        return mapping.get(letter.upper(), "") == inst.correct_answer

    # -- loading ----------------------------------------------------------

    def instances_for(self, persona_id: int) -> list[V2Instance]:
        g = self.df[self.df.persona_id == persona_id]
        out: list[V2Instance] = []
        for r in g.itertuples():
            try:
                uq = json.loads(r.user_query)
            except Exception:
                uq = ast.literal_eval(r.user_query)
            out.append(self.freeze_options(V2Instance(
                persona_id=int(r.persona_id), question_id=r.question_id,
                user_query_content=uq["content"],
                correct_answer=r.correct_answer,
                incorrect_answers=json.loads(r.incorrect_answers),
                chat_history_128k_link=r.chat_history_128k_link,
                pref_type=r.pref_type, conversation_scenario=r.conversation_scenario,
                topic_query=r.topic_query, who=r.who, updated=bool(r.updated),
                total_tokens_128k=int(r.total_tokens_in_chat_history_128k),
                distance_to_snippet_128k=int(r.distance_from_related_snippet_to_query_128k),
            )))
        return sorted(out, key=lambda i: i.question_id)

    def history(self, persona_id: int) -> list[dict[str, str]]:
        """H_i: the persona's complete 128K text history.

        The released evaluator appends the query AFTER the whole history, so the entire
        file is observable past and there is no future segment to exclude.
        """
        g = self.df[self.df.persona_id == persona_id]
        link = g.chat_history_128k_link.iloc[0]
        payload = json.loads((DATA / link).read_text())
        msgs = payload["chat_history"]
        for m in msgs:
            extra = set(m) - {"role", "content"}
            if extra:
                raise RuntimeError(f"non-text field {extra} in history of persona {persona_id}")
        return [{"role": m["role"], "content": m["content"]} for m in msgs]

    def split(self, name: str) -> list[int]:
        return [int(p) for p in self.frozen["splits"][name]]
