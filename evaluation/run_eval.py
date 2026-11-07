from __future__ import annotations

import argparse
import json
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import fitz
import pytesseract

from backend.checker import apply_rules
from backend.ocr import resolve_tesseract_executable
from backend.ocr_labels import get_page_labels

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = Path(__file__).with_name("cases_rules.json")
DEFAULT_GROUND_TRUTH = Path(__file__).with_name("page12_ground_truth.json")
DEFAULT_RESULTS = Path(__file__).with_name("results.md")
FUZZY_MATCH_THRESHOLD = 0.70


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_rule_cases(
    cases: list[dict[str, Any]],
    rules: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Run the deterministic checker against cases with hand-authored expectations."""
    rule_by_id = {rule["id"]: rule for rule in rules}
    results = []
    for case in cases:
        if case.get("synthetic") is not True:
            raise ValueError(f"Rule case {case.get('id')} is not explicitly marked synthetic")
        rule_id = case["rule_id"]
        if rule_id not in rule_by_id:
            raise ValueError(f"Unknown rule id {rule_id!r} in case {case['id']}")

        case_input = case["input"]
        findings = apply_rules(
            case_input["design"],
            [rule_by_id[rule_id]],
            labels=case_input.get("labels", []),
            pages_checked=case_input.get("pages_checked", []),
        )
        if len(findings) != 1:
            raise ValueError(f"Case {case['id']} produced {len(findings)} findings; expected one")

        predicted = findings[0]["verdict"]
        expected = case["expected_verdict"]
        results.append(
            {
                "id": case["id"],
                "rule_id": rule_id,
                "expected": expected,
                "predicted": predicted,
                "match": expected == predicted,
                "finding": findings[0],
            }
        )

    metrics = {
        "total_cases": len(results),
        "caught_violations": sum(
            row["expected"] == "not_fine" and row["predicted"] == "not_fine" for row in results
        ),
        "missed_violations": sum(
            row["expected"] == "not_fine" and row["predicted"] == "fine" for row in results
        ),
        "false_alarms": sum(
            row["expected"] == "fine" and row["predicted"] == "not_fine" for row in results
        ),
        "unknowns": sum(row["predicted"] == "unknown" for row in results),
        "not_applicable": sum(row["predicted"] == "not_applicable" for row in results),
        "mismatches": sum(not row["match"] for row in results),
    }
    return results, metrics


def resolve_pdf(source_pdf: str, override: str | None = None) -> Path:
    configured_path = Path(override or source_pdf).expanduser()
    candidates = [configured_path]
    if not configured_path.is_absolute():
        candidates.extend(
            [
                PROJECT_ROOT / configured_path,
                Path.home() / "Downloads" / configured_path.name,
            ]
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    searched = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(f"Could not find the real-page PDF. Searched: {searched}")


def compare_ocr_labels(
    ground_truth: list[dict[str, str]],
    ocr_labels: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Match human labels to OCR output one-to-one using normalized exact/fuzzy text."""
    available = list(enumerate(ocr_labels))
    results = []
    for truth in ground_truth:
        expected_text = " ".join(truth.get("text", "").split())
        if not expected_text:
            continue
        normalized_truth = expected_text.casefold()

        exact_index = next(
            (
                index
                for index, (_, label) in enumerate(available)
                if " ".join(str(label.get("text", "")).split()).casefold() == normalized_truth
            ),
            None,
        )
        if exact_index is not None:
            _, label = available.pop(exact_index)
            results.append(
                {
                    "id": truth["id"],
                    "human_text": expected_text,
                    "status": "found exactly",
                    "ocr_text": label.get("text", ""),
                    "confidence": label.get("confidence"),
                    "similarity": 1.0,
                }
            )
            continue

        best_index = None
        best_ratio = -1.0
        for index, (_, label) in enumerate(available):
            candidate_text = " ".join(str(label.get("text", "")).split())
            ratio = SequenceMatcher(None, normalized_truth, candidate_text.casefold()).ratio()
            if ratio > best_ratio:
                best_index, best_ratio = index, ratio

        best_label = available[best_index][1] if best_index is not None else None
        if best_label is not None and best_ratio >= FUZZY_MATCH_THRESHOLD:
            available.pop(best_index)
            status = "found with errors"
        else:
            status = "missed"

        results.append(
            {
                "id": truth["id"],
                "human_text": expected_text,
                "status": status,
                "ocr_text": best_label.get("text", "") if best_label else "",
                "confidence": best_label.get("confidence") if best_label else None,
                "similarity": best_ratio if best_label else None,
            }
        )
    return results


def evaluate_real_page(
    ground_truth: dict[str, Any],
    pdf_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """OCR the requested real PDF page and compare only against human-filled labels."""
    pytesseract.pytesseract.tesseract_cmd = resolve_tesseract_executable()
    pdf_bytes = pdf_path.read_bytes()
    page_number = int(ground_truth["page"])
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if not 1 <= page_number <= document.page_count:
            raise ValueError(f"Ground-truth page {page_number} is outside 1-{document.page_count}")
        ocr_labels = get_page_labels(
            document[page_number - 1],
            page_number,
            pdf_bytes,
            cache_dir=PROJECT_ROOT / "backend" / "ocr_cache",
        )
    finally:
        document.close()

    comparisons = compare_ocr_labels(ground_truth.get("labels", []), ocr_labels)
    return comparisons, ocr_labels


def _confidence(value: Any) -> str:
    return f"{value:.3f}" if isinstance(value, (int, float)) else "—"


def render_results(
    rule_results: list[dict[str, Any]],
    metrics: dict[str, int],
    ground_truth: dict[str, Any],
    pdf_path: Path,
    label_comparisons: list[dict[str, Any]],
    ocr_labels: list[dict[str, Any]],
) -> str:
    lines = [
        "# Evaluation Results",
        "",
        "> A tests rule logic on explicitly synthetic data; it does not measure vessel compliance or extraction accuracy.",
        "> B compares human-entered labels from the real PDF page with OCR output and is the real measure of extraction accuracy.",
        "",
        "## A: Synthetic rule cases",
        "",
        f"Dataset: `{DEFAULT_CASES.name}` ({metrics['total_cases']} synthetic cases). Expected verdicts are hand-entered from `rules.json` thresholds; the checker is not used to generate them.",
        "",
        "| Case | Rule | Expected | Predicted | Match |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rule_results:
        lines.append(
            f"| {row['id']} | {row['rule_id']} | {row['expected']} | {row['predicted']} | {'yes' if row['match'] else '**NO**'} |"
        )

    lines.extend(
        [
            "",
            "| Metric | Count |",
            "| --- | ---: |",
            f"| Caught violations (expected and predicted `not_fine`) | {metrics['caught_violations']} |",
            f"| Missed violations (expected `not_fine`, predicted `fine`; dangerous error) | **{metrics['missed_violations']}** |",
            f"| False alarms (expected `fine`, predicted `not_fine`) | {metrics['false_alarms']} |",
            f"| Unknowns (abstentions) | {metrics['unknowns']} |",
            f"| Not applicable | {metrics['not_applicable']} |",
            f"| All expected/predicted mismatches | {metrics['mismatches']} |",
            "",
            "## B: Real page-12 OCR check",
            "",
            f"Source PDF: `{pdf_path}`  ",
            f"Page: {ground_truth['page']}  ",
            f"Human labels filled: {sum(bool(label.get('text', '').strip()) for label in ground_truth.get('labels', []))}/{len(ground_truth.get('labels', []))}  ",
            f"OCR labels extracted: {len(ocr_labels)}  ",
            f"Fuzzy text-match threshold: {FUZZY_MATCH_THRESHOLD:.2f} similarity (normalized exact matches are checked first).",
            "",
        ]
    )

    if label_comparisons:
        lines.extend(
            [
                "| Human label ID | Human text | Status | OCR text | OCR confidence | Similarity |",
                "| --- | --- | --- | --- | ---: | ---: |",
            ]
        )
        for row in label_comparisons:
            similarity = f"{row['similarity']:.3f}" if row["similarity"] is not None else "—"
            lines.append(
                f"| {row['id']} | {row['human_text']} | {row['status']} | {row['ocr_text']} | {_confidence(row['confidence'])} | {similarity} |"
            )
    else:
        lines.append(
            "No human ground-truth labels have been entered yet. Per-label accuracy is therefore not scored; fill `text` in `page12_ground_truth.json` by reading the drawing, then rerun this script."
        )

    lines.extend(
        [
            "",
            "### OCR output (machine labels, not ground truth)",
            "",
            "These are the page-12 labels emitted by `backend/ocr_labels.py`; they must not be treated as human transcription.",
            "",
            "| OCR label | Confidence |",
            "| --- | ---: |",
        ]
    )
    for label in ocr_labels:
        escaped_text = str(label.get("text", "")).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {escaped_text} | {_confidence(label.get('confidence'))} |")

    lines.append("")
    return "\n".join(lines)


def run_evaluation(
    cases_path: Path = DEFAULT_CASES,
    ground_truth_path: Path = DEFAULT_GROUND_TRUTH,
    pdf_override: str | None = None,
) -> tuple[str, dict[str, int]]:
    rules = load_json(PROJECT_ROOT / "rules.json")
    cases_data = load_json(cases_path)
    if cases_data.get("dataset_type") != "synthetic":
        raise ValueError("Rule cases must be explicitly marked as synthetic")
    rule_results, metrics = evaluate_rule_cases(cases_data["cases"], rules)

    ground_truth = load_json(ground_truth_path)
    pdf_path = resolve_pdf(ground_truth["source_pdf"], pdf_override)
    label_comparisons, ocr_labels = evaluate_real_page(ground_truth, pdf_path)
    return render_results(rule_results, metrics, ground_truth, pdf_path, label_comparisons, ocr_labels), metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate synthetic rule cases and OCR against human page-12 labels.")
    parser.add_argument("--pdf", help="Path to the real GA PDF; defaults to page12_ground_truth.json, then Downloads.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    args = parser.parse_args()

    try:
        report, metrics = run_evaluation(args.cases, args.ground_truth, args.pdf)
    except Exception as error:
        print(f"Evaluation could not complete: {error}", file=__import__("sys").stderr)
        return 1

    results_path = args.results if args.results.is_absolute() else PROJECT_ROOT / args.results
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nSaved: {results_path}")

    if metrics["missed_violations"] != 0:
        print("FAIL: dangerous missed violations must be zero.", file=__import__("sys").stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
