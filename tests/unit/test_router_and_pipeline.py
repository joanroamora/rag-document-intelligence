"""Unit and pipeline integration tests for Module 1 reception, routing, and normalization."""

import pytest

from rag_platform.contracts import (
    DocumentFormat,
    EpistemicSpan,
    EpistemicStatus,
    ExtractionRoute,
    HumanReviewStatus,
    TenantScope,
)
from rag_platform.processing import (
    DocumentNormalizer,
    DocumentProcessingPipeline,
    ExtractedPagePayload,
    IngestionConfig,
    IntelligentExtractionRouter,
    PageDiagnostic,
    RawPageInput,
    RouterConfig,
    RoutingDecision,
    UnsupportedDocumentError,
    detect_document_format,
    validate_stream_and_register,
)


class _MockMultiRouteExtractor:
    """Deterministic mock extractor simulating GCP OCR containers and Gemini Flash/Pro routes."""

    def extract_page(
        self,
        page: RawPageInput,
        decision: RoutingDecision,
    ) -> ExtractedPagePayload:
        route = decision.selected_route

        if route == ExtractionRoute.ROUTE_A_DIGITAL_TEXT:
            return ExtractedPagePayload(
                observed_text=page.digital_text or "[ilegible]",
                extractor_confidence=0.97,
                block_type=page.block_type,
            )

        if route == ExtractionRoute.ROUTE_B_OPEN_SOURCE_OCR:
            # Simulate page 2 failing standard OCR so it escalates to Route C
            if page.page_number == 2:
                return ExtractedPagePayload(
                    observed_text="Texto [ilegible] [ilegible] borroso",
                    extractor_confidence=0.45,
                    block_type=page.block_type,
                )
            return ExtractedPagePayload(
                observed_text="Acta escaneada legible extraída con OCR en contenedor GCP.",
                extractor_confidence=0.88,
                block_type=page.block_type,
            )

        if route == ExtractionRoute.ROUTE_C_ENHANCED_OCR:
            return ExtractedPagePayload(
                observed_text="Texto recuperado tras preprocesamiento de imagen en contenedor GCP.",
                extractor_confidence=0.85,
                block_type=page.block_type,
            )

        if route == ExtractionRoute.ROUTE_D_GEMINI_FLASH:
            hypothesis = EpistemicSpan(
                text="Total estimado de 150,000 USD",
                status=EpistemicStatus.INFERRED_HYPOTHESIS,
                confidence=0.75,
                rationale="Suma deducida de filas parcialmente visibles en tabla",
            )
            return ExtractedPagePayload(
                observed_text="| Concepto | Valor |\n| Indemnización | $150,000 |",
                extractor_confidence=0.93,
                inferred_hypotheses=[hypothesis],
                block_type="table",
            )

        # Route E
        return ExtractedPagePayload(
            observed_text="Transcripción de máxima capacidad en documento muy deteriorado.",
            extractor_confidence=0.82,
            block_type=page.block_type,
        )


def test_reception_formats_and_streaming_limits() -> None:
    """Verify supported extensions, streaming byte limit enforcement, and GCS URI format."""
    assert detect_document_format("Demanda_Inicial.PDF") == DocumentFormat.PDF
    assert detect_document_format("anexo.docx") == DocumentFormat.DOCX
    assert detect_document_format("memorial.rtf") == DocumentFormat.RTF
    assert detect_document_format("notas.txt") == DocumentFormat.TXT

    with pytest.raises(UnsupportedDocumentError, match="Unsupported file extension"):
        detect_document_format("malware.exe")

    scope = TenantScope(tenant_id="tenant-law", project_id="proj-2026", case_id="case-9")
    cfg = IngestionConfig(max_file_size_bytes=100)

    # Empty stream rejected
    with pytest.raises(UnsupportedDocumentError, match="is empty"):
        validate_stream_and_register(
            job_id="job-1",
            document_id="doc-1",
            filename="vacio.pdf",
            scope=scope,
            bucket_name="bitcitychamp-project-rag-documents-dev",
            byte_stream=[b""],
            config=cfg,
        )

    # Oversized stream rejected immediately without buffering entire file
    with pytest.raises(UnsupportedDocumentError, match="exceeds maximum allowed size"):
        validate_stream_and_register(
            job_id="job-2",
            document_id="doc-2",
            filename="pesado.pdf",
            scope=scope,
            bucket_name="bitcitychamp-project-rag-documents-dev",
            byte_stream=[b"x" * 60, b"y" * 50],
            config=cfg,
        )

    receipt = validate_stream_and_register(
        job_id="job-3",
        document_id="doc-3",
        filename="expediente.pdf",
        scope=scope,
        bucket_name="bitcitychamp-project-rag-documents-dev",
        byte_stream=[b"PDF-1.7 ", b"contenido valido"],
        config=cfg,
    )
    assert receipt.size_bytes == 24
    assert receipt.gcs_uri == (
        "gs://bitcitychamp-project-rag-documents-dev/tenant-law/proj-2026/doc-3/expediente.pdf"
    )


