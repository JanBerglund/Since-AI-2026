"""Schemas and protocols used by the PVAG comparison pipeline."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from claim_models import SpecClaim
from retrieval import SearchResult
from scrape import Clause


class ComparisonAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relevant: bool
    verdict: Literal["comparison", "not_applicable_topic"] = "comparison"
    clause_id: str | None = None
    comparison: Literal["min", "max", "exact"] | None = None
    value: str | int | float | None = None
    unit: str | None = None
    quote_from_clause: str | None = None
    notes: str = ""

    @field_validator("value", mode="before")
    @classmethod
    def reject_boolean_value(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("threshold value must not be a boolean")
        return value

    @model_validator(mode="after")
    def validate_relevance(self) -> "ComparisonAssessment":
        if not self.relevant:
            if self.verdict != "not_applicable_topic":
                raise ValueError("irrelevant assessments must use verdict='not_applicable_topic'")
            return self
        if self.verdict != "comparison":
            raise ValueError("relevant assessments must use verdict='comparison'")
        if (
            self.clause_id is None
            or self.comparison is None
            or self.value is None
            or self.unit is None
            or self.quote_from_clause is None
        ):
            raise ValueError("relevant assessments require comparison fields")
        return self


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
    hypothetical: bool = False
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
