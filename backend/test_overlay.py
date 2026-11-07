import tempfile
import unittest
from pathlib import Path

import pymupdf

from backend.overlay import draw_report


def make_pdf():
    document = pymupdf.open()
    document.new_page(width=400, height=300)
    document.new_page(width=400, height=300)
    rotated_page = document.new_page(width=400, height=300)
    rotated_page.set_rotation(90)
    pdf_bytes = document.tobytes()
    document.close()
    return pdf_bytes


class OverlayTests(unittest.TestCase):
    def test_selected_page_pngs_and_unlocated_findings(self):
        findings = [
            {
                "number": 1,
                "page": None,
                "bbox": [20, 20, 120, 60],
                "verdict": "not_fine",
                "label": "UNLOCATED FINDING",
            },
            {
                "number": 2,
                "page": 2,
                "bbox": None,
                "verdict": "not_fine",
                "label": "MISSING BOX FINDING",
            },
            {
                "number": 3,
                "page": 2,
                "bbox": [0, 0, 0, 0],
                "verdict": "unknown",
                "label": "ZERO BOX FINDING",
            },
            {
                "number": 4,
                "page": 3,
                "bbox": [30, 30, 140, 80],
                "verdict": "not_fine",
                "label": "LOCATED ROTATED MARK",
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            pngs = draw_report(
                make_pdf(),
                findings,
                temp_path / "annotated.pdf",
                temp_path / "report",
                pages=[2, 3],
            )

            self.assertEqual(len(pngs), 2)
            self.assertFalse((temp_path / "report_page1.png").exists())
            self.assertTrue((temp_path / "report_page2.png").exists())
            self.assertTrue((temp_path / "report_page3.png").exists())

            annotated = pymupdf.open(temp_path / "annotated.pdf")
            try:
                self.assertEqual(annotated.page_count, 3)
                self.assertNotIn("MISSING BOX FINDING", annotated[1].get_text())
                self.assertNotIn("ZERO BOX FINDING", annotated[1].get_text())
                self.assertNotIn("UNLOCATED FINDING", annotated[1].get_text())
                self.assertIn("LOCATED ROTATED MARK", annotated[2].get_text())
            finally:
                annotated.close()


if __name__ == "__main__":
    unittest.main()