"""Determine PVAG applicability from known vessel passenger limits."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from scrape import Clause


class ScopeFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_persons: int | None = 8
    is_ferry: bool | None = False
    permitted_passengers: int | None = None
    overnight_passengers: int | None = None


class ScopeDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["in_scope", "out_of_scope", "unclear"]
    clause_id: str | None
    quote: str
    reason: str


def determine_scope(
    facts: ScopeFacts,
    clauses: list[Clause],
) -> ScopeDecision:
    by_id = {clause.id: clause for clause in clauses}
    required = ("V201.1", "V201.1.1", "V201.1.2")
    missing = [clause_id for clause_id in required if clause_id not in by_id]
    if missing:
        return ScopeDecision(
            scope="unclear",
            clause_id=None,
            quote="",
            reason=f"Required PVAG scoping clause(s) missing: {', '.join(missing)}.",
        )

    total_limit = facts.max_persons
    permitted = facts.permitted_passengers
    overnight = facts.overnight_passengers
    nonferry_clause = by_id["V201.1.1"]
    ferry_clause = by_id["V201.1.2"]

    if facts.is_ferry is True:
        if permitted is not None and permitted > 99:
            return ScopeDecision(
                scope="in_scope",
                clause_id=ferry_clause.id,
                quote=ferry_clause.text,
                reason="The permitted passenger count exceeds the ferry threshold.",
            )
        if (permitted is not None and permitted <= 99) or (
            total_limit is not None and total_limit <= 99
        ):
            return ScopeDecision(
                scope="out_of_scope",
                clause_id=ferry_clause.id,
                quote=ferry_clause.text,
                reason="The known passenger/person limit does not exceed the ferry threshold.",
            )
        return ScopeDecision(
            scope="unclear",
            clause_id=ferry_clause.id,
            quote=ferry_clause.text,
            reason="The permitted passenger count is not known well enough to apply the ferry threshold.",
        )

    if facts.is_ferry is False:
        if (permitted is not None and permitted > 150) or (
            overnight is not None and overnight > 49
        ):
            return ScopeDecision(
                scope="in_scope",
                clause_id=nonferry_clause.id,
                quote=nonferry_clause.text,
                reason="A known permitted or overnight passenger count exceeds the large-vessel threshold.",
            )
        if (
            (permitted is not None and permitted <= 150)
            and (overnight is not None and overnight <= 49)
        ) or (total_limit is not None and total_limit <= 49):
            return ScopeDecision(
                scope="out_of_scope",
                clause_id=nonferry_clause.id,
                quote=nonferry_clause.text,
                reason="Known counts are below both large-vessel passenger thresholds.",
            )
        return ScopeDecision(
            scope="unclear",
            clause_id=nonferry_clause.id,
            quote=nonferry_clause.text,
            reason="Passenger and overnight passenger counts are insufficient to decide scope.",
        )

    if total_limit is not None and total_limit <= 49:
        return ScopeDecision(
            scope="out_of_scope",
            clause_id=nonferry_clause.id,
            quote=nonferry_clause.text,
            reason="The total person limit is below both ferry and non-ferry thresholds.",
        )
    return ScopeDecision(
        scope="unclear",
        clause_id=nonferry_clause.id,
        quote=nonferry_clause.text,
        reason="Whether the vessel is a ferry and the permitted passenger counts are not known.",
    )
