from __future__ import annotations

import os
import re
import shutil
from typing import Any

import pytesseract
from PIL import Image


def resolve_tesseract_executable() -> str:
    """Find the real Tesseract executable on this machine, preferring the project-local E: install."""
    candidates = [
        os.environ.get("TESSERACT_PATH"),
        r"E:\OCR\tesseract.exe",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        shutil.which("tesseract"),
    ]

    for candidate in candidates:
        if not candidate:
            continue
        if os.path.exists(candidate):
            return candidate

    raise FileNotFoundError(
        r"Tesseract OCR executable not found. Install it to E:\OCR\tesseract.exe or add it to PATH."
    )


try:
    pytesseract.pytesseract.tesseract_cmd = resolve_tesseract_executable()
except (FileNotFoundError, OSError, ValueError):
    pytesseract.pytesseract.tesseract_cmd = None


def extract_doors_from_text(text: str) -> list[dict[str, Any]]:
    """Extract door ids and widths from free-form OCR or PDF text."""
    doors: list[dict[str, Any]] = []
    for line in (text or "").splitlines():
        candidate = re.sub(r"\s+", " ", line).strip()
        if not candidate:
            continue

        door_match = re.search(r"(?i)\b(?:d|door)[\s-]*(\d{1,4})\b", candidate)
        width_match = re.search(r"(\d{2,4})\s*(?:mm|MM)", candidate)
        if not door_match or not width_match:
            continue

        door_number = int(door_match.group(1))
        width = int(width_match.group(1))
        doors.append({
            "id": f"D-{door_number}",
            "clear_width_mm": width,
            "source": "ocr text",
        })

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for door in doors:
        door_id = door["id"]
        if door_id in seen:
            continue
        seen.add(door_id)
        unique.append(door)
    return unique


def _ocr_page_text(page: Any) -> str:
    """Render a PDF page to an image, OCR it, and return the recognized text."""
    try:
        pix = page.get_pixmap(matrix=None)
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        text = pytesseract.image_to_string(image, config="--psm 6")
        return text or ""
    except Exception:
        return ""


def extract_doors_from_pdf_page(page: Any) -> list[dict[str, Any]]:
    """Extract door facts from either raw text or OCR text on a single PDF page."""
    text = page.get_text("text") or ""
    doors = extract_doors_from_text(text)
    if doors:
        return doors

    ocr_text = _ocr_page_text(page)
    return extract_doors_from_text(ocr_text)
