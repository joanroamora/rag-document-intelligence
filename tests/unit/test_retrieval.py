"""Unit and integration tests for Module 3: Hybrid & Agentic Retrieval."""

import pytest

from rag_platform.contracts import (
    AgenticQueryPlan,
    ChunkRecord,
    ExtractionRoute,
    HumanReviewStatus,
    PlannedSubQuery,
    QueryBudget,
    RetrievalMode,
    TenantScope,
)
from rag_platform.indexing import (
    DeterministicHashEmbedder,
    InMemoryMultiTenantVectorStore,
    VectorIndexingService,
)
from rag_platform.retrieval import (
    AgenticRetrievalEngine,
    BM25LexicalIndex,
    HeuristicGeminiQueryPlanner,
    HybridRetriever,
    detect_exhaustive_intent,
)


def _build_retriever() -> HybridRetriever:
    """Create a fresh HybridRetriever wired with deterministic vector and BM25 stores."""
    vec_service = VectorIndexingService(
        embedder=DeterministicHashEmbedder(),
        vector_store=InMemoryMultiTenantVectorStore(),
    )
    lex_index = BM25LexicalIndex()
    return HybridRetriever(vector_service=vec_service, lexical_index=lex_index)


def _make_linked_corpus(tenant_id: str = "tenant-law") -> list[ChunkRecord]:
    """Create a 4-chunk hierarchical and neighbor-linked corpus for testing."""
    base_uri = f"gs://bucket/{tenant_id}/proj-1/doc-10/expediente.pdf"
    c1 = ChunkRecord(
        tenant_id=tenant_id,
        project_id="proj-1",
        case_id="case-1",
        document_id="doc-10",
        chunk_id="c-01",
        parent_id="sec-pagos",
        section_id="sec-pagos",
        previous_chunk_id=None,
        next_chunk_id="c-02",
        page_start=1,
        page_end=1,
        position_index=0,
        normalized_text="Sección Pagos: Pago número uno por 10,000 USD realizado en enero.",
        extraction_route=ExtractionRoute.ROUTE_A_DIGITAL_TEXT,
        extraction_quality_score=0.98,
        source_reference=base_uri,
        extraction_provider="gcp_digital_parser",
        extraction_model_version="native-1.0",
    )
    c2 = ChunkRecord(
        tenant_id=tenant_id,
        project_id="proj-1",
        case_id="case-1",
        document_id="doc-10",
        chunk_id="c-02",
        parent_id="sec-pagos",
        section_id="sec-pagos",
        previous_chunk_id="c-01",
        next_chunk_id="c-03",
        page_start=2,
        page_end=2,
        position_index=1,
        normalized_text=(
            "Pago número dos por 25,000 USD con recibo parcialmente [ilegible] en marzo."
        ),
        inferred_context_notes=["El monto podría corresponder al segundo hito de obra"],
        extraction_route=ExtractionRoute.ROUTE_D_GEMINI_FLASH,
        extraction_quality_score=0.84,
        source_reference=base_uri,
        extraction_provider="gemini_api",
        extraction_model_version="gemini-2.5-flash",
        transcription_uncertainty=0.25,
        human_review_status=HumanReviewStatus.PENDING_REVIEW,
    )
    c3 = ChunkRecord(
        tenant_id=tenant_id,
        project_id="proj-1",
        case_id="case-1",
        document_id="doc-10",
        chunk_id="c-03",
        parent_id="sec-pagos",
        section_id="sec-pagos",
        previous_chunk_id="c-02",
        next_chunk_id="c-04",
        page_start=3,
        page_end=3,
        position_index=2,
        normalized_text="Pago número tres por 40,000 USD liquidado en junio sin observaciones.",
        extraction_route=ExtractionRoute.ROUTE_A_DIGITAL_TEXT,
        extraction_quality_score=0.97,
        source_reference=base_uri,
        extraction_provider="gcp_digital_parser",
        extraction_model_version="native-1.0",
    )
    c4 = ChunkRecord(
        tenant_id=tenant_id,
        project_id="proj-1",
        case_id="case-1",
        document_id="doc-10",
        chunk_id="c-04",
        parent_id="sec-confidencialidad",
        section_id="sec-confidencialidad",
        previous_chunk_id="c-03",
        next_chunk_id=None,
        page_start=4,
        page_end=4,
        position_index=3,
        normalized_text="Cláusula de confidencialidad: reserva estricta durante cinco años.",
        extraction_route=ExtractionRoute.ROUTE_A_DIGITAL_TEXT,
        extraction_quality_score=0.99,
        source_reference=base_uri,
        extraction_provider="gcp_digital_parser",
        extraction_model_version="native-1.0",
    )
    return [c1, c2, c3, c4]


