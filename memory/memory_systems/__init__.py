import logging

logger = logging.getLogger(__name__)


def _optional_import(module_name, class_name):
    """Import a memory backend class, returning None if its optional dependency isn't installed.

    Mirrors the pattern env/env_server.py already uses for ENV_FACTORIES: a backend we aren't
    using (e.g. paid-cloud clients like mirix/letta/mem0/zep) shouldn't prevent the server from
    starting for the backends we are using.
    """
    try:
        module = __import__(f"{__name__}.{module_name}", fromlist=[class_name])
        return getattr(module, class_name)
    except ImportError as exc:
        logger.warning("Memory backend %r unavailable (%s): %s", class_name, module_name, exc)
        return None


MirixMemorySystem = _optional_import("mirix", "MirixMemorySystem")
LongContextMemorySystem = _optional_import("long_context", "LongContextMemorySystem")
Mem0MemorySystem = _optional_import("mem0", "Mem0MemorySystem")
LettaMemorySystem = _optional_import("letta", "LettaMemorySystem")
RAGMemorySystem = _optional_import("rag", "RAGMemorySystem")
MemoRAGMemorySystem = _optional_import("memorag", "MemoRAGMemorySystem")
GraphRAGMemorySystem = _optional_import("langchain_graphrag", "GraphRAGMemorySystem")
AMemMemorySystem = _optional_import("amem", "AMemMemorySystem")
LightMemMemorySystem = _optional_import("lightmem", "LightMemMemorySystem")
ReasoningBankMemorySystem = _optional_import("reasoningbank", "ReasoningBankMemorySystem")
ZepMemorySystem = _optional_import("zep", "ZepMemorySystem")
