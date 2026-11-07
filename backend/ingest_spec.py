"""Extract numbered specification sections from a text-based PDF."""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

import pymupdf
from pydantic import BaseModel, ConfigDict


ROOT = Path(__file__).resolve().parent
DEFAULT_PDF = ROOT / "data/spec/spec.pdf"
DEFAULT_OUTPUT = ROOT / "data/spec_sections.json"
MAX_SECTION_CHARS = 6_000
HEADING = re.compile(
    r"^\s*(?P<id>\d+(?:\.\d+)*)(?:\s*[-–—]\s*|\s+)(?P<title>[A-Za-z].*?)\s*$"
)
TOC_ENTRY = re.compile(
    r"^\s*(?P<id>\d+(?:\.\d+)*)(?:\s*[-–—]\s*|\s+)"
    r"(?P<title>.*?)(?:\.{3,}|…{2,}|·{2,})\s*\d+\s*$"
)
HEADING_NUMBER = re.compile(r"^\s*(?P<id>\d+(?:\.\d+)*)\s*$")
PAGE_FOOTER = re.compile(r"^-\s*\d+\s*-$")
TOC_LEADER = re.compile(r"(?:\.{3,}|…{2,}|·{2,})")


class SpecSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    text: str
    page: int


def _is_toc_page(text: str) -> bool:
    if "contents" in text.casefold():
        return True
    return sum(bool(TOC_ENTRY.match(line)) for line in text.splitlines()) >= 3


def _contents_ids(document: pymupdf.Document) -> dict[str, str]:
    entries = {}
    for page in document:
        text = page.get_text("text", sort=True)
        if not _is_toc_page(text):
            continue
        for line in text.splitlines():
            match = TOC_ENTRY.match(line)
            if match:
                entries[match.group("id")] = match.group("title").strip().rstrip(".")
    return entries


def _heading(
    line: str,
    allowed_ids: dict[str, str] | None = None,
    *,
    bold: bool = False,
) -> tuple[str, str] | None:
    if TOC_LEADER.search(line):
        return None
    match = HEADING.match(line)
    if not match:
        return None
    clause_id, title = match.group("id", "title")
    title = title.strip().rstrip(".")
    if allowed_ids is not None:
        expected_title = re.sub(r"[^a-z0-9]", "", allowed_ids.get(clause_id, "").casefold())
        actual_title = re.sub(r"[^a-z0-9]", "", title.casefold())
        if (
            not expected_title
            or clause_id not in allowed_ids
            or difflib.SequenceMatcher(None, actual_title, expected_title).ratio() < 0.78
        ):
            return None
    if allowed_ids is None and not bold:
        return None
    if len(re.sub(r"[^A-Za-z]", "", title)) < 4:
        return None
    if re.fullmatch(r"[xX×]\s*[\d.,]+", title):
        return None
    return clause_id, title


def _page_lines(page: pymupdf.Page) -> list[tuple[str, bool]]:
    lines: list[tuple[str, bool]] = []
    data = page.get_text("dict", sort=True)
    has_lines = False
    for block in data["blocks"]:
        block_lines = block.get("lines", [])
        if block_lines and has_lines:
            lines.append(("", False))
        for line in block_lines:
            spans = [span for span in line["spans"] if span["text"].strip()]
            text = "".join(span["text"] for span in line["spans"]).strip()
            bold = bool(spans) and all(
                span["flags"] & 16 or "bold" in span["font"].casefold()
                for span in spans
            )
            lines.append((text, bold))
        has_lines = has_lines or bool(block_lines)
    return lines


def _merge_split_headings(
    lines: list[tuple[str, bool]],
    allowed_ids: dict[str, str] | None,
) -> list[tuple[str, bool]]:
    merged: list[tuple[str, bool]] = []
    index = 0
    while index < len(lines):
        text, bold = lines[index]
        number = HEADING_NUMBER.match(text)
        if number is not None:
            next_index = index + 1
            while next_index < len(lines) and not lines[next_index][0].strip():
                next_index += 1
            if next_index < len(lines):
                title, title_bold = lines[next_index]
                candidate = f"{number.group('id')} {title.strip()}"
                if title_bold and _heading(candidate, allowed_ids, bold=True):
                    merged.append((candidate, True))
                    index = next_index + 1
                    continue
        merged.append((text, bold))
        index += 1
    return merged


