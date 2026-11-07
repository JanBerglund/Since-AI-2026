import unittest

from backend.presence import evaluate_presence, phrase_in

RULE = {
    "id": "marpol_annex1_oil_residue_tank_shown",
    "kind": "presence",
    "standard": "MARPOL Annex I",
    "clause": "Reg. 12 (verify)",
    "text": "A tank for oil residues (sludge) is shown on the drawings",
    "applies_when": [{"field": "gross_tonnage", "op": ">=", "value": 400}],
    "look_for": ["SLUDGE TANK", "OIL SLUDGE", "WASTE OIL", "OIL RESIDUE"],
    "exclude": ["SEWAGE", "GREY WATER", "BLACK WATER"],
    "min_confidence": 0.6,
}
BIG = {"vessel_type": "research", "gross_tonnage": 2000}


def label(text, page=12, conf=0.7):
    return {"text": text, "page": page, "bbox": [1, 2, 3, 4], "confidence": conf}


class PresenceTests(unittest.TestCase):
    def test_oil_sludge_label_found(self):
        finding = evaluate_presence(RULE, BIG, [label("WASTE_OIL/SLUDGE 4-31-0")], [12])
        self.assertEqual(finding["verdict"], "fine")
        self.assertEqual(finding["page"], 12)

    def test_sewage_sludge_tank_must_not_count(self):
        finding = evaluate_presence(RULE, BIG, [label("SEWAGE SLUDGE TANK 3-45-4")], [12])
        self.assertEqual(finding["verdict"], "unknown")

    def test_ocr_garble_still_matches(self):
        finding = evaluate_presence(RULE, BIG, [label("SLUDGE- TANK5")], [12])
        self.assertEqual(finding["verdict"], "fine")

    def test_not_found_is_unknown_never_not_fine(self):
        finding = evaluate_presence(RULE, BIG, [label("FUEL OIL 6P")], [12])
        self.assertEqual(finding["verdict"], "unknown")

    def test_tonnage_unknown_gives_unknown(self):
        finding = evaluate_presence(RULE, {"vessel_type": "research"}, [label("WASTE OIL/SLUDGE")], [12])
        self.assertEqual(finding["verdict"], "unknown")
        self.assertEqual(finding["missing"], ["gross_tonnage"])

    def test_small_ship_not_applicable(self):
        finding = evaluate_presence(RULE, {"gross_tonnage": 300}, [], [12])
        self.assertEqual(finding["verdict"], "not_applicable")

    def test_low_confidence_match_is_unknown(self):
        candidate = label("WASTE OIL/SLUDGE", conf=0.58)
        finding = evaluate_presence(RULE, BIG, [candidate], [12])
        self.assertEqual(finding["verdict"], "unknown")
        self.assertEqual(finding["page"], 12)
        self.assertEqual(finding["bbox"], candidate["bbox"])

    def test_label_on_page_not_selected_is_ignored(self):
        finding = evaluate_presence(RULE, BIG, [label("WASTE OIL/SLUDGE", page=5)], [12])
        self.assertEqual(finding["verdict"], "unknown")

    def test_short_words_are_not_fuzzy(self):
        self.assertFalse(phrase_in("OIL SLUDGE", "OILY SLUDGE"))


if __name__ == "__main__":
    unittest.main()