from __future__ import annotations

from typing import Any


def rule_applies(ship: dict[str, Any], rule: dict[str, Any]) -> bool:
    """Return True when the rule is relevant to this ship."""
    only_if = rule.get("only_if") or {}
    if not only_if:
        return True

    for key, expected_value in only_if.items():
        if ship.get(key) != expected_value:
            return False
    return True


def apply_rules(design: dict[str, Any], rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply a small set of deterministic rules to a design JSON."""
    ship = design.get("ship", {})
    entities = {
        "door": design.get("doors", []),
        "corridor": design.get("corridors", []),
    }
    findings: list[dict[str, Any]] = []

    for rule in rules:
        if not rule_applies(ship, rule):
            continue

        standard = str(rule.get("standard", "")).upper()
        if ship.get("type", "").lower() == "research" and standard in {"ADA", "PVAG"}:
            continue

        for item in entities.get(rule.get("thing"), []):
            field_name = rule.get("field")
            if field_name != "clear_width_mm":
                continue

            value = item.get(field_name)
            item_id = item.get("id", rule.get("thing", "item"))
            page = item.get("page", 1)
            bbox = item.get("bbox", [0, 0, 0, 0])
            source = item.get("source", "unknown")

            if value is None:
                findings.append(
                    {
                        "number": len(findings) + 1,
                        "rule": rule.get("id", "rule"),
                        "clause": rule.get("clause", "unknown"),
                        "item": item_id,
                        "verdict": "unknown",
                        "label": f"{item_id}: clear width missing",
                        "page": page,
                        "bbox": bbox,
                        "source": source,
                    }
                )
                continue

            threshold = rule.get("min", 0)
            if value >= threshold:
                verdict = "fine"
                label = f"{item_id}: {value} mm, meets {threshold}"
            else:
                verdict = "not_fine"
                label = f"{item_id}: {value} mm, needs {threshold}"

            findings.append(
                {
                    "number": len(findings) + 1,
                    "rule": rule.get("id", "rule"),
                    "clause": rule.get("clause", "unknown"),
                    "item": item_id,
                    "verdict": verdict,
                    "label": label,
                    "page": page,
                    "bbox": bbox,
                    "source": source,
                }
            )

    return findings
