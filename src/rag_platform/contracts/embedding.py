"""Module 2 contracts: Embedding provider abstraction and vector compatibility (Section 4)."""

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class EmbeddingTaskType(StrEnum):
    """Task roles aligned with Gemini Embedding API specifications."""

    RETRIEVAL_DOCUMENT = "RETRIEVAL_DOCUMENT"
    RETRIEVAL_QUERY = "RETRIEVAL_QUERY"


class EmbeddingIncompatibilityError(ValueError):
    """Raised when a query vector space does not match the target vector index signature."""


class EmbeddingSpaceSignature(BaseModel):
    """Versioned embedding space metadata required for index and query compatibility."""

    embedding_provider: str = Field(..., min_length=1, description="e.g., gemini_api")
    embedding_model: str = Field(..., min_length=1, description="e.g., text-embedding-004")
    embedding_model_version: str = Field(..., min_length=1, description="Explicit model version")
    embedding_dimension: int = Field(..., gt=0, description="Vector dimension size")
    chunking_version: str = Field(..., min_length=1, description="Compatible chunking version")


def assert_embedding_compatibility(
    query_signature: EmbeddingSpaceSignature,
    index_signature: EmbeddingSpaceSignature,
) -> None:
    """Enforce Invariant #5: query must be vectorized with the exact compatible index model."""
    if (
        query_signature.embedding_provider != index_signature.embedding_provider
        or query_signature.embedding_model != index_signature.embedding_model
        or query_signature.embedding_model_version != index_signature.embedding_model_version
        or query_signature.embedding_dimension != index_signature.embedding_dimension
        or query_signature.chunking_version != index_signature.chunking_version
    ):
        raise EmbeddingIncompatibilityError(
            f"Incompatible embedding spaces: query ({query_signature.embedding_provider}/"
            f"{query_signature.embedding_model}@{query_signature.embedding_model_version}, "
            f"dim={query_signature.embedding_dimension}, chunk={query_signature.chunking_version}) "
            f"!= index ({index_signature.embedding_provider}/"
            f"{index_signature.embedding_model}@{index_signature.embedding_model_version}, "
            f"dim={index_signature.embedding_dimension}, chunk={index_signature.chunking_version})"
        )


class VectorIndexRecord(BaseModel):
    """Indexed vector record with mandatory tenant metadata and space signature."""

    chunk_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)
    project_id: str = Field(..., min_length=1)
    case_id: str | None = Field(default=None)
    document_id: str = Field(..., min_length=1)
    vector: list[float] = Field(..., min_length=1)
    space_signature: EmbeddingSpaceSignature

    @model_validator(mode="after")
    def validate_vector_dimension(self) -> "VectorIndexRecord":
        """Ensure actual vector length matches declared embedding_dimension."""
        if len(self.vector) != self.space_signature.embedding_dimension:
            raise ValueError(
                f"Vector length ({len(self.vector)}) does not match declared "
                f"embedding_dimension ({self.space_signature.embedding_dimension})"
            )
        return self
