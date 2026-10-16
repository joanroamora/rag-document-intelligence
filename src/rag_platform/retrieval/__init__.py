"""Module 3 — Hybrid & Agentic Retrieval components."""

from rag_platform.retrieval.agentic_retriever import (
    AgenticRetrievalEngine,
    AgenticRetrievalResult,
    HeuristicGeminiQueryPlanner,
    QueryPlanner,
    SubQueryGeneratorFn,
    detect_exhaustive_intent,
)
from rag_platform.retrieval.hybrid_retriever import (
    ExpandedEvidenceItem,
    HybridRetrievalResult,
    HybridRetriever,
    HybridRetrieverConfig,
)
from rag_platform.retrieval.lexical_bm25 import (
    BM25LexicalIndex,
    ScoredLexicalMatch,
    tokenize_for_bm25,
)

__all__ = [
    "AgenticRetrievalEngine",
    "AgenticRetrievalResult",
    "BM25LexicalIndex",
    "ExpandedEvidenceItem",
    "HeuristicGeminiQueryPlanner",
    "HybridRetrievalResult",
    "HybridRetriever",
    "HybridRetrieverConfig",
    "QueryPlanner",
    "ScoredLexicalMatch",
    "SubQueryGeneratorFn",
    "detect_exhaustive_intent",
    "tokenize_for_bm25",
]
