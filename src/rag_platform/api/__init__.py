"""FastAPI REST service layer for Cloud Run deployment."""

from rag_platform.api.app import (
    DefaultCloudExtractor,
    app,
    build_default_orchestrator,
    create_app,
)
from rag_platform.api.schemas import (
    AskQuestionRequest,
    DeleteDocumentResponse,
    HealthResponse,
    IngestDocumentRequest,
    IngestDocumentResponse,
    UploadBinaryDocumentRequest,
)

__all__ = [
    "AskQuestionRequest",
    "DefaultCloudExtractor",
    "DeleteDocumentResponse",
    "HealthResponse",
    "IngestDocumentRequest",
    "IngestDocumentResponse",
    "UploadBinaryDocumentRequest",
    "app",
    "build_default_orchestrator",
    "create_app",
]
