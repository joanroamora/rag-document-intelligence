"""Integration tests for the FastAPI REST service layer and multi-tenant HTTP guards."""

from fastapi.testclient import TestClient

from rag_platform.api import create_app
from rag_platform.contracts import AnswerEpistemicStatus, RetrievalMode


def test_health_and_missing_tenant_headers_rejected() -> None:
    """Verify GET /, GET /health, and HTTP 403 when tenant headers are missing."""
    client = TestClient(create_app())

    ui_res = client.get("/")
    assert ui_res.status_code == 200
    assert "text/html" in ui_res.headers["content-type"]
    assert "AETHER RAG — Enterprise Document Intelligence" in ui_res.text

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["indexed_chunks"] == 0

    # Missing headers rejected with 403 Forbidden
    resp_no_headers = client.post(
        "/v1/rag/ask",
        json={"question": "consulta sin credenciales de tenant"},
    )
    assert resp_no_headers.status_code == 403

    # Blank X-Project-Id rejected with 403 Forbidden
    resp_blank_proj = client.post(
        "/v1/rag/ask",
        headers={"X-Tenant-Id": "tenant-a", "X-Project-Id": "   "},
        json={"question": "consulta con proyecto vacío"},
    )
    assert resp_blank_proj.status_code == 403


def test_api_ingest_ask_isolation_and_delete_lifecycle() -> None:
    """Verify full HTTP lifecycle: ingest -> ask (hybrid & agentic) -> isolate -> delete."""
    client = TestClient(create_app())
    headers_a = {"X-Tenant-Id": "tenant-bufete-a", "X-Project-Id": "proj-litigios"}
    headers_b = {"X-Tenant-Id": "tenant-bufete-b", "X-Project-Id": "proj-litigios"}

    # 1. Reject unsupported file extension (.exe) with 400 Bad Request
    bad_ingest = client.post(
        "/v1/documents/ingest",
        headers=headers_a,
        json={
            "job_id": "job-bad",
            "document_id": "doc-bad",
            "filename": "virus.exe",
            "raw_content_text": "contenido",
            "pages": [{"page_number": 1, "digital_text": "texto", "block_type": "paragraph"}],
        },
    )
    assert bad_ingest.status_code == 400

    # 2. Valid 2-page PDF ingestion under tenant-bufete-a
    ingest_res = client.post(
        "/v1/documents/ingest",
        headers=headers_a,
        json={
            "job_id": "job-100",
            "document_id": "doc-laudo-100",
            "filename": "laudo_arbitral.pdf",
            "case_id": "arb-2026",
            "raw_content_text": "%PDF-1.7 laudo arbitral",
            "pages": [
                {
                    "page_number": 1,
                    "digital_text": (
                        "Artículo Primero: El tribunal arbitral condena al pago de "
                        "500,000 USD por lucro cesante."
                    ),
                    "block_type": "header",
                },
                {
                    "page_number": 2,
                    "digital_text": (
                        "Artículo Segundo: Costas procesales fijadas en 30,000 USD "
                        "con timbre [ilegible]."
                    ),
                    "block_type": "header",
                },
            ],
        },
    )
    assert ingest_res.status_code == 201
    ingest_data = ingest_res.json()
    assert ingest_data["total_pages"] == 2
    assert ingest_data["chunks_indexed"] == 2

    # 3. Verify health endpoint reflects 2 indexed chunks for tenant-bufete-a
    health_after = client.get("/health").json()
    assert health_after["indexed_chunks"] == 2
    assert health_after["tenant_counts"] == {"tenant-bufete-a": 2}

    # 4. Ask in STANDARD_HYBRID mode under tenant-bufete-a
    ask_a = client.post(
        "/v1/rag/ask",
        headers=headers_a,
        json={
            "question": "condena al pago de 500,000 USD por lucro cesante",
            "case_id": "arb-2026",
            "mode": RetrievalMode.STANDARD_HYBRID,
            "top_k": 1,
        },
    )
    assert ask_a.status_code == 200
    body_a = ask_a.json()
    assert body_a["epistemic_status"] == AnswerEpistemicStatus.GROUNDED_CERTAIN
    assert "500,000 USD" in body_a["synthesized_answer"]
    assert len(body_a["citations"]) == 1

    # 5. Ask in DEEP_AGENTIC mode hitting uncertain page 2
    ask_agentic = client.post(
        "/v1/rag/ask",
        headers=headers_a,
        json={
            "question": "¿Cuáles son las costas procesales de 30,000 USD?",
            "mode": RetrievalMode.DEEP_AGENTIC,
            "top_k": 1,
        },
    )
    assert ask_agentic.status_code == 200
    assert (
        ask_agentic.json()["epistemic_status"]
        == AnswerEpistemicStatus.GROUNDED_WITH_UNCERTAINTY
    )

    # 6. Cross-tenant ask from tenant-bufete-b must abstain with zero data leakage
    ask_b = client.post(
        "/v1/rag/ask",
        headers=headers_b,
        json={"question": "condena al pago de 500,000 USD por lucro cesante"},
    )
    assert ask_b.status_code == 200
    assert (
        ask_b.json()["epistemic_status"]
        == AnswerEpistemicStatus.ABSTAINED_INSUFFICIENT_EVIDENCE
    )
    assert ask_b.json()["citations"] == []

    # 7. Delete document under tenant-bufete-a and verify cleanup
    del_res = client.delete("/v1/documents/doc-laudo-100", headers=headers_a)
    assert del_res.status_code == 200
    assert del_res.json()["deleted_vector_chunks"] == 2
    assert del_res.json()["deleted_lexical_chunks"] == 2
    assert client.get("/health").json()["indexed_chunks"] == 0
