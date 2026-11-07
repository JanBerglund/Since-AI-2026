from __future__ import annotations

from typing import Any

try:                                  # inside the backend package
    from .presence import evaluate_presence
except ImportError:                   # when run on its own (tests)
    from presence import evaluate_presence

OPS = {
    ">=": lambda a, b: a >= b, ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b, "<": lambda a, b: a < b,
    "==": lambda a, b: a == b, "!=": lambda a, b: a != b,
    "in": lambda a, b: a in b, "not_in": lambda a, b: a not in b,
}


def conditions_hold(conditions: list[dict[str, Any]], data: dict[str, Any]):
    """Checks a list of conditions against a dict (ship facts or one item).
    Returns ("yes" | "no" | "unknown", name of the field that decided it)."""
    for cond in conditions:
        value = data.get(cond["field"])
        if value is None:
            return "unknown", cond["field"]
        if not OPS[cond["op"]](value, cond["value"]):
            return "no", cond["field"]
    return "yes", None


def rule_applies(ship: dict[str, Any], rule: dict[str, Any]) -> bool:
    """OLD style: every key in only_if must equal the ship value. Kept so old rules still work."""
    for key, expected_value in (rule.get("only_if") or {}).items():
        if ship.get(key) != expected_value:
            return False
    return True


def _finding(rule, number, verdict, label, item="", page=None, bbox=None, source="", missing=None):
    return {
        "number": number,
        "rule": rule.get("id", "rule"),
        "clause": f'{rule.get("standard", "")} {rule.get("clause", "")}'.strip() or "unknown",
        "item": item or rule.get("text", ""),
        "verdict": verdict,
        "label": label,
        "page": page,          # None = no known location, nothing is drawn on the PDF
        "bbox": bbox,
        "source": source,
        "missing": missing or [],
        "verified": bool(rule.get("verified", False)),   # lets the UI warn about unverified rules
    }


def apply_rules(design: dict[str, Any], rules: list[dict[str, Any]],
                labels: list[dict[str, Any]] | None = None,
                pages_checked: list[int] | None = None) -> list[dict[str, Any]]:
    """Deterministic rule evaluation. `labels` (OCR text labels) and `pages_checked`
    are only needed for rules with "kind": "presence"."""
    ship = dict(design.get("ship", {}))
    if "vessel_type" not in ship and "type" in ship:      # accept the old key name
        ship["vessel_type"] = ship["type"]

    entities = {
        "door": design.get("doors", []),
        "corridor": design.get("corridors", []),
    }
    findings: list[dict[str, Any]] = []

    for rule in rules:
        number = len(findings) + 1

        # --- rules of the kind "must be shown on the drawing" -------------------------------
        if rule.get("kind") == "presence":
            f = evaluate_presence(rule, ship, labels or [], pages_checked or [])
            f.update(number=number, verified=bool(rule.get("verified", False)))
            findings.append(f)
            continue

        # --- does the rule apply to this ship? ---------------------------------------------
        if not rule_applies(ship, rule):                  # old style, silent skip
            continue
        applies, field = conditions_hold(rule.get("applies_when", []), ship)
        if applies == "no":
            findings.append(_finding(rule, number, "not_applicable",
                                     f"Does not apply to this ship ('{field}' is {ship.get(field)!r})"))
            continue
        if applies == "unknown":
            findings.append(_finding(rule, number, "unknown",
                                     f"Cannot tell if this rule applies: '{field}' is not known",
                                     missing=[field]))
            continue

        # --- check every item the rule is about --------------------------------------------
        field_name = rule.get("field")
        threshold = rule.get("min", 0)
        for item in entities.get(rule.get("thing"), []):
            item_id = item.get("id", rule.get("thing", "item"))
            where = dict(page=item.get("page"), bbox=item.get("bbox"), source=item.get("source", "unknown"))
            number = len(findings) + 1

            covered, cond_field = conditions_hold(rule.get("where", []), item)
            if covered == "no":
                continue                                  # the rule does not cover this item
            if covered == "unknown":
                findings.append(_finding(rule, number, "unknown",
                                         f"{item_id}: cannot tell if the rule covers it ('{cond_field}' missing)",
                                         item_id, missing=[cond_field], **where))
                continue

            raw = item.get(field_name)
            try:
                value = float(raw) if raw is not None else None
            except (TypeError, ValueError):
                findings.append(_finding(rule, number, "unknown",
                                         f"{item_id}: '{field_name}' is not a number ({raw!r})",
                                         item_id, missing=[field_name], **where))
                continue
            if value is None:
                findings.append(_finding(rule, number, "unknown", f"{item_id}: {field_name} missing",
                                         item_id, missing=[field_name], **where))
                continue
            if item.get("confidence", 1.0) < rule.get("min_confidence", 0.6):
                findings.append(_finding(rule, number, "unknown",
                                         f"{item_id}: {value:g} mm read with low confidence, please check",
                                         item_id, **where))
                continue

            if value + 1e-9 >= threshold:                 # tiny tolerance for decimal rounding
                findings.append(_finding(rule, number, "fine",
                                         f"{item_id}: {value:g} mm, meets {threshold:g}", item_id, **where))
            else:
                findings.append(_finding(rule, number, "not_fine",
                                         f"{item_id}: {value:g} mm, needs {threshold:g}", item_id, **where))
    return findings
