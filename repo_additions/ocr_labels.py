"""Turns one PDF page into TEXT LABELS: [{"text", "page", "bbox", "confidence"}].

- Uses the PDF's own text layer if it has one (exact, confidence 1.0).
- Otherwise runs Tesseract (pytesseract) on a picture of the page. pytesseract gives a confidence
  per word, so we use the real number (0-1) instead of a fixed guess.
- "bbox" is [x0, y0, x1, y1] in PDF points AS YOU SEE THE PAGE (top-left = 0,0), also for pages
  that are stored rotated. That is exactly what overlay.py draws with.
- Words that sit next to each other on one line are joined into a label
  ("SEWAGE" + "SLUDGE" + "TANK" -> "SEWAGE SLUDGE TANK"). The MARPOL rule relies on this so that a
  sewage tank is not mistaken for an oil sludge tank.
- Results are cached on disk (OCR takes seconds per page).

Known limits: text printed vertically or upside down is read badly by Tesseract in this mode.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

try:
    import pymupdf
except ImportError:  # older PyMuPDF
    import fitz as pymupdf

import pytesseract
from PIL import Image


def ocr_available() -> bool:
    """False if Tesseract cannot be started (so the API can say so instead of 'no door found')."""
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _text_layer_words(page) -> list[dict[str, Any]]:
    words = []
    for x0, y0, x1, y1, text, *_ in page.get_text("words"):
        rect = pymupdf.Rect(x0, y0, x1, y1) * page.rotation_matrix  # internal -> as you see it
        rect.normalize()
        words.append({"text": text, "bbox": [rect.x0, rect.y0, rect.x1, rect.y1], "confidence": 1.0})
    return words


def _ocr_words(page, dpi: int) -> list[dict[str, Any]]:
    if not ocr_available():
        raise RuntimeError("Tesseract OCR was not found. Set TESSERACT_PATH or install it (see README).")
    pix = page.get_pixmap(dpi=dpi, alpha=False)          # drawn as you see the page
    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    data = pytesseract.image_to_data(image, config="--oem 1 --psm 11", output_type=pytesseract.Output.DICT)
    scale = 72 / dpi                                      # pixels -> PDF points
    words = []
    for i, text in enumerate(data["text"]):
        text = (text or "").strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1
        if not text or conf < 0:
            continue
        x0, y0 = data["left"][i] * scale, data["top"][i] * scale
        x1, y1 = x0 + data["width"][i] * scale, y0 + data["height"][i] * scale
        words.append({"text": text, "bbox": [x0, y0, x1, y1], "confidence": conf / 100})
    return words


def group_words(words: list[dict[str, Any]], page_number: int) -> list[dict[str, Any]]:
    """Joins words on the same line that are close together into labels."""
    groups: list[list[dict[str, Any]]] = []
    ends: list[list[float]] = []                          # per group: [right edge, vertical centre]
    for w in sorted(words, key=lambda w: w["bbox"][0]):   # left to right
        x0, y0, x1, y1 = w["bbox"]
        height = max(y1 - y0, 1.0)
        centre = (y0 + y1) / 2
        best, best_gap = None, None
        for i, (right, c) in enumerate(ends):
            gap = x0 - right
            if abs(centre - c) <= 0.5 * height and -0.3 * height <= gap <= 1.2 * height:
                if best is None or gap < best_gap:
                    best, best_gap = i, gap
        if best is None:
            groups.append([w])
            ends.append([x1, centre])
        else:
            groups[best].append(w)
            ends[best] = [x1, centre]

    labels = []
    for g in groups:
        labels.append({
            "text": " ".join(w["text"] for w in g),
            "page": page_number,
            "bbox": [min(w["bbox"][0] for w in g), min(w["bbox"][1] for w in g),
                     max(w["bbox"][2] for w in g), max(w["bbox"][3] for w in g)],
            "confidence": round(sum(w["confidence"] for w in g) / len(g), 3),
        })
    return labels


def get_page_labels(page, page_number: int, pdf_bytes: bytes, cache_dir: Path | None = None,
                    dpi: int = 300) -> list[dict[str, Any]]:
    """Labels for one page (page_number starts at 1). Cached on disk if cache_dir is given."""
    cache_file = None
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(pdf_bytes).hexdigest()[:16]
        cache_file = cache_dir / f"{key}_p{page_number}_{dpi}.json"
        if cache_file.exists():
            return json.loads(cache_file.read_text(encoding="utf-8"))

    words = _text_layer_words(page) or _ocr_words(page, dpi)
    labels = group_words(words, page_number)

    if cache_file is not None:
        cache_file.write_text(json.dumps(labels), encoding="utf-8")
    return labels
