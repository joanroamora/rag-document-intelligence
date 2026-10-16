"""Module 3.1: Hybrid Retrieval (Vector + BM25 + RRF + Reranking + Context Expansion)."""

from collections.abc import Sequence

from pydantic import BaseModel, Field

from rag_platform.contracts import (
    ChunkRecord,
    EvidenceCitation,
    RetrievalMode,
    TenantScope,
)
from rag_platform.indexing import VectorIndexingService
from rag_platform.retrieval.lexical_bm25 import BM25LexicalIndex, tokenize_for_bm25


class ExpandedEvidenceItem(BaseModel):
    """Retrieved evidence unit with verifiable citation and expanded hierarchical context."""

    citation: EvidenceCitation
    primary_chunk: ChunkRecord
    previous_neighbor: ChunkRecord | None = None
    next_neighbor: ChunkRecord | None = None
    section_peers: list[ChunkRecord] = Field(default_factory=list)
    inferred_context_notes: list[str] = Field(
        default_factory=list,
        description="Segregated contextual hypotheses; never merged into observed transcription",
    )

    def render_expanded_context(self) -> str:
        """Format observed text, adjacent neighbors, and segregated hypotheses for Module 4."""
        parts: list[str] = []
        if self.previous_neighbor is not None:
            parts.append(
                f"[CONTEXTO ANTERIOR ({self.previous_neighbor.chunk_id})]: "
                f"{self.previous_neighbor.normalized_text}"
            )

        parts.append(
            f"[EVIDENCIA PRINCIPAL ({self.primary_chunk.chunk_id}, "
            f"p.{self.primary_chunk.page_start}-{self.primary_chunk.page_end})]: "
            f"{self.primary_chunk.normalized_text}"
        )

        if self.next_neighbor is not None:
            parts.append(
                f"[CONTEXTO SIGUIENTE ({self.next_neighbor.chunk_id})]: "
                f"{self.next_neighbor.normalized_text}"
            )

        if self.inferred_context_notes:
            notes_str = "; ".join(self.inferred_context_notes)
            parts.append(
                f"[HIPÓTESIS INFERIDA - NO ES TRANSCRIPCIÓN CIERTA]: {notes_str}"
            )

        return "\n".join(parts)


class HybridRetrievalResult(BaseModel):
    """Structured output of Hybrid or Agentic Retrieval with sufficiency diagnostics."""

    query: str = Field(..., min_length=1)
    mode: RetrievalMode = Field(default=RetrievalMode.STANDARD_HYBRID)
    scope: TenantScope
    items: list[ExpandedEvidenceItem] = Field(default_factory=list)
    is_exhaustive_scan: bool = Field(default=False)
    is_evidence_sufficient: bool = Field(default=False)
    insufficiency_reason: str | None = Field(default=None)


class HybridRetrieverConfig(BaseModel):
    """Tunable parameters for RRF fusion, reranking threshold, and context expansion."""

    rrf_k: int = Field(default=60, ge=1, le=500)
    default_top_k: int = Field(default=5, ge=1, le=100)
    exhaustive_vector_limit: int = Field(default=200, ge=10, le=2000)
    min_vector_similarity: float = Field(default=0.35, ge=0.0, le=1.0)
    min_rerank_score: float = Field(default=0.15, ge=0.0, le=1.0)
    expand_neighbors: bool = Field(default=True)
    expand_section: bool = Field(default=True)


