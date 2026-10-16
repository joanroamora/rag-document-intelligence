"""Module 1.2: Intelligent page/block extraction router and quality evaluation (Routes A-E)."""

from pydantic import BaseModel, Field

from rag_platform.contracts import ExtractionRoute


class RouterConfig(BaseModel):
    """Thresholds and model configuration for intelligent extraction routing."""

    min_digital_chars_per_page: int = Field(default=30, ge=1)
    max_digital_anomaly_ratio: float = Field(default=0.08, ge=0.0, le=1.0)
    acceptance_quality_threshold: float = Field(default=0.70, ge=0.1, le=1.0)
    gemini_flash_model_id: str = Field(default="gemini-2.5-flash", min_length=1)
    gemini_pro_model_id: str = Field(default="gemini-2.5-pro", min_length=1)
    is_gemini_pro_free_tier_enabled: bool = Field(
        default=False,
        description="Must be explicitly verified free in account; never auto-enable paid billing",
    )


class PageDiagnostic(BaseModel):
    """Cheap pre-extraction diagnostic metrics for a document page or block."""

    page_number: int = Field(..., ge=1)
    has_digital_text_layer: bool = Field(default=False)
    digital_char_count: int = Field(default=0, ge=0)
    anomaly_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    has_complex_tables_or_diagrams: bool = Field(default=False)
    is_degraded_or_handwritten: bool = Field(default=False)


class RoutingDecision(BaseModel):
    """Selected extraction route and provider metadata for a page or block."""

    page_number: int = Field(..., ge=1)
    selected_route: ExtractionRoute
    provider: str = Field(..., min_length=1)
    model_version: str = Field(..., min_length=1)
    requires_human_review: bool = Field(default=False)
    rationale: str = Field(..., min_length=1)


class ExtractionQualityReport(BaseModel):
    """Post-extraction quality evaluation determining acceptance or route escalation."""

    quality_score: float = Field(..., ge=0.0, le=1.0)
    accepted: bool
    next_escalation_route: ExtractionRoute | None = Field(default=None)
    requires_human_review: bool = Field(default=False)


