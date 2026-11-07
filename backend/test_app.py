import asyncio
from io import BytesIO
import unittest
from unittest.mock import patch

import fitz
from starlette.datastructures import UploadFile

from backend.app import _extract_design_from_pdf, check


def make_blank_pdf(page_count):
    document = fitz.open()
    for _ in range(page_count):
        document.new_page()
    pdf_bytes = document.tobytes()
    document.close()
    return pdf_bytes


class PdfCheckTests(unittest.TestCase):
    def test_pdf_extraction_visits_only_selected_pages(self):
        pdf_bytes = make_blank_pdf(3)
        with patch(
            "backend.app.extract_doors_from_pdf_page",
            return_value=[{"id": "D-1", "clear_width_mm": 900}],
        ) as extract_page:
            design = _extract_design_from_pdf(pdf_bytes, {3})

        self.assertEqual(extract_page.call_count, 1)
        self.assertEqual(design["doors"][0]["page"], 3)

    def test_pdf_without_recognized_width_returns_unknown(self):
        upload = UploadFile(
            filename="drawing.pdf",
            file=BytesIO(make_blank_pdf(12)),
        )
        result = asyncio.run(check(file=upload, pages="12", door_schedule=None))

        self.assertEqual(result["summary"]["unknown"], 1)
        self.assertEqual(result["findings"][0]["verdict"], "unknown")
        self.assertEqual(result["findings"][0]["page"], 12)

    def test_csv_schedule_uses_door_threshold_and_source(self):
        drawing = UploadFile(filename="drawing.pdf", file=BytesIO(make_blank_pdf(1)))
        schedule = UploadFile(
            filename="doors.csv",
            file=BytesIO(b"id,clear_width_mm,page\nD-214,780,1\nD-300,900,1\n"),
        )
        result = asyncio.run(check(file=drawing, pages="1", door_schedule=schedule))

        door_findings = [finding for finding in result["findings"] if finding["rule"] == "door_clear_width"]
        self.assertEqual([finding["verdict"] for finding in door_findings], ["not_fine", "fine"])
        self.assertTrue(all(finding["source"] == "door schedule: doors.csv" for finding in door_findings))
        self.assertEqual(result["summary"]["fine"], 1)
        self.assertEqual(result["summary"]["not_fine"], 1)

    def test_json_schedule_missing_width_returns_unknown(self):
        drawing = UploadFile(filename="drawing.pdf", file=BytesIO(make_blank_pdf(1)))
        schedule = UploadFile(
            filename="doors.json",
            file=BytesIO(b'{"doors":[{"id":"D-214","page":1}]}'),
        )
        result = asyncio.run(check(file=drawing, pages="1", door_schedule=schedule))

        self.assertEqual(result["summary"]["unknown"], 1)
        self.assertEqual(result["findings"][0]["verdict"], "unknown")
        self.assertIn("door schedule", result["findings"][0]["source"])


if __name__ == "__main__":
    unittest.main()