def _clean_line(line: str) -> str | None:
    stripped = line.strip()
    if PAGE_FOOTER.fullmatch(stripped):
        return None
    if stripped == "PERSEUS Deliverable Nr. 7.4":
        return ""
    return stripped


def _split_paragraph(paragraph: str, limit: int) -> list[str]:
    if len(paragraph) <= limit:
        return [paragraph]
    pieces: list[str] = []
    remaining = paragraph
    while len(remaining) > limit:
        split_at = remaining.rfind(" ", 0, limit + 1)
        if split_at < 1:
            split_at = limit
        pieces.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        pieces.append(remaining)
    return pieces


def _section_records(
    section_id: str,
    title: str,
    body_lines: list[tuple[str, int]],
    first_page: int,
) -> list[SpecSection]:
    heading_text = f"{section_id} {title}"
    paragraphs: list[tuple[str, int]] = []
    current_lines: list[str] = []
    current_page = first_page
    for line, page_number in [*body_lines, ("", first_page)]:
        if not line.strip():
            paragraph = " ".join(part.strip() for part in current_lines if part.strip())
            if paragraph:
                paragraphs.extend(
                    (piece, current_page)
                    for piece in _split_paragraph(paragraph, MAX_SECTION_CHARS)
                )
            current_lines = []
            continue
        if not current_lines:
            current_page = page_number
        current_lines.append(line)
    if not paragraphs:
        return [SpecSection(id=section_id, title=title, text=heading_text, page=first_page)]

    chunks: list[list[tuple[str, int]]] = []
    current: list[tuple[str, int]] = []
    current_length = 0
    for paragraph, page_number in paragraphs:
        added_length = len(paragraph) + (2 if current else 0)
        if current and current_length + added_length > MAX_SECTION_CHARS:
            chunks.append(current)
            current = []
            current_length = 0
        current.append((paragraph, page_number))
        current_length += len(paragraph) + (2 if len(current) > 1 else 0)
    if current:
        chunks.append(current)

    sections = []
    for index, chunk in enumerate(chunks, 1):
        record_id = section_id if index == 1 else f"{section_id}#{index}"
        page = chunk[0][1]
        text = "\n\n".join(paragraph for paragraph, _ in chunk)
        sections.append(
            SpecSection(
                id=record_id,
                title=title,
                text=f"{heading_text}\n\n{text}",
                page=page,
            )
        )
    return sections


def extract_sections(pdf_path: Path) -> list[SpecSection]:
    sections: list[SpecSection] = []
    active_id: str | None = None
    active_title = ""
    active_page = 0
    body_lines: list[tuple[str, int]] = []

    with pymupdf.open(pdf_path) as document:
        allowed_ids = _contents_ids(document)
        if not allowed_ids:
            allowed_ids = None
        for page_number, page in enumerate(document, start=1):
            page_lines = _merge_split_headings(_page_lines(page), allowed_ids)
            raw_text = "\n".join(line for line, _ in page_lines)
            if _is_toc_page(raw_text):
                continue
            for original_line, bold in page_lines:
                line = _clean_line(original_line)
                if line is None:
                    continue
                match = _heading(line, allowed_ids, bold=bold)
                if match is None:
                    body_lines.append((line, page_number))
                    continue
                if active_id is not None:
                    sections.extend(
                        _section_records(
                            active_id,
                            active_title,
                            body_lines,
                            active_page,
                        )
                    )
                active_id, active_title = match
                active_page = page_number
                body_lines = []

    if active_id is not None:
        sections.extend(
            _section_records(
                active_id,
                active_title,
                body_lines,
                active_page,
            )
        )
    if not sections:
        raise ValueError(f"No numbered sections found in {pdf_path}")
    return sections


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        sections = extract_sections(args.pdf)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                [section.model_dump() for section in sections],
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Could not ingest specification: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    print(f"Extracted {len(sections)} sections to {args.output}")
    for section in sections[:3]:
        print(
            json.dumps(
                {
                    "id": section.id,
                    "title": section.title,
                    "page": section.page,
                    "text_sample": section.text[:350],
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
