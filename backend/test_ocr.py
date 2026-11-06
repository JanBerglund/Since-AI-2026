import unittest

from backend.ocr import extract_doors_from_text, resolve_tesseract_executable


class OcrParsingTests(unittest.TestCase):
    def test_extracts_door_measurements_from_ocr_text(self):
        text = """
        D-214 780 mm
        D-300 900 mm
        corridor 915 mm
        """
        doors = extract_doors_from_text(text)
        self.assertEqual(len(doors), 2)
        self.assertEqual(doors[0]["id"], "D-214")
        self.assertEqual(doors[0]["clear_width_mm"], 780)
        self.assertEqual(doors[1]["id"], "D-300")
        self.assertEqual(doors[1]["clear_width_mm"], 900)

    def test_resolves_working_tesseract_binary(self):
        resolved = resolve_tesseract_executable()
        self.assertTrue(resolved)
        self.assertTrue(resolved.lower().endswith("tesseract.exe"))


if __name__ == "__main__":
    unittest.main()


if __name__ == "__main__":
    unittest.main()
