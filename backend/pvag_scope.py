"""Determine PVAG applicability from vessel facts and PVAG scope clauses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from scrape import Clause


class ScopeFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int | bool | None = None
    quote: str | None = None
    section_id: str | None = None
    source: Literal["extracted", "user"] | None = None


class ScopeFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_passengers: ScopeFact = ScopeFact()
    overnight_passengers: ScopeFact = ScopeFact()
    crew: ScopeFact = ScopeFact()
    is_ferry: ScopeFact = ScopeFact()
    is_tender: ScopeFact = ScopeFact()


class ScopeDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["in_scope", "out_of_scope", "unclear"]
    facts: ScopeFacts
    clauses: dict[str, str]
    reason: str


# Thresholds are stated by V201.1.1 (large vessels) and V201.1.2 (ferries).
NONFERRY_PASSENGER_THRESHOLD = 150
NONFERRY_OVERNIGHT_THRESHOLD = 49
FERRY_PASSENGER_THRESHOLD = 99


def _decision(
    scope: Literal["in_scope", "out_of_scope", "unclear"],
    facts: ScopeFacts,
    clauses: dict[str, str],
    reason: str,
) -> ScopeDecision:
    return ScopeDecision(scope=scope, facts=facts, clauses=clauses, reason=reason)


def determine_scope(
    facts: ScopeFacts,
    clauses: list[Clause],
) -> ScopeDecision:
    by_id = {clause.id: clause for clause in clauses}
    required = ("V201.1.1", "V201.1.2", "V106.5")
    missing = [clause_id for clause_id in required if clause_id not in by_id]
    clause_quotes = {
        clause_id: by_id[clause_id].text
        for clause_id in required
        if clause_id in by_id
    }
    if missing:
        return _decision(
            "unclear",
            facts,
            clause_quotes,
            f"Required PVAG scoping clause(s) missing: {', '.join(missing)}.",
        )

    passengers = facts.max_passengers.value
    overnight = facts.overnight_passengers.value
    is_ferry = facts.is_ferry.value
    is_tender = facts.is_tender.value

    if is_tender is True:
        return _decision(
            "unclear",
            facts,
            clause_quotes,
            "The vessel is identified as a tender; the available PVAG scope clauses "
            "do not establish whether the passenger thresholds apply.",
        )

    if is_ferry is True:
        if isinstance(passengers, int) and passengers > FERRY_PASSENGER_THRESHOLD:
            return _decision(
                "in_scope",
                facts,
                clause_quotes,
                "The known passenger count exceeds the ferry threshold.",
            )
        if isinstance(passengers, int):
            return _decision(
                "out_of_scope",
                facts,
                clause_quotes,
                "The known passenger count is at or below the ferry threshold.",
            )
        return _decision(
            "unclear",
            facts,
            clause_quotes,
            "The ferry passenger count is unknown.",
        )

    if is_ferry is None:
        if (
            isinstance(passengers, int)
            and passengers > NONFERRY_PASSENGER_THRESHOLD
        ) or (
            isinstance(overnight, int)
            and overnight > NONFERRY_OVERNIGHT_THRESHOLD
        ):
            return _decision(
                "in_scope",
                facts,
                clause_quotes,
                "A known passenger or overnight count exceeds a non-ferry threshold.",
            )
        if isinstance(passengers, int) and passengers <= 49:
            return _decision(
                "out_of_scope",
                facts,
                clause_quotes,
                "The known passenger count is below every applicable threshold.",
            )
        return _decision(
            "unclear",
            facts,
            clause_quotes,
            "Ferry status and the applicable passenger thresholds cannot be "
            "established from the known facts.",
        )

    if (
        isinstance(passengers, int)
        and passengers > NONFERRY_PASSENGER_THRESHOLD
    ) or (
        isinstance(overnight, int)
        and overnight > NONFERRY_OVERNIGHT_THRESHOLD
    ):
        return _decision(
            "in_scope",
            facts,
            clause_quotes,
            "A known passenger or overnight passenger count exceeds a non-ferry threshold.",
        )

    if (
        isinstance(passengers, int)
        and passengers <= NONFERRY_PASSENGER_THRESHOLD
        and isinstance(overnight, int)
        and overnight <= NONFERRY_OVERNIGHT_THRESHOLD
    ):
        return _decision(
            "out_of_scope",
            facts,
            clause_quotes,
            "Known passenger and overnight passenger counts are below the "
            "non-ferry thresholds.",
        )
    if isinstance(passengers, int) and passengers <= 49:
        return _decision(
            "out_of_scope",
            facts,
            clause_quotes,
            "The known passenger count is below every applicable threshold.",
        )

    return _decision(
        "unclear",
        facts,
        clause_quotes,
        "A required passenger or overnight passenger count is unknown.",
    )


def scope_facts_from_job(data: dict[str, Any]) -> ScopeFacts:
    return ScopeFacts.model_validate(data)
