"""Module 3.2: Deep Agentic Retrieval with Query Planner, Budget Guards, and Exhaustive Scan."""

import re
from collections.abc import Callable
from typing import Protocol

from pydantic import BaseModel, Field

from rag_platform.contracts import (
    AgenticQueryPlan,
    EvidenceCitation,
    PlannedSubQuery,
    QueryBudget,
    RetrievalMode,
    TenantScope,
)
from rag_platform.retrieval.hybrid_retriever import (
    ExpandedEvidenceItem,
    HybridRetrievalResult,
    HybridRetriever,
)
from rag_platform.retrieval.lexical_bm25 import tokenize_for_bm25

SubQueryGeneratorFn = Callable[[str, QueryBudget], list[PlannedSubQuery]]

_EXHAUSTIVE_PATTERNS: tuple[str, ...] = (
    r"\btodos\b",
    r"\btodas\b",
    r"\bcada\s+uno\b",
    r"\bcada\s+\w+",
    r"\blista\s+completa\b",
    r"\btotalidad\b",
    r"\ball\b",
    r"\bevery\b",
)


def detect_exhaustive_intent(question: str) -> bool:
    """Return True if the question asks for exhaustive coverage ('todos', 'cada pago', 'all')."""
    lowered = question.lower()
    return any(re.search(pattern, lowered) is not None for pattern in _EXHAUSTIVE_PATTERNS)


class QueryPlanner(Protocol):
    """Protocol for structured query planning without direct index or cross-tenant access."""

    def build_plan(
        self,
        question: str,
        scope: TenantScope,
        budget: QueryBudget | None = None,
    ) -> AgenticQueryPlan:
        """Decompose a complex question into a validated AgenticQueryPlan."""
        ...


class HeuristicGeminiQueryPlanner:
    """Query planner combining optional Gemini Flash decomposition with deterministic fallback."""

    def __init__(self, llm_generator: SubQueryGeneratorFn | None = None) -> None:
        self._llm_generator = llm_generator

    def build_plan(
        self,
        question: str,
        scope: TenantScope,
        budget: QueryBudget | None = None,
    ) -> AgenticQueryPlan:
        """Build a budget-constrained AgenticQueryPlan with exhaustive-intent detection."""
        if not question or not question.strip():
            raise ValueError("question cannot be empty")

        active_budget = budget or QueryBudget()

        if self._llm_generator is not None:
            planned = self._llm_generator(question, active_budget)
            subqueries = planned[: active_budget.max_subqueries]
        else:
            subqueries = self._decompose_deterministically(question, active_budget)

        return AgenticQueryPlan(
            original_question=question,
            authorized_scope=scope,
            mode=RetrievalMode.DEEP_AGENTIC,
            budget=active_budget,
            subqueries=subqueries,
        )

    def _decompose_deterministically(
        self,
        question: str,
        budget: QueryBudget,
    ) -> list[PlannedSubQuery]:
        """Split compound questions into bounded subqueries with lexical keywords."""
        is_exhaustive = detect_exhaustive_intent(question)
        raw_parts = re.split(
            r"\s+(?:y\s+además|además|asimismo|;\s*|\?\s+¿?)\s*",
            question.strip(),
            flags=re.IGNORECASE,
        )
        cleaned_parts = [p.strip() for p in raw_parts if p and p.strip()]
        if not cleaned_parts:
            cleaned_parts = [question.strip()]

        bounded_parts = cleaned_parts[: budget.max_subqueries]
        subqueries: list[PlannedSubQuery] = []

        for idx, part in enumerate(bounded_parts, start=1):
            keywords = tokenize_for_bm25(part)[:8]
            part_exhaustive = is_exhaustive or detect_exhaustive_intent(part)
            subqueries.append(
                PlannedSubQuery(
                    subquery_id=f"sq-{idx:02d}",
                    query_text=part,
                    lexical_keywords=keywords,
                    requires_exhaustive_scan=part_exhaustive,
                )
            )

        return subqueries


class AgenticRetrievalResult(BaseModel):
    """Output of Deep Agentic Retrieval including executed plan, budget usage, and evidence."""

    plan: AgenticQueryPlan
    retrieval_result: HybridRetrievalResult
    executed_subqueries: int = Field(..., ge=0)
    estimated_tokens_used: int = Field(..., ge=0)
    budget_truncated: bool = Field(default=False)


