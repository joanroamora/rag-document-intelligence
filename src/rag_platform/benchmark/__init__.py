"""Benchmark and evaluation suite for OCR quality (CER/WER) and RAG retrieval (Recall/MRR/nDCG)."""

from rag_platform.benchmark.evaluator import (
    BenchmarkCaseResult,
    BenchmarkQueryCase,
    BenchmarkSuiteReport,
    RAGBenchmarkRunner,
    compute_cer,
    compute_ndcg_at_k,
    compute_recall_at_k,
    compute_reciprocal_rank,
    compute_wer,
    levenshtein_distance,
)

__all__ = [
    "BenchmarkCaseResult",
    "BenchmarkQueryCase",
    "BenchmarkSuiteReport",
    "RAGBenchmarkRunner",
    "compute_cer",
    "compute_ndcg_at_k",
    "compute_recall_at_k",
    "compute_reciprocal_rank",
    "compute_wer",
    "levenshtein_distance",
]
