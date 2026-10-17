"""Cloud Run FastAPI application exposing the multi-tenant RAG Platform."""

import base64
import io
import os
import re
import uuid
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from pypdf import PdfReader

from rag_platform.adapters import (
    GeminiClientConfig,
    GeminiGroundedSynthesizer,
    GeminiMultimodalRouteExtractor,
    GeminiRESTClient,
)
from rag_platform.api.schemas import (
    AskQuestionRequest,
    DeleteDocumentResponse,
    HealthResponse,
    IngestDocumentRequest,
    IngestDocumentResponse,
    UploadBinaryDocumentRequest,
)
from rag_platform.api.ui import ENTERPRISE_UI_HTML
from rag_platform.contracts import GeneratedRAGResponse, TenantScope, UsageMode
from rag_platform.generation import GroundedAnswerGenerator
from rag_platform.indexing import (
    DeterministicHashEmbedder,
    GeminiFreeTierEmbedder,
    InMemoryMultiTenantVectorStore,
    VectorIndexingService,
)
from rag_platform.orchestrator import RAGPlatformOrchestrator
from rag_platform.processing import (
    DocumentNormalizer,
    DocumentProcessingPipeline,
    ExtractedPagePayload,
    IntelligentExtractionRouter,
    RawPageInput,
    RouteExtractorBackend,
    RoutingDecision,
    UnsupportedDocumentError,
)
from rag_platform.retrieval import BM25LexicalIndex, HybridRetriever


class DefaultCloudExtractor:
    """Default cloud extractor backend for API runtime."""

    def extract_page(
        self,
        page: RawPageInput,
        decision: RoutingDecision,
    ) -> ExtractedPagePayload:
        _ = decision
        return ExtractedPagePayload(
            observed_text=page.digital_text or "[ilegible]",
            extractor_confidence=0.96,
            block_type=page.block_type,
        )


def build_default_orchestrator(
    gemini_api_key: str | None = None,
) -> RAGPlatformOrchestrator:
    """Build a RAGPlatformOrchestrator wired for Cloud Run (Gemini Free Tier or CPU)."""
    resolved_key = gemini_api_key or (
        os.getenv("GEMINI_API_KEY")
        if os.getenv("USE_LIVE_GEMINI_API", "").lower() == "true"
        else None
    )

    if resolved_key and resolved_key.strip():
        client = GeminiRESTClient(GeminiClientConfig(api_key=resolved_key.strip()))
        extractor: RouteExtractorBackend = GeminiMultimodalRouteExtractor(client)
        embedder = GeminiFreeTierEmbedder(transport_fn=client.batch_embed_contents)
        generator = GroundedAnswerGenerator(
            synthesizer=GeminiGroundedSynthesizer(client)
        )
    else:
        extractor = DefaultCloudExtractor()
        embedder = DeterministicHashEmbedder()  # type: ignore[assignment]
        generator = GroundedAnswerGenerator()

    doc_pipeline = DocumentProcessingPipeline(
        normalizer=DocumentNormalizer(
            router=IntelligentExtractionRouter(),
            extractor=extractor,
        )
    )
    hybrid_retriever = HybridRetriever(
        vector_service=VectorIndexingService(
            embedder=embedder,
            vector_store=InMemoryMultiTenantVectorStore(),
        ),
        lexical_index=BM25LexicalIndex(),
    )
    return RAGPlatformOrchestrator(
        document_pipeline=doc_pipeline,
        hybrid_retriever=hybrid_retriever,
        answer_generator=generator,
    )


def require_tenant_headers(
    x_tenant_id: Annotated[str | None, Header()] = None,
    x_project_id: Annotated[str | None, Header()] = None,
) -> tuple[str, str]:
    """Enforce Invariant #3: Require explicit X-Tenant-Id and X-Project-Id headers."""
    if not x_tenant_id or not x_tenant_id.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or blank X-Tenant-Id header required for multi-tenant isolation.",
        )
    if not x_project_id or not x_project_id.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or blank X-Project-Id header required for multi-tenant isolation.",
        )
    return x_tenant_id.strip(), x_project_id.strip()


TenantHeadersDep = Annotated[tuple[str, str], Depends(require_tenant_headers)]


def _extract_pages_from_bytes(
    *,
    filename: str,
    raw_bytes: bytes,
    force_route_d: bool = False,
) -> list[RawPageInput]:
    """Extract RawPageInput items from uploaded PDF, TXT, RTF, or DOCX bytes."""
    if not raw_bytes:
        raise ValueError("Uploaded file is empty")

    block_kind = "table" if force_route_d else "paragraph"
    lower_name = filename.lower()

    if lower_name.endswith(".pdf"):
        try:
            reader = PdfReader(io.BytesIO(raw_bytes))
            pages: list[RawPageInput] = []
            for idx, pdf_page in enumerate(reader.pages, start=1):
                txt = (pdf_page.extract_text() or "").strip()
                pages.append(
                    RawPageInput(
                        page_number=idx,
                        digital_text=txt if txt else None,
                        has_complex_tables_or_diagrams=force_route_d,
                        block_type=block_kind,
                    )
                )
            if pages:
                return pages
        except Exception:
            pass

    decoded = raw_bytes.decode("utf-8", errors="ignore")
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", decoded).strip()
    if not cleaned:
        cleaned = "[ilegible]"

    chunks = [
        cleaned[i : i + 1800].strip()
        for i in range(0, len(cleaned), 1800)
        if cleaned[i : i + 1800].strip()
    ]
    if not chunks:
        chunks = ["[ilegible]"]

    return [
        RawPageInput(
            page_number=idx,
            digital_text=part,
            has_complex_tables_or_diagrams=force_route_d,
            block_type=block_kind,
        )
        for idx, part in enumerate(chunks, start=1)
    ]


