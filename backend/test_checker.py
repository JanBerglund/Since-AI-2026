import json
import unittest

from backend.checker import apply_rules


class RuleCheckerTests(unittest.TestCase):
    def test_explicit_violation_is_not_fine(self):
        design = {
            "ship": {"type": "cargo"},
            "doors": [
                {"id": "D-214", "page": 1, "bbox": [10, 10, 200, 100], "clear_width_mm": 780, "source": "demo"},
            ],
        }
        rules = [{
            "id": "door_clear_width",
            "standard": "ADA",
            "clause": "ADA 404.2.3",
            "thing": "door",
            "field": "clear_width_mm",
            "min": 815,
            "only_if": {},
            "verified": False,
        }]

        findings = apply_rules(design, rules)

        self.assertEqual(findings[0]["verdict"], "not_fine")
        self.assertIn("needs 815", findings[0]["label"])

    def test_missing_value_becomes_unknown(self):
        design = {
            "ship": {"type": "cargo"},
            "doors": [
                {"id": "D-300", "page": 2, "bbox": [5, 5, 50, 50], "source": "demo"},
            ],
        }
        rules = [{
            "id": "door_clear_width",
            "standard": "ADA",
            "clause": "ADA 404.2.3",
            "thing": "door",
            "field": "clear_width_mm",
            "min": 815,
            "only_if": {},
            "verified": False,
        }]

        findings = apply_rules(design, rules)

        self.assertEqual(findings[0]["verdict"], "unknown")
        self.assertIn("missing", findings[0]["label"].lower())

    def test_research_vessel_skips_ada_rules(self):
        design = {
            "ship": {"type": "research"},
            "doors": [
                {"id": "D-999", "page": 1, "bbox": [10, 10, 200, 100], "clear_width_mm": 700, "source": "demo"},
            ],
        }
        rules = [{
            "id": "door_clear_width",
            "standard": "ADA",
            "clause": "ADA 404.2.3",
            "thing": "door",
            "field": "clear_width_mm",
            "min": 815,
            "only_if": {},
            "verified": False,
        }]

        findings = apply_rules(design, rules)

        self.assertEqual(findings, [])

    def test_door_width_rule_does_not_apply_to_corridors(self):
        design = {
            "ship": {"type": "cargo"},
            "doors": [
                {"id": "D-1", "clear_width_mm": 900},
            ],
        }
        rules = [
            {
                "id": "corridor_width",
                "standard": "ADA",
                "clause": "ADA 403.5.1",
                "thing": "corridor",
                "field": "clear_width_mm",
                "min": 915,
                "only_if": {},
            }
        ]

        self.assertEqual(apply_rules(design, rules), [])


if __name__ == "__main__":
    unittest.main()
