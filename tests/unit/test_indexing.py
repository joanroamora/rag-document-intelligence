"""Unit and integration tests for Module 2: Embeddings & Vector Indexing."""

import pytest
from pydantic import ValidationError

from rag_platform.contracts import (
    ChunkRecord,
    EmbeddingIncompatibilityError,
    EmbeddingTaskType,
    ExtractionRoute,
    TenantScope,
)
from rag_platform.indexing import (
    DeterministicHashEmbedder,
    EmbedderConfig,
    EmbeddingQuotaExceededError,
    GeminiFreeTierEmbedder,
    InMemoryMultiTenantVectorStore,
    VectorIndexingService,
)
from rag_platform.processing import (
    DocumentNormalizer,
    DocumentProcessingPipeline,
    ExtractedPagePayload,
    IntelligentExtractionRouter,
    RawPageInput,
    RoutingDecision,
    validate_stream_and_register,
)


def _make_chunk(
    *,
    chunk_id: str,
    text: str,
    tenant_id: str = "tenant-a",
    project_id: str = "proj-1",
    case_id: str | None = "case-100",
    document_id: str = "doc-1",
    chunking_version: str = "1.0.0",
) -> ChunkRecord:
    """Create a valid ChunkRecord fixture for indexing tests."""
    return ChunkRecord(
        chunking_version=chunking_version,
        tenant_id=tenant_id,
        project_id=project_id,
        case_id=case_id,
        document_id=document_id,
        chunk_id=chunk_id,
        page_start=1,
        page_end=1,
        position_index=0,
        normalized_text=text,
        extraction_route=ExtractionRoute.ROUTE_A_DIGITAL_TEXT,
        extraction_quality_score=0.96,
        source_reference=f"gs://bucket/{tenant_id}/{project_id}/{document_id}/file.pdf",
        extraction_provider="gcp_digital_parser",
        extraction_model_version="native-pdf-1.0",
    )


def test_free_tier_cost_guard_and_batch_circuit_breaker() -> None:
    """Verify Invariant #4 (Free Tier guard), batching, retries, and circuit breaker."""
    with pytest.raises(ValidationError, match="Paid tier is strictly prohibited"):
        EmbedderConfig(allow_paid_tier=True)

    call_log: list[tuple[list[str], EmbeddingTaskType]] = []
    should_fail = False

    def mock_gemini_transport(
        batch: list[str],
        task_type: EmbeddingTaskType,
        cfg: EmbedderConfig,
    ) -> list[list[float]]:
        call_log.append((batch, task_type))
        if should_fail:
            raise RuntimeError("HTTP 429 Resource Exhausted: Free Tier RPM limit reached")
        return [[1.0] + [0.0] * (cfg.dimension - 1) for _ in batch]

    cfg = EmbedderConfig(
        dimension=8,
        max_batch_size=2,
        max_retries=1,
        circuit_breaker_failure_threshold=2,
    )
    embedder = GeminiFreeTierEmbedder(config=cfg, transport_fn=mock_gemini_transport)

    # 5 texts with max_batch_size=2 -> 3 batch calls (2 + 2 + 1)
    vectors = embedder.embed_texts(
        ["uno", "dos", "tres", "cuatro", "cinco"],
        task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
    )
    assert len(vectors) == 5
    assert len(call_log) == 3
    assert [len(b[0]) for b in call_log] == [2, 2, 1]

    # Simulate persistent 429 quota exhaustion tripping the circuit breaker
    should_fail = True
    with pytest.raises(EmbeddingQuotaExceededError, match="failed after retries"):
        embedder.embed_texts(["consulta bajo cuota agotada"])

    assert embedder.is_circuit_open is True

    # Subsequent calls fail fast without invoking transport while circuit is open
    prev_calls = len(call_log)
    with pytest.raises(EmbeddingQuotaExceededError, match="Circuit breaker is OPEN"):
        embedder.embed_texts(["otra consulta"])
    assert len(call_log) == prev_calls


def test_idempotent_upsert_delete_and_rebuild() -> None:
    """Verify incremental indexing, idempotency on duplicate chunk_id, delete, and rebuild."""
    embedder = DeterministicHashEmbedder()
    store = InMemoryMultiTenantVectorStore()
    service = VectorIndexingService(embedder=embedder, vector_store=store)
    scope = TenantScope(tenant_id="tenant-a", project_id="proj-1", case_id="case-100")

    c1 = _make_chunk(
        chunk_id="c-01",
        document_id="doc-1",
        text="Contrato de suministro eléctrico y penalidades por interrupción.",
    )
    c2 = _make_chunk(
        chunk_id="c-02",
        document_id="doc-2",
        text="Informe pericial contable sobre liquidación de intereses moratorios.",
    )

    service.index_chunks([c1, c2])
    assert store.get_stats().total_indexed_chunks == 2

    # Re-indexing c1 with updated text must overwrite in place (total remains 2)
    c1_updated = _make_chunk(
        chunk_id="c-01",
        document_id="doc-1",
        text="Contrato actualizado de suministro eléctrico con anexo técnico.",
    )
    service.index_chunks([c1_updated])
    stats = store.get_stats()
    assert stats.total_indexed_chunks == 2
    assert stats.tenant_counts == {"tenant-a": 2}

    # Delete doc-1 removes only c-01
    deleted = store.delete_document(scope=scope, document_id="doc-1")
    assert deleted == 1
    assert store.get_stats().total_indexed_chunks == 1

    # Rebuild replaces entire index with provided corpus
    service.rebuild_index([c1_updated, c2])
    assert store.get_stats().total_indexed_chunks == 2


