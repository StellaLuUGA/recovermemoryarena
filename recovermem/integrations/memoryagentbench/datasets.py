"""MAB-AR source histories.

One ``SourceHistory`` is one MemoryAgentBench context together with every query attached
to it. That grouping is the whole point: MAB stores a long context once and asks many
questions of it, so the queries inside a history share their entire evidence source and
are NOT exchangeable with one another. Every split, every risk average and every
calibration unit downstream is keyed on ``history_id``.

Chunking, query templating and dataset loading are upstream MAB code, called verbatim.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

from recovermem.integrations.memoryagentbench.upstream import load_mab

#: The three Accurate Retrieval sources in scope, with their upstream config paths.
#: ``dataset``/``sub_dataset`` mirror the YAML so the audit can prove the match.
AR_SOURCES: dict[str, dict[str, Any]] = {
    "event_qa": {
        "config_path": "configs/data_conf/Accurate_Retrieval/EventQA/Eventqa_full.yaml",
        "dataset": "Accurate_Retrieval",
        "sub_dataset": "eventqa_full",
        "native_metric": "substring_exact_match",
    },
    "ruler_qa1": {
        "config_path": "configs/data_conf/Accurate_Retrieval/Ruler/QA/Ruler_qa1_197k.yaml",
        "dataset": "Accurate_Retrieval",
        "sub_dataset": "ruler_qa1_197K",
        "native_metric": "substring_exact_match",
    },
    "ruler_qa2": {
        "config_path": "configs/data_conf/Accurate_Retrieval/Ruler/QA/Ruler_qa2_421k.yaml",
        "dataset": "Accurate_Retrieval",
        "sub_dataset": "ruler_qa2_421K",
        "native_metric": "substring_exact_match",
    },
}

#: Agent-name token MAB's template dispatcher maps to the retrieval-agent query wording.
#: MAB-AR routes evidence through a memory host, so the RAG phrasing is the faithful one;
#: the long-context phrasing ("the memorized documents") describes a different setting.
TEMPLATE_AGENT_NAME = "Structure_rag_recovermem"


@dataclass
class ARQuery:
    """One native MAB query attached to a source history."""

    history_id: str
    query_index: int          # position within the history, native order
    qa_pair_id: Optional[str]
    query_text: str           # MAB's templated query, verbatim
    raw_question: str
    answers: Any              # native gold answer(s), passed to the native metric unchanged

    @property
    def query_id(self) -> str:
        return f"{self.history_id}::q{self.query_index:04d}"


@dataclass
class SourceHistory:
    """One MAB context (the independent statistical unit) plus its queries."""

    source: str               # "event_qa" | "ruler_qa1" | "ruler_qa2"
    sample_index: int         # position in the upstream filtered dataset
    context: str
    chunks: list[str]
    queries: list[ARQuery]
    sub_dataset: str
    dataset: str
    context_chars: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def history_id(self) -> str:
        return f"{self.source}::h{self.sample_index:04d}"

    @property
    def n_queries(self) -> int:
        return len(self.queries)

    def context_hash(self) -> str:
        return hashlib.sha256(self.context.encode("utf-8")).hexdigest()

    def as_messages(self) -> list[dict[str, str]]:
        """The raw history H_i as chat turns -- one user turn per native chunk.

        This is the immutable object the recovery backend retrieves over, and the same
        chunk sequence the host memorizes. Building both from one list is what makes
        the two routes read the same underlying history.
        """
        return [{"role": "user", "content": c} for c in self.chunks]


def _load_config(config_path: str) -> dict[str, Any]:
    import yaml

    from recovermem.integrations.memoryagentbench.upstream import MAB_ROOT

    with open(MAB_ROOT / config_path) as fh:
        return yaml.safe_load(fh)


def load_ar_source(
    source: str,
    chunk_size: Optional[int] = None,
    max_samples: Optional[int] = None,
) -> list[SourceHistory]:
    """Load every source history for one AR source using upstream MAB code.

    ``max_samples`` overrides the YAML's ``max_test_samples``. The upstream default caps
    EventQA at 5 samples, which is a *reporting* convenience in MAB, not a property of
    the data; the structural audit needs the true population, so the cap is lifted by
    passing ``max_samples=None`` explicitly via ``load_all_ar_sources``.
    """
    if source not in AR_SOURCES:
        raise ValueError(f"unknown AR source {source!r}; expected one of {sorted(AR_SOURCES)}")

    mab = load_mab()
    spec = AR_SOURCES[source]
    cfg = _load_config(spec["config_path"])

    if cfg["dataset"] != spec["dataset"] or cfg["sub_dataset"].strip() != spec["sub_dataset"]:
        raise RuntimeError(
            f"{spec['config_path']} declares "
            f"({cfg['dataset']!r}, {cfg['sub_dataset'].strip()!r}) but the integration "
            f"expects ({spec['dataset']!r}, {spec['sub_dataset']!r}); upstream changed."
        )

    load_cfg = dict(cfg)
    load_cfg["sub_dataset"] = cfg["sub_dataset"].strip()
    load_cfg["max_test_samples"] = max_samples
    loaded = mab["load_eval_data"](load_cfg)
    items = list(loaded["data"]) if isinstance(loaded, dict) else list(loaded)

    csize = chunk_size if chunk_size is not None else int(cfg["chunk_size"])
    template = mab["get_template"](load_cfg["sub_dataset"], "query", TEMPLATE_AGENT_NAME)

    histories: list[SourceHistory] = []
    for idx, item in enumerate(items):
        context = item["context"]
        chunks = mab["chunk_text_into_sentences"](context, chunk_size=csize)
        questions = _as_list(item.get("questions"))
        answers = _as_list(item.get("answers"))
        qa_ids = _as_list((item.get("metadata") or {}).get("qa_pair_ids") or item.get("qa_pair_ids"))

        hid = f"{source}::h{idx:04d}"
        queries: list[ARQuery] = []
        paired = _pair_questions_answers(questions, answers)
        for qi, (question, answer) in enumerate(paired):
            queries.append(
                ARQuery(
                    history_id=hid,
                    query_index=qi,
                    qa_pair_id=str(qa_ids[qi]) if qi < len(qa_ids) else None,
                    query_text=template.format(question=question),
                    raw_question=question,
                    answers=answer,
                )
            )

        histories.append(
            SourceHistory(
                source=source,
                sample_index=idx,
                context=context,
                chunks=chunks,
                queries=queries,
                sub_dataset=load_cfg["sub_dataset"],
                dataset=cfg["dataset"],
                context_chars=len(context),
                metadata={
                    k: v for k, v in (item.get("metadata") or {}).items()
                    if k not in ("context",)
                },
            )
        )
    return histories


def _pair_questions_answers(questions: list, answers: list) -> list[tuple[str, Any]]:
    """Mirror MAB's ``ConversationCreator._create_query_answer_pairs`` exactly.

    Upstream treats "many questions AND many answers" as an element-wise zip and anything
    else as a single query whose gold is the whole answer list. Reproducing that branch
    rather than always zipping matters: for a single-question history the gold is the
    full list of acceptable answers, and zipping would silently keep only the first.
    """
    if len(questions) > 1 and len(answers) > 1:
        return list(zip(questions, answers))
    return [(questions[0] if questions else "", answers)]


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def load_all_ar_sources(
    chunk_size: Optional[int] = None,
    max_samples: Optional[int] = None,
) -> dict[str, list[SourceHistory]]:
    """All three AR sources, uncapped by default."""
    return {
        src: load_ar_source(src, chunk_size=chunk_size, max_samples=max_samples)
        for src in AR_SOURCES
    }


def iter_all(histories: dict[str, list[SourceHistory]]) -> Iterator[SourceHistory]:
    for src in AR_SOURCES:
        yield from histories.get(src, [])
