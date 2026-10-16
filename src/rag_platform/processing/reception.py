"""Module 1.1: Document reception, streaming validation, and ingestion job registration."""

from collections.abc import Iterable
from pathlib import PurePosixPath

from pydantic import BaseModel, Field

from rag_platform.contracts import DocumentFormat, TenantScope

SUPPORTED_EXTENSIONS: dict[str, DocumentFormat] = {
    ".pdf": DocumentFormat.PDF,
    ".docx": DocumentFormat.DOCX,
    ".rtf": DocumentFormat.RTF,
    ".txt": DocumentFormat.TXT,
}


class UnsupportedDocumentError(ValueError):
    """Raised when a file format, size, or payload violates ingestion policies."""


class IngestionConfig(BaseModel):
    """Operational limits for streaming document reception."""

    max_file_size_bytes: int = Field(
        default=100 * 1024 * 1024,
        gt=0,
        description="Maximum allowed file size in bytes (default 100 MB)",
    )
    stream_chunk_size_bytes: int = Field(
        default=64 * 1024,
        gt=0,
        description="Chunk size in bytes when streaming uploads to GCS",
    )


class IngestionJobReceipt(BaseModel):
    """Registered ingestion job metadata linking tenant scope and GCS storage URI."""

    job_id: str = Field(..., min_length=1)
    document_id: str = Field(..., min_length=1)
    scope: TenantScope
    filename: str = Field(..., min_length=1)
    document_format: DocumentFormat
    size_bytes: int = Field(..., gt=0)
    gcs_uri: str = Field(..., pattern=r"^gs://[a-z0-9._-]+/.+$")


def detect_document_format(filename: str) -> DocumentFormat:
    """Detect and validate document format from filename extension."""
    suffix = PurePosixPath(filename.strip()).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS.keys()))
        raise UnsupportedDocumentError(
            f"Unsupported file extension '{suffix or '<none>'}'. Allowed formats: {allowed}"
        )
    return SUPPORTED_EXTENSIONS[suffix]


def validate_stream_and_register(
    *,
    job_id: str,
    document_id: str,
    filename: str,
    scope: TenantScope,
    bucket_name: str,
    byte_stream: Iterable[bytes],
    config: IngestionConfig | None = None,
) -> IngestionJobReceipt:
    """Validate file stream without loading the full payload in memory and register GCS URI."""
    cfg = config or IngestionConfig()
    doc_format = detect_document_format(filename)

    total_bytes = 0
    for chunk in byte_stream:
        total_bytes += len(chunk)
        if total_bytes > cfg.max_file_size_bytes:
            raise UnsupportedDocumentError(
                f"File '{filename}' exceeds maximum allowed size of {cfg.max_file_size_bytes} bytes"
            )

    if total_bytes == 0:
        raise UnsupportedDocumentError(f"File '{filename}' is empty (0 bytes)")

    safe_name = PurePosixPath(filename.strip()).name
    gcs_uri = (
        f"gs://{bucket_name}/{scope.tenant_id}/{scope.project_id}/{document_id}/{safe_name}"
    )

    return IngestionJobReceipt(
        job_id=job_id,
        document_id=document_id,
        scope=scope,
        filename=safe_name,
        document_format=doc_format,
        size_bytes=total_bytes,
        gcs_uri=gcs_uri,
    )
