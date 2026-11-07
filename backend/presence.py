"""Presence rules: "this thing must be SHOWN on the drawing".
Example: MARPOL Annex I wants a tank for oil residues (sludge) on ships of 400 GT and above.

Standalone on purpose (no FastAPI, no PyMuPDF) so it is easy to test and to plug into checker.py.

Input
  rule   : dict from rules.json with "kind": "presence"
  ship   : dict of ship facts, e.g. {"vessel_type": "research", "gross_tonnage": None}
           (None or missing = we do not know)
  labels : OCR text labels, e.g. [{"text": "WASTE OIL/SLUDGE 4-31-0", "page": 12,
                                   "bbox": [x0, y0, x1, y1], "confidence": 0.7}]
  pages_checked : list of page numbers that were searched

Output: one finding dict. IMPORTANT design choices:
  - "Not found" is NEVER "not_fine". OCR can miss a label, or the tank can be on another sheet.
    It is "unknown".
  - "fine" means ONLY "the required item is labelled on the drawing". It does NOT mean the
    tank is big enough. The rule text must say that.
"""
import re
from difflib import SequenceMatcher

OPS = {
    ">=": lambda a, b: a >= b,
    ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
}


def _words(text):
    # keep only letters: "WASTE_OIL/SLUDGE 4-31-0" -> ["WASTE", "OIL", "SLUDGE"]; "TANK5" -> ["TANK"]
    return re.findall(r"[A-Z]+", text.upper())


def _same_word(a, b):
    if a == b:
        return True
    if len(a) >= 4 and len(b) >= 4:  # forgive small OCR errors, but only in longer words
        return SequenceMatcher(None, a, b).ratio() >= 0.85
    return False


def phrase_in(phrase, text):
    """True if the words of `phrase` appear next to each other in `text`."""
    want, have = _words(phrase), _words(text)
    if not want:
        return False
    for start in range(len(have) - len(want) + 1):
        if all(_same_word(w, h) for w, h in zip(want, have[start:start + len(want)])):
            return True
    return False


def check_applies(rule, ship):
    """Returns ("yes"|"no"|"unknown", name of the ship fact that decided it)."""
    for cond in rule.get("applies_when", []):
        value = ship.get(cond["field"])
        if value is None:
            return "unknown", cond["field"]
        if not OPS[cond["op"]](value, cond["value"]):
            return "no", cond["field"]
    return "yes", None


def evaluate_presence(rule, ship, labels, pages_checked):
    finding = {
        "rule": rule["id"],
        "clause": f'{rule["standard"]} {rule["clause"]}',
        "item": rule["text"],
        "verdict": "unknown",
        "label": "",
        "page": None,        # None = no location on the drawing, so nothing is drawn
        "bbox": None,
        "source": "",
        "missing": [],
        "pages_checked": list(pages_checked),
    }

    # 1. Does the rule apply to this ship?
    applies, field = check_applies(rule, ship)
    if applies == "unknown":
        finding["label"] = f"Cannot tell if this rule applies: '{field}' is not known"
        finding["missing"] = [field]
        return finding
    if applies == "no":
        finding["verdict"] = "not_applicable"
        finding["label"] = f"Does not apply to this ship ('{field}' is {ship[field]!r})"
        return finding

    # 2. Look for a matching label (and ignore labels that contain an excluded word)
    min_conf = rule.get("min_confidence", 0.6)
    weak = None
    for lab in labels:
        if lab["page"] not in pages_checked:
            continue
        if any(phrase_in(x, lab["text"]) for x in rule.get("exclude", [])):
            continue
        if not any(phrase_in(p, lab["text"]) for p in rule["look_for"]):
            continue
        if lab.get("confidence", 1.0) < min_conf:
            weak = weak or lab
            continue
        finding.update(verdict="fine", page=lab["page"], bbox=lab["bbox"],
                       label=f'Shown on drawing: "{lab["text"]}" (presence only, capacity not assessed)',
                       source=f'OCR, page {lab["page"]}')
        return finding

    # 3. Nothing usable found: unknown, never not_fine
    if weak:
        finding.update(
            page=weak.get("page"),
            bbox=weak.get("bbox"),
            source=f"OCR, page {weak['page']}" if weak.get("page") is not None else "OCR",
        )
        finding["label"] = f'A possible match "{weak["text"]}" was found but OCR confidence is too low'
    else:
        finding["label"] = "Not found on the pages checked (it may be missing, unreadable or on another sheet)"
    finding["missing"] = ["a readable label on the pages checked"]
    return finding
