"""Extract vessel scope facts from specification sections."""

from __future__ import annotations

import re
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, field_validator

from claim_models import load_sections, quote_is_verbatim, select_sections, write_json
from llm import GeminiClient


class ExtractedFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int | bool | None = None
    quote: str | None = None
    section_id: str | None = None

    @field_validator("quote", "section_id")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None and value.strip() else None


class ExtractedVesselFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_passengers: ExtractedFact = Field(default_factory=ExtractedFact)
    overnight_passengers: ExtractedFact = Field(default_factory=ExtractedFact)
    crew: ExtractedFact = Field(default_factory=ExtractedFact)
    is_ferry: ExtractedFact = Field(default_factory=ExtractedFact)
    is_tender: ExtractedFact = Field(default_factory=ExtractedFact)


def _prompt(sections: list[object]) -> str:
    source = "\n\n".join(
        f"Section {section.id} — {section.title}\n{section.text}"
        for section in sections
    )
    return (
        "Extract vessel facts from this ship specification. Return one object "
        "for each field: max_passengers, overnight_passengers, crew, is_ferry, "
        "and is_tender. Each object must contain value, quote, and section_id. "
        "Use null for value, quote, and section_id when the document says "
        "nothing. Do not treat crew as passengers. Use only explicit statements; "
        "do not infer values. Quotes must be copied verbatim from the source "
        "section text and section_id must identify their source section.\n\n"
        f"Source sections:\n{source}"
    )


def _validate_quotes(
    facts: ExtractedVesselFacts,
    sections: list[object],
) -> ExtractedVesselFacts:
    section_map = {section.id: section for section in sections}
    for field_name in facts.model_fields:
        fact = getattr(facts, field_name)
        if fact.section_id:
            canonical_section_id = re.sub(
                r"^\s*section\s+",
                "",
                fact.section_id,
                flags=re.IGNORECASE,
            ).strip()
            if canonical_section_id != fact.section_id:
                fact = fact.model_copy(update={"section_id": canonical_section_id})
                facts = facts.model_copy(update={field_name: fact})
        if fact.value is None:
            if fact.quote is not None or fact.section_id is not None:
                raise ValueError(f"{field_name} has metadata but no value")
            continue
        if not fact.quote or not fact.section_id:
            raise ValueError(f"{field_name} requires quote and section_id")
        section = section_map.get(fact.section_id)
        if section is None or not quote_is_verbatim(fact.quote, section.text):
            raise ValueError(
                f"{field_name} quote is not a verbatim substring of section "
                f"{fact.section_id!r}"
            )
    return facts


def extract_vessel_facts(
    sections_path: Path,
    output_path: Path,
    *,
    client: GeminiClient | None = None,
) -> dict[str, object]:
    all_sections = load_sections(sections_path)
    selected = select_sections(all_sections)
    if not selected:
        raise ValueError(f"No sections matched the configured include-list in {sections_path}")
    keywords = ("passenger", "crew", "ferry", "tender", "capacity", "accommodation")
    relevant_sections = [
        section
        for section in selected
        if any(keyword in f"{section.title} {section.text}".casefold() for keyword in keywords)
    ]
    source_sections = relevant_sections or selected
    result = (client or GeminiClient()).generate_json(
        _prompt(source_sections),
        ExtractedVesselFacts,
        role="extraction",
    )
    if result == "invalid":
        raise ValueError("Vessel-facts extraction returned an invalid model response")
    facts = _validate_quotes(result, source_sections)
    return {
        field_name: {
            **getattr(facts, field_name).model_dump(),
            "source": "extracted",
        }
        for field_name in facts.model_fields
    }


def extract_and_save_vessel_facts(
    sections_path: Path,
    output_path: Path,
    *,
    client: GeminiClient | None = None,
) -> dict[str, object]:
    facts = extract_vessel_facts(sections_path, output_path, client=client)
    write_json(output_path, facts)
    return facts
