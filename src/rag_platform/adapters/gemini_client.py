"""Gemini Developer API Free Tier HTTP client and adapters for Modules 1, 2, and 4."""

import json
from collections.abc import Sequence
from typing import Any

import httpx
from pydantic import BaseModel, Field, model_validator

from rag_platform.contracts import (
    EmbeddingTaskType,
    EpistemicSpan,
    EpistemicStatus,
    ExtractionRoute,
    GroundedClaim,
)
from rag_platform.generation import ExtractiveGroundedSynthesizer, GeneratorConfig
from rag_platform.indexing import EmbedderConfig, EmbeddingQuotaExceededError
from rag_platform.processing import ExtractedPagePayload, RawPageInput, RoutingDecision
from rag_platform.retrieval import ExpandedEvidenceItem


class GeminiClientConfig(BaseModel):
    """Configuration for Gemini Developer API Free Tier REST transport."""

    api_key: str = Field(..., min_length=1, repr=False)
    base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta",
        min_length=1,
    )
    timeout_seconds: float = Field(default=15.0, gt=0.0, le=60.0)
    allow_paid_tier: bool = Field(
        default=False,
        description="Must remain False to enforce Invariant #4 (Zero automatic billing)",
    )

    @model_validator(mode="after")
    def enforce_free_tier_invariant(self) -> "GeminiClientConfig":
        """Enforce Invariant #4: Never enable paid billing tier automatically."""
        if self.allow_paid_tier:
            raise ValueError(
                "Paid tier is strictly prohibited by project governance (Invariant #4)."
            )
        if not self.api_key.strip():
            raise ValueError("api_key cannot be blank or whitespace")
        return self


class GeminiRESTClient:
    """Lightweight HTTPX client for Gemini API Free Tier embeddings and generation."""

    def __init__(
        self,
        config: GeminiClientConfig,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.config = config
        self._client = http_client or httpx.Client(timeout=config.timeout_seconds)

    def batch_embed_contents(
        self,
        batch: list[str],
        task_type: EmbeddingTaskType,
        embedder_cfg: EmbedderConfig,
    ) -> list[list[float]]:
        """Execute batchEmbedContents against Gemini Embedding API Free Tier."""
        model_path = f"models/{embedder_cfg.model_name}"
        url = f"{self.config.base_url}/{model_path}:batchEmbedContents"
        requests_payload = [
            {
                "model": model_path,
                "content": {"parts": [{"text": text}]},
                "taskType": str(task_type),
                "outputDimensionality": embedder_cfg.dimension,
            }
            for text in batch
        ]

        response = self._client.post(
            url,
            params={"key": self.config.api_key},
            json={"requests": requests_payload},
        )
        if response.status_code == 429 or response.status_code >= 500:
            raise EmbeddingQuotaExceededError(
                f"Gemini API HTTP {response.status_code}: Free Tier rate limit or server error"
            )
        response.raise_for_status()

        data = response.json()
        embeddings_raw = data.get("embeddings", [])
        return [list(item.get("values", [])) for item in embeddings_raw]

    def generate_structured_json(
        self,
        *,
        model_id: str,
        system_instruction: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        """Execute generateContent with deterministic JSON response mime type."""
        url = f"{self.config.base_url}/models/{model_id}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "responseMimeType": "application/json",
            },
        }
        response = self._client.post(
            url,
            params={"key": self.config.api_key},
            json=payload,
        )
        if response.status_code == 429 or response.status_code >= 500:
            raise EmbeddingQuotaExceededError(
                f"Gemini API HTTP {response.status_code} on model {model_id}"
            )
        response.raise_for_status()

        body = response.json()
        candidates = body.get("candidates", [])
        if not candidates:
            raise ValueError("Gemini API returned no candidates")
        parts = candidates[0].get("content", {}).get("parts", [])
        raw_text = parts[0].get("text", "{}") if parts else "{}"
        parsed = json.loads(raw_text)
        if not isinstance(parsed, dict):
            raise ValueError("Expected JSON object from Gemini structured output")
        return parsed


