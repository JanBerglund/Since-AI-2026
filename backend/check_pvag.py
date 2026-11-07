"""Compare reviewed ship claims with PVAG and record vessel scope separately."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Literal

from claim_models import SpecClaim, normalize_whitespace, write_json
from consistency import load_claims
from pvag_models import (
    ComparisonAssessment,
    JsonGenerator,
    ModelAssessment,
    PVAGFinding,
    Retriever,
)
from pvag_scope import ScopeFacts, determine_scope
from retrieval import CLAUSES_PATH, EMBEDDINGS_PATH, PVAGRetriever, SearchResult
from units import comparable_values, parse_number
from llm import GeminiClient


ROOT = Path(__file__).resolve().parent
DEFAULT_ACCEPTED = ROOT / "claims/accepted.json"
DEFAULT_OUTPUT = ROOT / "claims/pvag_findings.json"
NUMBER_IN_TEXT = re.compile(r"(?<![\w.])[+-]?\d+(?:[.,]\d+)?")
GEOMETRIC_OR_CAPACITY = re.compile(
    r"\b(width|height|length|depth|clearance|area|slope|gradient|"
    r"radius|diameter|distance|thickness|capacity|persons?|passengers?|"
    r"occupants?|berths?|occupancy)\b",
    re.IGNORECASE,
)


def is_geometric_or_capacity_claim(claim: SpecClaim) -> bool:
    searchable = f"{claim.quantity} {claim.subject}"
    if GEOMETRIC_OR_CAPACITY.search(searchable):
        return True
    return "count" in claim.quantity.casefold() and bool(
        re.search(r"\b(person|passenger|occupant|crew|berth|capacity)\b", claim.subject, re.I)
    )


def _prompt(claim: SpecClaim, results: list[SearchResult]) -> str:
    candidates = "\n\n".join(
        f"Clause {result.clause.id} — {result.clause.title}\n{result.clause.text}"
        for result in results
    )
    return (
        "Choose the single retrieved PVAG clause that directly sets a numeric "
        "requirement relevant to this specification claim. If no clause gives "
        "a directly comparable numeric threshold, use the most relevant clause "
        "only if it states a measurable threshold; otherwise return a JSON "
        "assessment with value='unknown', unit='', quote_from_clause='', and "
        "notes explaining no threshold, which will be treated as unknown. Do "
        "not compare the vessel value yourself. "
        "Extract comparison (min, max, exact), numeric threshold value, unit, "
        "and a verbatim quote containing that threshold. Use only normative "
        "clause text below, not advisory text.\n\n"
        f"Specification claim: {claim.subject}; {claim.quantity} = "
        f"{claim.value} {claim.unit}\nSpecification quote: {claim.quote}\n\n"
        f"Retrieved candidates:\n{candidates}"
    )


def _assessment(
    client: JsonGenerator,
    role: Literal["judgement", "extraction"],
    prompt: str,
    retrieved: dict[str, Clause],
) -> ModelAssessment:
    output = client.generate_json(prompt, ComparisonAssessment, role=role)
    if output == "invalid":
        return ModelAssessment(status="invalid", output=None, issue="Invalid model response")
    clause = retrieved.get(output.clause_id)
    if clause is None:
        return ModelAssessment(
            status="invalid",
            output=output,
            issue="Model selected a clause outside the retrieved candidates",
        )
    normalized_quote = normalize_whitespace(output.quote_from_clause)
    if not normalized_quote or normalized_quote not in normalize_whitespace(clause.text):
        return ModelAssessment(
            status="invalid",
            output=output,
            issue="Clause quote is not a verbatim substring after whitespace normalization",
        )
    threshold = parse_number(output.value)
    quote_numbers = {
        parse_number(number)
        for number in NUMBER_IN_TEXT.findall(output.quote_from_clause)
    }
    if threshold is None or threshold not in quote_numbers:
        return ModelAssessment(
            status="invalid",
            output=output,
            issue="Threshold value does not appear numerically in its quoted clause text",
        )
    return ModelAssessment(status="valid", output=output)


def _agreed_threshold(
    judgement: ModelAssessment,
    extraction: ModelAssessment,
) -> tuple[ComparisonAssessment | None, str | None]:
    if judgement.status != "valid" or extraction.status != "valid":
        return None, "At least one model response failed validation."
    first = judgement.output
    second = extraction.output
    if first is None or second is None:
        return None, "A validated model response was not retained."
    if first.clause_id != second.clause_id:
        return None, "Models selected different clause IDs."
    if first.comparison != second.comparison:
        return None, "Models disagreed on the comparison direction."
    values = comparable_values(first.value, first.unit, second.value, second.unit)
    if values is None or values[0] != values[1]:
        return None, "Models disagreed on the numeric threshold or unit."
    return first, None


def _compare_claim(
    claim: SpecClaim,
    threshold: ComparisonAssessment,
) -> tuple[Literal["pass", "fail", "unknown"], str]:
    values = comparable_values(claim.value, claim.unit, threshold.value, threshold.unit)
    if values is None:
        return "unknown", "Claim and clause threshold have non-numeric or incompatible units."
    actual, limit = values
    if threshold.comparison == "min":
        passed = actual >= limit
        operator = ">="
    elif threshold.comparison == "max":
        passed = actual <= limit
        operator = "<="
    else:
        passed = actual == limit
        operator = "=="
    verdict: Literal["pass", "fail"] = "pass" if passed else "fail"
    return verdict, (
        f"Python comparison: {claim.value} {claim.unit} {operator} "
        f"{threshold.value} {threshold.unit}."
    )


def check_claims(
    claims: list[SpecClaim],
    retriever: Retriever,
    judgement_client: JsonGenerator,
    extraction_client: JsonGenerator,
    *,
    scope_facts: ScopeFacts = ScopeFacts(),
) -> list[PVAGFinding]:
    scope = determine_scope(scope_facts, retriever.clauses)
    findings: list[PVAGFinding] = []
    pvag_clauses = {
        clause.id: clause for clause in retriever.clauses if clause.id.startswith("V")
    }
    for claim in claims:
        if not is_geometric_or_capacity_claim(claim):
            continue
        results = retriever.search(
            f"{claim.subject} {claim.quantity} {claim.value} {claim.unit} {claim.quote}",
            k=3,
            id_prefix="V",
        )
        candidate_map = {
            result.clause.id: result.clause
            for result in results
            if result.clause.id in pvag_clauses
        }
        judgement = ModelAssessment(
            status="invalid",
            output=None,
            issue="No PVAG clauses were retrieved for this claim.",
        )
        extraction = judgement.model_copy(deep=True)
        clause_id = None
        clause_quote = ""
        clause_url = None
        hypothetical: Literal["pass", "fail", "unknown"] = "unknown"
        if candidate_map:
            prompt = _prompt(claim, results)
            judgement = _assessment(
                judgement_client,
                "judgement",
                prompt,
                candidate_map,
            )
            extraction = _assessment(
                extraction_client,
                "extraction",
                prompt,
                candidate_map,
            )
            agreed, disagreement = _agreed_threshold(judgement, extraction)
            if agreed is not None:
                clause = candidate_map[agreed.clause_id]
                clause_id = clause.id
                clause_quote = agreed.quote_from_clause
                clause_url = clause.source_url
                hypothetical, comparison_reason = _compare_claim(claim, agreed)
                reason = comparison_reason
            else:
                reason = disagreement or "The model assessments could not be reconciled."
        else:
            reason = "No PVAG clause candidates were retrieved."

        verdict = hypothetical if scope.scope == "in_scope" else "unknown"
        if scope.scope != "in_scope":
            reason = f"{reason} PVAG scope is {scope.scope}: {scope.reason}"
        title = (
            candidate_map[clause_id].title
            if clause_id is not None
            else f"{claim.quantity} requirement"
        )
        findings.append(
            PVAGFinding(
                id=f"pvag-{len(findings) + 1:04d}",
                verdict=verdict,
                hypothetical_verdict=hypothetical,
                scope=scope.scope,
                scope_clause_id=scope.clause_id,
                scope_quote=scope.quote,
                title=title,
                reason=reason,
                claim=claim,
                clause_id=clause_id,
                clause_quote=clause_quote,
                clause_url=clause_url,
                judgement=judgement,
                extraction=extraction,
            )
        )
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accepted", type=Path, default=DEFAULT_ACCEPTED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--clauses", type=Path, default=CLAUSES_PATH)
    parser.add_argument("--embeddings", type=Path, default=EMBEDDINGS_PATH)
    args = parser.parse_args()
    try:
        claims = load_claims(args.accepted)
        retriever = PVAGRetriever(
            clauses_path=args.clauses,
            embeddings_path=args.embeddings,
        )
        findings = check_claims(
            claims,
            retriever,
            GeminiClient(),
            GeminiClient(),
        )
        write_json(
            args.output,
            [finding.model_dump(mode="json") for finding in findings],
        )
    except (OSError, RuntimeError, ValueError) as error:
        print(f"PVAG check failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    for finding in findings:
        print(
            f"{finding.id}: {finding.verdict} "
            f"(hypothetical={finding.hypothetical_verdict}, scope={finding.scope})"
        )
    print(f"Saved {len(findings)} PVAG finding(s) to {args.output}")


if __name__ == "__main__":
    main()
