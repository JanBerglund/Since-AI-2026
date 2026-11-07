from __future__ import annotations

from collections.abc import Collection
from pathlib import Path
from typing import Any

import pymupdf

# Change colours here. Values are (red, green, blue) from 0 to 1.
COLORS = {
    "fine":     (0.10, 0.65, 0.25),   # green
    "not_fine": (0.85, 0.10, 0.10),   # red
    "unknown":  (1.00, 0.60, 0.00),   # amber
}
NAMES = {"fine": "Fine", "not_fine": "Not fine", "unknown": "Cannot determine"}


# --- Rotated pages -------------------------------------------------------------------------
# Many CAD drawings are stored sideways (page.rotation = 90). All boxes in this project are in
# VISUAL coordinates (x, y as you see the page, 0,0 = top-left). These helpers convert them
# to what PyMuPDF needs for drawing. On normal pages they do nothing.
def _rect(page, r):
    return pymupdf.Rect(r) * page.derotation_matrix

def _pt(page, p):
    return pymupdf.Point(p) * page.derotation_matrix

def _text(page, p, s, **kw):
    page.insert_text(_pt(page, p), s, rotate=page.rotation, **kw)


def draw_report(
    pdf_source: str | Path | bytes,
    findings: list[dict[str, Any]],
    out_pdf: str | Path,
    png_prefix: str | Path,
    pages: Collection[int] | None = None,
) -> list[str]:
    """Draws the findings on top of the original drawing.
    Saves one annotated PDF and PNGs for selected pages. Returns PNG file names."""
    if isinstance(pdf_source, bytes):
        doc = pymupdf.open(stream=pdf_source, filetype="pdf")
    else:
        doc = pymupdf.open(pdf_source)

    selected_pages = set(pages) if pages is not None else None
    pngs = []

    for page in doc:
        page_number = page.number + 1
        if selected_pages is not None and page_number not in selected_pages:
            continue

        page_findings = [f for f in findings if f.get("page") == page_number]

        # 1. coloured box + number badge + label for each finding THAT HAS A LOCATION
        #    (bbox None or all zeros = location unknown: not drawn, only counted in the summary)
        located = [f for f in page_findings if f.get("bbox") and any(f["bbox"])]
        for f in located:
            color = COLORS[f["verdict"]]
            box = pymupdf.Rect(f["bbox"])          # visual coordinates
            page.draw_rect(_rect(page, box), color=color, fill=color, fill_opacity=0.35, width=1.5)

            # number badge in the top-left corner of the box
            centre = pymupdf.Point(box.x0, box.y0)
            page.draw_circle(_pt(page, centre), 7, color=color, fill=color)
            _text(page, (centre.x - 3, centre.y + 3), str(f["number"]), fontsize=8, color=(1, 1, 1))

            # label only for red and amber items (it explains WHY)
            if f["verdict"] != "fine":
                width = pymupdf.get_text_length(f["label"], fontsize=8) + 6
                x = min(box.x1 + 4, page.rect.width - width - 4)
                y = box.y0 - 18 if box.y0 < 300 else box.y1 + 6      # above or below the box
                label_box = pymupdf.Rect(x, y, x + width, y + 12)
                page.draw_rect(_rect(page, label_box), color=color, fill=(1, 1, 1), width=1)
                _text(page, (x + 3, y + 9), f["label"], fontsize=8, color=color)

        # 2. legend (top of page)
        page.draw_rect(_rect(page, (10, 10, 400, 31)), color=None, fill=(1, 1, 1))
        x = 20
        for verdict in ("fine", "not_fine", "unknown"):
            page.draw_rect(_rect(page, (x, 15, x + 12, 27)), color=COLORS[verdict], fill=COLORS[verdict])
            _text(page, (x + 17, 25), NAMES[verdict], fontsize=9, color=(0, 0, 0))
            x += 120

        # 3. summary line (bottom of page)
        count = {v: sum(1 for f in page_findings if f["verdict"] == v) for v in COLORS}
        summary = (f"Page {page.number + 1}: {len(page_findings)} checked - "
                   f"{count['fine']} fine, {count['not_fine']} not fine, {count['unknown']} cannot determine")
        if len(located) < len(page_findings):
            summary += f" ({len(page_findings) - len(located)} without location, not drawn)"
        page.draw_rect(_rect(page, (10, page.rect.height - 31, 700, page.rect.height - 8)), color=None, fill=(1, 1, 1))
        _text(page, (20, page.rect.height - 15), summary, fontsize=10, color=(0, 0, 0))

        # 4. save this page as a PNG
        png_name = f"{png_prefix}_page{page_number}.png"
        page.get_pixmap(dpi=110).save(png_name)
        pngs.append(png_name)

    doc.save(out_pdf)
    doc.close()
    return pngs
