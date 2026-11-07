# Suggested changes to backend/app.py and backend/ocr.py

Small, separate edits. Do them in this order and run the tests after each one.

## 1. Stop inventing ship facts (app.py)

    def _empty_design():
        return {"ship": {"type": "cargo"}, "doors": []}      # <- "cargo" is made up

Every upload is treated as a cargo ship. Use unknown instead, and take real facts from the user:

    def _empty_design(vessel_type=None, gross_tonnage=None):
        return {"ship": {"vessel_type": vessel_type, "gross_tonnage": gross_tonnage}, "doors": []}

Add two OPTIONAL form fields to /check (`vessel_type: str | None = Form(None)`,
`gross_tonnage: float | None = Form(None)`) and two inputs on the website ("Ship type", "Gross tonnage",
both optional). Applicability (ADA/PVAG, MARPOL 400 GT) depends on them, and the Meyer drawing does not
state gross tonnage. Empty = unknown = the rule says "cannot tell if this rule applies".

## 2. Do not invent door facts (app.py)

In `_extract_design_from_pdf` and `_parse_door_schedule` remove `"accessible_route": True` (nobody said
that) and use `"bbox": None` instead of `[0, 0, 0, 0]` (overlay.py now skips findings without a box).

## 3. Findings without a page (app.py, in check())

The new checker returns findings with `page: None` (rule does not apply, applicability unknown,
presence rule not found). This line then crashes:

    if int(finding.get("page", 1)) in selected_pages

Use:

    findings = [f for f in findings if f.get("page") is None or f["page"] in selected_pages]

and delete the lines that force a page:

    if not selected_pages:
        finding["page"] = 1

Also make the per-page image loop use `f.get("page") == page` (None never matches, so those findings
only appear in the table).

## 4. Pass labels to the checker (app.py)

    from backend.ocr_labels import get_page_labels, ocr_available
    ...
    labels = []
    if filename.endswith(".pdf"):
        doc = fitz.open(stream=content, filetype="pdf")
        for n in selected_pages:
            labels += get_page_labels(doc[n - 1], n, content, cache_dir=FILES_DIR.parent / "ocr_cache")
        doc.close()
    findings = apply_rules(design, rules, labels=labels, pages_checked=selected_pages)

(Put ocr_labels.py, presence.py and checker_proposed.py -> checker.py in backend/.)

## 5. Validate input and stop swallowing errors (app.py, ocr.py)

- `_parse_pages`: `int("abc")` gives a 500 error. Catch ValueError, check 1 <= page <= number of pages,
  return HTTP 400 with a clear message.
- `_extract_design_from_pdf`: `except Exception: return design` hides a broken PDF as "no door found".
  Return HTTP 400 "Could not open the PDF" instead.
- `ocr.py` `_ocr_page_text`: `except Exception: return ""` makes "Tesseract is not installed" look like
  "no measurement found". Let the error through (ocr_labels.py raises a clear RuntimeError) and return
  HTTP 503 with the message.

## 6. Summary numbers (app.py)

`"checked": len(selected_pages)` counts pages, but the website prints "N checked: x fine, y not fine, ..."
as if N were findings. Use `len(findings)` and send pages in another field if you want to show them.

## 7. The report image never sees the PDF (app.py -> reporting.py)

    generate_report_image(page, page_findings, img_path)

gets no PDF, so it cannot draw on the drawing. Replace it with overlay.py's draw_report (pass the uploaded
PDF; it saves one annotated PDF and a PNG per page). It also needs a per-request folder instead of the fixed
`report_page{n}.png`, otherwise two users overwrite each other's images.
