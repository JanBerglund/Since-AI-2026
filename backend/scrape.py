"""Scrape and parse the official PVAG chapter pages."""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel


BASE_URL = "https://www.access-board.gov/pvag/ch-v{chapter}/"
CACHE_DIR = Path("data/raw_html")
OUTPUT_PATH = Path("data/clauses.json")
USER_AGENT = (
    "PVAG-RAG-hackathon/0.1 "
    "(research scraper for proposed Passenger Vessels Accessibility Guidelines)"
)
CHAPTERS = range(1, 12)
CLAUSE_HEADING = re.compile(r"^(V\d+\.\d+(?:\.\d+)*)\s+(.+?)\s*$")
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
CONTENT_TAGS = {"p", "li", "dt", "dd", "td", "th", "blockquote", "pre"}
TOPIC_KEYWORDS = (
    "corridor",
    "walking surface",
    "door",
    "ramp",
    "elevator",
    "route",
    "passing space",
    "accessible",
    "wheelchair",
    "toilet",
    "sign",
    "stair",
    "deck",
    "guest room",
    "communication",
    "threshold",
    "handrail",
    "surface",
    "transfer",
    "boarding",
    "lighting",
    "alarm",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
LOGGER = logging.getLogger(__name__)


class Clause(BaseModel):
    id: str
    chapter: str
    title: str
    text: str
    parent_id: str | None
    source_url: str
    topics: list[str]
    advisory: str = ""


def _normalized_text(element: Tag) -> str:
    # Keep the source's text sequence intact; only collapse whitespace.
    return " ".join(element.get_text("", strip=False).split())


def _clause_content(heading: Tag) -> tuple[str, str]:
    blocks: list[str] = []
    advisories: list[str] = []
    for element in heading.next_elements:
        if not isinstance(element, Tag):
            continue
        if element.name in HEADING_TAGS:
            break
        if element.name not in CONTENT_TAGS:
            continue
        if any(parent.name in CONTENT_TAGS for parent in element.parents if parent is not heading):
            continue
        text = _normalized_text(element)
        if text:
            if "advisory" in element.get("class", []):
                advisories.append(text)
            else:
                blocks.append(text)
    return " ".join(blocks), " ".join(advisories)


def _parent_id(clause_id: str) -> str:
    components = clause_id.split(".")
    return ".".join(components[:-1])


def _topics(title: str, text: str) -> list[str]:
    searchable = f"{title} {text}".lower()
    return [
        keyword
        for keyword in TOPIC_KEYWORDS
        if re.search(rf"\b{re.escape(keyword)}\w*\b", searchable)
    ]


def parse_chapter(html: str, chapter: int, source_url: str) -> list[Clause]:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("main .usa-prose")
    if content is None:
        raise ValueError(f"Chapter V{chapter} has no main .usa-prose content")

    clauses: list[Clause] = []
    for heading in content.find_all(list(HEADING_TAGS)):
        heading_text = _normalized_text(heading)
        match = CLAUSE_HEADING.match(heading_text)
        if not match:
            continue
        clause_id, title = match.groups()
        text, advisory = _clause_content(heading)
        if not title.strip() or not text:
            LOGGER.error("Skipping %s in chapter V%s: missing title or clause text", clause_id, chapter)
            continue
        clauses.append(
            Clause(
                id=clause_id,
                chapter=f"V{chapter}",
                title=title,
                text=text,
                advisory=advisory,
                parent_id=_parent_id(clause_id),
                source_url=source_url,
                topics=_topics(title, text),
            )
        )
    if not clauses:
        raise ValueError(f"No clauses parsed from chapter V{chapter}")
    return clauses


def fetch_chapter(session: requests.Session, chapter: int) -> tuple[str, str]:
    source_url = BASE_URL.format(chapter=chapter)
    cache_path = CACHE_DIR / f"ch-v{chapter}.html"
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8"), source_url

    if chapter > 1:
        time.sleep(1)
    response = session.get(source_url, timeout=30)
    response.raise_for_status()
    html = response.text
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(html, encoding="utf-8")
    return html, source_url


def scrape(chapters: Iterable[int] = CHAPTERS) -> tuple[list[Clause], dict[str, int]]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    clauses: list[Clause] = []
    counts: dict[str, int] = {}

    for chapter in chapters:
        chapter_name = f"V{chapter}"
        try:
            html, source_url = fetch_chapter(session, chapter)
            parsed = parse_chapter(html, chapter, source_url)
        except (requests.RequestException, OSError, ValueError) as error:
            LOGGER.error("Could not process chapter %s: %s", chapter_name, error)
            counts[chapter_name] = 0
            continue
        clauses.extend(parsed)
        counts[chapter_name] = len(parsed)
        LOGGER.info("Parsed %d clauses from %s", len(parsed), chapter_name)

    ids = [clause.id for clause in clauses]
    duplicates = sorted({clause_id for clause_id in ids if ids.count(clause_id) > 1})
    if duplicates:
        raise ValueError(f"Duplicate clause ids found: {', '.join(duplicates)}")
    if not clauses:
        raise RuntimeError("No PVAG clauses were parsed")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps([clause.model_dump() for clause in clauses], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return clauses, counts


def main() -> None:
    clauses, counts = scrape()
    by_chapter = {f"V{chapter}": [] for chapter in (1, 2)}
    for clause in clauses:
        if clause.chapter in by_chapter and len(by_chapter[clause.chapter]) < 3:
            by_chapter[clause.chapter].append(clause.model_dump())
    print(
        json.dumps(
            {
                "clause_count_per_chapter": counts,
                "first_three_clauses": by_chapter,
                "total_clauses": len(clauses),
                "output_file": str(OUTPUT_PATH),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
