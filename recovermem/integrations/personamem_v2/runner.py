"""Per-persona paired collection for PersonaMem-v2 128K text MCQ.

One persona = one source unit = one Mem0 store built once from that persona's 128K history
and then reused, read-only, for all of the persona's eligible queries. Queries and answers
are never written back.
"""

from __future__ import annotations

import hashlib
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from recovermem.hosts.mem0_adapter import Mem0Adapter, Mem0Config
from recovermem.integrations.personamem_v2.dataset import V2Bench, V2Instance
from recovermem.integrations.prefeval.answerer import LocalLlamaAnswerer, build_prompt
from recovermem.integrations.prefeval.runner import _Mem0ErrorCounter, chunk_messages
from recovermem.recovery.trajectory_retriever import TrajectoryRetriever
from recovermem.scoring.features import CandidateAction, DecisionState, extract_features
from recovermem.tokens import TokenCounter

LLAMA_SNAPSHOT = (
    "/home/aristella/.cache/huggingface/hub/models--meta-llama--Llama-3.1-8B-Instruct/"
    "snapshots/0e9e39f249a16976918f6564b8830bc894c89659"
)
WRITE_CHUNK_TOKENS = 4096
#: The released MCQ prompt asks for reasoning BEFORE the letter, so the output reserve is
#: far larger than PrefEval's 8. Measured on 10 held-out predictor_train queries, the model
#: needs 270 / 350 / 718 tokens (min / median / max) to reach "Final Answer:"; 1024 gives
#: 1.4x headroom over the observed worst case. An earlier value of 256 truncated the chain
#: before the answer on 116 of 138 smoke calls -- the defect this reserve exists to avoid.
MAX_OUTPUT_TOKENS = 1024


class V2Answerer(LocalLlamaAnswerer):
    """Same local endpoint and settings as every other ReCoverMem workload.

    The assistant prefill PrefEval used is dropped here: PersonaMem-v2's released prompt
    asks the model to reason first and then emit ``Final Answer: [Letter]``, and parsing is
    the released ``extract_final_answer``.
    """

    def __init__(self, bench: V2Bench, **kw):
        kw.setdefault("max_tokens", MAX_OUTPUT_TOKENS)
        super().__init__(**kw)
        self.bench = bench

    def answer(self, state_text: str, evidence_text: str):  # type: ignore[override]
        import time as _t

        messages = build_prompt(state_text, evidence_text)[:2]  # drop the <choice> prefill
        started = _t.perf_counter()
        resp = self.client.chat.completions.create(
            model=self.model, messages=messages,
            temperature=self.temperature, max_tokens=self.max_tokens, logprobs=True,
        )
        latency = _t.perf_counter() - started
        self.n_calls += 1
        completion = resp.choices[0].message.content or ""
        mean_lp = None
        try:
            toks = resp.choices[0].logprobs.content or []
            if toks:
                mean_lp = sum(t.logprob for t in toks) / len(toks)
        except Exception:
            pass
        from recovermem.integrations.prefeval.answerer import AnswerResult

        return AnswerResult(completion=completion,
                            parsed_choice=self.bench.extract_answer(completion) or None,
                            prompt_tokens=getattr(resp.usage, "prompt_tokens", 0),
                            completion_tokens=getattr(resp.usage, "completion_tokens", 0),
                            mean_logprob=mean_lp, latency_s=latency)


