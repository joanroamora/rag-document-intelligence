"""Module 2: Multi-tenant Vector Store abstraction, compatibility guards, and indexing service."""

import math
from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel, Field

from rag_platform.contracts import (
    ChunkRecord,
    EmbeddingSpaceSignature,
    EmbeddingTaskType,
    TenantScope,
    VectorIndexRecord,
    assert_embedding_compatibility,
)
from rag_platform.indexing.embedder import EmbeddingProvider


class ScoredVectorMatch(BaseModel):
    """Vector search hit pairing the indexed record, original chunk, and similarity score."""

    record: VectorIndexRecord
    chunk: ChunkRecord
    similarity_score: float = Field(..., ge=-1.0, le=1.0)


class IndexStats(BaseModel):
    """Diagnostic snapshot of the vector index state and per-tenant distribution."""

    total_indexed_chunks: int = Field(..., ge=0)
    space_signature: EmbeddingSpaceSignature | None = None
    tenant_counts: dict[str, int] = Field(default_factory=dict)


class VectorStore(Protocol):
    """Pluggable interface for vector stores (Qdrant, ChromaDB, or InMemory)."""

    def upsert(
        self,
        records: Sequence[VectorIndexRecord],
        chunks: Sequence[ChunkRecord],
    ) -> int:
        """Incrementally and idempotently index chunk vectors."""
        ...

    def search(
        self,
        query_vector: Sequence[float],
        query_signature: EmbeddingSpaceSignature,
        scope: TenantScope,
        top_k: int = 5,
    ) -> list[ScoredVectorMatch]:
        """Execute pre-filtered multi-tenant vector similarity search."""
        ...

    def delete_document(self, scope: TenantScope, document_id: str) -> int:
        """Remove all indexed chunks belonging to a specific document within a tenant scope."""
        ...

    def rebuild(
        self,
        records: Sequence[VectorIndexRecord],
        chunks: Sequence[ChunkRecord],
    ) -> int:
        """Clear and reconstruct the entire index from canonical chunks and vectors."""
        ...

    def get_stats(self) -> IndexStats:
        """Return index statistics and current embedding space signature."""
        ...


def _cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    """Compute bounded cosine similarity in [-1.0, 1.0] between two equal-length vectors."""
    if len(vec_a) != len(vec_b):
        raise ValueError(
            f"Vector dimension mismatch: {len(vec_a)} vs {len(vec_b)}"
        )
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=True))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    raw = dot / (norm_a * norm_b)
    return max(-1.0, min(1.0, round(raw, 6)))


class InMemoryMultiTenantVectorStore:
    """Deterministic multi-tenant vector store enforcing compatibility and pre-filtering."""

    def __init__(self, expected_signature: EmbeddingSpaceSignature | None = None) -> None:
        self._signature: EmbeddingSpaceSignature | None = expected_signature
        # Keyed by (tenant_id, project_id, chunk_id) for idempotent incremental updates
        self._entries: dict[tuple[str, str, str], tuple[VectorIndexRecord, ChunkRecord]] = {}

    def upsert(
        self,
        records: Sequence[VectorIndexRecord],
        chunks: Sequence[ChunkRecord],
    ) -> int:
        """Idempotently insert or update records after validating embedding compatibility."""
        if len(records) != len(chunks):
            raise ValueError(
                f"Records count ({len(records)}) must match chunks count ({len(chunks)})"
            )
        if not records:
            return 0

        for record, chunk in zip(records, chunks, strict=True):
            if record.chunk_id != chunk.chunk_id:
                raise ValueError(
                    f"Mismatched chunk_id between VectorIndexRecord ({record.chunk_id}) "
                    f"and ChunkRecord ({chunk.chunk_id})"
                )
            if (
                record.tenant_id != chunk.tenant_id
                or record.project_id != chunk.project_id
                or record.document_id != chunk.document_id
            ):
                raise ValueError(
                    f"Tenant/document metadata mismatch on chunk {chunk.chunk_id}"
                )

            if self._signature is None:
                self._signature = record.space_signature
            else:
                assert_embedding_compatibility(record.space_signature, self._signature)

            key = (record.tenant_id, record.project_id, record.chunk_id)
            self._entries[key] = (record, chunk)

        return len(records)

    def search(
        self,
        query_vector: Sequence[float],
        query_signature: EmbeddingSpaceSignature,
        scope: TenantScope,
        top_k: int = 5,
    ) -> list[ScoredVectorMatch]:
        """Filter by TenantScope BEFORE vector scoring and enforce embedding compatibility."""
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        if self._signature is not None:
            assert_embedding_compatibility(query_signature, self._signature)

        if len(query_vector) != query_signature.embedding_dimension:
            raise ValueError(
                f"Query vector length ({len(query_vector)}) does not match "
                f"query_signature dimension ({query_signature.embedding_dimension})"
            )

        matches: list[ScoredVectorMatch] = []

        # Invariant #3: Apply strict multi-tenant pre-filtering before computing similarity
        for record, chunk in self._entries.values():
            if not scope.matches_filter(
                tenant_id=record.tenant_id,
                project_id=record.project_id,
                case_id=record.case_id,
                document_id=record.document_id,
            ):
                continue

            score = _cosine_similarity(query_vector, record.vector)
            matches.append(
                ScoredVectorMatch(
                    record=record,
                    chunk=chunk,
                    similarity_score=score,
                )
            )

        # Deterministic ordering: descending similarity score, then ascending chunk_id
        matches.sort(key=lambda m: (-m.similarity_score, m.record.chunk_id))
        return matches[:top_k]

    def delete_document(self, scope: TenantScope, document_id: str) -> int:
        """Delete all indexed entries for a document strictly within the authorized TenantScope."""
        keys_to_delete = [
            key
            for key, (record, _chunk) in self._entries.items()
            if record.document_id == document_id
            and scope.matches_filter(
                tenant_id=record.tenant_id,
                project_id=record.project_id,
                case_id=record.case_id,
                document_id=record.document_id,
            )
        ]
        for key in keys_to_delete:
            del self._entries[key]
        return len(keys_to_delete)

    def rebuild(
        self,
        records: Sequence[VectorIndexRecord],
        chunks: Sequence[ChunkRecord],
    ) -> int:
        """Clear existing index and rebuild from scratch with the provided corpus."""
        self._entries.clear()
        self._signature = None
        return self.upsert(records, chunks)

    def get_stats(self) -> IndexStats:
        """Compute current index statistics and per-tenant chunk counts."""
        tenant_counts: dict[str, int] = {}
        for record, _chunk in self._entries.values():
            tenant_counts[record.tenant_id] = tenant_counts.get(record.tenant_id, 0) + 1

        return IndexStats(
            total_indexed_chunks=len(self._entries),
            space_signature=self._signature,
            tenant_counts=tenant_counts,
        )


