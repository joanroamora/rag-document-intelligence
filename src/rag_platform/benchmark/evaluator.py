"""Reproducible OCR (CER/WER) and RAG (Recall@K, MRR, nDCG@K) benchmark evaluator."""

import math
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, Field

from rag_platform.contracts import RetrievalMode, TenantScope
from rag_platform.orchestrator import RAGPlatformOrchestrator


def levenshtein_distance(seq_a: Sequence[Any], seq_b: Sequence[Any]) -> int:
    """Compute exact Levenshtein edit distance between two sequences."""
    len_a = len(seq_a)
    len_b = len(seq_b)
    if len_a == 0:
        return len_b
    if len_b == 0:
        return len_a

    prev_row = list(range(len_b + 1))
    for i, item_a in enumerate(seq_a, start=1):
        curr_row = [i] + [0] * len_b
        for j, item_b in enumerate(seq_b, start=1):
            cost = 0 if item_a == item_b else 1
            curr_row[j] = min(
                prev_row[j] + 1,
                curr_row[j - 1] + 1,
                prev_row[j - 1] + cost,
            )
        prev_row = curr_row
    return prev_row[len_b]


def compute_cer(reference_text: str, hypothesis_text: str) -> float:
    """Compute Character Error Rate (CER) against a reference transcription."""
    ref_chars = list(reference_text.strip())
    hyp_chars = list(hypothesis_text.strip())
    if not ref_chars:
        return 0.0 if not hyp_chars else 1.0
    dist = levenshtein_distance(ref_chars, hyp_chars)
    return round(dist / len(ref_chars), 6)


def compute_wer(reference_text: str, hypothesis_text: str) -> float:
    """Compute Word Error Rate (WER) against a reference transcription."""
    ref_words = reference_text.strip().split()
    hyp_words = hypothesis_text.strip().split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    dist = levenshtein_distance(ref_words, hyp_words)
    return round(dist / len(ref_words), 6)


def compute_recall_at_k(
    retrieved_chunk_ids: Sequence[str],
    relevant_chunk_ids: set[str],
    k: int,
) -> float:
    """Compute Recall@K in [0.0, 1.0] for a single query."""
    if k <= 0:
        raise ValueError("k must be greater than 0")
    if not relevant_chunk_ids:
        return 1.0
    top_k_set = set(retrieved_chunk_ids[:k])
    hits = len(top_k_set & relevant_chunk_ids)
    return round(hits / len(relevant_chunk_ids), 6)


def compute_reciprocal_rank(
    retrieved_chunk_ids: Sequence[str],
    relevant_chunk_ids: set[str],
) -> float:
    """Compute Reciprocal Rank (RR) of the first relevant chunk."""
    for rank_idx, cid in enumerate(retrieved_chunk_ids, start=1):
        if cid in relevant_chunk_ids:
            return round(1.0 / rank_idx, 6)
    return 0.0


def compute_ndcg_at_k(
    retrieved_chunk_ids: Sequence[str],
    relevant_chunk_ids: set[str],
    k: int,
) -> float:
    """Compute binary Normalized Discounted Cumulative Gain (nDCG@K) in [0.0, 1.0]."""
    if k <= 0:
        raise ValueError("k must be greater than 0")
    if not relevant_chunk_ids:
        return 1.0

    dcg = 0.0
    for rank_idx, cid in enumerate(retrieved_chunk_ids[:k], start=1):
        if cid in relevant_chunk_ids:
            dcg += 1.0 / math.log2(rank_idx + 1.0)

    ideal_hits = min(len(relevant_chunk_ids), k)
    idcg = sum(1.0 / math.log2(r + 1.0) for r in range(1, ideal_hits + 1))
    if idcg == 0.0:
        return 0.0
    return round(dcg / idcg, 6)


class BenchmarkQueryCase(BaseModel):
    """Single reproducible RAG evaluation case with ground-truth relevant chunk IDs."""

    case_name: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    scope: TenantScope
    expected_chunk_ids: list[str] = Field(..., min_length=1)
    mode: RetrievalMode = Field(default=RetrievalMode.STANDARD_HYBRID)
    k: int = Field(default=5, ge=1, le=50)


class BenchmarkCaseResult(BaseModel):
    """Metrics produced for a single BenchmarkQueryCase."""

    case_name: str
    retrieved_chunk_ids: list[str]
    recall_at_k: float = Field(..., ge=0.0, le=1.0)
    reciprocal_rank: float = Field(..., ge=0.0, le=1.0)
    ndcg_at_k: float = Field(..., ge=0.0, le=1.0)
    citation_precision: float = Field(..., ge=0.0, le=1.0)


class BenchmarkSuiteReport(BaseModel):
    """Aggregated RAG benchmark report across all evaluation cases."""

    total_cases: int = Field(..., ge=0)
    mean_recall_at_k: float = Field(..., ge=0.0, le=1.0)
    mrr: float = Field(..., ge=0.0, le=1.0)
    mean_ndcg_at_k: float = Field(..., ge=0.0, le=1.0)
    mean_citation_precision: float = Field(..., ge=0.0, le=1.0)
    case_results: list[BenchmarkCaseResult] = Field(default_factory=list)


class RAGBenchmarkRunner:
    """Executes reproducible RAG benchmark suites against a RAGPlatformOrchestrator."""

    def __init__(self, orchestrator: RAGPlatformOrchestrator) -> None:
        self.orchestrator = orchestrator

    def evaluate_suite(
        self,
        cases: Sequence[BenchmarkQueryCase],
    ) -> BenchmarkSuiteReport:
        """Run all benchmark cases and aggregate Recall@K, MRR, nDCG@K, and precision."""
        if not cases:
            return BenchmarkSuiteReport(
                total_cases=0,
                mean_recall_at_k=0.0,
                mrr=0.0,
                mean_ndcg_at_k=0.0,
                mean_citation_precision=0.0,
                case_results=[],
            )

        results: list[BenchmarkCaseResult] = []
        for case in cases:
            response = self.orchestrator.ask(
                question=case.question,
                scope=case.scope,
                mode=case.mode,
                top_k=case.k,
            )
            retrieved_ids = [c.chunk_id for c in response.citations]
            expected_set = set(case.expected_chunk_ids)

            recall = compute_recall_at_k(retrieved_ids, expected_set, case.k)
            rr = compute_reciprocal_rank(retrieved_ids, expected_set)
            ndcg = compute_ndcg_at_k(retrieved_ids, expected_set, case.k)

            cited_in_claims = {
                cid for claim in response.claims for cid in claim.cited_chunk_ids
            }
            if not cited_in_claims:
                precision = 0.0
            else:
                hits = len(cited_in_claims & expected_set)
                precision = round(hits / len(cited_in_claims), 6)

            results.append(
                BenchmarkCaseResult(
                    case_name=case.case_name,
                    retrieved_chunk_ids=retrieved_ids,
                    recall_at_k=recall,
                    reciprocal_rank=rr,
                    ndcg_at_k=ndcg,
                    citation_precision=precision,
                )
            )

        n = len(results)
        return BenchmarkSuiteReport(
            total_cases=n,
            mean_recall_at_k=round(sum(r.recall_at_k for r in results) / n, 6),
            mrr=round(sum(r.reciprocal_rank for r in results) / n, 6),
            mean_ndcg_at_k=round(sum(r.ndcg_at_k for r in results) / n, 6),
            mean_citation_precision=round(
                sum(r.citation_precision for r in results) / n, 6
            ),
            case_results=results,
        )
