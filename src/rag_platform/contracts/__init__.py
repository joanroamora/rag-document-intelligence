"""Canonical versioned contracts for Modules 1 through 4."""

from rag_platform.contracts.chunk import ChunkRecord
from rag_platform.contracts.document import (
    BoundingBox,
    DocumentFormat,
    EpistemicSpan,
    EpistemicStatus,
    ExtractionRoute,
    HumanReviewStatus,
    NormalizedBlock,
    NormalizedDocument,
)
from rag_platform.contracts.embedding import (
    EmbeddingIncompatibilityError,
    EmbeddingSpaceSignature,
    EmbeddingTaskType,
    VectorIndexRecord,
    assert_embedding_compatibility,
)
from rag_platform.contracts.generation import (
    AnswerEpistemicStatus,
    GeneratedRAGResponse,
    GroundedClaim,
)
from rag_platform.contracts.retrieval import (
    AgenticQueryPlan,
    EvidenceCitation,
    PlannedSubQuery,
    QueryBudget,
    RetrievalMode,
)
from rag_platform.contracts.tenant import TenantScope, UsageMode

__all__ = [
    "AgenticQueryPlan",
    "AnswerEpistemicStatus",
    "BoundingBox",
    "ChunkRecord",
    "DocumentFormat",
    "EmbeddingIncompatibilityError",
    "EmbeddingSpaceSignature",
    "EmbeddingTaskType",
    "EpistemicSpan",
    "EpistemicStatus",
    "EvidenceCitation",
    "ExtractionRoute",
    "GeneratedRAGResponse",
    "GroundedClaim",
    "HumanReviewStatus",
    "NormalizedBlock",
    "NormalizedDocument",
    "PlannedSubQuery",
    "QueryBudget",
    "RetrievalMode",
    "TenantScope",
    "UsageMode",
    "VectorIndexRecord",
    "assert_embedding_compatibility",
]
