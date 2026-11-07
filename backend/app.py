from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import Any
import uuid

import fitz
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.checker import apply_rules, conditions_hold, rule_applies
from backend.ocr import extract_doors_from_pdf_page
from backend.ocr_labels import get_page_labels, ocr_available
from backend.overlay import draw_report
from backend.reporting import generate_report_image

app = FastAPI(title="Ship Compliance Checker API", version="0.1.0")
FILES_DIR = Path(__file__).resolve().parent / "files"
FILES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=str(FILES_DIR)), name="files")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _rules_path() -> Path:
    return Path(__file__).resolve().parent.parent / "rules.json"


def _load_rules() -> list[dict[str, Any]]:
    with _rules_path().open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _parse_pages(raw_pages: str, total_pages: int | None = None) -> list[int]:
    pages: list[int] = []
    for chunk in raw_pages.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            try:
                start_text, end_text = chunk.split("-", 1)
                start = int(start_text)
                end = int(end_text)
            except ValueError as error:
                raise HTTPException(status_code=400, detail=f"Invalid page selection {chunk!r}.") from error
            if start < 1 or end < start or (total_pages is not None and end > total_pages):
                limit = f"1-{total_pages}" if total_pages is not None else "a positive page range"
                raise HTTPException(status_code=400, detail=f"Page selection {chunk!r} is outside {limit}.")
            pages.extend(range(start, end + 1))
        else:
            try:
                page_number = int(chunk)
            except ValueError as error:
                raise HTTPException(status_code=400, detail=f"Invalid page selection {chunk!r}.") from error
            if page_number < 1 or (total_pages is not None and page_number > total_pages):
                limit = f"1-{total_pages}" if total_pages is not None else "a positive page number"
                raise HTTPException(status_code=400, detail=f"Page selection {chunk!r} is outside {limit}.")
            pages.append(page_number)
    return pages


def _empty_design(
    vessel_type: str | None = None,
    gross_tonnage: float | None = None,
) -> dict[str, Any]:
    return {
        "ship": {"vessel_type": vessel_type, "gross_tonnage": gross_tonnage},
        "doors": [],
    }


def _parse_door_schedule(
    content: bytes,
    filename: str,
    selected_pages: list[int],
) -> list[dict[str, Any]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=400, detail="Door schedule must be UTF-8 encoded.") from error

    suffix = Path(filename).suffix.lower()
    if suffix == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise HTTPException(status_code=400, detail="Door schedule JSON is invalid.") from error
        rows = data if isinstance(data, list) else data.get("doors") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise HTTPException(status_code=400, detail="Door schedule JSON must contain a doors array.")
    elif suffix == ".csv":
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise HTTPException(status_code=400, detail="Door schedule CSV must include a header row.")
        rows = [
            {str(key).strip().lower(): value for key, value in row.items() if key is not None}
            for row in reader
        ]
    else:
        raise HTTPException(status_code=400, detail="Door schedule must be a .csv or .json file.")

    parsed: list[dict[str, Any]] = []
    selected_page_set = set(selected_pages)
    for row_number, row in enumerate(rows, start=2):
        if not isinstance(row, dict):
            raise HTTPException(status_code=400, detail=f"Door schedule row {row_number} must be an object.")

        door_id = str(row.get("id") or row.get("door_id") or "").strip()
        if not door_id:
            raise HTTPException(status_code=400, detail=f"Door schedule row {row_number} is missing id.")

        width_value = row.get("clear_width_mm")
        if width_value is None or str(width_value).strip() == "":
            width = None
        else:
            try:
                width = int(str(width_value).strip().lower().removesuffix("mm").strip())
            except ValueError as error:
                raise HTTPException(
                    status_code=400,
                    detail=f"Door schedule row {row_number} has an invalid clear_width_mm.",
                ) from error
            if width < 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Door schedule row {row_number} has a negative clear_width_mm.",
                )

        page_value = row.get("page")
        if page_value is None or str(page_value).strip() == "":
            page_number = None
        else:
            try:
                page_number = int(page_value)
            except (TypeError, ValueError) as error:
                raise HTTPException(
                    status_code=400,
                    detail=f"Door schedule row {row_number} has an invalid page.",
                ) from error
            if page_number < 1:
                raise HTTPException(status_code=400, detail=f"Door schedule row {row_number} has an invalid page.")

        if selected_page_set and page_number is not None and page_number not in selected_page_set:
            continue

        parsed.append(
            {
                "id": door_id,
                "clear_width_mm": width,
                "page": page_number,
                "bbox": None,
                "source": f"door schedule: {Path(filename).name}",
            }
        )

    if not parsed:
        raise HTTPException(status_code=400, detail="Door schedule has no rows for the selected pages.")
    return parsed


def _extract_design_from_pdf(
    pdf_bytes: bytes,
    selected_pages: set[int] | None = None,
    vessel_type: str | None = None,
    gross_tonnage: float | None = None,
) -> dict[str, Any]:
    """Convert a simple PDF with page text into the minimal design format we check."""
    design = _empty_design(vessel_type, gross_tonnage)

    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as error:
        raise HTTPException(status_code=400, detail="Could not open the PDF.") from error

    for page_number, page in enumerate(document, start=1):
        if selected_pages is not None and page_number not in selected_pages:
            continue

        detected = extract_doors_from_pdf_page(page)
        if not detected:
            continue

        for door in detected:
            door_id = str(door.get("id", "door")).upper()
            width_text = door.get("clear_width_mm")
            if width_text is None:
                continue

            design["doors"].append(
                {
                    "id": door_id,
                    "page": page_number,
                    "bbox": None,
                    "clear_width_mm": int(width_text),
                    "source": f"pdf page {page_number}",
                }
            )

    document.close()
    return design