class IntelligentExtractionRouter:
    """Routes pages across Routes A-E based on cheap diagnostics and post-extraction quality."""

    def __init__(self, config: RouterConfig | None = None) -> None:
        self.config = config or RouterConfig()

    def select_initial_route(self, diagnostic: PageDiagnostic) -> RoutingDecision:
        """Select optimal initial extraction route from pre-extraction page diagnostics."""
        # Route D: Tables, diagrams, or visual elements requiring multimodal vision
        if diagnostic.has_complex_tables_or_diagrams:
            return RoutingDecision(
                page_number=diagnostic.page_number,
                selected_route=ExtractionRoute.ROUTE_D_GEMINI_FLASH,
                provider="gemini_api",
                model_version=self.config.gemini_flash_model_id,
                rationale="Page contains complex tables or visual diagrams requiring Route D Flash",
            )

        # Route A: Clean digital text layer
        has_enough_chars = diagnostic.digital_char_count >= self.config.min_digital_chars_per_page
        low_anomalies = diagnostic.anomaly_ratio <= self.config.max_digital_anomaly_ratio
        if diagnostic.has_digital_text_layer and has_enough_chars and low_anomalies:
            return RoutingDecision(
                page_number=diagnostic.page_number,
                selected_route=ExtractionRoute.ROUTE_A_DIGITAL_TEXT,
                provider="gcp_digital_extractor",
                model_version="1.0.0",
                rationale="Clean digital text layer detected with low anomaly ratio",
            )

        # Route C: Degraded scan, handwriting, or high anomaly digital text
        if diagnostic.is_degraded_or_handwritten:
            return RoutingDecision(
                page_number=diagnostic.page_number,
                selected_route=ExtractionRoute.ROUTE_C_ENHANCED_OCR,
                provider="gcp_enhanced_ocr",
                model_version="tesseract-5.3-preprocessed",
                rationale="Degraded typescript or handwriting requires image preprocessing + OCR",
            )

        # Route B: Standard legible scan
        return RoutingDecision(
            page_number=diagnostic.page_number,
            selected_route=ExtractionRoute.ROUTE_B_OPEN_SOURCE_OCR,
            provider="gcp_open_source_ocr",
            model_version="tesseract-5.3",
            rationale="Standard scanned page routed to open-source container OCR",
        )

    def evaluate_extraction_quality(
        self,
        *,
        current_route: ExtractionRoute,
        observed_text: str,
        extractor_confidence: float,
        anomaly_ratio: float = 0.0,
    ) -> ExtractionQualityReport:
        """Compute Extraction Quality Score and determine whether to accept or escalate."""
        clean_text = observed_text.strip()
        if not clean_text:
            quality_score = 0.0
        else:
            illegible_count = clean_text.count("[ilegible]")
            words = max(1, len(clean_text.split()))
            illegible_penalty = min(0.6, (illegible_count / words) * 2.0)
            anomaly_penalty = min(0.5, anomaly_ratio * 1.5)
            raw_score = extractor_confidence - illegible_penalty - anomaly_penalty
            quality_score = round(max(0.0, min(1.0, raw_score)), 4)

        if quality_score >= self.config.acceptance_quality_threshold:
            return ExtractionQualityReport(
                quality_score=quality_score,
                accepted=True,
                next_escalation_route=None,
                requires_human_review=False,
            )

        # Escalation chain: A -> B -> C -> D -> E (if free tier enabled) -> Human Review
        next_route, needs_human = self._determine_escalation(current_route)
        return ExtractionQualityReport(
            quality_score=quality_score,
            accepted=False,
            next_escalation_route=next_route,
            requires_human_review=needs_human,
        )

    def resolve_route_decision(
        self,
        page_number: int,
        route: ExtractionRoute,
    ) -> RoutingDecision:
        """Build RoutingDecision metadata for a specific target route during escalation."""
        if route == ExtractionRoute.ROUTE_A_DIGITAL_TEXT:
            return RoutingDecision(
                page_number=page_number,
                selected_route=route,
                provider="gcp_digital_extractor",
                model_version="1.0.0",
                rationale="Direct digital text extraction",
            )
        if route == ExtractionRoute.ROUTE_B_OPEN_SOURCE_OCR:
            return RoutingDecision(
                page_number=page_number,
                selected_route=route,
                provider="gcp_open_source_ocr",
                model_version="tesseract-5.3",
                rationale="Escalated to open-source OCR in GCP container",
            )
        if route == ExtractionRoute.ROUTE_C_ENHANCED_OCR:
            return RoutingDecision(
                page_number=page_number,
                selected_route=route,
                provider="gcp_enhanced_ocr",
                model_version="tesseract-5.3-preprocessed",
                rationale="Escalated to image preprocessing and second-pass OCR",
            )
        if route == ExtractionRoute.ROUTE_D_GEMINI_FLASH:
            return RoutingDecision(
                page_number=page_number,
                selected_route=route,
                provider="gemini_api",
                model_version=self.config.gemini_flash_model_id,
                rationale="Escalated to Gemini Flash Free Tier multimodal extraction",
            )
        # Route E
        return RoutingDecision(
            page_number=page_number,
            selected_route=ExtractionRoute.ROUTE_E_GEMINI_PRO,
            provider="gemini_api",
            model_version=self.config.gemini_pro_model_id,
            requires_human_review=not self.config.is_gemini_pro_free_tier_enabled,
            rationale="Escalated to maximum capacity Route E (Gemini Pro Free Tier)",
        )

    def _determine_escalation(
        self,
        current_route: ExtractionRoute,
    ) -> tuple[ExtractionRoute | None, bool]:
        """Determine next fallback route while strictly enforcing Free Tier cost protection."""
        if current_route == ExtractionRoute.ROUTE_A_DIGITAL_TEXT:
            return ExtractionRoute.ROUTE_B_OPEN_SOURCE_OCR, False
        if current_route == ExtractionRoute.ROUTE_B_OPEN_SOURCE_OCR:
            return ExtractionRoute.ROUTE_C_ENHANCED_OCR, False
        if current_route == ExtractionRoute.ROUTE_C_ENHANCED_OCR:
            return ExtractionRoute.ROUTE_D_GEMINI_FLASH, False
        if current_route == ExtractionRoute.ROUTE_D_GEMINI_FLASH:
            if self.config.is_gemini_pro_free_tier_enabled:
                return ExtractionRoute.ROUTE_E_GEMINI_PRO, False
            # Invariant #4: Never activate paid billing; mark for human review if Pro is not free
            return None, True
        return None, True