class AgenticRetrievalEngine:
    """Backend executor for AgenticQueryPlan enforcing TenantScope and QueryBudget."""

    def __init__(
        self,
        hybrid_retriever: HybridRetriever,
        planner: QueryPlanner | None = None,
    ) -> None:
        self.hybrid_retriever = hybrid_retriever
        self.planner = planner or HeuristicGeminiQueryPlanner()

    def retrieve(
        self,
        question: str,
        authorized_scope: TenantScope,
        budget: QueryBudget | None = None,
        top_k_per_subquery: int = 5,
    ) -> AgenticRetrievalResult:
        """Plan and execute multi-step agentic retrieval strictly under authorized_scope."""
        plan = self.planner.build_plan(
            question=question,
            scope=authorized_scope,
            budget=budget,
        )
        return self.execute_plan(
            plan=plan,
            authorized_scope=authorized_scope,
            top_k_per_subquery=top_k_per_subquery,
        )

    def execute_plan(
        self,
        plan: AgenticQueryPlan,
        authorized_scope: TenantScope,
        top_k_per_subquery: int = 5,
    ) -> AgenticRetrievalResult:
        """Execute a validated AgenticQueryPlan while locking TenantScope and token budget."""
        # Invariant #3: Planner can NEVER alter or widen the backend's authorized TenantScope
        if plan.authorized_scope != authorized_scope:
            raise PermissionError(
                "Security violation: AgenticQueryPlan scope does not match backend "
                "authorized_scope."
            )

        fused_by_chunk: dict[str, ExpandedEvidenceItem] = {}
        any_exhaustive = False
        executed_count = 0

        max_subqueries = min(len(plan.subqueries), plan.budget.max_subqueries)
        for subquery in plan.subqueries[:max_subqueries]:
            executed_count += 1
            is_sq_exhaustive = subquery.requires_exhaustive_scan
            if is_sq_exhaustive:
                any_exhaustive = True

            effective_query = subquery.query_text
            if subquery.lexical_keywords:
                kw_suffix = " ".join(subquery.lexical_keywords)
                effective_query = f"{subquery.query_text} {kw_suffix}"

            sub_result = self.hybrid_retriever.retrieve(
                query_text=effective_query,
                scope=authorized_scope,
                top_k=top_k_per_subquery,
                exhaustive=is_sq_exhaustive,
            )

            for item in sub_result.items:
                cid = item.primary_chunk.chunk_id
                if cid not in fused_by_chunk:
                    fused_by_chunk[cid] = item
                else:
                    existing = fused_by_chunk[cid]
                    combined_rrf = round(
                        existing.citation.rrf_score + item.citation.rrf_score,
                        6,
                    )
                    best_rerank = max(
                        existing.citation.rerank_score or 0.0,
                        item.citation.rerank_score or 0.0,
                    )
                    updated_citation = EvidenceCitation(
                        chunk_id=existing.citation.chunk_id,
                        document_id=existing.citation.document_id,
                        page_start=existing.citation.page_start,
                        page_end=existing.citation.page_end,
                        source_reference=existing.citation.source_reference,
                        observed_excerpt=existing.citation.observed_excerpt,
                        has_uncertainty=existing.citation.has_uncertainty,
                        human_review_status=existing.citation.human_review_status,
                        rrf_score=combined_rrf,
                        rerank_score=best_rerank,
                    )
                    fused_by_chunk[cid] = ExpandedEvidenceItem(
                        citation=updated_citation,
                        primary_chunk=existing.primary_chunk,
                        previous_neighbor=existing.previous_neighbor,
                        next_neighbor=existing.next_neighbor,
                        section_peers=existing.section_peers,
                        inferred_context_notes=existing.inferred_context_notes,
                    )

        sorted_items = sorted(
            fused_by_chunk.values(),
            key=lambda it: (
                -(it.citation.rerank_score or 0.0),
                -it.citation.rrf_score,
                it.primary_chunk.chunk_id,
            ),
        )

        # Enforce max_input_tokens budget (~4 chars per token heuristic)
        bounded_items: list[ExpandedEvidenceItem] = []
        tokens_used = 0
        budget_truncated = False

        for item in sorted_items:
            rendered = item.render_expanded_context()
            est_tokens = max(1, len(rendered) // 4)
            if tokens_used + est_tokens > plan.budget.max_input_tokens:
                budget_truncated = True
                break
            bounded_items.append(item)
            tokens_used += est_tokens

        is_sufficient = len(bounded_items) > 0
        insufficiency_reason: str | None = None
        if not is_sufficient:
            insufficiency_reason = (
                "Agentic retrieval found no verifiable evidence matching subqueries within "
                "the authorized tenant scope."
            )

        hybrid_res = HybridRetrievalResult(
            query=plan.original_question,
            mode=RetrievalMode.DEEP_AGENTIC,
            scope=authorized_scope,
            items=bounded_items,
            is_exhaustive_scan=any_exhaustive,
            is_evidence_sufficient=is_sufficient,
            insufficiency_reason=insufficiency_reason,
        )

        return AgenticRetrievalResult(
            plan=plan,
            retrieval_result=hybrid_res,
            executed_subqueries=executed_count,
            estimated_tokens_used=tokens_used,
            budget_truncated=budget_truncated,
        )