@app.get("/health")
def health() -> dict[str, str]:
    """Simple health check for the backend."""
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, str]:
    """Base route for quick manual checking in a browser."""
    return {"message": "Ship compliance API is running"}


@app.post("/check")
async def check(
    file: UploadFile = File(...),
    pages: str = Form(...),
    door_schedule: UploadFile | None = File(None),
    vessel_type: str | None = Form(None),
    gross_tonnage: float | None = Form(None),
) -> dict[str, Any]:
    """Apply deterministic checks to design data and return the app contract."""
    content = await file.read()
    filename = (file.filename or "").lower()
    total_pages = None
    if filename.endswith(".pdf"):
        try:
            page_document = fitz.open(stream=content, filetype="pdf")
        except Exception as error:
            raise HTTPException(status_code=400, detail="Could not open the PDF.") from error
        total_pages = page_document.page_count
        page_document.close()

    selected_pages = _parse_pages(pages, total_pages)
    rules = _load_rules()

    design = _empty_design(vessel_type, gross_tonnage)
    if door_schedule is not None:
        schedule_content = await door_schedule.read()
        design["doors"] = _parse_door_schedule(
            schedule_content,
            door_schedule.filename or "schedule.csv",
            selected_pages,
        )
    elif content:
        if filename.endswith(".json"):
            try:
                design = json.loads(content.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                design = _empty_design(vessel_type, gross_tonnage)
            if isinstance(design, dict):
                ship = design.get("ship")
                if not isinstance(ship, dict):
                    ship = {}
                else:
                    ship = dict(ship)
                if vessel_type is not None:
                    ship["vessel_type"] = vessel_type
                if gross_tonnage is not None:
                    ship["gross_tonnage"] = gross_tonnage
                design["ship"] = ship
            else:
                design = _empty_design(vessel_type, gross_tonnage)
        elif filename.endswith(".pdf"):
            try:
                design = _extract_design_from_pdf(
                    content,
                    set(selected_pages) or None,
                    vessel_type,
                    gross_tonnage,
                )
            except (OSError, RuntimeError) as error:
                raise HTTPException(status_code=503, detail=str(error)) from error

    labels = []
    if filename.endswith(".pdf"):
        try:
            document = fitz.open(stream=content, filetype="pdf")
            try:
                for page_number in selected_pages:
                    page = document[page_number - 1]
                    if not page.get_text("words") and not ocr_available():
                        raise RuntimeError(
                            "Tesseract OCR was not found. Set TESSERACT_PATH or install it (see README)."
                        )
                    labels.extend(
                        get_page_labels(
                            page,
                            page_number,
                            content,
                            cache_dir=FILES_DIR.parent / "ocr_cache",
                        )
                    )
            finally:
                document.close()
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    findings = apply_rules(design, rules, labels=labels, pages_checked=selected_pages)
    if selected_pages:
        findings = [
            finding
            for finding in findings
            if finding.get("page") is None or finding["page"] in selected_pages
        ]

    ship_facts = dict(design.get("ship") or {})
    if "vessel_type" not in ship_facts and "type" in ship_facts:
        ship_facts["vessel_type"] = ship_facts["type"]
    door_rule = next((rule for rule in rules if rule.get("id") == "door_clear_width"), None)
    door_rule_applies = False
    if door_rule is not None and rule_applies(ship_facts, door_rule):
        applicability, _ = conditions_hold(door_rule.get("applies_when", []), ship_facts)
        standard = str(door_rule.get("standard", "")).upper()
        research_vessel_exempt = (
            str(ship_facts.get("vessel_type", "")).lower() == "research"
            and standard in {"ADA", "PVAG"}
        )
        door_rule_applies = applicability == "yes" and not research_vessel_exempt

    if filename.endswith(".pdf") and door_schedule is None and selected_pages and door_rule_applies:
        detected_pages = {
            int(door["page"])
            for door in design.get("doors", [])
            if door.get("page") is not None
        }
        for page_number in selected_pages:
            if page_number in detected_pages:
                continue
            findings.append(
                {
                    "rule": "measurement_not_detected",
                    "clause": "Extraction status",
                    "item": f"Page {page_number}",
                    "verdict": "unknown",
                    "label": "No door clear-width measurement was recognized; no compliance verdict was made.",
                    "page": page_number,
                    "bbox": None,
                    "source": f"PDF page {page_number} text/OCR",
                }
            )

    for index, finding in enumerate(findings, start=1):
        finding["number"] = index

    summary = {
        "checked": len(findings),
        "fine": sum(1 for item in findings if item["verdict"] == "fine"),
        "not_fine": sum(1 for item in findings if item["verdict"] == "not_fine"),
        "unknown": sum(1 for item in findings if item["verdict"] == "unknown"),
        "not_applicable": sum(1 for item in findings if item["verdict"] == "not_applicable"),
    }

    report_pages = selected_pages or [
        finding["page"] for finding in findings if finding.get("page") is not None
    ] or [1]
    request_id = uuid.uuid4().hex
    request_dir = FILES_DIR / request_id
    request_dir.mkdir(parents=True, exist_ok=True)
    images = []

    if filename.endswith(".pdf"):
        draw_report(
            content,
            findings,
            request_dir / "annotated.pdf",
            request_dir / "report",
            pages=report_pages,
        )
        images = [
            {"page": page, "url": f"/files/{request_id}/report_page{page}.png"}
            for page in report_pages
        ]
    else:
        for page in report_pages:
            page_findings = [finding for finding in findings if finding.get("page") == page]
            img_path = request_dir / f"report_page{page}.png"
            generate_report_image(page, page_findings, img_path)
            images.append({"page": page, "url": f"/files/{request_id}/report_page{page}.png"})

    return {
        "summary": summary,
        "findings": findings,
        "images": images,
    }
