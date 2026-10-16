"""Semantic and hierarchical document chunker complying with Section 3.4 specifications."""

from pydantic import BaseModel, Field

from rag_platform.contracts import (
    BoundingBox,
    ChunkRecord,
    HumanReviewStatus,
    NormalizedBlock,
    NormalizedDocument,
)


class ChunkerConfig(BaseModel):
    """Configuration parameters for semantic chunking and hierarchy extraction."""

    target_chunk_size_chars: int = Field(default=800, ge=100, le=5000)
    max_chunk_size_chars: int = Field(default=1200, ge=200, le=10000)
    chunk_overlap_chars: int = Field(default=120, ge=0, le=1000)
    chunking_version: str = Field(default="1.0.0")
    preserve_table_integrity: bool = Field(default=True)


class _ChunkDraft:
    """Internal collector accumulating blocks before finalizing into a ChunkRecord."""

    def __init__(self, section_id: str | None, parent_id: str | None) -> None:
        self.section_id = section_id
        self.parent_id = parent_id
        self.blocks: list[NormalizedBlock] = []

    @property
    def current_length(self) -> int:
        return sum(len(b.observed_text) for b in self.blocks)

    def add_block(self, block: NormalizedBlock) -> None:
        self.blocks.append(block)


class SemanticChunker:
    """Orchestrates semantic chunking, boundary preservation, and epistemological separation."""

    def __init__(self, config: ChunkerConfig | None = None) -> None:
        self.config = config or ChunkerConfig()

    def chunk_document(self, document: NormalizedDocument) -> list[ChunkRecord]:
        """Convert a NormalizedDocument into an ordered list of linked ChunkRecords."""
        if not document.blocks:
            return []

        drafts: list[_ChunkDraft] = []
        current_section_id: str | None = None
        current_parent_id: str | None = None
        current_draft = _ChunkDraft(section_id=None, parent_id=None)

        for block in document.blocks:
            is_header = block.block_type in ("header", "title", "heading")
            is_table = block.block_type == "table"

            # When encountering a new section header, update hierarchy and start fresh draft
            if is_header:
                current_section_id = block.block_id
                current_parent_id = block.block_id
                if current_draft.blocks:
                    drafts.append(current_draft)
                    current_draft = _ChunkDraft(
                        section_id=current_section_id,
                        parent_id=current_parent_id,
                    )
                else:
                    current_draft.section_id = current_section_id
                    current_draft.parent_id = current_parent_id

            # Keep tables intact if preserve_table_integrity is active
            if is_table and self.config.preserve_table_integrity and current_draft.blocks:
                drafts.append(current_draft)
                current_draft = _ChunkDraft(
                    section_id=current_section_id,
                    parent_id=current_parent_id,
                )

            # Check if adding this block exceeds maximum chunk size
            block_len = len(block.observed_text)
            exceeds_max = (
                current_draft.current_length + block_len > self.config.max_chunk_size_chars
            )
            if current_draft.blocks and exceeds_max:
                drafts.append(current_draft)
                current_draft = _ChunkDraft(
                    section_id=current_section_id,
                    parent_id=current_parent_id,
                )

            current_draft.add_block(block)

            # Flush if target size reached and it was a table or natural boundary
            if is_table or current_draft.current_length >= self.config.target_chunk_size_chars:
                drafts.append(current_draft)
                current_draft = _ChunkDraft(
                    section_id=current_section_id,
                    parent_id=current_parent_id,
                )

        if current_draft.blocks:
            drafts.append(current_draft)

        return self._build_final_records(document, drafts)

    def _build_final_records(
        self,
        document: NormalizedDocument,
        drafts: list[_ChunkDraft],
    ) -> list[ChunkRecord]:
        """Transform drafts into validated ChunkRecords with two-pass adjacency linking."""
        total_drafts = len(drafts)
        records: list[ChunkRecord] = []

        for idx, draft in enumerate(drafts):
            chunk_id = f"{document.document_id}-chk-{idx + 1:04d}"
            prev_id = f"{document.document_id}-chk-{idx:04d}" if idx > 0 else None
            next_id = (
                f"{document.document_id}-chk-{idx + 2:04d}" if idx + 1 < total_drafts else None
            )

            # Aggregate text and notes
            text_segments = [
                b.observed_text.strip() for b in draft.blocks if b.observed_text.strip()
            ]
            normalized_text = " \n".join(text_segments)

            # Segregate all inferred hypotheses into context notes (Epistemological safety)
            inferred_notes: list[str] = []
            for b in draft.blocks:
                for span in b.inferred_hypotheses:
                    note = f"[Inferencia ({span.status}, conf={span.confidence:.2f})]: {span.text}"
                    if span.rationale:
                        note += f" — Motivo: {span.rationale}"
                    inferred_notes.append(note)

            # Quality metrics aggregation
            avg_quality = sum(b.extraction_quality_score for b in draft.blocks) / len(draft.blocks)
            uncertainty = max(0.0, 1.0 - avg_quality)

            # Compute bounding box envelope if available
            bounding_box = self._compute_bounding_envelope(draft.blocks)

            # Check human review requirement
            has_pending_review = any(
                b.human_review_status == HumanReviewStatus.PENDING_REVIEW for b in draft.blocks
            )
            needs_human_review = uncertainty > 0.5 or has_pending_review
            review_status = (
                HumanReviewStatus.PENDING_REVIEW
                if needs_human_review
                else HumanReviewStatus.NOT_REQUIRED
            )

            primary_block = draft.blocks[0]
            record = ChunkRecord(
                schema_version="1.0.0",
                chunking_version=self.config.chunking_version,
                tenant_id=document.scope.tenant_id,
                project_id=document.scope.project_id,
                case_id=document.scope.case_id,
                document_id=document.document_id,
                chunk_id=chunk_id,
                parent_id=draft.parent_id,
                section_id=draft.section_id,
                previous_chunk_id=prev_id,
                next_chunk_id=next_id,
                page_start=min(b.page_number for b in draft.blocks),
                page_end=max(b.page_number for b in draft.blocks),
                position_index=idx,
                bounding_box=bounding_box,
                normalized_text=normalized_text,
                inferred_context_notes=inferred_notes,
                extraction_route=primary_block.extraction_route,
                extraction_quality_score=round(avg_quality, 4),
                source_reference=document.gcs_uri,
                extraction_provider=primary_block.extraction_provider,
                extraction_model_version=primary_block.extraction_model_version,
                transcription_uncertainty=round(uncertainty, 4),
                human_review_status=review_status,
            )
            records.append(record)

        return records

    @staticmethod
    def _compute_bounding_envelope(blocks: list[NormalizedBlock]) -> BoundingBox | None:
        """Calculate the outer bounding box encompassing all constituent blocks."""
        boxes = [b.bounding_box for b in blocks if b.bounding_box is not None]
        if not boxes:
            return None
        return BoundingBox(
            x0=min(b.x0 for b in boxes),
            y0=min(b.y0 for b in boxes),
            x1=max(b.x1 for b in boxes),
            y1=max(b.y1 for b in boxes),
        )
