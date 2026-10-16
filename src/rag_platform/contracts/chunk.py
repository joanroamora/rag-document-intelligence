"""Module 1 output contract: Semantic and hierarchical Chunk Corpus (Section 3.5)."""

from pydantic import BaseModel, Field, model_validator

from rag_platform.contracts.document import (
    BoundingBox,
    ExtractionRoute,
    HumanReviewStatus,
)


class ChunkRecord(BaseModel):
    """Canonical versioned chunk contract with hierarchy, adjacency, and provenance."""

    schema_version: str = Field(default="1.0.0")
    chunking_version: str = Field(default="1.0.0")

    # Multi-tenant isolation identifiers
    tenant_id: str = Field(..., min_length=1)
    project_id: str = Field(..., min_length=1)
    case_id: str | None = Field(default=None)
    document_id: str = Field(..., min_length=1)

    # Hierarchical and adjacency links
    chunk_id: str = Field(..., min_length=1)
    parent_id: str | None = Field(
        default=None, description="Parent section or chapter identifier"
    )
    section_id: str | None = Field(default=None)
    previous_chunk_id: str | None = Field(default=None)
    next_chunk_id: str | None = Field(default=None)

    # Physical location
    page_start: int = Field(..., ge=1)
    page_end: int = Field(..., ge=1)
    position_index: int = Field(..., ge=0)
    bounding_box: BoundingBox | None = None

    # Normalized content & epistemological separation
    normalized_text: str = Field(
        ...,
        min_length=1,
        description="Observed transcription and explicitly marked uncertain text",
    )
    inferred_context_notes: list[str] = Field(
        default_factory=list,
        description="Segregated contextual hypotheses; never merged into normalized_text",
    )

    # Extraction quality and provenance
    extraction_route: ExtractionRoute
    extraction_quality_score: float = Field(..., ge=0.0, le=1.0)
    source_reference: str = Field(
        ...,
        pattern=r"^gs://[a-z0-9._-]+/.+$",
        description="Immutable GCS reference to original document",
    )
    extraction_provider: str = Field(..., min_length=1)
    extraction_model_version: str = Field(..., min_length=1)
    transcription_uncertainty: float = Field(default=0.0, ge=0.0, le=1.0)
    human_review_status: HumanReviewStatus = Field(default=HumanReviewStatus.NOT_REQUIRED)

    @model_validator(mode="after")
    def validate_page_range_and_quality(self) -> "ChunkRecord":
        """Enforce valid page ranges and human review status on high uncertainty."""
        if self.page_end < self.page_start:
            raise ValueError("page_end must be greater than or equal to page_start")
        if (
            self.transcription_uncertainty > 0.5
            and self.human_review_status == HumanReviewStatus.NOT_REQUIRED
        ):
            raise ValueError(
                "Chunks with transcription_uncertainty > 0.5 must require or record human review"
            )
        return self
