"""Merge findings, locate specification quotes, and render report pages."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal

import pymupdf
from pydantic import BaseModel, ConfigDict

from claim_models import normalize_whitespace, quote_is_verbatim, write_json
from ingest_spec import SpecSection


ROOT = Path(__file__).resolve().parent
DEFAULT_PDF = ROOT / "data/spec/spec.pdf"
DEFAULT_SECTIONS = ROOT / "data/spec_sections.json"
DEFAULT_CONSISTENCY = ROOT / "claims/consistency.json"
DEFAULT_PVAG = ROOT / "claims/pvag_findings.json"
DEFAULT_OUTPUT = ROOT / "report/report.json"
RENDER_DPI = 130
QUOTE_CHUNK_WORDS = 10
QUOTE_CHUNK_OVERLAP = 2


class SpecReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section: str
    page: int
    quote: str
    rects: list[list[float]]


class ReportPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    n: int
    image: str
    w: int
    h: int


class ReportClause(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    quote: str
    url: str


class ReportFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["consistency", "pvag"]
    verdict: Literal["pass", "fail", "unknown"]
    scope: str
    scope_status: str
    hypothetical: str
    title: str
    reason: str
    spec_refs: list[SpecReference]
    clause: ReportClause | None


class Report(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pdf: str
    pages: list[ReportPage]
    findings: list[ReportFinding]
    scope: dict[str, Any]


class QuoteLocator:
    def __init__(self, document: pymupdf.Document) -> None:
        self.document = document
        self.misses: list[tuple[str, int]] = []
        self.located_quotes = 0

    def locate(self, section: SpecSection, quote: str) -> list[SpecReference]:
        normalized_quote = normalize_whitespace(quote)
        if not normalized_quote:
            self.misses.append((section.id, section.page))
            return []

        direct = self._search_all_pages(normalized_quote, section, quote)
        if direct:
            self.located_quotes += 1
            return direct

        words = normalized_quote.split()
        if len(words) < QUOTE_CHUNK_WORDS:
            chunks = [normalized_quote]
        else:
            step = QUOTE_CHUNK_WORDS - QUOTE_CHUNK_OVERLAP
            chunks = [
                " ".join(words[index : index + QUOTE_CHUNK_WORDS])
                for index in range(0, len(words), step)
            ]
            if len(words) > QUOTE_CHUNK_WORDS:
                tail = " ".join(words[-QUOTE_CHUNK_WORDS:])
                if tail != chunks[-1]:
                    chunks.append(tail)

        found: dict[int, list[list[float]]] = defaultdict(list)
        for chunk in chunks:
            for page_index, page in enumerate(self.document):
                for rect in page.search_for(chunk):
                    coordinates = [float(value) for value in rect]
                    if coordinates not in found[page_index + 1]:
                        found[page_index + 1].append(coordinates)

        if not found:
            self.misses.append((section.id, section.page))
            return []
        self.located_quotes += 1
        return [
            SpecReference(
                section=section.id,
                page=page_number,
                quote=quote,
                rects=rects,
            )
            for page_number, rects in sorted(found.items())
        ]

    def _search_all_pages(
        self,
        text: str,
        section: SpecSection,
        quote: str,
    ) -> list[SpecReference]:
        references = []
        for page_number, page in enumerate(self.document, start=1):
            rectangles = [
                [float(value) for value in rect]
                for rect in page.search_for(text)
            ]
            if rectangles:
                references.append(
                    SpecReference(
                        section=section.id,
                        page=page_number,
                        quote=quote,
                        rects=rectangles,
                    )
                )
        return references


def _read_optional_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError(f"Expected a JSON array of objects in {path}")
    return data


def _section_map(path: Path) -> dict[str, SpecSection]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array of sections in {path}")
    sections = [SpecSection.model_validate(item) for item in data]
    return {section.id: section for section in sections}


def _reference(
    claim: dict[str, Any],
    sections: dict[str, SpecSection],
    locator: QuoteLocator,
) -> list[SpecReference]:
    section_id = claim.get("section_id")
    quote = claim.get("quote")
    if not isinstance(section_id, str) or not isinstance(quote, str):
        return []
    section = sections.get(section_id)
    if section is None:
        raise ValueError(f"Finding refers to missing specification section {section_id!r}")
    if not quote_is_verbatim(quote, section.text):
        locator.misses.append((section.id, section.page))
        return [
            SpecReference(
                section=section.id,
                page=section.page,
                quote=quote,
                rects=[],
            )
        ]
    references = locator.locate(section, quote)
    return references or [
        SpecReference(
            section=section.id,
            page=section.page,
            quote=quote,
            rects=[],
        )
    ]


def _consistency_finding(
    item: dict[str, Any],
    sections: dict[str, SpecSection],
    locator: QuoteLocator,
) -> ReportFinding:
    claim_a = item.get("claim_a")
    claim_b = item.get("claim_b")
    if not isinstance(claim_a, dict) or not isinstance(claim_b, dict):
        raise ValueError(f"Consistency finding {item.get('id')} has no claim pair")
    claim_a_refs = _reference(claim_a, sections, locator)
    claim_b_refs = _reference(claim_b, sections, locator)
    refs = [*claim_a_refs, *claim_b_refs]
    return ReportFinding(
        id=str(item["id"]),
        kind="consistency",
        verdict="unknown",
        scope="not_applicable",
        scope_status="not_applicable",
        hypothetical="not_applicable",
        title=f"Possible conflict: {item.get('quantity', 'specification')} values need review",
        reason=str(item.get("reason", "Specification claims conflict.")),
        spec_refs=refs,
        clause=None,
    )


def _pvag_finding(
    item: dict[str, Any],
    sections: dict[str, SpecSection],
    locator: QuoteLocator,
    scope_status: str,
) -> ReportFinding:
    claim = item.get("claim")
    if not isinstance(claim, dict):
        raise ValueError(f"PVAG finding {item.get('id')} has no specification claim")
    refs = _reference(claim, sections, locator)
    clause_id = item.get("clause_id")
    clause_quote = item.get("clause_quote", "")
    clause_url = item.get("clause_url")
    clause = None
    if isinstance(clause_id, str) and isinstance(clause_url, str):
        clause = ReportClause(
            id=clause_id,
            quote=str(clause_quote),
            url=clause_url,
        )
    return ReportFinding(
        id=str(item["id"]),
        kind="pvag",
        verdict=item["verdict"],
        scope="hypothetical" if item.get("hypothetical", False) else "in_scope",
        scope_status=scope_status,
        hypothetical=(
            "hypothetical"
            if item.get("hypothetical", False)
            else str(item["hypothetical_verdict"])
        ),
        title=str(item.get("title", "PVAG comparison")),
        reason=str(item.get("reason", "")),
        spec_refs=refs,
        clause=clause,
    )


def build_report(
    pdf_path: Path,
    sections_path: Path,
    consistency_path: Path,
    pvag_path: Path,
    output_path: Path,
    pages_dir: Path,
    scope: dict[str, Any] | None = None,
) -> Report:
    sections = _section_map(sections_path)
    consistency = _read_optional_list(consistency_path)
    pvag = _read_optional_list(pvag_path)
    output_parent = output_path.parent.resolve()
    pages_dir.mkdir(parents=True, exist_ok=True)

    with pymupdf.open(pdf_path) as document:
        locator = QuoteLocator(document)
        pages = []
        for page_number, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(dpi=RENDER_DPI, alpha=False)
            image_path = pages_dir / f"p{page_number:03d}.png"
            pixmap.save(image_path)
            try:
                relative_image = image_path.resolve().relative_to(output_parent).as_posix()
            except ValueError:
                relative_image = image_path.resolve().as_posix()
            pages.append(
                ReportPage(
                    n=page_number,
                    image=relative_image,
                    w=pixmap.width,
                    h=pixmap.height,
                )
            )

        findings = [
            _consistency_finding(item, sections, locator)
            for item in consistency
        ]
        scope_data = scope or {}
        scope_status = str(scope_data.get("scope", "unclear"))
        findings.extend(
            _pvag_finding(item, sections, locator, scope_status)
            for item in pvag
        )
        facts = scope_data.get("facts", {})
        normalized_scope = {
            "result": scope_status,
            "facts": facts,
            "quotes": scope_data.get("clauses", {}),
            "sources": {
                name: value.get("source")
                for name, value in facts.items()
                if isinstance(value, dict) and value.get("source") is not None
            },
            "reason": scope_data.get("reason", ""),
        }
        result = Report(
            pdf=pdf_path.name,
            pages=pages,
            findings=findings,
            scope=normalized_scope,
        )

    write_json(output_path, result.model_dump(mode="json"))
    missing = len(locator.misses)
    verdict_counts: dict[str, int] = defaultdict(int)
    scope_counts: dict[str, int] = defaultdict(int)
    for finding in findings:
        verdict_counts[finding.verdict] += 1
        scope_counts[finding.scope] += 1
    for section_id, page_number in locator.misses:
        print(
            f"Quote not located: section={section_id}, page={page_number}",
            file=sys.stderr,
        )
    print(
        f"Specification quotes located: {locator.located_quotes}; "
        f"not located: {missing}"
    )
    print(f"Verdicts: {dict(sorted(verdict_counts.items()))}")
    print(f"Scope: {dict(sorted(scope_counts.items()))}")
    print(f"Rendered {len(pages)} pages at {RENDER_DPI} DPI")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--sections", type=Path, default=DEFAULT_SECTIONS)
    parser.add_argument("--consistency", type=Path, default=DEFAULT_CONSISTENCY)
    parser.add_argument("--pvag", type=Path, default=DEFAULT_PVAG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pages-dir", type=Path)
    args = parser.parse_args()
    pages_dir = args.pages_dir or args.output.parent / "pages"
    try:
        report = build_report(
            args.pdf,
            args.sections,
            args.consistency,
            args.pvag,
            args.output,
            pages_dir,
        )
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Report build failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(f"Saved {len(report.findings)} finding(s) to {args.output}")


if __name__ == "__main__":
    main()
