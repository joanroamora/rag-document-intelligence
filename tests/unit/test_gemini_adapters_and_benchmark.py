"""Unit and integration tests for Feature 8: Gemini Free Tier adapters and RAG Benchmark suite."""

import json

import httpx
import pytest
from pydantic import ValidationError

from rag_platform import RAGPlatformOrchestrator
from rag_platform.adapters import (
    GeminiClientConfig,
    GeminiGroundedSynthesizer,
    GeminiMultimodalRouteExtractor,
    GeminiRESTClient,
)
from rag_platform.api import build_default_orchestrator
from rag_platform.benchmark import (
    BenchmarkQueryCase,
    RAGBenchmarkRunner,
    compute_cer,
    compute_ndcg_at_k,
    compute_recall_at_k,
    compute_reciprocal_rank,
    compute_wer,
)
from rag_platform.contracts import (
    AnswerEpistemicStatus,
    EmbeddingTaskType,
    ExtractionRoute,
    RetrievalMode,
    TenantScope,
)
from rag_platform.generation import GroundedAnswerGenerator
from rag_platform.indexing import (
    EmbedderConfig,
    EmbeddingQuotaExceededError,
    GeminiFreeTierEmbedder,
)
from rag_platform.processing import RawPageInput, RoutingDecision


def test_gemini_client_config_and_rest_embeddings_transport() -> None:
    """Verify Free Tier guard on GeminiClientConfig and batchEmbedContents HTTP payload."""
    with pytest.raises(ValidationError, match="Paid tier is strictly prohibited"):
        GeminiClientConfig(api_key="test-key", allow_paid_tier=True)

    with pytest.raises(ValidationError, match="api_key cannot be blank"):
        GeminiClientConfig(api_key="   ")

    should_rate_limit = False

    def handler(request: httpx.Request) -> httpx.Response:
        if should_rate_limit:
            return httpx.Response(status_code=429, json={"error": "Resource Exhausted"})
        assert "batchEmbedContents" in str(request.url)
        body = json.loads(request.content.decode())
        reqs = body["requests"]
        return httpx.Response(
            status_code=200,
            json={"embeddings": [{"values": [0.6, 0.8, 0.0, 0.0]} for _ in reqs]},
        )

    transport = httpx.MockTransport(handler)
    client = GeminiRESTClient(
        config=GeminiClientConfig(api_key="AIzaSyMockFreeTierKey"),
        http_client=httpx.Client(transport=transport),
    )
    embedder = GeminiFreeTierEmbedder(
        config=EmbedderConfig(dimension=4, max_retries=0),
        transport_fn=client.batch_embed_contents,
    )

    vectors = embedder.embed_texts(
        ["cláusula primera", "cláusula segunda"],
        task_type=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
    )
    assert len(vectors) == 2
    assert len(vectors[0]) == 4

    should_rate_limit = True
    with pytest.raises(EmbeddingQuotaExceededError, match="HTTP 429"):
        embedder.embed_texts(["consulta bloqueada por 429"])


