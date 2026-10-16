"""Module 1 contracts: Document reception, extraction routing, and epistemological normalization."""

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from rag_platform.contracts.tenant import TenantScope


class DocumentFormat(StrEnum):
    """Supported initial document formats."""

    PDF = "pdf"
    DOCX = "docx"
    RTF = "rtf"
    TXT = "txt"


class ExtractionRoute(StrEnum):
    """Intelligent page/block extraction routes (A through E)."""

    ROUTE_A_DIGITAL_TEXT = "A"
    ROUTE_B_OPEN_SOURCE_OCR = "B"
    ROUTE_C_ENHANCED_OCR = "C"
    ROUTE_D_GEMINI_FLASH = "D"
    ROUTE_E_GEMINI_PRO = "E"


class EpistemicStatus(StrEnum):
    """Epistemological classification separating observed transcription from inference."""

    OBSERVED = "observed"
    UNCERTAIN = "uncertain"
    INFERRED_HYPOTHESIS = "inferred_hypothesis"
    ILLEGIBLE = "illegible"


class HumanReviewStatus(StrEnum):
    """Verification state for low-confidence or conflicting extractions."""

    NOT_REQUIRED = "not_required"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class BoundingBox(BaseModel):
    """Normalized page coordinates (0.0 to 1.0)."""

    x0: float = Field(..., ge=0.0, le=1.0)
    y0: float = Field(..., ge=0.0, le=1.0)
    x1: float = Field(..., ge=0.0, le=1.0)
    y1: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_bounds(self) -> "BoundingBox":
        """Ensure x1 >= x0 and y1 >= y0."""
        if self.x1 < self.x0 or self.y1 < self.y0:
            raise ValueError("BoundingBox upper bounds (x1, y1) must be >= lower bounds (x0, y0)")
        return self


class EpistemicSpan(BaseModel):
    """Granular text segment preserving epistemological fidelity."""

    text: str = Field(..., min_length=1)
    status: EpistemicStatus = Field(default=EpistemicStatus.OBSERVED)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    rationale: str | None = Field(
        default=None,
        description="Mandatory explanation when status is INFERRED_HYPOTHESIS or UNCERTAIN",
    )

    @property
    def can_be_cited_as_fact(self) -> bool:
        """Inferred hypotheses and illegible segments must never be cited as factual quotes."""
        return self.status == EpistemicStatus.OBSERVED

    @model_validator(mode="after")
    def validate_epistemic_safety(self) -> "EpistemicSpan":
        """Enforce epistemological safety rule: never confuse inference with observed text."""
        if self.status == EpistemicStatus.INFERRED_HYPOTHESIS and not self.rationale:
            raise ValueError("rationale is mandatory when EpistemicStatus is INFERRED_HYPOTHESIS")
        if self.status == EpistemicStatus.ILLEGIBLE and self.text != "[ilegible]":
            raise ValueError("Illegible spans must use the explicit '[ilegible]' marker")
        return self


class NormalizedBlock(BaseModel):
    """Common internal representation for a page block prior to semantic chunking."""

    block_id: str = Field(..., min_length=1)
    page_number: int = Field(..., ge=1)
    block_type: str = Field(default="paragraph", description="paragraph, table, header, figure")
    extraction_route: ExtractionRoute
    extraction_provider: str = Field(..., min_length=1)
    extraction_model_version: str = Field(..., min_length=1)
    extraction_quality_score: float = Field(..., ge=0.0, le=1.0)
    observed_text: str = Field(
        ...,
        description="Strictly observed/uncertain transcription; excludes inferred hypotheses",
    )
    inferred_hypotheses: list[EpistemicSpan] = Field(
        default_factory=list,
        description="Segregated context inferences that must never silently become facts",
    )
    bounding_box: BoundingBox | None = None
    human_review_status: HumanReviewStatus = Field(default=HumanReviewStatus.NOT_REQUIRED)


class NormalizedDocument(BaseModel):
    """Internal normalized document produced by Document Normalizer (Section 3.3)."""

    schema_version: str = Field(default="1.0.0")
    scope: TenantScope
    document_id: str = Field(..., min_length=1)
    filename: str = Field(..., min_length=1)
    document_format: DocumentFormat
    gcs_uri: str = Field(..., pattern=r"^gs://[a-z0-9._-]+/.+$")
    total_pages: int = Field(..., ge=1)
    blocks: list[NormalizedBlock] = Field(default_factory=list)
