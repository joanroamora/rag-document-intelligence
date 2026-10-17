"""Module 4: Grounded Answer Generation, Citation Guard, and Epistemic Safety Validator."""

from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel, Field, model_validator

from rag_platform.contracts import (
    AnswerEpistemicStatus,
    EvidenceCitation,
    GeneratedRAGResponse,
    GroundedClaim,
    HumanReviewStatus,
)
from rag_platform.retrieval import ExpandedEvidenceItem, HybridRetrievalResult


class CitationVerificationError(ValueError):
    """Raised when generated claims cite unauthorized chunks or leak inferred hypotheses."""


class GeneratorConfig(BaseModel):
    """Configuration for Module 4 generation enforcing Free Tier usage."""

    provider_name: str = Field(default="gemini_api", min_length=1)
    model_version: str = Field(default="gemini-2.5-flash", min_length=1)
    allow_paid_tier: bool = Field(
        default=False,
        description="Must remain False to enforce Invariant #4 (Zero automatic billing)",
    )

    @model_validator(mode="after")
    def enforce_free_tier_invariant(self) -> "GeneratorConfig":
        """Enforce Invariant #4: Never enable paid billing tier automatically."""
        if self.allow_paid_tier:
            raise ValueError(
                "Paid tier is strictly prohibited by project governance (Invariant #4)."
            )
        return self


class AnswerSynthesisBackend(Protocol):
    """Pluggable interface for answer synthesis (Gemini Flash Free Tier or Extractive)."""

    def synthesize(
        self,
        question: str,
        evidence_items: Sequence[ExpandedEvidenceItem],
        config: GeneratorConfig,
    ) -> tuple[str, list[GroundedClaim], bool]:
        """Synthesize an answer, list of grounded claims, and conflict flag."""
        ...


class ExtractiveGroundedSynthesizer:
    """Deterministic extractive synthesizer that builds cited claims from observed evidence."""

    def synthesize(
        self,
        question: str,
        evidence_items: Sequence[ExpandedEvidenceItem],
        config: GeneratorConfig,
    ) -> tuple[str, list[GroundedClaim], bool]:
        """Construct grounded claims directly from retrieved evidence and detect conflicts."""
        _ = (question, config)
        claims: list[GroundedClaim] = []
        summary_lines: list[str] = []
        has_conflict = False

        for item in evidence_items:
            cid = item.citation.chunk_id
            excerpt = item.citation.observed_excerpt.strip()
            uncertain = item.citation.has_uncertainty

            if "[contradicción]" in excerpt.lower() or "contradictorio" in excerpt.lower():
                has_conflict = True

            claims.append(
                GroundedClaim(
                    statement=f"{excerpt} [{cid}]",
                    cited_chunk_ids=[cid],
                    contains_uncertainty=uncertain,
                )
            )
            page_range = f"p.{item.citation.page_start}-{item.citation.page_end}"
            summary_lines.append(f"- {excerpt} (Fuente: {cid}, {page_range})")

        synthesized = "\n".join(summary_lines)
        return synthesized, claims, has_conflict