def test_gemini_multimodal_extractor_and_degraded_429_fallback() -> None:
    """Verify Route D Gemini Flash JSON extraction and degraded fallback on 429."""
    mode = "ok"

    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        if mode == "429":
            return httpx.Response(status_code=429, json={"error": "Quota exceeded"})
        structured_output = {
            "observed_text": "| Partida | Monto |\n| Obra Civil | $95,000 |",
            "extractor_confidence": 0.92,
            "inferred_hypotheses": [
                {
                    "text": "Subtotal calculado sin IVA",
                    "confidence": 0.78,
                    "rationale": "Columna de impuestos vacía",
                }
            ],
        }
        return httpx.Response(
            status_code=200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": json.dumps(structured_output)}]
                        }
                    }
                ]
            },
        )

    client = GeminiRESTClient(
        config=GeminiClientConfig(api_key="AIzaSyMockFreeTierKey"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    extractor = GeminiMultimodalRouteExtractor(client)
    page = RawPageInput(
        page_number=1,
        digital_text="Tabla parcial",
        has_complex_tables_or_diagrams=True,
        block_type="table",
    )
    decision_d = RoutingDecision(
        page_number=1,
        selected_route=ExtractionRoute.ROUTE_D_GEMINI_FLASH,
        provider="gemini_api",
        model_version="gemini-2.5-flash",
        rationale="Complex table",
    )

    payload_ok = extractor.extract_page(page, decision_d)
    assert "$95,000" in payload_ok.observed_text
    assert payload_ok.extractor_confidence == 0.92
    assert len(payload_ok.inferred_hypotheses) == 1
    assert payload_ok.inferred_hypotheses[0].text == "Subtotal calculado sin IVA"

    # When 429 occurs, degrade gracefully with [ilegible] and low confidence (0.40)
    mode = "429"
    payload_degraded = extractor.extract_page(page, decision_d)
    assert "[ilegible]" in payload_degraded.observed_text
    assert payload_degraded.extractor_confidence == 0.40


def test_gemini_grounded_synthesizer_and_fallback() -> None:
    """Verify GeminiGroundedSynthesizer structured synthesis and 429 extractive fallback."""
    orchestrator = build_default_orchestrator()
    scope = TenantScope(tenant_id="tenant-synth", project_id="proj-1")

    _receipt, _doc, chunks = orchestrator.ingest_document(
        job_id="job-s1",
        document_id="doc-s1",
        filename="acta_directorio.pdf",
        scope=scope,
        bucket_name="bitcitychamp-project-rag-documents-dev",
        byte_stream=[b"%PDF-1.7 acta directorio"],
        pages=[
            RawPageInput(
                page_number=1,
                digital_text="Acuerdo Unánime: Se aprueba dividendo de 120,000 USD.",
                block_type="header",
            )
        ],
    )
    valid_cid = chunks[0].chunk_id
    retrieval_res = orchestrator.hybrid_retriever.retrieve(
        query_text="aprueba dividendo 120,000 USD",
        scope=scope,
    )

    mode = "ok"

    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        if mode == "429":
            return httpx.Response(status_code=429, json={"error": "Rate limit"})
        llm_json = {
            "synthesized_answer": (
                f"El directorio aprobó un dividendo de 120,000 USD [{valid_cid}]."
            ),
            "has_conflict": False,
            "claims": [
                {
                    "statement": "Se aprueba dividendo de 120,000 USD.",
                    "cited_chunk_ids": [valid_cid],
                    "contains_uncertainty": False,
                }
            ],
        }
        return httpx.Response(
            status_code=200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": json.dumps(llm_json)}]}}
                ]
            },
        )

    client = GeminiRESTClient(
        config=GeminiClientConfig(api_key="AIzaSyMockFreeTierKey"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    gen = GroundedAnswerGenerator(synthesizer=GeminiGroundedSynthesizer(client))

    ans_ok = gen.generate(retrieval_res)
    assert ans_ok.epistemic_status == AnswerEpistemicStatus.GROUNDED_CERTAIN
    assert "120,000 USD" in ans_ok.synthesized_answer

    # Trigger 429 -> seamlessly falls back to ExtractiveGroundedSynthesizer
    mode = "429"
    ans_fallback = gen.generate(retrieval_res)
    assert ans_fallback.epistemic_status == AnswerEpistemicStatus.GROUNDED_CERTAIN
    assert len(ans_fallback.claims) == 1


def test_ocr_cer_wer_and_rag_benchmark_runner_suite() -> None:
    """Verify CER, WER, Recall@K, MRR, nDCG@K, and full RAGBenchmarkRunner execution."""
    assert compute_cer("Contrato de obra", "Contrato de obra") == 0.0
    assert compute_wer("Contrato de obra pública", "Contrato de obra privada") == 0.25
    assert compute_recall_at_k(["c-1", "c-2"], {"c-2", "c-3"}, k=2) == 0.5
    assert compute_reciprocal_rank(["c-9", "c-2", "c-1"], {"c-2"}) == 0.5
    assert compute_ndcg_at_k(["c-1", "c-2"], {"c-1"}, k=2) == 1.0

    orchestrator: RAGPlatformOrchestrator = build_default_orchestrator()
    scope = TenantScope(tenant_id="tenant-bench", project_id="proj-eval", case_id="case-b1")

    _receipt, _doc, chunks = orchestrator.ingest_document(
        job_id="job-bench",
        document_id="doc-bench-01",
        filename="pliego_licitacion.pdf",
        scope=scope,
        bucket_name="bitcitychamp-project-rag-documents-dev",
        byte_stream=[b"%PDF-1.7 pliego licitacion"],
        pages=[
            RawPageInput(
                page_number=1,
                digital_text="Sección A: Garantía de seriedad de oferta por 45,000 USD.",
                block_type="header",
            ),
            RawPageInput(
                page_number=2,
                digital_text="Sección B: Plazo máximo de ejecución de obra de 180 días.",
                block_type="header",
            ),
        ],
    )

    runner = RAGBenchmarkRunner(orchestrator)
    cases = [
        BenchmarkQueryCase(
            case_name="garantia_seriedad",
            question="garantía de seriedad de oferta por 45,000 USD",
            scope=scope,
            expected_chunk_ids=[chunks[0].chunk_id],
            mode=RetrievalMode.STANDARD_HYBRID,
            k=1,
        ),
        BenchmarkQueryCase(
            case_name="plazo_ejecucion",
            question="plazo máximo de ejecución de obra de 180 días",
            scope=scope,
            expected_chunk_ids=[chunks[1].chunk_id],
            mode=RetrievalMode.DEEP_AGENTIC,
            k=1,
        ),
    ]

    report = runner.evaluate_suite(cases)
    assert report.total_cases == 2
    assert report.mean_recall_at_k == 1.0
    assert report.mrr == 1.0
    assert report.mean_ndcg_at_k == 1.0
    assert report.mean_citation_precision == 1.0