class V2Runner:
    def __init__(self, store_root: str | Path, b_mem: Optional[int] = None,
                 bench: Optional[V2Bench] = None):
        self.counter = TokenCounter(LLAMA_SNAPSHOT)
        if not self.counter.exact:
            raise RuntimeError("exact Llama tokenizer unavailable; refusing to run")
        self.bench = bench or V2Bench()
        self.store_root = Path(store_root)
        self.b_mem = b_mem
        self.b_rec = b_mem
        self.answerer = V2Answerer(self.bench)
        self.recovery = TrajectoryRetriever(self.counter, window=0)
        self.mem0_errors = _Mem0ErrorCounter()
        import logging
        logging.getLogger("mem0").addHandler(self.mem0_errors)
        logging.getLogger("mem0.memory.main").addHandler(self.mem0_errors)
        self.host = Mem0Adapter(
            config=Mem0Config(llm_base_url="http://127.0.0.1:8123/v1",
                              llm_model="llama-3.1-8b-instruct-local", llm_temperature=0.0,
                              embedder_device="cpu", collection_name="recovermem_pm2_128k"),
            counter=self.counter, store_root=self.store_root)

    def build_memory(self, persona_id: int) -> dict[str, Any]:
        """Fresh store, stream the persona's 128K history exactly once."""
        eid = f"persona{persona_id}"
        d = self.store_root / eid
        if d.exists():
            shutil.rmtree(d)
        self.host.reset(eid)
        history = self.bench.history(persona_id)
        chunks = chunk_messages(history, self.counter, WRITE_CHUNK_TOKENS)
        self.mem0_errors.reset()
        t0 = time.perf_counter()
        for ch in chunks:
            self.host.write(ch)
        build_s = time.perf_counter() - t0
        snap = self.host.snapshot()
        return dict(history=history, build_s=build_s, n_chunks=len(chunks),
                    n_messages=len(history),
                    history_tokens=self.counter.count_messages(history),
                    mem0_memory_count=int(snap.get("n_memories") or 0),
                    mem0_parse_failures=self.mem0_errors.count,
                    write_prompt_tokens=self.host.write_prompt_tokens)

    def uncapped_evidence(self, inst: V2Instance) -> dict[str, Any]:
        ev = self.host.retrieve(inst.common_state_text(), budget_tokens=10 ** 9)
        return dict(uncapped_evidence_tokens=ev.tokens, n_candidates=ev.n_candidates,
                    n_packed=ev.n_packed, retrieval_latency_s=ev.latency_s,
                    largest_candidate_tokens=max((c["tokens"] for c in ev.candidates), default=0))

    def run_instance(self, inst: V2Instance, history: list[dict[str, str]]) -> dict[str, Any]:
        if self.b_mem is None:
            raise RuntimeError("B_mem is not frozen; run the budget audit first")
        x = inst.common_state_text()
        xh = hashlib.sha256(x.encode()).hexdigest()
        state = DecisionState(query=x, step_index=0, max_steps=1, state_hash=xh,
                              state_tokens=self.counter.count_text(x))

        mem_ev = self.host.retrieve(x, self.b_mem)
        t0 = time.perf_counter(); mem_ans = self.answerer.answer(x, mem_ev.text)
        mem_lat = time.perf_counter() - t0
        mem_hash = hashlib.sha256(x.encode()).hexdigest()

        rec_ev = self.recovery.recover(x, history, self.b_rec)
        t0 = time.perf_counter(); rec_ans = self.answerer.answer(x, rec_ev.text)
        rec_lat = time.perf_counter() - t0
        rec_hash = hashlib.sha256(x.encode()).hexdigest()

        cand = CandidateAction(name="mcq_choice",
                               arguments={"choice": mem_ans.parsed_choice} if mem_ans.parsed_choice else {},
                               text=mem_ans.completion, mean_logprob=mem_ans.mean_logprob)
        feats = extract_features(state, mem_ev, cand)

        u_mem = 1.0 if self.bench.is_correct(mem_ans.completion, inst) else 0.0
        u_rec = 1.0 if self.bench.is_correct(rec_ans.completion, inst) else 0.0
        return dict(persona_id=inst.persona_id, question_id=inst.question_id,
                    pref_type=inst.pref_type, conversation_scenario=inst.conversation_scenario,
                    distance_to_snippet_128k=inst.distance_to_snippet_128k,
                    state_hash=xh, memory_branch_state_hash=mem_hash,
                    recovery_branch_state_hash=rec_hash,
                    pair_valid=(xh == mem_hash == rec_hash),
                    state_tokens=state.state_tokens,
                    option_order_hash=inst.option_order_hash(), correct_letter=inst.correct_letter,
                    row_seed=inst.row_seed,
                    b_mem=self.b_mem, b_rec=self.b_rec,
                    memory_evidence_tokens=mem_ev.tokens, recovery_evidence_tokens=rec_ev.tokens,
                    n_memory_candidates=mem_ev.n_candidates, n_memory_packed=mem_ev.n_packed,
                    n_recovery_packed=len(rec_ev.items),
                    memory_choice=mem_ans.parsed_choice, recovery_choice=rec_ans.parsed_choice,
                    memory_completion=mem_ans.completion, recovery_completion=rec_ans.completion,
                    memory_prompt_tokens=mem_ans.prompt_tokens,
                    recovery_prompt_tokens=rec_ans.prompt_tokens,
                    u_mem=u_mem, u_rec=u_rec, r_mem=int(u_mem >= 0.5), r_rec=int(u_rec >= 0.5),
                    features=dict(feats.values),
                    memory_latency_s=mem_lat, recovery_latency_s=rec_lat)
