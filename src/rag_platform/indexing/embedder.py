"""Module 2: Pluggable Embedding Providers and Gemini API Free Tier quota guards."""

import hashlib
import math
import re
from collections.abc import Callable, Sequence
from typing import Protocol

from pydantic import BaseModel, Field, model_validator

from rag_platform.contracts import EmbeddingSpaceSignature, EmbeddingTaskType

BatchTransportFn = Callable[
    [list[str], EmbeddingTaskType, "EmbedderConfig"],
    list[list[float]],
]


class EmbeddingQuotaExceededError(RuntimeError):
    """Raised when Gemini API Free Tier quota is exhausted or circuit breaker is open."""


class EmbedderConfig(BaseModel):
    """Configuration for embedding generation enforcing Free Tier and batch constraints."""

    provider_name: str = Field(default="gemini_api", min_length=1)
    model_name: str = Field(default="gemini-embedding-001", min_length=1)
    model_version: str = Field(default="001", min_length=1)
    dimension: int = Field(default=768, gt=0, le=3072)
    chunking_version: str = Field(default="1.0.0", min_length=1)
    max_batch_size: int = Field(default=32, ge=1, le=100)
    max_retries: int = Field(default=3, ge=0, le=5)
    circuit_breaker_failure_threshold: int = Field(default=3, ge=1, le=10)
    allow_paid_tier: bool = Field(
        default=False,
        description="Must remain False to enforce Invariant #4 (Zero automatic billing)",
    )

    @model_validator(mode="after")
    def enforce_free_tier_invariant(self) -> "EmbedderConfig":
        """Enforce Invariant #4: Never enable paid billing tier automatically."""
        if self.allow_paid_tier:
            raise ValueError(
                "Paid tier is strictly prohibited by project governance (Invariant #4). "
                "Use Gemini API Free Tier or open-source CPU fallback."
            )
        return self

    def to_space_signature(self) -> EmbeddingSpaceSignature:
        """Build the canonical EmbeddingSpaceSignature for compatibility validation."""
        return EmbeddingSpaceSignature(
            embedding_provider=self.provider_name,
            embedding_model=self.model_name,
            embedding_model_version=self.model_version,
            embedding_dimension=self.dimension,
            chunking_version=self.chunking_version,
        )


class EmbeddingProvider(Protocol):
    """Pluggable interface for embedding providers (Gemini API Free Tier, Qwen3, BGE-M3)."""

    def get_space_signature(self) -> EmbeddingSpaceSignature:
        """Return the versioned signature of the vector space produced by this provider."""
        ...

    def embed_texts(
        self,
        texts: Sequence[str],
        task_type: EmbeddingTaskType = EmbeddingTaskType.RETRIEVAL_DOCUMENT,
    ) -> list[list[float]]:
        """Vectorize a sequence of texts using the specified retrieval task role."""
        ...


def _l2_normalize(vector: list[float]) -> list[float]:
    """Normalize a vector to unit L2 length for cosine similarity calculations."""
    norm = math.sqrt(sum(val * val for val in vector))
    if norm == 0.0:
        return vector
    return [round(val / norm, 8) for val in vector]


class DeterministicHashEmbedder:
    """Zero-dependency CPU feature-hashing embedder for deterministic CI tests and fallback."""

    def __init__(self, config: EmbedderConfig | None = None) -> None:
        self.config = config or EmbedderConfig(
            provider_name="local_cpu_hash",
            model_name="sha256-feature-hash",
            model_version="1.0.0",
            dimension=64,
        )

    def get_space_signature(self) -> EmbeddingSpaceSignature:
        """Return the versioned embedding space signature."""
        return self.config.to_space_signature()

    def embed_texts(
        self,
        texts: Sequence[str],
        task_type: EmbeddingTaskType = EmbeddingTaskType.RETRIEVAL_DOCUMENT,
    ) -> list[list[float]]:
        """Project tokenized text features into a normalized vector of configured dimension."""
        dim = self.config.dimension
        results: list[list[float]] = []

        for text in texts:
            if not text or not text.strip():
                raise ValueError("Cannot embed empty text")

            vec = [0.0] * dim
            tokens = re.findall(r"\w+", text.lower())
            if not tokens:
                tokens = [text.strip().lower()]

            for token in tokens:
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                bucket = int.from_bytes(digest[:4], "big") % dim
                sign = 1.0 if (digest[4] % 2 == 0) else -1.0
                vec[bucket] += sign

            # Guarantee non-zero vector even if token signs cancel out
            if all(v == 0.0 for v in vec):
                fallback_hash = hashlib.sha256(
                    f"{task_type}:{text}".encode("utf-8")
                ).digest()
                vec[fallback_hash[0] % dim] = 1.0

            results.append(_l2_normalize(vec))

        return results