def create_app(
    orchestrator: RAGPlatformOrchestrator | None = None,
    default_bucket: str | None = None,
) -> FastAPI:
    """Create and configure the multi-tenant FastAPI application."""
    active_orchestrator = orchestrator or build_default_orchestrator()
    bucket_name = default_bucket or os.getenv(
        "GCS_DOCUMENTS_BUCKET",
        "bitcitychamp-project-rag-documents-dev",
    )
    env_name = os.getenv("ENVIRONMENT", "dev")

    application = FastAPI(
        title="RAG Document Intelligence Platform",
        version="0.1.0",
        description="Multi-format document RAG with verifiable evidence and tenant isolation.",
    )

    @application.get("/", response_class=HTMLResponse, include_in_schema=False)
    def get_enterprise_ui() -> HTMLResponse:
        return HTMLResponse(content=ENTERPRISE_UI_HTML)

    @application.get("/health", response_model=HealthResponse)
    def get_health() -> HealthResponse:
        stats = active_orchestrator.hybrid_retriever.vector_service.vector_store.get_stats()
        return HealthResponse(
            status="ok",
            version="0.1.0",
            environment=env_name,
            indexed_chunks=stats.total_indexed_chunks,
            tenant_counts=stats.tenant_counts,
        )

    @application.post(
        "/v1/documents/ingest",
        response_model=IngestDocumentResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def ingest_document(
        payload: IngestDocumentRequest,
        tenant_headers: TenantHeadersDep,
    ) -> IngestDocumentResponse:
        tenant_id, project_id = tenant_headers
        try:
            scope = TenantScope(
                tenant_id=tenant_id,
                project_id=project_id,
                case_id=payload.case_id,
                usage_mode=payload.usage_mode,
                ttl_seconds=payload.ttl_seconds,
            )
            receipt, norm_doc, chunks = active_orchestrator.ingest_document(
                job_id=payload.job_id,
                document_id=payload.document_id,
                filename=payload.filename,
                scope=scope,
                bucket_name=bucket_name,
                byte_stream=[payload.raw_content_text.encode()],
                pages=payload.pages,
            )
        except (UnsupportedDocumentError, ValidationError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        return IngestDocumentResponse(
            receipt=receipt,
            total_pages=norm_doc.total_pages,
            chunks_indexed=len(chunks),
            chunk_ids=[c.chunk_id for c in chunks],
        )

    @application.post(
        "/v1/documents/upload",
        response_model=IngestDocumentResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def upload_binary_document(
        payload: UploadBinaryDocumentRequest,
        tenant_headers: TenantHeadersDep,
    ) -> IngestDocumentResponse:
        tenant_id, project_id = tenant_headers
        try:
            raw_b64 = payload.content_base64
            if "," in raw_b64:
                raw_b64 = raw_b64.split(",", 1)[1]
            raw_bytes = base64.b64decode(raw_b64)
            pages = _extract_pages_from_bytes(
                filename=payload.filename,
                raw_bytes=raw_bytes,
                force_route_d=payload.force_multimodal_route_d,
            )
            doc_id = payload.document_id or f"doc-{uuid.uuid4().hex[:8]}"
            job_id = f"job-{uuid.uuid4().hex[:8]}"
            scope = TenantScope(
                tenant_id=tenant_id,
                project_id=project_id,
                case_id=payload.case_id,
            )
            receipt, norm_doc, chunks = active_orchestrator.ingest_document(
                job_id=job_id,
                document_id=doc_id,
                filename=payload.filename,
                scope=scope,
                bucket_name=bucket_name,
                byte_stream=[raw_bytes],
                pages=pages,
            )
        except (UnsupportedDocumentError, ValidationError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        return IngestDocumentResponse(
            receipt=receipt,
            total_pages=norm_doc.total_pages,
            chunks_indexed=len(chunks),
            chunk_ids=[c.chunk_id for c in chunks],
        )

    @application.post("/v1/rag/ask", response_model=GeneratedRAGResponse)
    def ask_question(
        payload: AskQuestionRequest,
        tenant_headers: TenantHeadersDep,
    ) -> GeneratedRAGResponse:
        tenant_id, project_id = tenant_headers
        scope = TenantScope(
            tenant_id=tenant_id,
            project_id=project_id,
            case_id=payload.case_id,
            document_id=payload.document_id,
            usage_mode=UsageMode.PERSISTENT_CORPUS,
        )
        return active_orchestrator.ask(
            question=payload.question,
            scope=scope,
            mode=payload.mode,
            top_k=payload.top_k,
            budget=payload.budget,
        )

    @application.delete(
        "/v1/documents/{document_id}",
        response_model=DeleteDocumentResponse,
    )
    def delete_document(
        document_id: str,
        tenant_headers: TenantHeadersDep,
    ) -> DeleteDocumentResponse:
        tenant_id, project_id = tenant_headers
        scope = TenantScope(tenant_id=tenant_id, project_id=project_id)
        del_vec = (
            active_orchestrator.hybrid_retriever.vector_service.vector_store.delete_document(
                scope=scope,
                document_id=document_id,
            )
        )
        del_lex = active_orchestrator.hybrid_retriever.lexical_index.delete_document(
            scope=scope,
            document_id=document_id,
        )
        return DeleteDocumentResponse(
            document_id=document_id,
            deleted_vector_chunks=del_vec,
            deleted_lexical_chunks=del_lex,
        )

    return application


app = create_app()
