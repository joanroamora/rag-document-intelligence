"""Module 4 contracts: Grounded answer generation, claim citations, and epistemic status."""

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from rag_platform.contracts.retrieval import EvidenceCitation, RetrievalMode
from rag_platform.contracts.tenant import TenantScope


class AnswerEpistemicStatus(StrEnum):
    """Epistemological classification of a generated RAG response."""

    GROUNDED_CERTAIN = "grounded_certain"
    GROUNDED_WITH_UNCERTAINTY = "grounded_with_uncertainty"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    ABSTAINED_INSUFFICIENT_EVIDENCE = "abstained_insufficient_evidence"


class GroundedClaim(BaseModel):
    """A factual statement backed by one or more verifiable chunk IDs."""

    statement: str = Field(..., min_length=1)
    cited_chunk_ids: list[str] = Field(..., min_length=1)
    contains_uncertainty: bool = Field(default=False)


class GeneratedRAGResponse(BaseModel):
    """Canonical Module 4 output contract with cited claims and segregated hypotheses."""

    schema_version: str = Field(default="1.0.0")
    question: str = Field(..., min_length=1)
    scope: TenantScope
    mode: RetrievalMode = Field(default=RetrievalMode.STANDARD_HYBRID)
    epistemic_status: AnswerEpistemicStatus
    synthesized_answer: str = Field(..., min_length=1)
    claims: list[GroundedClaim] = Field(default_factory=list)
    citations: list[EvidenceCitation] = Field(default_factory=list)
    segregated_inferential_hypotheses: list[str] = Field(
        default_factory=list,
        description="Contextual deductions explicitly separated from observed facts",
    )
    uncertainty_warnings: list[str] = Field(default_factory=list)
    generator_provider: str = Field(default="gemini_api", min_length=1)
    generator_model_version: str = Field(default="gemini-2.5-flash", min_length=1)

    @model_validator(mode="after")
    def validate_grounding_integrity(self) -> "GeneratedRAGResponse":
        """Enforce that non-abstained answers have valid citations for every claim."""
        if self.epistemic_status == AnswerEpistemicStatus.ABSTAINED_INSUFFICIENT_EVIDENCE:
            if self.claims:
                raise ValueError(
                    "Abstained responses must not contain factual claims"
                )
            return self

        if not self.claims or not self.citations:
            raise ValueError(
                "Grounded responses must include at least one claim and one citation"
            )

        valid_chunk_ids = {c.chunk_id for c in self.citations}
        for claim in self.claims:
            for cid in claim.cited_chunk_ids:
                if cid not in valid_chunk_ids:
                    raise ValueError(
                        f"Claim references unverified chunk_id '{cid}' not present in citations"
                    )
        return self
