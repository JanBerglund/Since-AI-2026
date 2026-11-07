import asyncio
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import fitz
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from backend.app import _empty_design, _extract_design_from_pdf, _parse_pages, _parse_door_schedule, check


def make_blank_pdf(page_count):
    document = fitz.open()
    for _ in range(page_count):
        document.new_page()
    pdf_bytes = document.tobytes()
    document.close()
    return pdf_bytes


def run_check(**kwargs):
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch("backend.app.FILES_DIR", Path(temp_dir) / "files"):
            return asyncio.run(check(**kwargs))


class PdfCheckTests(unittest.TestCase):
    def test_ship_facts_are_optional_and_forwarded(self):
        self.assertEqual(
            _empty_design()["ship"],
            {"vessel_type": None, "gross_tonnage": None},
        )
        upload = UploadFile(
            filename="design.json",
            file=BytesIO(b'{"ship":{"type":"cargo"},"doors":[]}'),
        )
        with patch("backend.app.apply_rules", return_value=[]) as apply_rules, patch(
            "backend.app.generate_report_image"
        ):
            run_check(
                file=upload,
                pages="1",
                door_schedule=None,
                vessel_type="passenger",
                gross_tonnage=1200,
            )

        ship = apply_rules.call_args.args[0]["ship"]
        self.assertEqual(ship["vessel_type"], "passenger")
        self.assertEqual(ship["gross_tonnage"], 1200)

    def test_pdf_extraction_visits_only_selected_pages(self):
        pdf_bytes = make_blank_pdf(3)
        with patch(
            "backend.app.extract_doors_from_pdf_page",
            return_value=[{"id": "D-1", "clear_width_mm": 900}],
        ) as extract_page:
            design = _extract_design_from_pdf(pdf_bytes, {3})

        self.assertEqual(extract_page.call_count, 1)
        self.assertEqual(design["doors"][0]["page"], 3)

    def test_pdf_extraction_does_not_invent_door_location_or_route(self):
        with patch(
            "backend.app.extract_doors_from_pdf_page",
            return_value=[{"id": "D-1", "clear_width_mm": 900}],
        ):
            door = _extract_design_from_pdf(make_blank_pdf(1))["doors"][0]

        self.assertEqual(door["page"], 1)
        self.assertIsNone(door["bbox"])
        self.assertNotIn("accessible_route", door)

    def test_schedule_without_page_keeps_location_unknown(self):
        doors = _parse_door_schedule(
            b"id,clear_width_mm\nD-1,900\n",
            "doors.csv",
            [5],
        )

        self.assertIsNone(doors[0]["page"])
        self.assertIsNone(doors[0]["bbox"])
        self.assertNotIn("accessible_route", doors[0])

    def test_unlocated_schedule_measurement_does_not_add_not_detected_finding(self):
        drawing = UploadFile(filename="drawing.pdf", file=BytesIO(make_blank_pdf(1)))
        schedule = UploadFile(
            filename="doors.csv",
            file=BytesIO(b"id,clear_width_mm\nD-1,900\n"),
        )
        with patch("backend.app.generate_report_image"):
            result = run_check(
                    file=drawing,
                    pages="1",
                    door_schedule=schedule,
                    vessel_type="passenger",
                    gross_tonnage=2000,
            )

        door_findings = [finding for finding in result["findings"] if finding["rule"] == "door_clear_width"]
        self.assertEqual(len(door_findings), 1)
        self.assertEqual(door_findings[0]["verdict"], "fine")
        self.assertIsNone(door_findings[0]["page"])
        self.assertNotIn(
            "measurement_not_detected",
            [finding["rule"] for finding in result["findings"]],
        )

    def test_invalid_page_values_return_http_400(self):
        for raw_pages in ("abc", "0", "4", "2-1"):
            with self.subTest(raw_pages=raw_pages), self.assertRaises(HTTPException) as context:
                _parse_pages(raw_pages, total_pages=3)
            self.assertEqual(context.exception.status_code, 400)

    def test_invalid_pdf_returns_http_400(self):
        with self.assertRaises(HTTPException) as context:
            _extract_design_from_pdf(b"not a PDF")
        self.assertEqual(context.exception.status_code, 400)

    def test_ocr_runtime_error_returns_http_503(self):
        upload = UploadFile(filename="drawing.pdf", file=BytesIO(make_blank_pdf(1)))
        with patch("backend.app.extract_doors_from_pdf_page", return_value=[]), patch(
            "backend.app.get_page_labels", side_effect=RuntimeError("Tesseract unavailable")
        ), patch("backend.app.ocr_available", return_value=True):
            with self.assertRaises(HTTPException) as context:
                run_check(
                        file=upload,
                        pages="1",
                        door_schedule=None,
                        vessel_type="passenger",
                        gross_tonnage=300,
                )
        self.assertEqual(context.exception.status_code, 503)
        self.assertIn("Tesseract unavailable", context.exception.detail)

    def test_tesseract_not_found_from_door_extraction_returns_http_503(self):
        upload = UploadFile(filename="drawing.pdf", file=BytesIO(make_blank_pdf(1)))
        with patch(
            "backend.app.extract_doors_from_pdf_page",
            side_effect=FileNotFoundError("Tesseract executable missing"),
        ):
            with self.assertRaises(HTTPException) as context:
                run_check(
                        file=upload,
                        pages="1",
                        door_schedule=None,
                        vessel_type="passenger",
                        gross_tonnage=300,
                )
        self.assertEqual(context.exception.status_code, 503)
        self.assertIn("Tesseract executable missing", context.exception.detail)

    def test_pdf_without_recognized_width_returns_unknown(self):
        upload = UploadFile(
            filename="drawing.pdf",
            file=BytesIO(make_blank_pdf(12)),
        )
        result = run_check(
                file=upload,
                pages="12",
                door_schedule=None,
                vessel_type="passenger",
                gross_tonnage=300,
        )

        self.assertEqual(result["summary"]["unknown"], 1)
        measurement_finding = next(
            finding for finding in result["findings"] if finding["rule"] == "measurement_not_detected"
        )
        self.assertEqual(measurement_finding["verdict"], "unknown")
        self.assertEqual(measurement_finding["page"], 12)
        self.assertIsNone(measurement_finding["bbox"])

    def test_findings_without_pages_remain_in_table_only(self):
        upload = UploadFile(
            filename="design.json",
            file=BytesIO(b'{"ship":{},"doors":[]}'),
        )
        with patch("backend.app.generate_report_image") as generate_report_image:
            result = run_check(
                    file=upload,
                    pages="1",
                    door_schedule=None,
                    vessel_type=None,
                    gross_tonnage=None,
            )

        self.assertTrue(result["findings"])
        self.assertTrue(all(finding["page"] is None for finding in result["findings"]))
        self.assertEqual(generate_report_image.call_args.args[0], 1)
        self.assertEqual(generate_report_image.call_args.args[1], [])

    def test_summary_checked_counts_findings_not_selected_pages(self):
        upload = UploadFile(
            filename="design.json",
            file=BytesIO(
                b'{"doors":[{"id":"D-1","clear_width_mm":800,"page":1}]}'
            ),
        )
        with patch("backend.app.generate_report_image"):
            result = run_check(
                    file=upload,
                    pages="1-3",
                    door_schedule=None,
                    vessel_type="passenger",
                    gross_tonnage=300,
            )

        self.assertEqual(len(result["findings"]), 2)
        self.assertEqual(result["summary"]["checked"], 2)

    def test_summary_counts_not_applicable_findings(self):
        upload = UploadFile(
            filename="design.json",
            file=BytesIO(
                b'{"ship":{"vessel_type":"research","gross_tonnage":300},"doors":[]}'
            ),
        )
        with patch("backend.app.generate_report_image"):
            result = run_check(
                    file=upload,
                    pages="1",
                    door_schedule=None,
                    vessel_type="research",
                    gross_tonnage=300,
            )

        self.assertEqual(result["summary"]["checked"], 3)
        self.assertEqual(result["summary"]["not_applicable"], 3)

    def test_measurement_not_detected_requires_applicable_door_rule(self):
        with patch("backend.app.extract_doors_from_pdf_page", return_value=[]), patch(
            "backend.app.get_page_labels", return_value=[]
        ), patch("backend.app.ocr_available", return_value=True), patch("backend.app.draw_report"):
            results = {}
            for vessel_type, gross_tonnage in ((None, None), ("research", 2000), ("passenger", 2000)):
                upload = UploadFile(filename="drawing.pdf", file=BytesIO(make_blank_pdf(1)))
                result = run_check(
                        file=upload,
                        pages="1",
                        door_schedule=None,
                        vessel_type=vessel_type,
                        gross_tonnage=gross_tonnage,
                )
                results[vessel_type] = result["findings"]

        self.assertNotIn(
            "measurement_not_detected",
            [finding["rule"] for finding in results[None]],
        )
        self.assertNotIn(
            "measurement_not_detected",
            [finding["rule"] for finding in results["research"]],
        )
        self.assertIn(
            "measurement_not_detected",
            [finding["rule"] for finding in results["passenger"]],
        )

    def test_pdf_reports_are_request_scoped_and_only_render_selected_pages(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("backend.app.FILES_DIR", Path(temp_dir)), patch(
                "backend.app.extract_doors_from_pdf_page", return_value=[]
            ), patch("backend.app.get_page_labels", return_value=[]), patch(
                "backend.app.ocr_available", return_value=True
            ):
                results = []
                for _ in range(2):
                    upload = UploadFile(filename="drawing.pdf", file=BytesIO(make_blank_pdf(3)))
                    results.append(
                        asyncio.run(
                            check(
                                file=upload,
                                pages="2",
                                door_schedule=None,
                                vessel_type="passenger",
                                gross_tonnage=2000,
                            )
                        )
                    )

            image_urls = [result["images"][0]["url"] for result in results]
            request_ids = [url.split("/")[2] for url in image_urls]
            self.assertNotEqual(request_ids[0], request_ids[1])
            self.assertTrue(image_urls[0].endswith("/report_page2.png"))
            for request_id in request_ids:
                request_dir = Path(temp_dir) / request_id
                self.assertTrue((request_dir / "annotated.pdf").exists())
                self.assertTrue((request_dir / "report_page2.png").exists())
                self.assertFalse((request_dir / "report_page1.png").exists())
                self.assertFalse((request_dir / "report_page3.png").exists())

    def test_pdf_check_passes_selected_page_labels_to_checker(self):
        upload = UploadFile(
            filename="drawing.pdf",
            file=BytesIO(make_blank_pdf(3)),
        )
        labels = [{"text": "WASTE OIL SLUDGE TANK", "page": 2, "bbox": [1, 2, 3, 4], "confidence": 0.9}]
        with patch("backend.app.extract_doors_from_pdf_page", return_value=[]), patch(
            "backend.app.get_page_labels", return_value=labels
        ) as get_page_labels, patch("backend.app.ocr_available", return_value=True), patch(
            "backend.app.apply_rules", return_value=[]
        ) as apply_rules, patch("backend.app.generate_report_image"):
            run_check(
                    file=upload,
                    pages="2",
                    door_schedule=None,
                    vessel_type="research",
                    gross_tonnage=1200,
            )

        self.assertEqual(get_page_labels.call_count, 1)
        self.assertEqual(get_page_labels.call_args.args[1], 2)
        self.assertEqual(apply_rules.call_args.kwargs["labels"], labels)
        self.assertEqual(apply_rules.call_args.kwargs["pages_checked"], [2])

    def test_csv_schedule_uses_door_threshold_and_source(self):
        drawing = UploadFile(filename="drawing.pdf", file=BytesIO(make_blank_pdf(1)))
        schedule = UploadFile(
            filename="doors.csv",
            file=BytesIO(b"id,clear_width_mm,page\nD-214,780,1\nD-300,900,1\n"),
        )
        with patch("backend.app.generate_report_image"):
            result = run_check(
                    file=drawing,
                    pages="1",
                    door_schedule=schedule,
                    vessel_type="passenger",
                    gross_tonnage=300,
            )

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
        with patch("backend.app.generate_report_image"):
            result = run_check(
                    file=drawing,
                    pages="1",
                    door_schedule=schedule,
                    vessel_type="passenger",
                    gross_tonnage=300,
            )

        self.assertEqual(result["summary"]["unknown"], 1)
        self.assertEqual(result["findings"][0]["verdict"], "unknown")
        self.assertIn("door schedule", result["findings"][0]["source"])


if __name__ == "__main__":
    unittest.main()