"""Unit tests for canonical RAG platform contracts and architectural invariants."""

import pytest
from pydantic import ValidationError

from rag_platform.contracts import (
    AgenticQueryPlan,
    BoundingBox,
    ChunkRecord,
    EmbeddingIncompatibilityError,
    EmbeddingSpaceSignature,
    EpistemicSpan,
    EpistemicStatus,
    ExtractionRoute,
    HumanReviewStatus,
    PlannedSubQuery,
    QueryBudget,
    TenantScope,
    UsageMode,
    VectorIndexRecord,
    assert_embedding_compatibility,
)


def test_tenant_scope_filters_and_quick_rag_ttl() -> None:
    """Verify multi-tenant filter generation and mandatory TTL on Quick RAG."""
    scope = TenantScope(
        tenant_id="tenant-alpha",
        project_id="proj-litigation",
        case_id="case-001",
    )
    assert scope.to_metadata_filter() == {
        "tenant_id": "tenant-alpha",
        "project_id": "proj-litigation",
        "case_id": "case-001",
    }

    with pytest.raises(ValidationError, match="ttl_seconds is mandatory"):
        TenantScope(
            tenant_id="tenant-alpha",
            project_id="proj-litigation",
            usage_mode=UsageMode.QUICK_RAG,
        )

    quick_scope = TenantScope(
        tenant_id="tenant-alpha",
        project_id="proj-litigation",
        usage_mode=UsageMode.QUICK_RAG,
        ttl_seconds=3600,
    )
    assert quick_scope.ttl_seconds == 3600


def test_epistemic_safety_invariants() -> None:
    """Verify epistemological separation between observed text, hypotheses, and illegible spans."""
    observed = EpistemicSpan(
        text="Contrato firmado el 12 de mayo de 1998",
        status=EpistemicStatus.OBSERVED,
    )
    assert observed.can_be_cited_as_fact is True

    # Inferred hypothesis without rationale must fail
    with pytest.raises(ValidationError, match="rationale is mandatory"):
        EpistemicSpan(
            text="1998",
            status=EpistemicStatus.INFERRED_HYPOTHESIS,
        )

    hypothesis = EpistemicSpan(
        text="1998",
        status=EpistemicStatus.INFERRED_HYPOTHESIS,
        confidence=0.65,
        rationale="Deduced from adjacent stamp date on page 2",
    )
    assert hypothesis.can_be_cited_as_fact is False

    # Illegible marker must be explicit
    with pytest.raises(ValidationError, match="Illegible spans must use"):
        EpistemicSpan(text="guessed word", status=EpistemicStatus.ILLEGIBLE)

    illegible = EpistemicSpan(text="[ilegible]", status=EpistemicStatus.ILLEGIBLE, confidence=0.0)
    assert illegible.can_be_cited_as_fact is False


def test_chunk_record_uncertainty_and_hierarchy() -> None:
    """Verify ChunkRecord requires human review when transcription uncertainty > 0.5."""
    with pytest.raises(ValidationError, match="human review"):
        ChunkRecord(
            tenant_id="tenant-1",
            project_id="proj-1",
            document_id="doc-1",
            chunk_id="chunk-001",
            page_start=1,
            page_end=1,
            position_index=0,
            normalized_text="Texto parcialmente deteriorado [ilegible]",
            extraction_route=ExtractionRoute.ROUTE_D_GEMINI_FLASH,
            extraction_quality_score=0.45,
            source_reference="gs://rag-dev-bucket/tenant-1/doc-1.pdf",
            extraction_provider="gemini_api",
            extraction_model_version="gemini-2.5-flash",
            transcription_uncertainty=0.75,
            human_review_status=HumanReviewStatus.NOT_REQUIRED,
        )

    valid_chunk = ChunkRecord(
        tenant_id="tenant-1",
        project_id="proj-1",
        document_id="doc-1",
        chunk_id="chunk-001",
        parent_id="sec-01",
        page_start=1,
        page_end=2,
        position_index=0,
        bounding_box=BoundingBox(x0=0.1, y0=0.1, x1=0.9, y1=0.8),
        normalized_text="Cláusula Primera: Objeto del contrato.",
        inferred_context_notes=["Posible referencia al anexo B"],
        extraction_route=ExtractionRoute.ROUTE_A_DIGITAL_TEXT,
        extraction_quality_score=0.98,
        source_reference="gs://rag-dev-bucket/tenant-1/doc-1.pdf",
        extraction_provider="gcp_pdf_extractor",
        extraction_model_version="1.0.0",
        transcription_uncertainty=0.02,
    )
    assert valid_chunk.chunk_id == "chunk-001"


def test_embedding_space_compatibility() -> None:
    """Verify query and index embedding space compatibility invariant."""
    index_sig = EmbeddingSpaceSignature(
        embedding_provider="gemini_api",
        embedding_model="text-embedding-004",
        embedding_model_version="v1",
        embedding_dimension=3,
        chunking_version="1.0.0",
    )
    compatible_query_sig = EmbeddingSpaceSignature(
        embedding_provider="gemini_api",
        embedding_model="text-embedding-004",
        embedding_model_version="v1",
        embedding_dimension=3,
        chunking_version="1.0.0",
    )
    assert_embedding_compatibility(compatible_query_sig, index_sig)

    incompatible_query_sig = EmbeddingSpaceSignature(
        embedding_provider="open_source_cpu",
        embedding_model="bge-m3",
        embedding_model_version="v1",
        embedding_dimension=3,
        chunking_version="1.0.0",
    )
    with pytest.raises(EmbeddingIncompatibilityError, match="Incompatible embedding spaces"):
        assert_embedding_compatibility(incompatible_query_sig, index_sig)

    record = VectorIndexRecord(
        chunk_id="chunk-001",
        tenant_id="tenant-1",
        project_id="proj-1",
        document_id="doc-1",
        vector=[0.12, -0.45, 0.88],
        space_signature=index_sig,
    )
    assert len(record.vector) == 3


def test_agentic_query_plan_budget_enforcement() -> None:
    """Verify AgenticQueryPlan rejects subquery lists exceeding QueryBudget."""
    scope = TenantScope(tenant_id="tenant-1", project_id="proj-1")
    budget = QueryBudget(max_subqueries=2)

    with pytest.raises(ValidationError, match="exceeds budget.max_subqueries"):
        AgenticQueryPlan(
            original_question="Comparar pagos de todos los expedientes entre 1995 y 2005",
            authorized_scope=scope,
            budget=budget,
            subqueries=[
                PlannedSubQuery(subquery_id="sq-1", query_text="pagos 1995"),
                PlannedSubQuery(subquery_id="sq-2", query_text="pagos 2000"),
                PlannedSubQuery(subquery_id="sq-3", query_text="pagos 2005"),
            ],
        )
