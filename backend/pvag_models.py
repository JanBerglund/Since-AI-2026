"""Schemas and protocols used by the PVAG comparison pipeline."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, field_validator

from claim_models import SpecClaim
from retrieval import SearchResult
from scrape import Clause


class ComparisonAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clause_id: str
    comparison: Literal["min", "max", "exact"]
    value: str | int | float
    unit: str
    quote_from_clause: str
    notes: str

    @field_validator("value", mode="before")
    @classmethod
    def reject_boolean_value(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("threshold value must not be a boolean")
        return value


class ModelAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["valid", "invalid"]
    output: ComparisonAssessment | None
    issue: str | None = None


class PVAGFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["pvag"] = "pvag"
    verdict: Literal["pass", "fail", "unknown"]
    hypothetical_verdict: Literal["pass", "fail", "unknown"]
    scope: Literal["in_scope", "out_of_scope", "unclear"]
    scope_clause_id: str | None
    scope_quote: str
    title: str
    reason: str
    claim: SpecClaim
    clause_id: str | None
    clause_quote: str
    clause_url: str | None
    judgement: ModelAssessment
    extraction: ModelAssessment


class JsonGenerator(Protocol):
    def generate_json(
        self,
        prompt: str,
        output_model: type[ComparisonAssessment],
        *,
        role: Literal["judgement", "extraction"],
    ) -> ComparisonAssessment | Literal["invalid"]: ...


class Retriever(Protocol):
    clauses: list[Clause]

    def search(self, query: str, k: int = 5, **kwargs: object) -> list[SearchResult]: ...
