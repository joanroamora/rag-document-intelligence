"""Multi-tenant access control and lifecycle contracts."""

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class UsageMode(StrEnum):
    """Lifecycle and persistence modes defined in RAG architecture."""

    QUICK_RAG = "quick_rag"
    PERSISTENT_CORPUS = "persistent_corpus"
    THEMATIC_PROJECT = "thematic_project"


class TenantScope(BaseModel):
    """Mandatory multi-tenant scope applied before or during retrieval."""

    tenant_id: str = Field(..., min_length=1, description="Unique tenant identifier")
    project_id: str = Field(..., min_length=1, description="Logical project identifier")
    case_id: str | None = Field(default=None, description="Optional case/dossier identifier")
    document_id: str | None = Field(default=None, description="Optional specific document filter")
    usage_mode: UsageMode = Field(default=UsageMode.PERSISTENT_CORPUS)
    ttl_seconds: int | None = Field(
        default=None,
        gt=0,
        description="Required TTL in seconds when usage_mode is QUICK_RAG",
    )

    @model_validator(mode="after")
    def validate_mode_constraints(self) -> "TenantScope":
        """Enforce TTL requirement for Quick RAG and non-empty identifiers."""
        if not self.tenant_id.strip():
            raise ValueError("tenant_id cannot be blank or whitespace")
        if not self.project_id.strip():
            raise ValueError("project_id cannot be blank or whitespace")
        if self.usage_mode == UsageMode.QUICK_RAG and self.ttl_seconds is None:
            raise ValueError("ttl_seconds is mandatory when usage_mode is QUICK_RAG")
        return self

    def to_metadata_filter(self) -> dict[str, str]:
        """Return pre-retrieval backend filter dictionary for vector and lexical stores."""
        filters: dict[str, str] = {
            "tenant_id": self.tenant_id,
            "project_id": self.project_id,
        }
        if self.case_id is not None:
            filters["case_id"] = self.case_id
        if self.document_id is not None:
            filters["document_id"] = self.document_id
        return filters
