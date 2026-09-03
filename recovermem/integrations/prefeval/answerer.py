"""The fixed local answerer, shared byte-for-byte by both routes.

Only the evidence block differs between MEMORY and RECOVERY. The question block ``x_i``,
the system prompt, the assistant prefill, the decoding parameters and the output budget
are identical, and the caller asserts the ``x_i`` hashes match before a pair is logged.

Parsing is PrefEval's own ``extract_choice``, reached through the upstream module rather
than reimplemented, so the released metric is applied verbatim.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from recovermem.scoring.features import CandidateAction, DecisionState

PREFEVAL_ROOT = Path("/home/aristella/recoverappworld/PrefEval")

#: PrefEval's config.yaml system_prompt.
SYSTEM_PROMPT = "You are a helpful assistant."
#: PrefEval's config.yaml max_mcq_tokens is 5; 8 leaves room for the closing tag under
#: our own prefill while staying a negligible reserve. Recorded as B_out.
MAX_OUTPUT_TOKENS = 8
#: Upstream ends the prompt with an assistant turn containing exactly this.
ASSISTANT_PREFILL = "<choice>"

EVIDENCE_HEADER = (
    "Before answering my question, please consider the following context from our "
    "previous conversations:\n\n#Start of Context#\n"
)
EVIDENCE_FOOTER = (
    "\n#End of Context#\n\nPlease use this context to inform your answer and adhere to any "
    "preferences I've expressed that are relevant to the current query. Note that not all "
    "contexts are useful and there may be none that is useful. Now, please address my "
    "question:\n\n"
)


def _upstream_extract_choice():
    root = str(PREFEVAL_ROOT)
    if root not in sys.path:
        sys.path.append(root)  # append: PrefEval has generic top-level package names
    from utils.utils_mcq import extract_choice

    return extract_choice


def build_prompt(state_text: str, evidence_text: str) -> list[dict[str, str]]:
    """The full message list. ``state_text`` is inserted verbatim, never reformatted."""
    block = (EVIDENCE_HEADER + evidence_text + EVIDENCE_FOOTER) if evidence_text else ""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": block + state_text},
        {"role": "assistant", "content": ASSISTANT_PREFILL},
    ]


@dataclass
class AnswerResult:
    completion: str
    parsed_choice: Optional[str]
    prompt_tokens: int
    completion_tokens: int
    mean_logprob: Optional[float]
    latency_s: float


class LocalLlamaAnswerer:
    """OpenAI-compatible client pinned to the local vLLM server."""

    def __init__(
        self,
        model: str = "llama-3.1-8b-instruct-local",
        base_url: str = "http://127.0.0.1:8123/v1",
        api_key: str = "EMPTY",
        temperature: float = 0.0,
        max_tokens: int = MAX_OUTPUT_TOKENS,
    ):
        from openai import OpenAI

        if "127.0.0.1" not in base_url and "localhost" not in base_url:
            raise ValueError(f"answerer base_url {base_url!r} is not local; no external APIs")
        self.client = OpenAI(base_url=base_url, api_key=api_key, max_retries=3)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.n_calls = 0
        self._extract_choice = _upstream_extract_choice()

    def answer(self, state_text: str, evidence_text: str) -> AnswerResult:
        messages = build_prompt(state_text, evidence_text)
        started = time.perf_counter()
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            logprobs=True,
            extra_body={"continue_final_message": True, "add_generation_prompt": False},
        )
        latency = time.perf_counter() - started
        self.n_calls += 1
        completion = resp.choices[0].message.content or ""
        # Upstream re-attaches the prefill before parsing (benchmark_classification.py
        # does exactly this for claude/mistral), so the released parser sees the same
        # string shape it was written for.
        parsed = self._extract_choice(ASSISTANT_PREFILL + completion)
        mean_lp = None
        try:
            toks = resp.choices[0].logprobs.content or []
            if toks:
                mean_lp = sum(t.logprob for t in toks) / len(toks)
        except Exception:
            mean_lp = None
        usage = resp.usage
        return AnswerResult(
            completion=completion,
            parsed_choice=parsed,
            prompt_tokens=getattr(usage, "prompt_tokens", 0),
            completion_tokens=getattr(usage, "completion_tokens", 0),
            mean_logprob=mean_lp,
            latency_s=latency,
        )

    def as_proposer(self):
        """Adapt to the controller's ``ActionProposer`` protocol."""

        def proposer(state: DecisionState, evidence_text: str, **kwargs: Any) -> CandidateAction:
            r = self.answer(state.query, evidence_text)
            action = CandidateAction(
                name="mcq_choice",
                arguments={"choice": r.parsed_choice} if r.parsed_choice else {},
                text=r.completion,
                mean_logprob=r.mean_logprob,
            )
            action.result = r  # type: ignore[attr-defined]
            return action

        return proposer
