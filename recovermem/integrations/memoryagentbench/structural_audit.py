"""Zero-LLM structural audit of MAB-AR (brief §6).

Everything here is computed from the dataset and from upstream MAB's own code. No model
is called, no memory is built, and no route outcome is inspected -- the audit has to be
readable before any decision that could be influenced by results.

Token statistics use the EXACT served-model tokenizer (Llama-3.1-8B-Instruct), not
MemoryAgentBench's ``tiktoken.encoding_for_model("gpt-4o-mini")`` fallback. MAB's own
chunk boundaries still come from its tiktoken path, because chunking is a property of
the benchmark's streaming design rather than a ReCoverMem budget quantity; that split is
recorded explicitly below so the two counters are never confused.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path
from typing import Any

from recovermem.integrations.memoryagentbench.datasets import (
    AR_SOURCES,
    SourceHistory,
    load_ar_source,
)
from recovermem.integrations.memoryagentbench.upstream import MAB_ROOT, load_mab, mab_git_commit
from recovermem.tokens import TokenCounter

LLAMA_SNAPSHOT = (
    "/home/aristella/.cache/huggingface/hub/models--meta-llama--Llama-3.1-8B-Instruct/"
    "snapshots/0e9e39f249a16976918f6564b8830bc894c89659"
)
HF_DATASET = "ai-hyz/MemoryAgentBench"
HF_SPLIT = "Accurate_Retrieval"


def _dist(values: list[int]) -> dict[str, Any]:
    if not values:
        return {"n": 0}
    s = sorted(values)
    return {
        "n": len(s),
        "min": s[0],
        "q25": s[max(0, int(0.25 * (len(s) - 1)))],
        "median": statistics.median(s),
        "q75": s[min(len(s) - 1, int(0.75 * (len(s) - 1)))],
        "max": s[-1],
        "mean": sum(s) / len(s),
        "total": sum(s),
        "values": s,
    }


def _native_metric_path(sub_dataset: str) -> dict[str, Any]:
    """Which upstream branch of ``post_process`` scores this source, verbatim."""
    if "eventqa" in sub_dataset:
        fn = "utils.eval_other_utils._process_eventqa_dataset"
        note = (
            "parse_output() then calculate_metrics(); substring_exact_match is "
            "drqa_metric_max_over_ground_truths(substring_exact_match_score, ...). "
            "Also emits eventqa_recall, which the README does NOT use for AR accuracy."
        )
    elif "ruler" in sub_dataset:
        fn = "utils.eval_other_utils._process_ruler_memory_merging_dataset -> default_post_process"
        note = (
            "'ruler_niah' not in sub_dataset, so the branch falls through to "
            "default_post_process(): calculate_metrics() on the raw output and on "
            "parse_output(), element-wise max."
        )
    else:
        raise ValueError(f"unexpected AR sub_dataset {sub_dataset!r}")
    return {
        "post_process_branch": fn,
        "accuracy_field": "substring_exact_match",
        "definition": "normalize_answer(gold) in normalize_answer(prediction), max over gold answers",
        "llm_judge_required": False,
        "note": note,
    }


def audit(out_dir: str | Path) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    mab = load_mab()
    counter = TokenCounter(LLAMA_SNAPSHOT)
    if not counter.exact:
        raise RuntimeError(
            f"exact Llama tokenizer could not be loaded from {LLAMA_SNAPSHOT}; the audit "
            f"refuses to report heuristic token counts as measured ones"
        )

    from datasets import load_dataset

    raw = load_dataset(HF_DATASET, split=HF_SPLIT, revision="main")
    split_sources: dict[str, int] = {}
    for sample in raw:
        src = (sample.get("metadata") or {}).get("source", "")
        split_sources[src] = split_sources.get(src, 0) + 1

    per_source: dict[str, Any] = {}
    all_histories: list[SourceHistory] = []
    context_hashes: dict[str, list[str]] = {}
    qa_ids: dict[str, list[str]] = {}

    for src, spec in AR_SOURCES.items():
        histories = load_ar_source(src, max_samples=None)
        all_histories.extend(histories)

        ctx_tokens = [counter.count_text(h.context) for h in histories]
        q_counts = [h.n_queries for h in histories]
        chunk_counts = [len(h.chunks) for h in histories]
        query_tokens = [counter.count_text(q.query_text) for h in histories for q in h.queries]

        hashes = [h.context_hash() for h in histories]
        context_hashes[src] = hashes
        qa_ids[src] = [q.qa_pair_id or q.query_id for h in histories for q in h.queries]

        per_source[src] = {
            "config_path": spec["config_path"],
            "config_path_abs": str(MAB_ROOT / spec["config_path"]),
            "hf_dataset": HF_DATASET,
            "hf_split": HF_SPLIT,
            "hf_revision": "main",
            "hf_fingerprint": getattr(raw, "_fingerprint", None),
            "sub_dataset_source_filter": spec["sub_dataset"],
            "n_independent_source_histories": len(histories),
            "n_queries_total": sum(q_counts),
            "queries_per_history": _dist(q_counts),
            "context_tokens_llama_exact": _dist(ctx_tokens),
            "context_chars": _dist([h.context_chars for h in histories]),
            "native_chunks_per_history": _dist(chunk_counts),
            "templated_query_tokens_llama_exact": _dist(query_tokens),
            "identifier_fields": {
                "history_id": "synthesized: '<source>::h<sample_index>' (MAB has no native context id)",
                "qa_pair_id_present": all(q.qa_pair_id for h in histories for q in h.queries),
                "qa_pair_id_example": histories[0].queries[0].qa_pair_id if histories else None,
                "qa_pair_id_unique_within_source": len(set(qa_ids[src])) == len(qa_ids[src]),
                "native_metadata_keys": sorted((histories[0].metadata or {}).keys()) if histories else [],
            },
            "history_has_multiple_queries": any(c > 1 for c in q_counts),
            "duplicate_contexts_within_source": len(set(hashes)) != len(hashes),
            "native_metric": _native_metric_path(spec["sub_dataset"]),
        }

    # Cross-source overlap checks.
    flat_hashes = {h: [] for src in context_hashes for h in context_hashes[src]}
    for src, hs in context_hashes.items():
        for h in hs:
            flat_hashes[h].append(src)
    cross_ctx = {h: s for h, s in flat_hashes.items() if len(set(s)) > 1}

    all_qa = [i for src in qa_ids for i in qa_ids[src]]
    dup_qa = sorted({i for i in all_qa if all_qa.count(i) > 1})
    all_hids = [h.history_id for h in all_histories]

    total_hist = len(all_histories)
    total_q = sum(h.n_queries for h in all_histories)

    report = {
        "generated_by": "recovermem.integrations.memoryagentbench.structural_audit",
        "scope": "MemoryAgentBench Accurate Retrieval (MAB-AR): event_qa, ruler_qa1, ruler_qa2",
        "excluded_by_design": [
            "longmemeval_s", "longmemeval_s*", "detectiveQA", "FactConsolidation",
            "TTL/ICL", "recsys", "infbench",
        ],
        "provenance": {
            "mab_root": str(MAB_ROOT),
            "mab_commit": mab_git_commit(),
            "mem0_module_path": mab["mem0_path"],
            "tokenizer": LLAMA_SNAPSHOT,
            "tokenizer_exact": counter.exact,
            "tokenizer_class": type(counter._tok).__name__,
            "chunking_tokenizer": "upstream MAB tiktoken gpt-4o-mini (benchmark-native chunk boundaries, NOT a ReCoverMem budget quantity)",
        },
        "hf_split_composition_all_sources": split_sources,
        "per_source": per_source,
        "totals": {
            "n_independent_source_histories": total_hist,
            "n_queries": total_q,
            "queries_per_history": _dist([h.n_queries for h in all_histories]),
            "context_tokens_llama_exact": _dist(
                [counter.count_text(h.context) for h in all_histories]
            ),
            "history_ids": all_hids,
        },
        "exchangeability": {
            "independent_unit": "source history",
            "reason": (
                "MAB uses an inject-once/query-many design: every query in a history is "
                "answered from the same injected context, so queries within a history are "
                "not exchangeable with one another."
            ),
            "any_history_with_multiple_queries": any(h.n_queries > 1 for h in all_histories),
            "duplicate_history_ids": len(set(all_hids)) != len(all_hids),
            "cross_source_identical_contexts": {h: sorted(set(s)) for h, s in cross_ctx.items()},
            "cross_source_duplicate_qa_pair_ids": dup_qa,
        },
        "evaluation_semantics": {
            "queries_memorized": False,
            "model_answers_memorized": False,
            "upstream_reference": (
                "MemoryAgentBench main.py calls send_message(chunk, memorizing=True) during "
                "memory construction and send_message(query, memorizing=False) at evaluation; "
                "the memorizing=False path never writes to the host. ReCoverMem's runner "
                "reproduces that contract and asserts the host's memory count is unchanged "
                "across the query phase."
            ),
            "llm_judge_required_for_any_ar_source": False,
        },
    }

    (out / "structural_audit.json").write_text(json.dumps(report, indent=2, default=str))
    return report