class GroundedAnswerGenerator:
    """Module 4 orchestrator enforcing abstention, citation verification, and epistemic safety."""

    def __init__(
        self,
        config: GeneratorConfig | None = None,
        synthesizer: AnswerSynthesisBackend | None = None,
    ) -> None:
        self.config = config or GeneratorConfig()
        self.synthesizer = synthesizer or ExtractiveGroundedSynthesizer()

    def generate(self, retrieval_result: HybridRetrievalResult) -> GeneratedRAGResponse:
        """Validate retrieved evidence, synthesize grounded answer, and verify citations."""
        if not retrieval_result.is_evidence_sufficient or not retrieval_result.items:
            reason = (
                retrieval_result.insufficiency_reason
                or "No se encontró evidencia verificable en el alcance autorizado."
            )
            return GeneratedRAGResponse(
                question=retrieval_result.query,
                scope=retrieval_result.scope,
                mode=retrieval_result.mode,
                epistemic_status=AnswerEpistemicStatus.ABSTAINED_INSUFFICIENT_EVIDENCE,
                synthesized_answer=(
                    f"ABSTENCIÓN POR EVIDENCIA INSUFICIENTE: {reason} "
                    "El sistema no formula suposiciones sin respaldo documental."
                ),
                claims=[],
                citations=[],
                segregated_inferential_hypotheses=[],
                uncertainty_warnings=[],
                generator_provider=self.config.provider_name,
                generator_model_version=self.config.model_version,
            )

        synthesized_text, claims, has_conflict = self.synthesizer.synthesize(
            question=retrieval_result.query,
            evidence_items=retrieval_result.items,
            config=self.config,
        )

        # Invariant #2 & #3: Verify all cited chunk_ids and prevent hypothesis leakage
        self._verify_claims_and_epistemic_boundaries(
            synthesized_text=synthesized_text,
            claims=claims,
            evidence_items=retrieval_result.items,
        )

        citations: list[EvidenceCitation] = [it.citation for it in retrieval_result.items]
        segregated_hypotheses: list[str] = []
        uncertainty_warnings: list[str] = []
        any_uncertainty = False

        for item in retrieval_result.items:
            cid = item.citation.chunk_id
            for note in item.inferred_context_notes:
                segregated_hypotheses.append(f"[{cid}] Hipótesis contextual: {note}")

            if item.citation.has_uncertainty:
                any_uncertainty = True
                uncertainty_warnings.append(
                    f"El fragmento {cid} (p.{item.citation.page_start}-{item.citation.page_end}) "
                    "contiene pasajes inciertos o [ilegible]."
                )
            if item.citation.human_review_status == HumanReviewStatus.PENDING_REVIEW:
                any_uncertainty = True
                uncertainty_warnings.append(
                    f"El fragmento {cid} requiere revisión humana (PENDING_REVIEW)."
                )

        if has_conflict:
            status = AnswerEpistemicStatus.CONFLICTING_EVIDENCE
        elif any_uncertainty:
            status = AnswerEpistemicStatus.GROUNDED_WITH_UNCERTAINTY
        else:
            status = AnswerEpistemicStatus.GROUNDED_CERTAIN

        return GeneratedRAGResponse(
            question=retrieval_result.query,
            scope=retrieval_result.scope,
            mode=retrieval_result.mode,
            epistemic_status=status,
            synthesized_answer=synthesized_text,
            claims=claims,
            citations=citations,
            segregated_inferential_hypotheses=segregated_hypotheses,
            uncertainty_warnings=uncertainty_warnings,
            generator_provider=self.config.provider_name,
            generator_model_version=self.config.model_version,
        )

    @staticmethod
    def _extract_hypothesis_phrase(note: str) -> str:
        """Extract the core hypothesis text from a formatted chunk inference note."""
        cleaned = note.strip()
        if "]: " in cleaned:
            cleaned = cleaned.split("]: ", 1)[1]
        if " — Motivo:" in cleaned:
            cleaned = cleaned.split(" — Motivo:", 1)[0]
        return cleaned.strip().lower()

    def _verify_claims_and_epistemic_boundaries(
        self,
        *,
        synthesized_text: str,
        claims: Sequence[GroundedClaim],
        evidence_items: Sequence[ExpandedEvidenceItem],
    ) -> None:
        """Enforce Citation Guard and ensure inferred hypotheses are not presented as facts."""
        if not claims:
            raise CitationVerificationError(
                "Synthesizer produced a response without any verifiable GroundedClaim items."
            )

        allowed_ids = {it.citation.chunk_id for it in evidence_items}
        all_inferred_notes = [
            self._extract_hypothesis_phrase(note)
            for it in evidence_items
            for note in it.inferred_context_notes
            if self._extract_hypothesis_phrase(note)
        ]

        for claim in claims:
            for cid in claim.cited_chunk_ids:
                if cid not in allowed_ids:
                    raise CitationVerificationError(
                        f"Hallucinated or unauthorized citation '{cid}'. "
                        f"Allowed retrieved chunk IDs: {sorted(allowed_ids)}"
                    )
            lowered_stmt = claim.statement.lower()
            for note in all_inferred_notes:
                if note in lowered_stmt:
                    raise CitationVerificationError(
                        f"Epistemological violation (Invariant #2): Inferred hypothesis "
                        f"'{note}' was presented inside a factual claim."
                    )

        lowered_answer = synthesized_text.lower()
        for note in all_inferred_notes:
            if note in lowered_answer:
                raise CitationVerificationError(
                    f"Epistemological violation (Invariant #2): Inferred hypothesis "
                    f"'{note}' was merged into synthesized_answer as observed fact."
                )
