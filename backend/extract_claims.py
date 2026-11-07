"""Extract checkable claims from selected specification sections."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from claim_models import (
    ClaimBatch,
    ClaimDraft,
    INCLUDE_PATTERNS,
    InvalidSection,
    load_sections,
    quote_is_verbatim,
    select_sections,
    write_json,
)
from llm import GeminiClient


ROOT = Path(__file__).resolve().parent
DEFAULT_SECTIONS = ROOT / "data/spec_sections.json"
DEFAULT_OUTPUT = ROOT / "claims/draft.json"


def _prompt(section_id: str, title: str, text: str) -> str:
    return (
        "Extract only explicit, checkable claims stated in this ship "
        "specification section. Do not infer missing values or convert units. "
        "For each claim return section_id, subject, quantity, value, unit, "
        "and quote. Quantity should identify what is measured (for example "
        "width, height, frequency, voltage, count, or capacity). The quote "
        "must be copied verbatim from the section text; do not paraphrase. "
        "Return an empty claims list if there are no checkable claims.\n\n"
        f"Section ID: {section_id}\nTitle: {title}\n"
        f"Section text:\n{text}"
    )


def extract_claims(
    sections_path: Path,
    output_path: Path,
    *,
    client: GeminiClient | None = None,
    dry_run: bool = False,
) -> ClaimDraft | None:
    sections = select_sections(load_sections(sections_path))
    if not sections:
        raise ValueError(f"No sections matched the configured include-list in {sections_path}")
    max_sections = int(os.environ.get("SHIPCHECK_MAX_SECTIONS", "0"))
    if max_sections < 0:
        raise ValueError("SHIPCHECK_MAX_SECTIONS must be zero or a positive integer")
    if max_sections:
        sections = sections[:max_sections]
    model_client = client or GeminiClient()
    draft = ClaimDraft()
    if not dry_run:
        if output_path.exists():
            draft = ClaimDraft.model_validate_json(
                output_path.read_text(encoding="utf-8")
            )
            section_map = {section.id: section for section in sections}
            for claim in draft.claims:
                section = section_map.get(claim.section_id)
                if section is None or not quote_is_verbatim(claim.quote, section.text):
                    raise ValueError(
                        f"Existing draft contains a claim that does not match "
                        f"section {claim.section_id!r}; use a new output path"
                    )
        else:
            write_json(output_path, draft.model_dump(mode="json"))
    processed = set(draft.processed_sections)

    for index, section in enumerate(sections, start=1):
        if section.id in processed:
            continue
        prompt = _prompt(section.id, section.title, section.text)
        if dry_run:
            print(f"\n--- {index}/{len(sections)}: {section.id} {section.title} ---")
            print(prompt)
            continue

        started = time.perf_counter()
        result = model_client.generate_json(prompt, ClaimBatch, role="extraction")
        elapsed = time.perf_counter() - started
        if result == "invalid":
            draft.invalid_sections.append(
                InvalidSection(section_id=section.id, reason="Invalid model response after retry")
            )
            draft.processed_sections.append(section.id)
            print(
                f"{index}/{len(sections)} {section.id}: invalid model response; "
                f"marked unknown ({elapsed:.1f}s)",
                file=sys.stderr,
            )
            write_json(output_path, draft.model_dump(mode="json"))
            continue

        valid_claims = []
        rejected_count = 0
        for claim in result.claims:
            if claim.section_id != section.id or not quote_is_verbatim(claim.quote, section.text):
                rejected_count += 1
                continue
            valid_claims.append(claim)
        draft.claims.extend(valid_claims)
        if rejected_count:
            print(
                f"{section.id}: rejected {rejected_count} claim(s) with a mismatched "
                "section ID or non-verbatim quote",
                file=sys.stderr,
            )
        print(
            f"{index}/{len(sections)} {section.id}: {len(valid_claims)} valid claims "
            f"({elapsed:.1f}s)",
            flush=True,
        )
        draft.processed_sections.append(section.id)
        write_json(output_path, draft.model_dump(mode="json"))

    return None if dry_run else draft


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sections", type=Path, default=DEFAULT_SECTIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print all selected prompts without making API requests",
    )
    args = parser.parse_args()
    try:
        result = extract_claims(
            args.sections,
            args.output,
            dry_run=args.dry_run,
        )
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Claim extraction failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    if result is not None:
        print(
            f"Saved {len(result.claims)} verified claims and "
            f"{len(result.invalid_sections)} invalid sections to {args.output}"
        )


if __name__ == "__main__":
    main()