class VectorIndexingService:
    """Module 2 orchestrator linking EmbeddingProvider with a multi-tenant VectorStore."""

    def __init__(
        self,
        embedder: EmbeddingProvider,
        vector_store: VectorStore,
    ) -> None:
        self.embedder = embedder
        self.vector_store = vector_store

    def build_index_records(
        self,
        chunks: Sequence[ChunkRecord],
    ) -> list[VectorIndexRecord]:
        """Vectorize chunks and construct validated VectorIndexRecord objects."""
        if not chunks:
            return []

        base_sig = self.embedder.get_space_signature()
        texts = [chunk.normalized_text for chunk in chunks]
        vectors = self.embedder.embed_texts(
            texts,
            task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
        )

        records: list[VectorIndexRecord] = []
        for chunk, vec in zip(chunks, vectors, strict=True):
            chunk_sig = EmbeddingSpaceSignature(
                embedding_provider=base_sig.embedding_provider,
                embedding_model=base_sig.embedding_model,
                embedding_model_version=base_sig.embedding_model_version,
                embedding_dimension=base_sig.embedding_dimension,
                chunking_version=chunk.chunking_version,
            )
            records.append(
                VectorIndexRecord(
                    chunk_id=chunk.chunk_id,
                    tenant_id=chunk.tenant_id,
                    project_id=chunk.project_id,
                    case_id=chunk.case_id,
                    document_id=chunk.document_id,
                    vector=vec,
                    space_signature=chunk_sig,
                )
            )
        return records

    def index_chunks(self, chunks: Sequence[ChunkRecord]) -> list[VectorIndexRecord]:
        """Incrementally vectorize and index a batch of chunks into the VectorStore."""
        records = self.build_index_records(chunks)
        self.vector_store.upsert(records, chunks)
        return records

    def rebuild_index(self, chunks: Sequence[ChunkRecord]) -> list[VectorIndexRecord]:
        """Re-vectorize and reconstruct the entire VectorStore from the canonical Chunk Corpus."""
        records = self.build_index_records(chunks)
        self.vector_store.rebuild(records, chunks)
        return records

    def search_by_text(
        self,
        query_text: str,
        scope: TenantScope,
        top_k: int = 5,
        query_embedder: EmbeddingProvider | None = None,
    ) -> list[ScoredVectorMatch]:
        """Vectorize a user query with RETRIEVAL_QUERY role and search within TenantScope."""
        active_embedder = query_embedder or self.embedder
        query_sig = active_embedder.get_space_signature()
        query_vectors = active_embedder.embed_texts(
            [query_text],
            task_type=EmbeddingTaskType.RETRIEVAL_QUERY,
        )
        return self.vector_store.search(
            query_vector=query_vectors[0],
            query_signature=query_sig,
            scope=scope,
            top_k=top_k,
        )
