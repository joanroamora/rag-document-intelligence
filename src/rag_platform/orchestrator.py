"""End-to-End RAG Platform Orchestrator linking Modules 1, 2, 3, and 4."""

from collections.abc import Iterable, Sequence

from rag_platform.contracts import (
    ChunkRecord,
    GeneratedRAGResponse,
    NormalizedDocument,
    QueryBudget,
    RetrievalMode,
    TenantScope,
)
from rag_platform.generation import GroundedAnswerGenerator
from rag_platform.processing import (
    DocumentProcessingPipeline,
    IngestionConfig,
    IngestionJobReceipt,
    RawPageInput,
    validate_stream_and_register,
)
from rag_platform.retrieval import AgenticRetrievalEngine, HybridRetriever


class RAGPlatformOrchestrator:
    """Unified multi-tenant facade orchestrating Document Ingestion through Cited Generation."""

    def __init__(
        self,
        document_pipeline: DocumentProcessingPipeline,
        hybrid_retriever: HybridRetriever,
        agentic_engine: AgenticRetrievalEngine | None = None,
        answer_generator: GroundedAnswerGenerator | None = None,
        ingestion_config: IngestionConfig | None = None,
    ) -> None:
        self.document_pipeline = document_pipeline
        self.hybrid_retriever = hybrid_retriever
        self.agentic_engine = agentic_engine or AgenticRetrievalEngine(
            hybrid_retriever=hybrid_retriever
        )
        self.answer_generator = answer_generator or GroundedAnswerGenerator()
        self.ingestion_config = ingestion_config

    def ingest_document(
        self,
        *,
        job_id: str,
        document_id: str,
        filename: str,
        scope: TenantScope,
        bucket_name: str,
        byte_stream: Iterable[bytes],
        pages: Sequence[RawPageInput],
    ) -> tuple[IngestionJobReceipt, NormalizedDocument, list[ChunkRecord]]:
        """Execute Module 1 (Reception -> Router -> Normalizer -> Chunker) and Module 2/3 Index."""
        receipt = validate_stream_and_register(
            job_id=job_id,
            document_id=document_id,
            filename=filename,
            scope=scope,
            bucket_name=bucket_name,
            byte_stream=byte_stream,
            config=self.ingestion_config,
        )
        normalized_doc, chunks = self.document_pipeline.process_document(
            receipt=receipt,
            pages=list(pages),
        )
        self.hybrid_retriever.index_corpus(chunks)
        return receipt, normalized_doc, chunks

    def ask(
        self,
        *,
        question: str,
        scope: TenantScope,
        mode: RetrievalMode = RetrievalMode.STANDARD_HYBRID,
        top_k: int = 5,
        budget: QueryBudget | None = None,
    ) -> GeneratedRAGResponse:
        """Execute Module 3 (Hybrid or Agentic Retrieval) and Module 4 (Grounded Generation)."""
        if mode == RetrievalMode.DEEP_AGENTIC:
            agentic_res = self.agentic_engine.retrieve(
                question=question,
                authorized_scope=scope,
                budget=budget,
                top_k_per_subquery=top_k,
            )
            retrieval_result = agentic_res.retrieval_result
        else:
            retrieval_result = self.hybrid_retriever.retrieve(
                query_text=question,
                scope=scope,
                top_k=top_k,
            )

        return self.answer_generator.generate(retrieval_result)
