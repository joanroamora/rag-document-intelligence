"""Unit and End-to-End integration tests for Module 4 and RAGPlatformOrchestrator."""

from collections.abc import Sequence

import pytest
from pydantic import ValidationError

from rag_platform.contracts import (
    AnswerEpistemicStatus,
    EpistemicSpan,
    EpistemicStatus,
    ExtractionRoute,
    GroundedClaim,
    RetrievalMode,
    TenantScope,
)
from rag_platform.generation import (
    CitationVerificationError,
    GeneratorConfig,
    GroundedAnswerGenerator,
)
from rag_platform.indexing import (
    DeterministicHashEmbedder,
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
    RoutingDecision,
)
from rag_platform.retrieval import BM25LexicalIndex, ExpandedEvidenceItem, HybridRetriever


class _FullPlatformMockExtractor:
    """Mock extractor for full Module 1 -> Module 4 end-to-end testing."""

    def extract_page(
        self,
        page: RawPageInput,
        decision: RoutingDecision,
    ) -> ExtractedPagePayload:
        if decision.selected_route == ExtractionRoute.ROUTE_D_GEMINI_FLASH:
            hypothesis = EpistemicSpan(
                text="Posible ajuste inflacionario del 12% anual",
                status=EpistemicStatus.INFERRED_HYPOTHESIS,
                confidence=0.72,
                rationale="Deducción por nota al margen en tabla de tarifas",
            )
            return ExtractedPagePayload(
                observed_text=page.digital_text or "[ilegible]",
                extractor_confidence=0.91,
                inferred_hypotheses=[hypothesis],
                block_type=page.block_type,
            )
        return ExtractedPagePayload(
            observed_text=page.digital_text or "[ilegible]",
            extractor_confidence=0.97,
            block_type=page.block_type,
        )


def _build_orchestrator() -> RAGPlatformOrchestrator:
    """Instantiate a complete RAGPlatformOrchestrator with in-memory stores."""
    doc_pipeline = DocumentProcessingPipeline(
        normalizer=DocumentNormalizer(
            router=IntelligentExtractionRouter(),
            extractor=_FullPlatformMockExtractor(),
        )
    )
    hybrid_retriever = HybridRetriever(
        vector_service=VectorIndexingService(
            embedder=DeterministicHashEmbedder(),
            vector_store=InMemoryMultiTenantVectorStore(),
        ),
        lexical_index=BM25LexicalIndex(),
    )
    return RAGPlatformOrchestrator(
        document_pipeline=doc_pipeline,
        hybrid_retriever=hybrid_retriever,
    )


def test_generator_free_tier_guard_and_citation_guard() -> None:
    """Verify Invariant #4 (Free Tier) and Citation Guard against hallucinated citations."""
    with pytest.raises(ValidationError, match="Paid tier is strictly prohibited"):
        GeneratorConfig(allow_paid_tier=True)

    orchestrator = _build_orchestrator()
    scope = TenantScope(tenant_id="tenant-bank", project_id="proj-credit", case_id="case-01")

    orchestrator.ingest_document(
        job_id="job-1",
        document_id="doc-pagare",
        filename="pagare_hipotecario.pdf",
        scope=scope,
        bucket_name="bitcitychamp-project-rag-documents-dev",
        byte_stream=[b"%PDF-1.7 pagare hipotecario"],
        pages=[
            RawPageInput(
                page_number=1,
                digital_text="Pagaré hipotecario por valor de 250,000 USD con tasa fija.",
                has_complex_tables_or_diagrams=True,
                block_type="table",
            )
        ],
    )

    retrieval_res = orchestrator.hybrid_retriever.retrieve(
        query_text="pagaré hipotecario valor 250,000 USD",
        scope=scope,
    )
    assert retrieval_res.is_evidence_sufficient is True

    # 1. Synthesizer that hallucinates a non-existent chunk_id must fail Citation Guard
    class _HallucinatingSynthesizer:
        def synthesize(
            self,
            question: str,
            evidence_items: Sequence[ExpandedEvidenceItem],
            config: GeneratorConfig,
        ) -> tuple[str, list[GroundedClaim], bool]:
            _ = (question, evidence_items, config)
            return (
                "Respuesta inventada",
                [GroundedClaim(statement="Dato falso", cited_chunk_ids=["chunk-fantasma-999"])],
                False,
            )

    bad_gen = GroundedAnswerGenerator(synthesizer=_HallucinatingSynthesizer())
    with pytest.raises(CitationVerificationError, match="Hallucinated or unauthorized citation"):
        bad_gen.generate(retrieval_res)

    # 2. Synthesizer that leaks an inferred hypothesis into observed facts must fail Invariant #2
    class _LeakyHypothesisSynthesizer:
        def synthesize(
            self,
            question: str,
            evidence_items: Sequence[ExpandedEvidenceItem],
            config: GeneratorConfig,
        ) -> tuple[str, list[GroundedClaim], bool]:
            _ = (question, config)
            valid_cid = evidence_items[0].citation.chunk_id
            return (
                "El documento afirma un posible ajuste inflacionario del 12% anual.",
                [
                    GroundedClaim(
                        statement="El pagaré es de 250,000 USD.",
                        cited_chunk_ids=[valid_cid],
                    )
                ],
                False,
            )

    leaky_gen = GroundedAnswerGenerator(synthesizer=_LeakyHypothesisSynthesizer())
    with pytest.raises(CitationVerificationError, match="Epistemological violation"):
        leaky_gen.generate(retrieval_res)


