"""Draft one PVAG rule with an OpenAI-compatible chat-completions API."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


CORPUS_PATH = Path("data/clauses.json")
DRAFTS_DIR = Path("drafts")
ENV_PATH = Path(".env")
CLAUSE_ID_PATTERN = re.compile(r"^V\d+\.\d+(?:\.\d+)*$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConditionDraft(StrictModel):
    scope: Literal["element", "project"]
    attr: Literal[
        "clear_width_mm",
        "passing_spaces_interval_m",
        "opening_depth_mm",
        "reduced_segment_length_mm",
        "reduced_segments_separation_mm",
        "reduced_segments_separation_width_mm",
        "door_to_stairway",
        "largest_deck_area_m2",
    ]
    op: Literal["eq", "ne", "lt", "lte", "gt", "gte", "in", "not_in"]
    value: Any
    default: Any | None = None

    @model_validator(mode="after")
    def validate_condition_scope(self) -> "ConditionDraft":
        expected_scope = "project" if self.attr == "largest_deck_area_m2" else "element"
        if self.scope != expected_scope:
            raise ValueError(f"{self.attr} must use scope {expected_scope!r}")
        return self


class OverrideDraft(StrictModel):
    conditions: list[ConditionDraft] = Field(min_length=1)
    threshold: float


class ExceptionDraft(StrictModel):
    conditions: list[ConditionDraft] = Field(min_length=1)
    relaxed_threshold: float | None = None
    outcome: Literal["pass", "defer"]


class RuleDraft(StrictModel):
    id: str
    clause: str
    title: str
    source_url: str
    text: str
    applies_to: Literal["walking_surface", "door", "ramp"]
    measure: Literal[
        "clear_width_mm",
        "passing_spaces_interval_m",
        "opening_depth_mm",
        "reduced_segment_length_mm",
        "reduced_segments_separation_mm",
        "reduced_segments_separation_width_mm",
    ]
    comparison: Literal["min", "max"]
    threshold: float = Field(gt=0)
    unit: Literal["mm", "m"]
    when: list[ConditionDraft] | None = None
    overrides: list[OverrideDraft] = Field(default_factory=list)
    exceptions: list[ExceptionDraft] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_measurement_units(self) -> "RuleDraft":
        expected_unit = "m" if self.measure == "passing_spaces_interval_m" else "mm"
        if self.unit != expected_unit:
            raise ValueError(f"{self.measure} must use unit {expected_unit!r}")
        signatures = [
            json.dumps(exception.model_dump(mode="json"), sort_keys=True)
            for exception in self.exceptions
        ]
        if len(signatures) != len(set(signatures)):
            raise ValueError("Duplicate exception objects are not allowed")
        if any(
            exception.relaxed_threshold is not None and exception.outcome != "pass"
            for exception in self.exceptions
        ):
            raise ValueError("An exception with a relaxed threshold must have outcome 'pass'")
        return self


class ProviderConfig(BaseModel):
    provider: str
    model: str
    api_key: str
    base_url: str = "https://api.openai.com/v1"

    @classmethod
    def from_environment(cls, env_path: Path = ENV_PATH) -> "ProviderConfig":
        _load_env_file(env_path)
        provider = os.environ.get("PVAG_LLM_PROVIDER", "")
        model = os.environ.get("PVAG_LLM_MODEL", "")
        api_key = os.environ.get("PVAG_LLM_API_KEY", "")
        defaults = {
            "ollama": "http://127.0.0.1:11434/v1",
            "gemini": "",
            "openai-compatible": "https://api.openai.com/v1",
        }
        default_base_url = defaults.get(provider, "")
        base_url = os.environ.get("PVAG_LLM_BASE_URL", default_base_url)
        missing = [
            name
            for name, value in (
                ("PVAG_LLM_PROVIDER", provider),
                ("PVAG_LLM_MODEL", model),
            )
            if not value.strip()
        ]
        if provider not in {"ollama"} and not api_key.strip():
            missing.append("PVAG_LLM_API_KEY")
        if missing:
            raise RuntimeError(
                "Missing LLM environment variables: "
                + ", ".join(missing)
                + ". For Ollama set PVAG_LLM_PROVIDER=ollama and PVAG_LLM_MODEL; "
                "for Gemini set PVAG_LLM_PROVIDER=gemini, PVAG_LLM_MODEL, "
                "and PVAG_LLM_API_KEY; "
                "for remote compatible APIs set PVAG_LLM_PROVIDER=openai-compatible, "
                "PVAG_LLM_MODEL, and PVAG_LLM_API_KEY. PVAG_LLM_BASE_URL is optional."
            )
        if provider not in {"ollama", "gemini", "openai-compatible"}:
            raise RuntimeError(
                f"Unsupported PVAG_LLM_PROVIDER {provider!r}; "
                "supported providers are ollama, gemini, and openai-compatible."
            )
        return cls(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url.rstrip("/"),
        )


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, separator, value = line.partition("=")
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name.strip()):
            raise ValueError(f"Invalid environment assignment in {path}:{line_number}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(name.strip(), value)


def load_clause(clause_id: str, corpus_path: Path = CORPUS_PATH) -> dict[str, Any]:
    if not CLAUSE_ID_PATTERN.fullmatch(clause_id):
        raise ValueError(f"Invalid clause ID: {clause_id!r}")
    records = json.loads(corpus_path.read_text(encoding="utf-8"))
    matches = [record for record in records if record.get("id") == clause_id]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one corpus record for {clause_id}; found {len(matches)}")
    return matches[0]


def build_prompt(clause: dict[str, Any]) -> str:
    source = {
        key: clause[key]
        for key in ("id", "title", "text", "source_url")
    }
    exception_instruction = (
        "The source contains an EXCEPTION provision: include one or more objects "
        "in exceptions, not an empty list. If an exception truly cannot be mapped "
        "to this measure, make exceptions empty and put 'EXCEPTION NOT MODELED:' "
        "and the reason in notes."
        if "EXCEPTION" in clause["text"].upper()
        else "The source has no EXCEPTION provision; use an empty exceptions list."
    )
    return (
        "Draft exactly one deterministic rule object for the PVAG clause below. "
        "Return one JSON object and no surrounding prose or markdown. The exact "
        "required top-level keys are: id, clause, title, source_url, text, "
        "applies_to, measure, comparison, threshold, unit. Spell the keys exactly: "
        "use 'clause' (not clause_id) and 'applies_to' (not apply_to). Set id and "
        "clause to the source id. Copy title, source_url, and text exactly from "
        "the source JSON. applies_to must be walking_surface, door, or ramp. "
        "comparison must be min or max. Use only numbers, units, and conditions "
        "explicitly stated in the clause. Prefer the metric threshold when the "
        "clause provides both customary and metric units. Do not invent thresholds, "
        "conditions, exceptions, or outcomes. If mapping wording to an element "
        "type, measurement, or supported design attribute is ambiguous, explain "
        "the ambiguity in notes and do not guess. Supported measurement/condition "
        "attributes are clear_width_mm, passing_spaces_interval_m, opening_depth_mm, "
        "reduced_segment_length_mm, reduced_segments_separation_mm, "
        "reduced_segments_separation_width_mm, and door_to_stairway. The measure "
        "must name a measured field, never 'min' or 'max': use clear_width_mm for "
        "clear width and passing_spaces_interval_m for passing-space intervals. "
        "The unit must be exactly 'mm' for millimeter fields or 'm' for "
        "passing_spaces_interval_m; express threshold in that unit (for example, "
        "915 with unit 'mm', not 36 with unit 'inches'). Attribute mapping: "
        "reduced segment length maps to reduced_segment_length_mm; the length of "
        "the full-width segment separating reduced segments maps to "
        "reduced_segments_separation_mm; that separating segment's width maps to "
        "reduced_segments_separation_width_mm. Largest deck area is a project "
        "attribute and maps to largest_deck_area_m2. Match each numeric condition "
        "to the noun and unit it measures; do not assign all measurements in one "
        "exception to the same attribute. Optional "
        "Include every distinct condition that changes the measured requirement. "
        "For example, a width threshold that changes when opening depth exceeds a "
        "stated value belongs in overrides; a permitted reduced minimum belongs "
        "in exceptions with outcome 'pass' and relaxed_threshold. Do not duplicate "
        "the same exception. Use outcome 'defer' only when the clause explicitly "
        "defers to an authority. If a distinct provision cannot be represented, "
        "state exactly what was omitted in notes. "
        "top-level keys: when (list of conditions), overrides (list of objects "
        "with conditions and threshold), exceptions (list of objects with "
        "conditions, optional relaxed_threshold, and outcome pass or defer), "
        "notes (list of strings). Every condition object must have exactly the "
        "shape {scope, attr, op, value}; scope is element or project and op is "
        "eq, ne, lt, lte, gt, gte, in, or not_in. Use an empty list when no "
        "overrides/exceptions apply; use null for when if there is no applicability "
        "condition. If the source contains an EXCEPTION provision, model the "
        "applicable exceptions or explicitly explain in notes why the provision "
        "cannot be represented by this rule. "
        + exception_instruction
        + " Extract the subject of the clause's main obligation as the measure. "
        "Numbers that restrict when that obligation applies belong in when, not "
        "in threshold. For example, if the clause says a space with width below "
        "X must provide spaces at intervals of Y maximum, measure the interval, "
        "use Y as the max threshold, and put width below X in when. "
        + " Do not add any other fields."
        "\n\nSOURCE CLAUSE JSON:\n"
        + json.dumps(source, ensure_ascii=False)
    )


def request_draft(
    prompt: str,
    config: ProviderConfig,
    *,
    require_exceptions: bool = False,
    source_clause: dict[str, Any] | None = None,
    timeout: float = 300,
) -> str:
    messages = [
        {
            "role": "system",
            "content": "You draft conservative, source-grounded JSON rule candidates.",
        },
        {"role": "user", "content": prompt},
    ]
    if config.provider == "ollama":
        base_url = config.base_url.removesuffix("/v1")
        endpoint = f"{base_url}/api/chat"
        schema = RuleDraft.model_json_schema()
        if source_clause is not None:
            for field in ("id", "clause", "title", "source_url", "text"):
                schema["properties"][field]["const"] = (
                    source_clause["id"] if field == "clause" else source_clause[field]
                )
        if require_exceptions:
            if "exceptions" not in schema["required"]:
                schema["required"].append("exceptions")
            schema["properties"]["exceptions"]["minItems"] = 1
        payload = {
            "model": config.model,
            "messages": messages,
            "stream": False,
            "format": schema,
            "think": False,
            "options": {"temperature": 0},
        }
    elif config.provider == "gemini":
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{config.model}:generateContent"
        )
        payload = {
            "systemInstruction": {
                "parts": [
                    {"text": "You draft conservative, source-grounded JSON rule candidates."}
                ]
            },
            "contents": [
                {"role": "user", "parts": [{"text": prompt}]},
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        }
    else:
        endpoint = f"{config.base_url}/chat/completions"
        payload = {
            "model": config.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": messages,
        }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    if config.provider == "openai-compatible" and config.api_key:
        authorization = "Bearer " + config.api_key
        request.add_header("Authorization", authorization)
    elif config.provider == "gemini":
        request.add_header("x-goog-api-key", config.api_key)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        if config.api_key:
            detail = detail.replace(config.api_key, "[redacted]")
        raise RuntimeError(f"LLM API returned HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        reason = str(error.reason)
        if config.api_key:
            reason = reason.replace(config.api_key, "[redacted]")
        raise RuntimeError(f"Could not reach the configured LLM API: {reason}") from error

    try:
        if config.provider == "ollama":
            return response_data["message"]["content"]
        if config.provider == "gemini":
            parts = response_data["candidates"][0]["content"]["parts"]
            return "".join(part["text"] for part in parts if "text" in part)
        return response_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError("LLM API response did not contain a chat message") from error


def validate_draft(raw_response: str, clause: dict[str, Any]) -> RuleDraft:
    try:
        draft = RuleDraft.model_validate_json(raw_response)
    except ValidationError as error:
        raise ValueError(f"LLM response does not match the rule schema:\n{error}") from error
    expected = {
        "id": clause["id"],
        "clause": clause["id"],
        "title": clause["title"],
        "source_url": clause["source_url"],
        "text": clause["text"],
    }
    for field, value in expected.items():
        if getattr(draft, field) != value:
            raise ValueError(f"Draft field {field!r} must exactly match the corpus")
    _validate_source_numbers(draft, clause["text"])
    if "EXCEPTION" in clause["text"].upper() and not draft.exceptions:
        explicit_omission = any(
            "exception not modeled:" in note.casefold()
            or "exception cannot be represented:" in note.casefold()
            for note in draft.notes
        )
        if not explicit_omission:
            raise ValueError(
                "The source contains an exception provision; model it or add an "
                "'EXCEPTION NOT MODELED:' explanation to the draft notes."
            )
    if any(exception.outcome == "defer" for exception in draft.exceptions):
        if "administrative authority" not in clause["text"].casefold():
            raise ValueError(
                "A defer outcome is only valid when the source explicitly names "
                "an administrative authority."
            )
    return draft


ATTRIBUTE_UNITS = {
    "clear_width_mm": "mm",
    "opening_depth_mm": "mm",
    "reduced_segment_length_mm": "mm",
    "reduced_segments_separation_mm": "mm",
    "reduced_segments_separation_width_mm": "mm",
    "passing_spaces_interval_m": "m",
    "largest_deck_area_m2": "m2",
}


def _metric_values(text: str, unit: str) -> set[float]:
    if unit == "m2":
        pattern = r"(?<!\d)(\d+(?:\.\d+)?)\s*m²\b"
    else:
        pattern = rf"(?<!\d)(\d+(?:\.\d+)?)\s*{re.escape(unit)}\b"
    return {float(value) for value in re.findall(pattern, text, flags=re.IGNORECASE)}


def _validate_source_numbers(draft: RuleDraft, source_text: str) -> None:
    allowed_thresholds = _metric_values(source_text, draft.unit)
    if draft.threshold not in allowed_thresholds:
        raise ValueError(
            f"Threshold {draft.threshold} {draft.unit} does not appear as a metric "
            "measurement in the source clause."
        )
    alternatives = [
        ("override threshold", override.threshold)
        for override in draft.overrides
    ] + [
        ("exception relaxed_threshold", exception.relaxed_threshold)
        for exception in draft.exceptions
        if exception.relaxed_threshold is not None
    ]
    for label, value in alternatives:
        if value not in allowed_thresholds:
            raise ValueError(
                f"{label} {value} {draft.unit} does not appear as a metric "
                "measurement in the source clause."
            )

    all_conditions = list(draft.when or [])
    for override in draft.overrides:
        all_conditions.extend(override.conditions)
    for exception in draft.exceptions:
        all_conditions.extend(exception.conditions)
    for condition in all_conditions:
        unit = ATTRIBUTE_UNITS.get(condition.attr)
        value = condition.value
        if unit is None or not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        if float(value) not in _metric_values(source_text, unit):
            raise ValueError(
                f"Condition value {value} for {condition.attr} is not stated with "
                f"its metric unit in the source clause."
            )
    for condition in all_conditions:
        if condition.attr == "door_to_stairway" and not isinstance(condition.value, bool):
            raise ValueError("door_to_stairway condition values must be JSON booleans")


def draft_clause(
    clause_id: str,
    *,
    corpus_path: Path = CORPUS_PATH,
    output_dir: Path = DRAFTS_DIR,
    config: ProviderConfig | None = None,
) -> Path:
    clause = load_clause(clause_id, corpus_path)
    provider_config = config or ProviderConfig.from_environment()
    prompt = build_prompt(clause)
    require_exceptions = "EXCEPTION" in clause["text"].upper()
    errors: list[str] = []
    for attempt in range(3):
        retry_prompt = prompt
        if errors:
            retry_prompt += (
                "\n\nYour previous candidate failed validation. Correct these issues "
                "without changing source fields:\n- "
                + "\n- ".join(errors)
                + "\nA condition value for door_to_stairway must be the JSON boolean "
                "true or false, not a quoted string."
            )
        raw_response = request_draft(
            retry_prompt,
            provider_config,
            require_exceptions=require_exceptions,
            source_clause=clause,
        )
        try:
            draft = validate_draft(raw_response, clause)
        except ValueError as error:
            errors.append(str(error))
            if attempt == 2:
                raise
        else:
            break
    else:
        raise RuntimeError(f"Could not validate draft for {clause_id}")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{clause_id}.json"
    output_path.write_text(
        json.dumps(draft.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Draft a PVAG rule for human review.")
    parser.add_argument("clause_id", help="Clause ID, for example V403.5.1")
    parser.add_argument("--corpus", type=Path, default=CORPUS_PATH)
    parser.add_argument("--output-dir", type=Path, default=DRAFTS_DIR)
    args = parser.parse_args()
    try:
        output_path = draft_clause(
            args.clause_id,
            corpus_path=args.corpus,
            output_dir=args.output_dir,
        )
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Draft failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(f"Draft saved for human review: {output_path}")


if __name__ == "__main__":
    main()