def test_bm25_lexical_search_and_tenant_isolation() -> None:
    """Verify BM25 ranking, tenant isolation before scoring, and document deletion."""
    retriever = _build_retriever()
    retriever.index_corpus(_make_linked_corpus(tenant_id="tenant-law"))
    retriever.index_corpus(_make_linked_corpus(tenant_id="tenant-other"))

    scope_law = TenantScope(tenant_id="tenant-law", project_id="proj-1")
    hits = retriever.lexical_index.search("cláusula confidencialidad reserva", scope=scope_law)

    assert len(hits) == 1
    assert hits[0].chunk.chunk_id == "c-04"
    assert hits[0].chunk.tenant_id == "tenant-law"
    assert hits[0].bm25_score > 0.0

    # Deleting doc-10 under tenant-other must not affect tenant-law
    scope_other = TenantScope(tenant_id="tenant-other", project_id="proj-1")
    removed = retriever.lexical_index.delete_document(scope_other, "doc-10")
    assert removed == 4
    assert len(retriever.lexical_index.search("confidencialidad", scope=scope_other)) == 0
    assert len(retriever.lexical_index.search("confidencialidad", scope=scope_law)) == 1


def test_hybrid_retrieval_rrf_context_expansion_and_epistemic_safety() -> None:
    """Verify RRF fusion, neighbor/section expansion, and epistemic note segregation."""
    retriever = _build_retriever()
    retriever.index_corpus(_make_linked_corpus())
    scope = TenantScope(tenant_id="tenant-law", project_id="proj-1")

    result = retriever.retrieve(
        query_text="recibo parcialmente ilegible en marzo pago dos",
        scope=scope,
        top_k=2,
    )

    assert result.is_evidence_sufficient is True
    assert result.mode == RetrievalMode.STANDARD_HYBRID
    top_item = result.items[0]
    assert top_item.primary_chunk.chunk_id == "c-02"
    assert top_item.citation.has_uncertainty is True
    assert top_item.citation.human_review_status == HumanReviewStatus.PENDING_REVIEW

    # Verify Hierarchical Context Expansion (neighbors and section peers)
    assert top_item.previous_neighbor is not None
    assert top_item.previous_neighbor.chunk_id == "c-01"
    assert top_item.next_neighbor is not None
    assert top_item.next_neighbor.chunk_id == "c-03"
    assert [p.chunk_id for p in top_item.section_peers] == ["c-01", "c-03"]

    # Epistemological safety: inferred hypothesis is segregated in rendered context
    rendered = top_item.render_expanded_context()
    assert "[EVIDENCIA PRINCIPAL (c-02, p.2-2)]" in rendered
    assert "[CONTEXTO ANTERIOR (c-01)]" in rendered
    assert "[CONTEXTO SIGUIENTE (c-03)]" in rendered
    assert "[HIPÓTESIS INFERIDA - NO ES TRANSCRIPCIÓN CIERTA]" in rendered
    assert "segundo hito de obra" not in top_item.citation.observed_excerpt


def test_agentic_retrieval_decomposition_exhaustive_scan_and_scope_lock() -> None:
    """Verify multi-subquery decomposition, exhaustive scan override, and privilege lock."""
    assert detect_exhaustive_intent("Listar todos los pagos del expediente") is True
    assert detect_exhaustive_intent("¿Cuál es la fecha del contrato?") is False

    retriever = _build_retriever()
    retriever.index_corpus(_make_linked_corpus())
    engine = AgenticRetrievalEngine(
        hybrid_retriever=retriever,
        planner=HeuristicGeminiQueryPlanner(),
    )
    scope = TenantScope(tenant_id="tenant-law", project_id="proj-1")

    # Even with top_k_per_subquery=1, exhaustive intent on 'cada pago' must scan all 3
    agentic_res = engine.retrieve(
        question=(
            "¿Cuál es la cláusula de confidencialidad y además "
            "listar cada pago del expediente?"
        ),
        authorized_scope=scope,
        top_k_per_subquery=1,
    )

    assert agentic_res.executed_subqueries == 2
    assert agentic_res.retrieval_result.mode == RetrievalMode.DEEP_AGENTIC
    assert agentic_res.retrieval_result.is_exhaustive_scan is True
    assert agentic_res.retrieval_result.is_evidence_sufficient is True

    retrieved_ids = {it.primary_chunk.chunk_id for it in agentic_res.retrieval_result.items}
    assert {"c-01", "c-02", "c-03", "c-04"}.issubset(retrieved_ids)

    # Security check: Tampering with plan's authorized_scope must raise PermissionError
    tampered_plan = AgenticQueryPlan(
        original_question="todos los pagos",
        authorized_scope=TenantScope(tenant_id="tenant-hacker", project_id="proj-1"),
        subqueries=[PlannedSubQuery(subquery_id="sq-1", query_text="pagos")],
    )
    with pytest.raises(PermissionError, match="Security violation"):
        engine.execute_plan(plan=tampered_plan, authorized_scope=scope)


def test_agentic_retrieval_insufficient_evidence_reporting() -> None:
    """Verify that unmatched queries report insufficient evidence without fabrication."""
    retriever = _build_retriever()
    retriever.index_corpus(_make_linked_corpus())
    engine = AgenticRetrievalEngine(hybrid_retriever=retriever)
    scope = TenantScope(tenant_id="tenant-law", project_id="proj-1")

    empty_res = engine.retrieve(
        question="¿Existe algún dictamen balístico o peritaje médico forense?",
        authorized_scope=scope,
        budget=QueryBudget(max_subqueries=2),
    )

    assert empty_res.retrieval_result.is_evidence_sufficient is False
    assert empty_res.retrieval_result.items == []
    assert empty_res.retrieval_result.insufficiency_reason is not None
