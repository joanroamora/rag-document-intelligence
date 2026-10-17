"""Request and response schemas for the Cloud Run FastAPI service."""

from pydantic import BaseModel, Field

from rag_platform.contracts import QueryBudget, RetrievalMode, UsageMode
from rag_platform.processing import IngestionJobReceipt, RawPageInput


class HealthResponse(BaseModel):
    """Health and diagnostic status returned by GET /health."""

    status: str = Field(default="ok")
    version: str = Field(default="0.1.0")
    environment: str = Field(default="dev")
    indexed_chunks: int = Field(..., ge=0)
    tenant_counts: dict[str, int] = Field(default_factory=dict)


class IngestDocumentRequest(BaseModel):
    """Payload for POST /v1/documents/ingest within a multi-tenant scope."""

    job_id: str = Field(..., min_length=1)
    document_id: str = Field(..., min_length=1)
    filename: str = Field(..., min_length=1)
    case_id: str | None = Field(default=None)
    usage_mode: UsageMode = Field(default=UsageMode.PERSISTENT_CORPUS)
    ttl_seconds: int | None = Field(default=None, gt=0)
    raw_content_text: str = Field(
        ...,
        min_length=1,
        description="Raw document content stream to validate and register",
    )
    pages: list[RawPageInput] = Field(..., min_length=1)


class IngestDocumentResponse(BaseModel):
    """Summary returned after Module 1 processing and Module 2/3 indexing."""

    receipt: IngestionJobReceipt
    total_pages: int = Field(..., ge=1)
    chunks_indexed: int = Field(..., ge=1)
    chunk_ids: list[str] = Field(default_factory=list)


class AskQuestionRequest(BaseModel):
    """Payload for POST /v1/rag/ask executing Hybrid or Deep Agentic RAG."""

    question: str = Field(..., min_length=1)
    case_id: str | None = Field(default=None)
    document_id: str | None = Field(default=None)
    mode: RetrievalMode = Field(default=RetrievalMode.STANDARD_HYBRID)
    top_k: int = Field(default=5, ge=1, le=50)
    budget: QueryBudget | None = Field(default=None)


class DeleteDocumentResponse(BaseModel):
    """Result of deleting a document's vectors and lexical entries within a TenantScope."""

    document_id: str = Field(..., min_length=1)
    deleted_vector_chunks: int = Field(..., ge=0)
    deleted_lexical_chunks: int = Field(..., ge=0)


class UploadBinaryDocumentRequest(BaseModel):
    """Payload for POST /v1/documents/upload accepting a Base64-encoded PDF/TXT/RTF/DOCX file."""

    filename: str = Field(..., min_length=1)
    content_base64: str = Field(..., min_length=1)
    document_id: str | None = Field(default=None)
    case_id: str | None = Field(default=None)
    force_multimodal_route_d: bool = Field(default=False)
