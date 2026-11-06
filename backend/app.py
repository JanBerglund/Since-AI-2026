from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import fitz
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.checker import apply_rules
from backend.ocr import extract_doors_from_pdf_page
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


def _parse_pages(raw_pages: str) -> list[int]:
    pages: list[int] = []
    for chunk in raw_pages.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start_text, end_text = chunk.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            pages.extend(range(start, end + 1))
        else:
            pages.append(int(chunk))
    return pages


def _empty_design() -> dict[str, Any]:
    return {"ship": {"type": "cargo"}, "doors": []}


def _extract_design_from_pdf(
    pdf_bytes: bytes,
    selected_pages: set[int] | None = None,
) -> dict[str, Any]:
    """Convert a simple PDF with page text into the minimal design format we check."""
    design = _empty_design()

    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return design

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
                    "bbox": [0, 0, 0, 0],
                    "clear_width_mm": int(width_text),
                    "accessible_route": True,
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
) -> dict[str, Any]:
    """Apply deterministic checks to design data and return the app contract."""
    selected_pages = _parse_pages(pages)
    rules = _load_rules()

    design = _empty_design()
    content = await file.read()
    filename = (file.filename or "").lower()
    if content:
        if filename.endswith(".json"):
            try:
                design = json.loads(content.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                design = _empty_design()
        elif filename.endswith(".pdf"):
            design = _extract_design_from_pdf(content, set(selected_pages) or None)

    findings = apply_rules(design, rules)
    if selected_pages:
        findings = [
            finding
            for finding in findings
            if int(finding.get("page", 1)) in selected_pages
        ]

    if filename.endswith(".pdf") and selected_pages:
        detected_pages = {
            int(door.get("page", 1))
            for door in design.get("doors", [])
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
                    "bbox": [0, 0, 0, 0],
                    "source": f"PDF page {page_number} text/OCR",
                }
            )

    for index, finding in enumerate(findings, start=1):
        finding["number"] = index
        if not selected_pages:
            finding["page"] = 1

    summary = {
        "checked": len(selected_pages) if selected_pages else max(1, len(findings)),
        "fine": sum(1 for item in findings if item["verdict"] == "fine"),
        "not_fine": sum(1 for item in findings if item["verdict"] == "not_fine"),
        "unknown": sum(1 for item in findings if item["verdict"] == "unknown"),
    }

    images = []
    for page in selected_pages or [findings[0]["page"] if findings else 1]:
        page_findings = [item for item in findings if int(item.get("page", 1)) == int(page)]
        img_path = FILES_DIR / f"report_page{page}.png"
        generate_report_image(page, page_findings, img_path)
        images.append({"page": page, "url": f"/files/report_page{page}.png"})

    return {
        "summary": summary,
        "findings": findings,
        "images": images,
    }
