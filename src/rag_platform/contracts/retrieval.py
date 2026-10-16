"""Module 3 & 4 contracts: Hybrid retrieval, agentic query planning, and cited evidence."""

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from rag_platform.contracts.document import HumanReviewStatus
from rag_platform.contracts.tenant import TenantScope


class RetrievalMode(StrEnum):
    """Supported retrieval execution modes (Section 5)."""

    STANDARD_HYBRID = "standard_hybrid"
    DEEP_AGENTIC = "deep_agentic"


class QueryBudget(BaseModel):
    """Strict operational limits for Agentic Retrieval.

    Prevents runaway loops and quota exhaustion.
    """

    max_iterations: int = Field(default=3, ge=1, le=10)
    max_subqueries: int = Field(default=5, ge=1, le=20)
    max_parallelism: int = Field(default=3, ge=1, le=10)
    max_input_tokens: int = Field(default=32000, ge=1000, le=250000)
    timeout_seconds: int = Field(default=30, ge=5, le=180)


class PlannedSubQuery(BaseModel):
    """Structured subquery emitted by Gemini Query Planner and executed by the backend."""

    subquery_id: str = Field(..., min_length=1)
    query_text: str = Field(..., min_length=1)
    lexical_keywords: list[str] = Field(default_factory=list)
    requires_exhaustive_scan: bool = Field(
        default=False,
        description="True when question asks for 'all cases' or 'every payment' (not just Top-K)",
    )


class AgenticQueryPlan(BaseModel):
    """Validated query plan contract for Deep Agentic Retrieval (Section 5.2)."""

    original_question: str = Field(..., min_length=1)
    authorized_scope: TenantScope
    mode: RetrievalMode = Field(default=RetrievalMode.DEEP_AGENTIC)
    budget: QueryBudget = Field(default_factory=QueryBudget)
    subqueries: list[PlannedSubQuery] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_subquery_budget(self) -> "AgenticQueryPlan":
        """Ensure planned subqueries do not exceed the query budget limit."""
        if len(self.subqueries) > self.budget.max_subqueries:
            raise ValueError(
                f"Number of subqueries ({len(self.subqueries)}) exceeds "
                f"budget.max_subqueries ({self.budget.max_subqueries})"
            )
        return self


class EvidenceCitation(BaseModel):
    """Verifiable evidence citation returned by Retrieval and required by Generation."""

    chunk_id: str = Field(..., min_length=1)
    document_id: str = Field(..., min_length=1)
    page_start: int = Field(..., ge=1)
    page_end: int = Field(..., ge=1)
    source_reference: str = Field(..., pattern=r"^gs://[a-z0-9._-]+/.+$")
    observed_excerpt: str = Field(..., min_length=1)
    has_uncertainty: bool = Field(default=False)
    human_review_status: HumanReviewStatus = Field(default=HumanReviewStatus.NOT_REQUIRED)
    rrf_score: float = Field(..., ge=0.0)
    rerank_score: float | None = Field(default=None)
