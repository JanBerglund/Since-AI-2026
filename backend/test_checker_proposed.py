import unittest

from backend.checker import apply_rules

DOOR = {
    "id": "door_clear_width",
    "standard": "ADA",
    "clause": "404.2.3",
    "text": "door width",
    "thing": "door",
    "field": "clear_width_mm",
    "min": 812.8,
    "verified": False,
    "applies_when": [{"field": "vessel_type", "op": "in", "value": ["passenger", "cruise"]}],
}
PASSENGER = {"vessel_type": "passenger"}


def run(doors, ship=PASSENGER, rules=None, **kwargs):
    return apply_rules({"ship": ship, "doors": doors}, rules or [DOOR], **kwargs)


class CheckerTests(unittest.TestCase):
    def test_basic_verdicts(self):
        findings = run([{"id": "A", "clear_width_mm": 900}, {"id": "B", "clear_width_mm": 780}, {"id": "C"}])
        self.assertEqual([finding["verdict"] for finding in findings], ["fine", "not_fine", "unknown"])

    def test_813_passes_because_threshold_is_812_8(self):
        self.assertEqual(run([{"id": "A", "clear_width_mm": 813}])[0]["verdict"], "fine")

    def test_no_fake_location(self):
        finding = run([{"id": "A", "clear_width_mm": 900}])[0]
        self.assertIsNone(finding["page"])
        self.assertIsNone(finding["bbox"])

    def test_research_vessel_gives_not_applicable(self):
        findings = run([{"id": "A", "clear_width_mm": 100}], ship={"vessel_type": "research"})
        self.assertEqual([finding["verdict"] for finding in findings], ["not_applicable"])

    def test_unknown_vessel_type_gives_one_unknown(self):
        findings = run([{"id": "A", "clear_width_mm": 900}, {"id": "B", "clear_width_mm": 900}], ship={})
        self.assertEqual([finding["verdict"] for finding in findings], ["unknown"])
        self.assertEqual(findings[0]["missing"], ["vessel_type"])

    def test_old_type_key_still_works(self):
        finding = run([{"id": "A", "clear_width_mm": 900}], ship={"type": "passenger"})[0]
        self.assertEqual(finding["verdict"], "fine")

    def test_where_filter(self):
        rule = dict(DOOR, where=[{"field": "accessible_route", "op": "==", "value": True}])
        findings = run(
            [
                {"id": "A", "clear_width_mm": 700, "accessible_route": False},
                {"id": "B", "clear_width_mm": 700, "accessible_route": True},
                {"id": "C", "clear_width_mm": 700},
            ],
            rules=[rule],
        )
        self.assertEqual(
            [(finding["item"], finding["verdict"]) for finding in findings],
            [("B", "not_fine"), ("C", "unknown")],
        )

    def test_text_numbers_and_garbage(self):
        findings = run([{"id": "A", "clear_width_mm": "780"}, {"id": "B", "clear_width_mm": "n/a"}])
        self.assertEqual([finding["verdict"] for finding in findings], ["not_fine", "unknown"])

    def test_low_confidence_is_unknown(self):
        finding = run([{"id": "A", "clear_width_mm": 700, "confidence": 0.3}])[0]
        self.assertEqual(finding["verdict"], "unknown")

    def test_verified_flag_is_passed_on(self):
        finding = run([{"id": "A", "clear_width_mm": 900}])[0]
        self.assertFalse(finding["verified"])

    def test_old_only_if_still_skips(self):
        rule = {"id": "x", "thing": "door", "field": "clear_width_mm", "min": 1, "only_if": {"vessel_type": "tug"}}
        self.assertEqual(run([{"id": "A", "clear_width_mm": 5}], rules=[rule]), [])

    def test_presence_rule_is_hooked_in(self):
        rule = {
            "id": "p",
            "kind": "presence",
            "standard": "MARPOL",
            "clause": "12",
            "text": "sludge tank shown",
            "look_for": ["SLUDGE TANK"],
            "exclude": ["SEWAGE"],
        }
        labels = [{"text": "WASTE OIL SLUDGE TANK", "page": 12, "bbox": [1, 2, 3, 4], "confidence": 0.7}]
        findings = apply_rules(
            {"ship": {"gross_tonnage": 2000}, "doors": []},
            [rule],
            labels=labels,
            pages_checked=[12],
        )
        self.assertEqual((findings[0]["verdict"], findings[0]["number"], findings[0]["page"]), ("fine", 1, 12))


if __name__ == "__main__":
    unittest.main()