"""Module 3.1: Multi-tenant Okapi BM25 lexical index and hierarchical chunk lookup."""

import math
import re
from collections.abc import Sequence

from pydantic import BaseModel, Field

from rag_platform.contracts import ChunkRecord, TenantScope

_STOPWORDS_ES_EN: frozenset[str] = frozenset(
    {
        "el",
        "la",
        "los",
        "las",
        "un",
        "una",
        "de",
        "del",
        "al",
        "en",
        "y",
        "o",
        "por",
        "para",
        "con",
        "sin",
        "sobre",
        "que",
        "se",
        "su",
        "sus",
        "es",
        "son",
        "como",
        "the",
        "a",
        "an",
        "of",
        "to",
        "in",
        "and",
        "or",
        "for",
        "with",
        "on",
        "is",
        "are",
    }
)


def tokenize_for_bm25(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric terms, removing common stopwords."""
    raw_tokens = re.findall(r"\w+", text.lower())
    filtered = [t for t in raw_tokens if len(t) > 1 and t not in _STOPWORDS_ES_EN]
    return filtered if filtered else raw_tokens


class ScoredLexicalMatch(BaseModel):
    """Lexical search hit pairing a ChunkRecord with its non-negative BM25 score."""

    chunk: ChunkRecord
    bm25_score: float = Field(..., ge=0.0)


class BM25LexicalIndex:
    """In-memory multi-tenant Okapi BM25 index with pre-retrieval scope filtering."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        # Keyed by (tenant_id, project_id, chunk_id)
        self._chunks: dict[tuple[str, str, str], ChunkRecord] = {}
        self._tokens: dict[tuple[str, str, str], list[str]] = {}

    def upsert(self, chunks: Sequence[ChunkRecord]) -> int:
        """Incrementally and idempotently index chunks for lexical BM25 retrieval."""
        for chunk in chunks:
            key = (chunk.tenant_id, chunk.project_id, chunk.chunk_id)
            self._chunks[key] = chunk
            self._tokens[key] = tokenize_for_bm25(chunk.normalized_text)
        return len(chunks)

    def delete_document(self, scope: TenantScope, document_id: str) -> int:
        """Remove all lexical entries for a document within the authorized TenantScope."""
        keys_to_remove = [
            key
            for key, chunk in self._chunks.items()
            if chunk.document_id == document_id
            and scope.matches_filter(
                tenant_id=chunk.tenant_id,
                project_id=chunk.project_id,
                case_id=chunk.case_id,
                document_id=chunk.document_id,
            )
        ]
        for key in keys_to_remove:
            del self._chunks[key]
            del self._tokens[key]
        return len(keys_to_remove)

    def rebuild(self, chunks: Sequence[ChunkRecord]) -> int:
        """Clear and reconstruct the lexical index from canonical chunks."""
        self._chunks.clear()
        self._tokens.clear()
        return self.upsert(chunks)

    def get_chunk(self, scope: TenantScope, chunk_id: str) -> ChunkRecord | None:
        """Retrieve a specific chunk by ID strictly within the authorized TenantScope."""
        key = (scope.tenant_id, scope.project_id, chunk_id)
        chunk = self._chunks.get(key)
        if chunk is None:
            return None
        if not scope.matches_filter(
            tenant_id=chunk.tenant_id,
            project_id=chunk.project_id,
            case_id=chunk.case_id,
            document_id=chunk.document_id,
        ):
            return None
        return chunk

    def get_section_chunks(
        self,
        scope: TenantScope,
        document_id: str,
        section_id: str,
    ) -> list[ChunkRecord]:
        """Retrieve all chunks sharing a section_id within the authorized TenantScope."""
        peers = [
            chunk
            for chunk in self._chunks.values()
            if chunk.document_id == document_id
            and chunk.section_id == section_id
            and scope.matches_filter(
                tenant_id=chunk.tenant_id,
                project_id=chunk.project_id,
                case_id=chunk.case_id,
                document_id=chunk.document_id,
            )
        ]
        peers.sort(key=lambda c: c.position_index)
        return peers

    def search(
        self,
        query_text: str,
        scope: TenantScope,
        top_k: int | None = 5,
    ) -> list[ScoredLexicalMatch]:
        """Execute Okapi BM25 search over chunks pre-filtered by TenantScope.

        When top_k is None, performs an exhaustive scan returning all matching chunks.
        """
        if top_k is not None and top_k <= 0:
            raise ValueError("top_k must be greater than 0 when specified")

        query_terms = tokenize_for_bm25(query_text)
        if not query_terms:
            return []

        # Invariant #3: Pre-filter candidate corpus strictly by TenantScope before scoring
        scoped_entries: list[tuple[ChunkRecord, list[str]]] = []
        for key, chunk in self._chunks.items():
            if scope.matches_filter(
                tenant_id=chunk.tenant_id,
                project_id=chunk.project_id,
                case_id=chunk.case_id,
                document_id=chunk.document_id,
            ):
                scoped_entries.append((chunk, self._tokens[key]))

        num_docs = len(scoped_entries)
        if num_docs == 0:
            return []

        avg_dl = sum(len(tokens) for _, tokens in scoped_entries) / num_docs
        if avg_dl == 0.0:
            avg_dl = 1.0

        # Compute document frequencies within the authorized scope
        unique_query_terms = list(dict.fromkeys(query_terms))
        doc_freq: dict[str, int] = {term: 0 for term in unique_query_terms}
        for _chunk, tokens in scoped_entries:
            token_set = set(tokens)
            for term in unique_query_terms:
                if term in token_set:
                    doc_freq[term] += 1

        matches: list[ScoredLexicalMatch] = []
        for chunk, tokens in scoped_entries:
            doc_len = len(tokens)
            score = 0.0
            for term in unique_query_terms:
                tf = tokens.count(term)
                if tf == 0:
                    continue
                df = doc_freq[term]
                idf = math.log(1.0 + (num_docs - df + 0.5) / (df + 0.5))
                denom = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / avg_dl))
                score += idf * ((tf * (self.k1 + 1.0)) / denom)

            if score > 0.0:
                matches.append(
                    ScoredLexicalMatch(
                        chunk=chunk,
                        bm25_score=round(score, 6),
                    )
                )

        matches.sort(key=lambda m: (-m.bm25_score, m.chunk.chunk_id))
        if top_k is None:
            return matches
        return matches[:top_k]
