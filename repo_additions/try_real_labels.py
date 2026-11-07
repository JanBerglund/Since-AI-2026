"""Run: python try_real_labels.py <GA.pdf> [page]   - OCR one page, then run the MARPOL presence rule on it."""
import sys, json, time
from pathlib import Path
import pymupdf
from ocr_labels import get_page_labels
from presence import evaluate_presence

pdf_path, page_no = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 12
pdf_bytes = Path(pdf_path).read_bytes()
doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

t = time.time()
labels = get_page_labels(doc[page_no - 1], page_no, pdf_bytes, cache_dir=Path("ocr_cache"))
print(f"{len(labels)} labels in {time.time() - t:.1f}s")
for lab in labels:
    if any(k in lab["text"].upper() for k in ("SLUDGE", "OILY", "SEWAGE", "WASTE")):
        print(f'  conf {lab["confidence"]:.2f}  "{lab["text"]}"')

rule = json.load(open("rules_proposed.json"))[2]
for gt in (None, 2000, 300):
    f = evaluate_presence(rule, {"vessel_type": "research", "gross_tonnage": gt}, labels, [page_no])
    print(f"gross_tonnage={gt}: {f['verdict']} - {f['label']}")
