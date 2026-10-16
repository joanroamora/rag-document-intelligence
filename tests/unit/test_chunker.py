"""Unit tests for SemanticChunker, hierarchy extraction, and epistemological safety."""

from rag_platform.contracts import (
    BoundingBox,
    DocumentFormat,
    EpistemicSpan,
    EpistemicStatus,
    ExtractionRoute,
    HumanReviewStatus,
    NormalizedBlock,
    NormalizedDocument,
    TenantScope,
)
from rag_platform.processing import ChunkerConfig, SemanticChunker


def _build_test_document(blocks: list[NormalizedBlock]) -> NormalizedDocument:
    """Helper to instantiate a valid NormalizedDocument with mock tenant scope."""
    return NormalizedDocument(
        schema_version="1.0.0",
        scope=TenantScope(tenant_id="tenant-alpha", project_id="proj-finance"),
        document_id="doc-expediente-99",
        filename="expediente_99.pdf",
        document_format=DocumentFormat.PDF,
        gcs_uri="gs://bitcitychamp-project-rag-documents-dev/tenant-alpha/expediente_99.pdf",
        total_pages=3,
        blocks=blocks,
    )


def test_empty_document_returns_empty_chunks() -> None:
    """An empty normalized document produces zero chunks."""
    chunker = SemanticChunker()
    doc = _build_test_document([])
    assert chunker.chunk_document(doc) == []


def test_hierarchy_and_section_tracking() -> None:
    """Section headers update current parent_id and section_id on subsequent chunks."""
    blocks = [
        NormalizedBlock(
            block_id="hdr-01",
            page_number=1,
            block_type="header",
            extraction_route=ExtractionRoute.ROUTE_A_DIGITAL_TEXT,
            extraction_provider="pymupdf",
            extraction_model_version="1.0",
            extraction_quality_score=0.98,
            observed_text="Capítulo 1: Antecedentes Legales",
        ),
        NormalizedBlock(
            block_id="p-01",
            page_number=1,
            block_type="paragraph",
            extraction_route=ExtractionRoute.ROUTE_A_DIGITAL_TEXT,
            extraction_provider="pymupdf",
            extraction_model_version="1.0",
            extraction_quality_score=0.96,
            observed_text="Las partes comparecieron ante el juzgado primero civil.",
        ),
        NormalizedBlock(
            block_id="hdr-02",
            page_number=2,
            block_type="header",
            extraction_route=ExtractionRoute.ROUTE_A_DIGITAL_TEXT,
            extraction_provider="pymupdf",
            extraction_model_version="1.0",
            extraction_quality_score=0.99,
            observed_text="Capítulo 2: Pretensiones y Pruebas",
        ),
        NormalizedBlock(
            block_id="p-02",
            page_number=2,
            block_type="paragraph",
            extraction_route=ExtractionRoute.ROUTE_A_DIGITAL_TEXT,
            extraction_provider="pymupdf",
            extraction_model_version="1.0",
            extraction_quality_score=0.95,
            observed_text="Se solicita el pago de la indemnización integral pactada.",
        ),
    ]

    doc = _build_test_document(blocks)
    chunker = SemanticChunker(ChunkerConfig(target_chunk_size_chars=200))
    chunks = chunker.chunk_document(doc)

    assert len(chunks) == 2
    # First chunk under Chapter 1
    assert chunks[0].section_id == "hdr-01"
    assert chunks[0].parent_id == "hdr-01"
    assert "Antecedentes Legales" in chunks[0].normalized_text
    # Second chunk under Chapter 2
    assert chunks[1].section_id == "hdr-02"
    assert chunks[1].parent_id == "hdr-02"
    assert "Pretensiones y Pruebas" in chunks[1].normalized_text


def test_table_integrity_preservation() -> None:
    """Tables are isolated into their own chunks when preserve_table_integrity is True."""
    blocks = [
        NormalizedBlock(
            block_id="p-intro",
            page_number=1,
            block_type="paragraph",
            extraction_route=ExtractionRoute.ROUTE_A_DIGITAL_TEXT,
            extraction_provider="pymupdf",
            extraction_model_version="1.0",
            extraction_quality_score=0.95,
            observed_text="A continuación se detallan los pagos efectuados:",
        ),
        NormalizedBlock(
            block_id="tbl-01",
            page_number=1,
            block_type="table",
            extraction_route=ExtractionRoute.ROUTE_D_GEMINI_FLASH,
            extraction_provider="gemini_api",
            extraction_model_version="gemini-2.5-flash",
            extraction_quality_score=0.92,
            observed_text="| Fecha | Monto | Estado |\n| 1999-04-12 | $50,000 | Aprobado |",
        ),
        NormalizedBlock(
            block_id="p-outro",
            page_number=1,
            block_type="paragraph",
            extraction_route=ExtractionRoute.ROUTE_A_DIGITAL_TEXT,
            extraction_provider="pymupdf",
            extraction_model_version="1.0",
            extraction_quality_score=0.97,
            observed_text="Todos los desembolsos fueron confirmados por tesorería.",
        ),
    ]

    doc = _build_test_document(blocks)
    chunker = SemanticChunker(ChunkerConfig(preserve_table_integrity=True))
    chunks = chunker.chunk_document(doc)

    # Paragraph intro, Table, and Paragraph outro are kept distinct
    assert len(chunks) == 3
    assert chunks[1].normalized_text.startswith("| Fecha | Monto | Estado |")
    assert chunks[1].extraction_route == ExtractionRoute.ROUTE_D_GEMINI_FLASH