class HybridRetriever:
    """Standard Mode Hybrid Retriever combining Vector Search, BM25, RRF, and Context Expansion."""

    def __init__(
        self,
        vector_service: VectorIndexingService,
        lexical_index: BM25LexicalIndex,
        config: HybridRetrieverConfig | None = None,
    ) -> None:
        self.vector_service = vector_service
        self.lexical_index = lexical_index
        self.config = config or HybridRetrieverConfig()

    def index_corpus(self, chunks: Sequence[ChunkRecord]) -> int:
        """Incrementally index chunks into both VectorStore and BM25LexicalIndex."""
        if not chunks:
            return 0
        self.vector_service.index_chunks(chunks)
        return self.lexical_index.upsert(chunks)

    def retrieve(
        self,
        query_text: str,
        scope: TenantScope,
        top_k: int | None = None,
        exhaustive: bool = False,
    ) -> HybridRetrievalResult:
        """Execute pre-filtered Hybrid Retrieval with RRF, reranking, and Context Expansion."""
        if not query_text or not query_text.strip():
            raise ValueError("query_text cannot be empty")

        effective_top_k = top_k or self.config.default_top_k
        vec_limit = (
            self.config.exhaustive_vector_limit
            if exhaustive
            else max(effective_top_k * 2, 10)
        )
        lex_limit = None if exhaustive else max(effective_top_k * 2, 10)

        vector_hits = self.vector_service.search_by_text(
            query_text=query_text,
            scope=scope,
            top_k=vec_limit,
        )
        lexical_hits = self.lexical_index.search(
            query_text=query_text,
            scope=scope,
            top_k=lex_limit,
        )

        # Reciprocal Rank Fusion (RRF) + candidate registry
        rrf_scores: dict[str, float] = {}
        vec_sim_by_id: dict[str, float] = {}
        chunks_by_id: dict[str, ChunkRecord] = {}
        k_const = self.config.rrf_k

        for rank_idx, v_hit in enumerate(vector_hits, start=1):
            cid = v_hit.chunk.chunk_id
            chunks_by_id[cid] = v_hit.chunk
            vec_sim_by_id[cid] = max(0.0, v_hit.similarity_score)
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (k_const + rank_idx))

        for rank_idx, l_hit in enumerate(lexical_hits, start=1):
            cid = l_hit.chunk.chunk_id
            chunks_by_id[cid] = l_hit.chunk
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (k_const + rank_idx))

        if not chunks_by_id:
            return HybridRetrievalResult(
                query=query_text,
                mode=RetrievalMode.STANDARD_HYBRID,
                scope=scope,
                items=[],
                is_exhaustive_scan=exhaustive,
                is_evidence_sufficient=False,
                insufficiency_reason="No matching documents found within authorized tenant scope.",
            )

        # Reranking: combine query term coverage, positive vector similarity, and quality score
        query_terms = set(tokenize_for_bm25(query_text))
        scored_candidates: list[tuple[str, float, float]] = []

        for cid, chunk in chunks_by_id.items():
            chunk_terms = set(tokenize_for_bm25(chunk.normalized_text))
            term_overlap = (
                len(query_terms & chunk_terms) / len(query_terms)
                if query_terms
                else 0.0
            )
            vec_sim = vec_sim_by_id.get(cid, 0.0)
            if term_overlap == 0.0 and vec_sim < self.config.min_vector_similarity:
                continue
            rerank_score = round(
                (0.55 * term_overlap)
                + (0.35 * vec_sim)
                + (0.10 * chunk.extraction_quality_score),
                6,
            )
            if rerank_score >= self.config.min_rerank_score:
                scored_candidates.append((cid, rrf_scores[cid], rerank_score))

        # Sort by rerank_score descending, then rrf_score descending, then chunk_id ascending
        scored_candidates.sort(key=lambda item: (-item[2], -item[1], item[0]))
        if not exhaustive:
            scored_candidates = scored_candidates[:effective_top_k]

        expanded_items: list[ExpandedEvidenceItem] = []
        for cid, rrf_val, rerank_val in scored_candidates:
            primary = chunks_by_id[cid]
            expanded_items.append(
                self._expand_and_cite(
                    primary=primary,
                    scope=scope,
                    rrf_score=round(rrf_val, 6),
                    rerank_score=rerank_val,
                )
            )

        if not expanded_items:
            return HybridRetrievalResult(
                query=query_text,
                mode=RetrievalMode.STANDARD_HYBRID,
                scope=scope,
                items=[],
                is_exhaustive_scan=exhaustive,
                is_evidence_sufficient=False,
                insufficiency_reason="Candidates fell below minimum relevance threshold.",
            )

        return HybridRetrievalResult(
            query=query_text,
            mode=RetrievalMode.STANDARD_HYBRID,
            scope=scope,
            items=expanded_items,
            is_exhaustive_scan=exhaustive,
            is_evidence_sufficient=True,
            insufficiency_reason=None,
        )

    def _expand_and_cite(
        self,
        *,
        primary: ChunkRecord,
        scope: TenantScope,
        rrf_score: float,
        rerank_score: float,
    ) -> ExpandedEvidenceItem:
        """Resolve neighbor and section chunks within TenantScope and build EvidenceCitation."""
        prev_chunk: ChunkRecord | None = None
        next_chunk: ChunkRecord | None = None
        section_peers: list[ChunkRecord] = []

        if self.config.expand_neighbors:
            if primary.previous_chunk_id:
                prev_chunk = self.lexical_index.get_chunk(scope, primary.previous_chunk_id)
            if primary.next_chunk_id:
                next_chunk = self.lexical_index.get_chunk(scope, primary.next_chunk_id)

        if self.config.expand_section and primary.section_id:
            all_peers = self.lexical_index.get_section_chunks(
                scope=scope,
                document_id=primary.document_id,
                section_id=primary.section_id,
            )
            section_peers = [c for c in all_peers if c.chunk_id != primary.chunk_id]

        has_uncertainty = (
            primary.transcription_uncertainty > 0.0
            or "[ilegible]" in primary.normalized_text.lower()
        )
        citation = EvidenceCitation(
            chunk_id=primary.chunk_id,
            document_id=primary.document_id,
            page_start=primary.page_start,
            page_end=primary.page_end,
            source_reference=primary.source_reference,
            observed_excerpt=primary.normalized_text,
            has_uncertainty=has_uncertainty,
            human_review_status=primary.human_review_status,
            rrf_score=rrf_score,
            rerank_score=rerank_score,
        )

        return ExpandedEvidenceItem(
            citation=citation,
            primary_chunk=primary,
            previous_neighbor=prev_chunk,
            next_neighbor=next_chunk,
            section_peers=section_peers,
            inferred_context_notes=list(primary.inferred_context_notes),
        )
