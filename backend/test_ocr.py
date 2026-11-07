import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.ocr import _ocr_page_text, extract_doors_from_text, resolve_tesseract_executable


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

    def test_ocr_runtime_errors_are_not_swallowed(self):
        page = SimpleNamespace(
            get_pixmap=lambda **kwargs: SimpleNamespace(width=1, height=1, samples=b"\x00\x00\x00")
        )
        with patch("backend.ocr.Image.frombytes", return_value=object()), patch(
            "backend.ocr.pytesseract.image_to_string", side_effect=RuntimeError("OCR failed")
        ):
            with self.assertRaisesRegex(RuntimeError, "OCR failed"):
                _ocr_page_text(page)


if __name__ == "__main__":
    unittest.main()


if __name__ == "__main__":
    unittest.main()