def test_deterministic_adjacency_links() -> None:
    """Verifies bidirectional previous_chunk_id and next_chunk_id linking."""
    blocks = [
        NormalizedBlock(
            block_id=f"b-{i}",
            page_number=i,
            block_type="paragraph",
            extraction_route=ExtractionRoute.ROUTE_A_DIGITAL_TEXT,
            extraction_provider="pymupdf",
            extraction_model_version="1.0",
            extraction_quality_score=0.95,
            observed_text=f"Contenido de prueba para el bloque número {i}." * 10,
        )
        for i in range(1, 4)
    ]

    doc = _build_test_document(blocks)
    chunker = SemanticChunker(ChunkerConfig(target_chunk_size_chars=100))
    chunks = chunker.chunk_document(doc)

    assert len(chunks) == 3
    # Chunk 0
    assert chunks[0].previous_chunk_id is None
    assert chunks[0].next_chunk_id == chunks[1].chunk_id
    assert chunks[0].position_index == 0
    # Chunk 1
    assert chunks[1].previous_chunk_id == chunks[0].chunk_id
    assert chunks[1].next_chunk_id == chunks[2].chunk_id
    assert chunks[1].position_index == 1
    # Chunk 2
    assert chunks[2].previous_chunk_id == chunks[1].chunk_id
    assert chunks[2].next_chunk_id is None
    assert chunks[2].position_index == 2


def test_epistemic_safety_segregation() -> None:
    """Inferred hypotheses must be segregated to notes and never pollute normalized_text."""
    hypothesis = EpistemicSpan(
        text="Cláusula de confidencialidad tácita",
        status=EpistemicStatus.INFERRED_HYPOTHESIS,
        confidence=0.72,
        rationale="Inferido a partir de la referencia cruzada al memorando 4",
    )
    block = NormalizedBlock(
        block_id="b-mixed",
        page_number=1,
        block_type="paragraph",
        extraction_route=ExtractionRoute.ROUTE_C_ENHANCED_OCR,
        extraction_provider="tesseract_ocr",
        extraction_model_version="5.3",
        extraction_quality_score=0.88,
        observed_text="El contrato rige durante tres años calendario a partir de su firma.",
        inferred_hypotheses=[hypothesis],
    )

    doc = _build_test_document([block])
    chunker = SemanticChunker()
    chunks = chunker.chunk_document(doc)

    assert len(chunks) == 1
    # Factual text remains pure
    assert chunks[0].normalized_text == (
        "El contrato rige durante tres años calendario a partir de su firma."
    )
    assert "confidencialidad tácita" not in chunks[0].normalized_text
    # Hypothesis is cleanly preserved in notes with confidence and rationale
    assert len(chunks[0].inferred_context_notes) == 1
    assert "confidencialidad tácita" in chunks[0].inferred_context_notes[0]
    assert "conf=0.72" in chunks[0].inferred_context_notes[0]
    assert "memorando 4" in chunks[0].inferred_context_notes[0]


def test_high_uncertainty_triggers_pending_review() -> None:
    """Low quality extractions require human review status."""
    low_quality_block = NormalizedBlock(
        block_id="b-degraded",
        page_number=1,
        block_type="paragraph",
        extraction_route=ExtractionRoute.ROUTE_C_ENHANCED_OCR,
        extraction_provider="tesseract_ocr",
        extraction_model_version="5.3",
        extraction_quality_score=0.40,  # Uncertainty = 0.60 > 0.50
        observed_text="Texto muy borroso con manchas [ilegible] en la firma.",
    )

    doc = _build_test_document([low_quality_block])
    chunker = SemanticChunker()
    chunks = chunker.chunk_document(doc)

    assert len(chunks) == 1
    assert chunks[0].transcription_uncertainty == 0.60
    assert chunks[0].human_review_status == HumanReviewStatus.PENDING_REVIEW


def test_bounding_box_envelope_calculation() -> None:
    """Outer bounding envelope correctly encompasses all constituent block coordinates."""
    b1 = NormalizedBlock(
        block_id="b1",
        page_number=1,
        extraction_route=ExtractionRoute.ROUTE_A_DIGITAL_TEXT,
        extraction_provider="pymupdf",
        extraction_model_version="1.0",
        extraction_quality_score=0.99,
        observed_text="Texto superior",
        bounding_box=BoundingBox(x0=0.1, y0=0.1, x1=0.8, y1=0.3),
    )
    b2 = NormalizedBlock(
        block_id="b2",
        page_number=1,
        extraction_route=ExtractionRoute.ROUTE_A_DIGITAL_TEXT,
        extraction_provider="pymupdf",
        extraction_model_version="1.0",
        extraction_quality_score=0.99,
        observed_text="Texto inferior",
        bounding_box=BoundingBox(x0=0.2, y0=0.4, x1=0.9, y1=0.7),
    )

    doc = _build_test_document([b1, b2])
    chunker = SemanticChunker(ChunkerConfig(target_chunk_size_chars=500))
    chunks = chunker.chunk_document(doc)

    assert len(chunks) == 1
    envelope = chunks[0].bounding_box
    assert envelope is not None
    assert envelope.x0 == 0.1
    assert envelope.y0 == 0.1
    assert envelope.x1 == 0.9
    assert envelope.y1 == 0.7
