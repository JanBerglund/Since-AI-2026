"""Find possible contradictions among human-reviewed claims."""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from claim_models import SpecClaim, write_json
from units import comparable_values


ROOT = Path(__file__).resolve().parent
DEFAULT_ACCEPTED = ROOT / "claims/accepted.json"
DEFAULT_OUTPUT = ROOT / "claims/consistency.json"
class ConsistencyPair(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["consistency"] = "consistency"
    subject: str
    quantity: str
    claim_a: SpecClaim
    claim_b: SpecClaim
    reason: str
    decision: Literal["yes", "no", "needs_review"]


class ConsistencyAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["yes", "no", "needs_review"]
    notes: str


class ConsistencyJudge(Protocol):
    def generate_json(
        self,
        prompt: str,
        output_model: type[ConsistencyAssessment],
        *,
        role: Literal["judgement"],
    ) -> ConsistencyAssessment | Literal["invalid"]: ...


def _normal_key(value: str) -> str:
    return " ".join(value.casefold().split())


def _subject_key(claim: SpecClaim) -> str:
    subject = _normal_key(claim.subject)
    if _normal_key(claim.quantity) in {"frequency", "voltage"}:
        if any(term in subject for term in ("pump", "ac", "power", "supply")):
            return "electrical-power-system"
    return subject


def _same_quote_span(claim_a: SpecClaim, claim_b: SpecClaim) -> bool:
    return _normal_key(claim_a.quote) == _normal_key(claim_b.quote)


def _judge_prompt(claim_a: SpecClaim, claim_b: SpecClaim) -> str:
    return (
        "You are the 31B consistency judge. Decide whether these two claims "
        "describe the same thing and different values. Return decision='yes' "
        "only for a real conflict, 'no' when they are compatible or refer to "
        "different things/conditions, and 'needs_review' when the evidence is "
        "ambiguous. Consider context, quote wording, and sections. Return "
        "both quotes and sections in your reasoning notes.\n\n"
        f"Claim A ({claim_a.section_id}): {claim_a.subject}; "
        f"{claim_a.quantity}={claim_a.value} {claim_a.unit}; "
        f"context={claim_a.context!r}; quote={claim_a.quote!r}\n"
        f"Claim B ({claim_b.section_id}): {claim_b.subject}; "
        f"{claim_b.quantity}={claim_b.value} {claim_b.unit}; "
        f"context={claim_b.context!r}; quote={claim_b.quote!r}"
    )


def find_contradictions(
    claims: list[SpecClaim],
    judge: ConsistencyJudge,
) -> list[ConsistencyPair]:
    pairs: list[ConsistencyPair] = []
    for claim_a, claim_b in itertools.combinations(claims, 2):
        if (
            claim_a.group_id
            and claim_a.group_id == claim_b.group_id
        ) or _same_quote_span(claim_a, claim_b):
            continue
        if (
            _subject_key(claim_a) != _subject_key(claim_b)
            or _normal_key(claim_a.quantity) != _normal_key(claim_b.quantity)
            or claim_a.context != claim_b.context
        ):
            continue
        values = comparable_values(
            claim_a.value,
            claim_a.unit,
            claim_b.value,
            claim_b.unit,
        )
        if values is None or values[0] == values[1]:
            continue
        print(
            f"Consistency candidate: {claim_a.section_id} vs {claim_b.section_id} "
            f"({claim_a.quantity})",
            file=sys.stdout,
        )
        decision = judge.generate_json(
            _judge_prompt(claim_a, claim_b),
            ConsistencyAssessment,
            role="judgement",
        )
        if decision == "invalid" or decision.decision == "no":
            continue
        pairs.append(
            ConsistencyPair(
                id=f"consistency-{len(pairs) + 1:04d}",
                subject=claim_a.subject,
                quantity=claim_a.quantity,
                claim_a=claim_a,
                claim_b=claim_b,
                reason=(
                    "Possible conflict, needs review. "
                    f"Values differ after unit normalization: "
                    f"{claim_a.value} {claim_a.unit} vs "
                    f"{claim_b.value} {claim_b.unit}. "
                    f"Judge notes: {decision.notes if decision != 'invalid' else 'invalid judge response'}"
                ),
                decision=decision.decision,
            )
        )
    return pairs


def load_claims(path: Path) -> list[SpecClaim]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array of accepted claims in {path}")
    return [SpecClaim.model_validate(item) for item in data]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accepted", type=Path, default=DEFAULT_ACCEPTED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        claims = load_claims(args.accepted)
        from llm import GeminiClient

        pairs = find_contradictions(claims, GeminiClient())
        write_json(args.output, [pair.model_dump(mode="json") for pair in pairs])
    except (OSError, ValueError) as error:
        print(f"Consistency check failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    for pair in pairs:
        print(json.dumps(pair.model_dump(mode="json"), ensure_ascii=False, indent=2))
    print(f"Found {len(pairs)} contradiction pair(s); saved to {args.output}")


if __name__ == "__main__":
    main()
