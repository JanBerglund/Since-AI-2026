import os
import unittest
from pathlib import Path

from backend.reporting import generate_report_image


class ReportingTests(unittest.TestCase):
    def test_generates_png_for_page(self):
        output_path = Path("backend/test_output/report_page_1.png")
        if output_path.exists():
            output_path.unlink()

        generate_report_image(
            page_number=1,
            findings=[
                {"page": 1, "verdict": "fine", "item": "D-300", "label": "D-300: 900 mm, meets 815"},
                {"page": 1, "verdict": "not_fine", "item": "D-214", "label": "D-214: 780 mm, needs 815"},
            ],
            output_path=output_path,
        )

        self.assertTrue(output_path.exists())
        self.assertGreater(output_path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