class GeminiMultimodalRouteExtractor:
    """Module 1 RouteExtractorBackend with Gemini Flash/Pro vision and degraded fallback."""

    def __init__(self, gemini_client: GeminiRESTClient) -> None:
        self.gemini_client = gemini_client

    def extract_page(
        self,
        page: RawPageInput,
        decision: RoutingDecision,
    ) -> ExtractedPagePayload:
        """Extract page content using local/container OCR or Gemini Flash/Pro on Routes D-E."""
        route = decision.selected_route
        if route in (
            ExtractionRoute.ROUTE_A_DIGITAL_TEXT,
            ExtractionRoute.ROUTE_B_OPEN_SOURCE_OCR,
            ExtractionRoute.ROUTE_C_ENHANCED_OCR,
        ):
            text = page.digital_text or "[ilegible]"
            conf = 0.96 if page.digital_text else 0.45
            return ExtractedPagePayload(
                observed_text=text,
                extractor_confidence=conf,
                block_type=page.block_type,
            )

        system_prompt = (
            "Eres un extractor documental forense con seguridad epistemológica estricta. "
            "Separa siempre observed_text (transcripción literal, marcando [ilegible] donde "
            "no pueda leerse) de inferred_hypotheses (deducciones contextuales)."
        )
        user_prompt = (
            f"Extrae la página {page.page_number} (tipo: {page.block_type}). "
            f"Texto base detectado: {page.digital_text or '[sin capa digital]'}"
        )

        try:
            result = self.gemini_client.generate_structured_json(
                model_id=decision.model_version,
                system_instruction=system_prompt,
                user_prompt=user_prompt,
            )
            observed = str(result.get("observed_text", "")).strip() or "[ilegible]"
            confidence = float(result.get("extractor_confidence", 0.88))
            raw_hypotheses = result.get("inferred_hypotheses", [])
            hypotheses: list[EpistemicSpan] = []
            for h_item in raw_hypotheses:
                if isinstance(h_item, dict) and h_item.get("text"):
                    hypotheses.append(
                        EpistemicSpan(
                            text=str(h_item["text"]),
                            status=EpistemicStatus.INFERRED_HYPOTHESIS,
                            confidence=float(h_item.get("confidence", 0.75)),
                            rationale=str(h_item.get("rationale", "Inferencia multimodal")),
                        )
                    )
            return ExtractedPagePayload(
                observed_text=observed,
                extractor_confidence=max(0.0, min(1.0, confidence)),
                inferred_hypotheses=hypotheses,
                block_type=page.block_type,
            )
        except Exception:
            # Degraded mode when Free Tier quota is exhausted: preserve observed text or mark
            # [ilegible] with low confidence so the page is routed to PENDING_REVIEW
            fallback_text = (
                f"{page.digital_text} [ilegible]"
                if page.digital_text
                else "[ilegible]"
            )
            return ExtractedPagePayload(
                observed_text=fallback_text,
                extractor_confidence=0.40,
                block_type=page.block_type,
            )


class GeminiGroundedSynthesizer:
    """Module 4 AnswerSynthesisBackend using Gemini Flash with extractive fallback on 429."""

    def __init__(self, gemini_client: GeminiRESTClient) -> None:
        self.gemini_client = gemini_client
        self._fallback = ExtractiveGroundedSynthesizer()

    def synthesize(
        self,
        question: str,
        evidence_items: Sequence[ExpandedEvidenceItem],
        config: GeneratorConfig,
    ) -> tuple[str, list[GroundedClaim], bool]:
        """Synthesize cited claims via Gemini Flash or degrade gracefully to extractive mode."""
        evidence_block = "\n\n".join(
            item.render_expanded_context() for item in evidence_items
        )
        system_prompt = (
            "Responde únicamente con hechos observados en las evidencias proporcionadas. "
            "Jamás incluyas las notas marcadas como HIPÓTESIS INFERIDA dentro de claims "
            "ni en synthesized_answer. Cita siempre chunk_ids exactos."
        )
        user_prompt = f"Pregunta: {question}\n\nEvidencias:\n{evidence_block}"

        try:
            data = self.gemini_client.generate_structured_json(
                model_id=config.model_version,
                system_instruction=system_prompt,
                user_prompt=user_prompt,
            )
            synthesized_answer = str(data.get("synthesized_answer", "")).strip()
            has_conflict = bool(data.get("has_conflict", False))
            raw_claims = data.get("claims", [])
            claims: list[GroundedClaim] = [
                GroundedClaim(
                    statement=str(c["statement"]),
                    cited_chunk_ids=[str(cid) for cid in c.get("cited_chunk_ids", [])],
                    contains_uncertainty=bool(c.get("contains_uncertainty", False)),
                )
                for c in raw_claims
                if isinstance(c, dict) and c.get("statement") and c.get("cited_chunk_ids")
            ]
            if not synthesized_answer or not claims:
                return self._fallback.synthesize(question, evidence_items, config)
            return synthesized_answer, claims, has_conflict
        except Exception:
            # Degraded mode on Free Tier 429 quota exhaustion
            return self._fallback.synthesize(question, evidence_items, config)