class GeminiFreeTierEmbedder:
    """Gemini Embedding API Free Tier provider with batching, retries, and circuit breaker."""

    def __init__(
        self,
        config: EmbedderConfig | None = None,
        transport_fn: BatchTransportFn | None = None,
    ) -> None:
        self.config = config or EmbedderConfig()
        self._transport_fn = transport_fn
        self._consecutive_failures = 0

    @property
    def is_circuit_open(self) -> bool:
        """Return True when consecutive failures have tripped the circuit breaker."""
        return self._consecutive_failures >= self.config.circuit_breaker_failure_threshold

    def reset_circuit_breaker(self) -> None:
        """Reset consecutive failure counter after manual or scheduled recovery."""
        self._consecutive_failures = 0

    def get_space_signature(self) -> EmbeddingSpaceSignature:
        """Return the versioned signature for Gemini Embedding API."""
        return self.config.to_space_signature()

    def embed_texts(
        self,
        texts: Sequence[str],
        task_type: EmbeddingTaskType = EmbeddingTaskType.RETRIEVAL_DOCUMENT,
    ) -> list[list[float]]:
        """Vectorize texts in bounded batches with retry and circuit breaker protection."""
        if not texts:
            return []

        for text in texts:
            if not text or not text.strip():
                raise ValueError("Cannot embed empty or whitespace-only text")

        if self.is_circuit_open:
            raise EmbeddingQuotaExceededError(
                f"Circuit breaker is OPEN for {self.config.model_name} after "
                f"{self._consecutive_failures} consecutive failures."
            )

        if self._transport_fn is None:
            raise EmbeddingQuotaExceededError(
                "No Gemini API transport configured. Inject transport_fn or use "
                "DeterministicHashEmbedder in offline/CI environments."
            )

        all_vectors: list[list[float]] = []
        batch_size = self.config.max_batch_size

        for start_idx in range(0, len(texts), batch_size):
            batch = list(texts[start_idx : start_idx + batch_size])
            batch_vectors = self._execute_batch_with_retry(batch, task_type)
            all_vectors.extend(batch_vectors)

        return all_vectors

    def _execute_batch_with_retry(
        self,
        batch: list[str],
        task_type: EmbeddingTaskType,
    ) -> list[list[float]]:
        """Execute a single batch request with retry accounting and circuit breaker guard."""
        assert self._transport_fn is not None
        max_attempts = self.config.max_retries + 1
        last_error: Exception | None = None

        for _attempt in range(max_attempts):
            try:
                vectors = self._transport_fn(batch, task_type, self.config)
                if len(vectors) != len(batch):
                    raise ValueError(
                        f"Provider returned {len(vectors)} vectors for batch of {len(batch)}"
                    )
                for vec in vectors:
                    if len(vec) != self.config.dimension:
                        raise ValueError(
                            f"Vector dimension {len(vec)} does not match expected "
                            f"{self.config.dimension}"
                        )
                self._consecutive_failures = 0
                return [_l2_normalize(v) for v in vectors]
            except ValueError:
                raise
            except Exception as exc:
                last_error = exc
                self._consecutive_failures += 1
                if self.is_circuit_open:
                    break

        raise EmbeddingQuotaExceededError(
            f"Gemini Free Tier embedding failed after retries "
            f"(consecutive_failures={self._consecutive_failures}): {last_error}"
        ) from last_error
