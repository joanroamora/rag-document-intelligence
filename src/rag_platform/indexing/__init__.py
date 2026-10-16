"""Module 2 — Embeddings & Vector Indexing components."""

from rag_platform.indexing.embedder import (
    BatchTransportFn,
    DeterministicHashEmbedder,
    EmbedderConfig,
    EmbeddingProvider,
    EmbeddingQuotaExceededError,
    GeminiFreeTierEmbedder,
)
from rag_platform.indexing.vector_store import (
    IndexStats,
    InMemoryMultiTenantVectorStore,
    ScoredVectorMatch,
    VectorIndexingService,
    VectorStore,
)

__all__ = [
    "BatchTransportFn",
    "DeterministicHashEmbedder",
    "EmbedderConfig",
    "EmbeddingProvider",
    "EmbeddingQuotaExceededError",
    "GeminiFreeTierEmbedder",
    "InMemoryMultiTenantVectorStore",
    "IndexStats",
    "ScoredVectorMatch",
    "VectorIndexingService",
    "VectorStore",
]
