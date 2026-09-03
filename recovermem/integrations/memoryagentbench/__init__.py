"""MemoryAgentBench Accurate Retrieval (MAB-AR) integration.

Scope is exactly the three Accurate Retrieval sources named in the paper:
EventQA, RULER QA1, RULER QA2. MemoryAgentBench's own LongMemEval category is
deliberately excluded -- the paper evaluates LongMemEval-V2 separately, and including
the older copy here would create source overlap between two reported settings.

The independent statistical unit is a SOURCE HISTORY (one MAB context with all of its
queries), not a query: MAB's "inject once, query many times" design means queries from
one history are not exchangeable with each other.
"""

from recovermem.integrations.memoryagentbench.datasets import (
    AR_SOURCES,
    SourceHistory,
    load_ar_source,
    load_all_ar_sources,
)

__all__ = ["AR_SOURCES", "SourceHistory", "load_ar_source", "load_all_ar_sources"]