def test_embedding_compatibility_enforced_on_upsert_and_search() -> None:
    """Verify Invariant #5: reject queries or upserts from incompatible embedding models."""
    embedder_v1 = DeterministicHashEmbedder(
        EmbedderConfig(
            provider_name="gemini_api",
            model_name="gemini-embedding-001",
            model_version="001",
            dimension=32,
        )
    )
    embedder_v2 = DeterministicHashEmbedder(
        EmbedderConfig(
            provider_name="gemini_api",
            model_name="gemini-embedding-001",
            model_version="002",  # Incompatible model version
            dimension=32,
        )
    )

    store = InMemoryMultiTenantVectorStore()
    service_v1 = VectorIndexingService(embedder=embedder_v1, vector_store=store)
    scope = TenantScope(tenant_id="tenant-a", project_id="proj-1")

    chunk = _make_chunk(chunk_id="c-01", text="Cláusula de jurisdicción arbitral.")
    service_v1.index_chunks([chunk])

    # Querying with a different model version must fail with EmbeddingIncompatibilityError
    with pytest.raises(EmbeddingIncompatibilityError, match="Incompatible embedding spaces"):
        service_v1.search_by_text(
            query_text="jurisdicción arbitral",
            scope=scope,
            query_embedder=embedder_v2,
        )

    # Upserting a chunk with incompatible chunking_version must also fail
    chunk_bad_ver = _make_chunk(
        chunk_id="c-02",
        text="Otro fragmento",
        chunking_version="2.0.0",
    )
    with pytest.raises(EmbeddingIncompatibilityError, match="Incompatible embedding spaces"):
        service_v1.index_chunks([chunk_bad_ver])


def test_strict_pre_retrieval_multitenant_isolation() -> None:
    """Verify Invariant #3: TenantScope filters out other tenants/projects/cases before search."""
    embedder = DeterministicHashEmbedder()
    store = InMemoryMultiTenantVectorStore()
    service = VectorIndexingService(embedder=embedder, vector_store=store)

    shared_text = "Confidencial: Reserva estratégica de litigio societario por 5 millones USD."
    chunk_tenant_a = _make_chunk(
        chunk_id="c-alpha",
        tenant_id="tenant-alpha",
        project_id="proj-secret",
        case_id="case-a",
        document_id="doc-a",
        text=shared_text,
    )
    chunk_tenant_b = _make_chunk(
        chunk_id="c-beta",
        tenant_id="tenant-beta",
        project_id="proj-secret",
        case_id="case-b",
        document_id="doc-b",
        text=shared_text,
    )
    service.index_chunks([chunk_tenant_a, chunk_tenant_b])

    scope_alpha = TenantScope(tenant_id="tenant-alpha", project_id="proj-secret")
    matches_alpha = service.search_by_text("litigio societario millones", scope=scope_alpha)

    assert len(matches_alpha) == 1
    assert matches_alpha[0].chunk.tenant_id == "tenant-alpha"
    assert matches_alpha[0].chunk.chunk_id == "c-alpha"

    # Filtering by a non-matching case_id within tenant-alpha returns zero results
    scope_wrong_case = TenantScope(
        tenant_id="tenant-alpha",
        project_id="proj-secret",
        case_id="case-nonexistent",
    )
    assert service.search_by_text("litigio societario", scope=scope_wrong_case) == []


class _SimpleDigitalExtractor:
    """Simple extractor for Module 1 -> Module 2 integration testing."""

    def extract_page(
        self,
        page: RawPageInput,
        decision: RoutingDecision,
    ) -> ExtractedPagePayload:
        _ = decision
        return ExtractedPagePayload(
            observed_text=page.digital_text or "[ilegible]",
            extractor_confidence=0.98,
            block_type=page.block_type,
        )


def test_module1_to_module2_end_to_end_pipeline() -> None:
    """Verify full flow: Document Reception -> Module 1 Chunker -> Module 2 Vector Search."""
    scope = TenantScope(tenant_id="tenant-civil", project_id="proj-obras", case_id="exp-42")
    receipt = validate_stream_and_register(
        job_id="job-42",
        document_id="doc-contrato-42",
        filename="contrato_obra_publica.pdf",
        scope=scope,
        bucket_name="bitcitychamp-project-rag-documents-dev",
        byte_stream=[b"%PDF-1.7 contrato de obra publica"],
    )

    pages = [
        RawPageInput(
            page_number=1,
            digital_text="Capítulo 1: Objeto del contrato de pavimentación vial urbana.",
            block_type="header",
        ),
        RawPageInput(
            page_number=2,
            digital_text="Capítulo 2: Cláusula penal por mora en entrega de obra pública.",
            block_type="header",
        ),
    ]

    pipeline = DocumentProcessingPipeline(
        normalizer=DocumentNormalizer(
            router=IntelligentExtractionRouter(),
            extractor=_SimpleDigitalExtractor(),
        )
    )
    _normalized_doc, chunks = pipeline.process_document(receipt, pages)
    assert len(chunks) == 2

    service = VectorIndexingService(
        embedder=DeterministicHashEmbedder(),
        vector_store=InMemoryMultiTenantVectorStore(),
    )
    service.index_chunks(chunks)

    hits = service.search_by_text(
        query_text="cláusula penal por mora en entrega de obra",
        scope=scope,
        top_k=2,
    )
    assert len(hits) == 2
    assert "Cláusula penal por mora" in hits[0].chunk.normalized_text
    assert hits[0].similarity_score > hits[1].similarity_score