def test_end_to_end_orchestrator_m1_to_m4_and_safe_abstention() -> None:
    """Verify full M1 -> M2 -> M3 -> M4 flow: ingestion, cited answer, uncertainty, abstention."""
    orchestrator = _build_orchestrator()
    scope_a = TenantScope(tenant_id="tenant-legal", project_id="proj-penal", case_id="exp-90")
    scope_b = TenantScope(tenant_id="tenant-other", project_id="proj-penal", case_id="exp-90")

    _receipt, _norm_doc, chunks = orchestrator.ingest_document(
        job_id="job-90",
        document_id="doc-sentencia-90",
        filename="sentencia_apelacion.pdf",
        scope=scope_a,
        bucket_name="bitcitychamp-project-rag-documents-dev",
        byte_stream=[b"%PDF-1.7 sentencia apelacion"],
        pages=[
            RawPageInput(
                page_number=1,
                digital_text="Sección Primera: El tribunal declara fundada la apelación civil.",
                block_type="header",
            ),
            RawPageInput(
                page_number=2,
                digital_text=(
                    "Tabla de liquidación: Indemnización de 80,000 USD con sello [ilegible]."
                ),
                has_complex_tables_or_diagrams=True,
                block_type="table",
            ),
        ],
    )
    assert len(chunks) == 2

    # Standard Hybrid Query on Page 1 (Clean Digital Text -> GROUNDED_CERTAIN)
    ans_clean = orchestrator.ask(
        question="tribunal declara fundada apelación civil",
        scope=scope_a,
        mode=RetrievalMode.STANDARD_HYBRID,
        top_k=1,
    )
    assert ans_clean.epistemic_status == AnswerEpistemicStatus.GROUNDED_CERTAIN
    assert len(ans_clean.claims) == 1
    assert len(ans_clean.citations) == 1
    assert "apelación civil" in ans_clean.synthesized_answer

    # Deep Agentic Query on Page 2 (Contains [ilegible] + inferred hypothesis)
    ans_uncertain = orchestrator.ask(
        question="¿Cuál es la tabla de liquidación e indemnización de 80,000 USD?",
        scope=scope_a,
        mode=RetrievalMode.DEEP_AGENTIC,
        top_k=1,
    )
    assert ans_uncertain.epistemic_status == AnswerEpistemicStatus.GROUNDED_WITH_UNCERTAINTY
    assert len(ans_uncertain.uncertainty_warnings) >= 1
    assert len(ans_uncertain.segregated_inferential_hypotheses) == 1
    assert "ajuste inflacionario" in ans_uncertain.segregated_inferential_hypotheses[0]
    assert "ajuste inflacionario" not in ans_uncertain.synthesized_answer

    # Cross-tenant query from scope_b must abstain with zero leakage
    ans_other_tenant = orchestrator.ask(
        question="tribunal declara fundada apelación civil indemnización",
        scope=scope_b,
        mode=RetrievalMode.STANDARD_HYBRID,
    )
    assert (
        ans_other_tenant.epistemic_status
        == AnswerEpistemicStatus.ABSTAINED_INSUFFICIENT_EVIDENCE
    )
    assert ans_other_tenant.claims == []
    assert ans_other_tenant.citations == []