def test_router_initial_route_selection() -> None:
    """Verify diagnostic routing across Routes A, B, C, and D."""
    router = IntelligentExtractionRouter()

    # Clean digital page -> Route A
    diag_a = PageDiagnostic(
        page_number=1,
        has_digital_text_layer=True,
        digital_char_count=450,
        anomaly_ratio=0.01,
    )
    assert (
        router.select_initial_route(diag_a).selected_route
        == ExtractionRoute.ROUTE_A_DIGITAL_TEXT
    )

    # Standard scanned page -> Route B
    diag_b = PageDiagnostic(page_number=2, has_digital_text_layer=False)
    assert (
        router.select_initial_route(diag_b).selected_route
        == ExtractionRoute.ROUTE_B_OPEN_SOURCE_OCR
    )

    # Degraded or handwritten page -> Route C
    diag_c = PageDiagnostic(
        page_number=3,
        has_digital_text_layer=False,
        is_degraded_or_handwritten=True,
    )
    assert (
        router.select_initial_route(diag_c).selected_route
        == ExtractionRoute.ROUTE_C_ENHANCED_OCR
    )

    # Page with tables or diagrams -> Route D (Gemini Flash)
    diag_d = PageDiagnostic(
        page_number=4,
        has_digital_text_layer=True,
        digital_char_count=200,
        has_complex_tables_or_diagrams=True,
    )
    decision_d = router.select_initial_route(diag_d)
    assert decision_d.selected_route == ExtractionRoute.ROUTE_D_GEMINI_FLASH
    assert decision_d.provider == "gemini_api"


def test_router_escalation_and_free_tier_cost_guard() -> None:
    """Verify escalation chain and ensure Route E is blocked unless Free Tier is enabled."""
    # Default config: Gemini Pro Free Tier is disabled (False) to prevent unexpected billing
    router_safe = IntelligentExtractionRouter(
        RouterConfig(is_gemini_pro_free_tier_enabled=False)
    )
    report_blocked = router_safe.evaluate_extraction_quality(
        current_route=ExtractionRoute.ROUTE_D_GEMINI_FLASH,
        observed_text="[ilegible] [ilegible] [ilegible]",
        extractor_confidence=0.35,
    )
    assert report_blocked.accepted is False
    assert report_blocked.next_escalation_route is None
    assert report_blocked.requires_human_review is True

    # When account explicitly confirms free-tier Gemini Pro availability
    router_pro = IntelligentExtractionRouter(
        RouterConfig(is_gemini_pro_free_tier_enabled=True)
    )
    report_pro = router_pro.evaluate_extraction_quality(
        current_route=ExtractionRoute.ROUTE_D_GEMINI_FLASH,
        observed_text="[ilegible] [ilegible] [ilegible]",
        extractor_confidence=0.35,
    )
    assert report_pro.accepted is False
    assert report_pro.next_escalation_route == ExtractionRoute.ROUTE_E_GEMINI_PRO
    assert report_pro.requires_human_review is False


def test_end_to_end_document_processing_pipeline() -> None:
    """Verify full Module 1 flow: Reception -> Router & Escalation -> Normalizer -> Chunker."""
    scope = TenantScope(tenant_id="tenant-gov", project_id="proj-audit", case_id="case-101")
    receipt = validate_stream_and_register(
        job_id="job-101",
        document_id="doc-audit-01",
        filename="informe_auditoria.pdf",
        scope=scope,
        bucket_name="bitcitychamp-project-rag-documents-dev",
        byte_stream=[b"%PDF-1.7 mock stream bytes"],
    )

    pages = [
        RawPageInput(
            page_number=1,
            digital_text="Sección 1: Resumen Ejecutivo de Auditoría Financiera.",
            block_type="header",
        ),
        RawPageInput(
            page_number=2,
            digital_text=None,  # Scanned page; mock Route B will fail and escalate to Route C
            block_type="paragraph",
        ),
        RawPageInput(
            page_number=3,
            digital_text="Tabla de pagos",
            has_complex_tables_or_diagrams=True,  # Routed to Route D (Gemini Flash)
            block_type="table",
        ),
    ]

    router = IntelligentExtractionRouter()
    normalizer = DocumentNormalizer(router=router, extractor=_MockMultiRouteExtractor())
    pipeline = DocumentProcessingPipeline(normalizer=normalizer)

    normalized_doc, chunks = pipeline.process_document(receipt, pages)

    assert normalized_doc.total_pages == 3
    assert len(normalized_doc.blocks) == 3

    # Page 1 used Route A
    assert normalized_doc.blocks[0].extraction_route == ExtractionRoute.ROUTE_A_DIGITAL_TEXT
    # Page 2 started at Route B, failed quality check, and automatically escalated to Route C
    assert normalized_doc.blocks[1].extraction_route == ExtractionRoute.ROUTE_C_ENHANCED_OCR
    # Page 3 used Route D (Gemini Flash)
    assert normalized_doc.blocks[2].extraction_route == ExtractionRoute.ROUTE_D_GEMINI_FLASH

    # Verify chunks generated by SemanticChunker
    assert len(chunks) == 2  # Chunk 0: header + escalated OCR paragraph; Chunk 1: isolated table
    assert chunks[0].section_id == "p0001-b01"
    assert chunks[0].next_chunk_id == chunks[1].chunk_id
    assert chunks[1].previous_chunk_id == chunks[0].chunk_id
    assert chunks[1].extraction_route == ExtractionRoute.ROUTE_D_GEMINI_FLASH
    assert chunks[1].human_review_status == HumanReviewStatus.NOT_REQUIRED
    # Epistemological safety: inferred hypothesis is in notes, not in normalized_text
    assert "150,000 USD" not in chunks[1].normalized_text
    assert len(chunks[1].inferred_context_notes) == 1
    assert "150,000 USD" in chunks[1].inferred_context_notes[0]
