"""Find deterministic numeric contradictions among human-reviewed claims."""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path
from typing import Literal

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


def _normal_key(value: str) -> str:
    return " ".join(value.casefold().split())


def find_contradictions(claims: list[SpecClaim]) -> list[ConsistencyPair]:
    pairs: list[ConsistencyPair] = []
    for claim_a, claim_b in itertools.combinations(claims, 2):
        if (
            _normal_key(claim_a.subject) != _normal_key(claim_b.subject)
            or _normal_key(claim_a.quantity) != _normal_key(claim_b.quantity)
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
        pairs.append(
            ConsistencyPair(
                id=f"consistency-{len(pairs) + 1:04d}",
                subject=claim_a.subject,
                quantity=claim_a.quantity,
                claim_a=claim_a,
                claim_b=claim_b,
                reason=(
                    f"Values differ after unit normalization: "
                    f"{claim_a.value} {claim_a.unit} vs "
                    f"{claim_b.value} {claim_b.unit}."
                ),
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
        pairs = find_contradictions(claims)
        write_json(args.output, [pair.model_dump(mode="json") for pair in pairs])
    except (OSError, ValueError) as error:
        print(f"Consistency check failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    for pair in pairs:
        print(json.dumps(pair.model_dump(mode="json"), ensure_ascii=False, indent=2))
    print(f"Found {len(pairs)} contradiction pair(s); saved to {args.output}")


if __name__ == "__main__":
    main()
