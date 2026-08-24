"""
Oracle searcher: ignores the query and always returns the episode's known
gold_docs + evidence_docs, regardless of what the agent asks for.

Not a real retriever — this exists only to answer one diagnostic question:
can the backbone model do this task at all when retrieval is not the
bottleneck? Every other part of the pipeline (model, agent loop, memory
backend, prompts, context window) stays exactly as in the BM25 run.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from .base import BaseSearcher

logger = logging.getLogger(__name__)


class OracleSearcher(BaseSearcher):
    @classmethod
    def parse_args(cls, parser):
        parser.add_argument(
            "--index-path",
            required=True,
            help="Path to a JSON file: a list of {docid, text} objects (this episode's gold_docs + evidence_docs).",
        )

    def __init__(self, args):
        if not args.index_path:
            raise ValueError("index_path is required for oracle searcher")

        with open(args.index_path, "r", encoding="utf-8") as f:
            self.docs: List[Dict[str, Any]] = json.load(f)

        logger.info(f"Oracle searcher initialized with {len(self.docs)} known-relevant docs")

    def search(self, query: str, k: int = 10, allowed_docids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        # Query is ignored by design: the oracle always hands back the same
        # known-relevant document set, up to k of them.
        results = []
        for doc in self.docs[:k]:
            results.append({"docid": str(doc["docid"]), "score": 1.0, "text": doc.get("text", "")})
        return results

    def get_document(self, docid: str) -> Optional[Dict[str, Any]]:
        for doc in self.docs:
            if str(doc["docid"]) == str(docid):
                return {"docid": str(docid), "text": doc.get("text", "")}
        return None

    @property
    def search_type(self) -> str:
        return "ORACLE"
