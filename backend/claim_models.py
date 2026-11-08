"""Shared models and helpers for specification-claim extraction and review."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ingest_spec import SpecSection


INCLUDE_PATTERNS = (
    "1",
    "2.3",
    "4.x",
    "5.6",
    "5.7",
    "6.3",
    "6.7",
    "7.1",
    "7.2",
    "8",
)


class SpecClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str
    subject: str
    quantity: str
    value: str | int | float
    unit: str
    quote: str
    comparison: Literal["min", "max", "exact", "approx"] = "exact"
    context: str | None = None
    group_id: str = ""

    @field_validator("value", mode="before")
    @classmethod
    def reject_boolean_value(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("must be a number or text value, not a boolean")
        return value

    @field_validator("section_id", "subject", "quantity", "unit", "quote")
    @classmethod
    def require_nonempty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value

    @field_validator("context")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            return None
        return value.strip() if value is not None else None

    @field_validator("group_id")
    @classmethod
    def normalize_group_id(cls, value: str) -> str:
        return value.strip()

    @field_validator("value")
    @classmethod
    def require_valid_value(cls, value: str | int | float) -> str | int | float:
        if isinstance(value, str) and not value.strip():
            raise ValueError("must not be empty")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("must be finite")
        return value


class ClaimBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[SpecClaim]


class InvalidSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str
    reason: str


class ClaimDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[SpecClaim] = Field(default_factory=list)
    invalid_sections: list[InvalidSection] = Field(default_factory=list)
    processed_sections: list[str] = Field(default_factory=list)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def quote_is_verbatim(quote: str, source: str) -> bool:
    normalized_quote = normalize_whitespace(quote)
    return bool(normalized_quote) and normalized_quote in normalize_whitespace(source)


def select_sections(
    sections: list[SpecSection],
    patterns: tuple[str, ...] = INCLUDE_PATTERNS,
) -> list[SpecSection]:
    def matches(section_id: str, pattern: str) -> bool:
        base = pattern[:-2] if pattern.endswith(".x") else pattern
        return (
            section_id == base
            or section_id.startswith(f"{base}.")
            or section_id.startswith(f"{base}#")
        )

    return [
        section
        for section in sections
        if any(matches(section.id, pattern) for pattern in patterns)
    ]


def load_sections(path: Path) -> list[SpecSection]:
    raw_sections = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_sections, list):
        raise ValueError(f"Expected a JSON array of sections in {path}")
    return [SpecSection.model_validate(section) for section in raw_sections]


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def quote_context(source: str, quote: str, radius: int = 180) -> str:
    normalized_source = normalize_whitespace(source)
    normalized_quote = normalize_whitespace(quote)
    start = normalized_source.find(normalized_quote)
    if start < 0:
        raise ValueError("Claim quote is not present in its source section")
    end = start + len(normalized_quote)
    excerpt_start = max(0, start - radius)
    excerpt_end = min(len(normalized_source), end + radius)
    prefix = "..." if excerpt_start else ""
    suffix = "..." if excerpt_end < len(normalized_source) else ""
    return f"{prefix}{normalized_source[excerpt_start:excerpt_end]}{suffix}"
