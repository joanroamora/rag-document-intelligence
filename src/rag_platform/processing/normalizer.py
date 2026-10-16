"""Module 1.3: Document Normalizer and end-to-end Module 1 processing pipeline."""

from typing import Protocol

from pydantic import BaseModel, Field

from rag_platform.contracts import (
    BoundingBox,
    ChunkRecord,
    EpistemicSpan,
    ExtractionRoute,
    HumanReviewStatus,
    NormalizedBlock,
    NormalizedDocument,
)
from rag_platform.processing.chunker import SemanticChunker
from rag_platform.processing.reception import IngestionJobReceipt
from rag_platform.processing.router import (
    IntelligentExtractionRouter,
    PageDiagnostic,
    RoutingDecision,
)


class RawPageInput(BaseModel):
    """Input representation of a document page prior to routing and normalization."""

    page_number: int = Field(..., ge=1)
    digital_text: str | None = Field(default=None)
    anomaly_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    has_complex_tables_or_diagrams: bool = Field(default=False)
    is_degraded_or_handwritten: bool = Field(default=False)
    block_type: str = Field(default="paragraph")
    bounding_box: BoundingBox | None = None

    def to_diagnostic(self) -> PageDiagnostic:
        """Build pre-extraction diagnostic metrics from raw page properties."""
        clean_digital = (self.digital_text or "").strip()
        return PageDiagnostic(
            page_number=self.page_number,
            has_digital_text_layer=len(clean_digital) > 0,
            digital_char_count=len(clean_digital),
            anomaly_ratio=self.anomaly_ratio,
            has_complex_tables_or_diagrams=self.has_complex_tables_or_diagrams,
            is_degraded_or_handwritten=self.is_degraded_or_handwritten,
        )


class ExtractedPagePayload(BaseModel):
    """Structured output returned by a route-specific extractor."""

    observed_text: str = Field(..., min_length=1)
    extractor_confidence: float = Field(default=0.95, ge=0.0, le=1.0)
    inferred_hypotheses: list[EpistemicSpan] = Field(default_factory=list)
    block_type: str = Field(default="paragraph")
    bounding_box: BoundingBox | None = None


class RouteExtractorBackend(Protocol):
    """Protocol for route-specific extractors (GCP OCR containers and Gemini Vision API)."""

    def extract_page(
        self,
        page: RawPageInput,
        decision: RoutingDecision,
    ) -> ExtractedPagePayload:
        """Execute extraction for a page under the specified routing decision."""


class DocumentNormalizer:
    """Executes intelligent routing, quality escalation, and structural normalization."""

    def __init__(
        self,
        router: IntelligentExtractionRouter,
        extractor: RouteExtractorBackend,
    ) -> None:
        self.router = router
        self.extractor = extractor

    def normalize_document(
        self,
        receipt: IngestionJobReceipt,
        pages: list[RawPageInput],
    ) -> NormalizedDocument:
        """Process raw pages with automatic route escalation into a NormalizedDocument."""
        normalized_blocks: list[NormalizedBlock] = []
        ordered_pages = sorted(pages, key=lambda p: p.page_number)

        for page in ordered_pages:
            block = self._process_single_page(page)
            normalized_blocks.append(block)

        total_pages = max((p.page_number for p in ordered_pages), default=1)
        return NormalizedDocument(
            schema_version="1.0.0",
            scope=receipt.scope,
            document_id=receipt.document_id,
            filename=receipt.filename,
            document_format=receipt.document_format,
            gcs_uri=receipt.gcs_uri,
            total_pages=total_pages,
            blocks=normalized_blocks,
        )

    def _process_single_page(self, page: RawPageInput) -> NormalizedBlock:
        """Diagnose, extract, evaluate quality, and escalate across Routes A-E if needed."""
        diagnostic = page.to_diagnostic()
        decision = self.router.select_initial_route(diagnostic)

        while True:
            payload = self.extractor.extract_page(page, decision)
            is_route_a = decision.selected_route == ExtractionRoute.ROUTE_A_DIGITAL_TEXT
            effective_anomaly = page.anomaly_ratio if is_route_a else 0.0
            report = self.router.evaluate_extraction_quality(
                current_route=decision.selected_route,
                observed_text=payload.observed_text,
                extractor_confidence=payload.extractor_confidence,
                anomaly_ratio=effective_anomaly,
            )

            if report.accepted or report.next_escalation_route is None:
                needs_review = report.requires_human_review or decision.requires_human_review
                review_status = (
                    HumanReviewStatus.PENDING_REVIEW
                    if needs_review
                    else HumanReviewStatus.NOT_REQUIRED
                )
                return NormalizedBlock(
                    block_id=f"p{page.page_number:04d}-b01",
                    page_number=page.page_number,
                    block_type=payload.block_type or page.block_type,
                    extraction_route=decision.selected_route,
                    extraction_provider=decision.provider,
                    extraction_model_version=decision.model_version,
                    extraction_quality_score=report.quality_score,
                    observed_text=payload.observed_text,
                    inferred_hypotheses=payload.inferred_hypotheses,
                    bounding_box=payload.bounding_box or page.bounding_box,
                    human_review_status=review_status,
                )

            # Escalate to the next fallback route
            decision = self.router.resolve_route_decision(
                page_number=page.page_number,
                route=report.next_escalation_route,
            )


class DocumentProcessingPipeline:
    """End-to-end Module 1 pipeline from reception receipt to semantic Chunk Corpus."""

    def __init__(
        self,
        normalizer: DocumentNormalizer,
        chunker: SemanticChunker | None = None,
    ) -> None:
        self.normalizer = normalizer
        self.chunker = chunker or SemanticChunker()

    def process_document(
        self,
        receipt: IngestionJobReceipt,
        pages: list[RawPageInput],
    ) -> tuple[NormalizedDocument, list[ChunkRecord]]:
        """Execute normalization followed by semantic and hierarchical chunking."""
        normalized_doc = self.normalizer.normalize_document(receipt, pages)
        chunks = self.chunker.chunk_document(normalized_doc)
        return normalized_doc, chunks
