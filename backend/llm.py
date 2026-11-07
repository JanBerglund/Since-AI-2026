"""Small Gemini JSON client with disk caching and local request budgets."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, RootModel, SecretStr, ValidationError


MODEL_ROLE = Literal["judgement", "extraction"]
MAX_REQUESTS_PER_MINUTE = 30
MAX_TOKENS_PER_MINUTE = 15_000
MAX_REQUESTS_PER_DAY = 14_400
MAX_OUTPUT_TOKENS = 4_096
TRANSIENT_HTTP_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_REQUEST_ATTEMPTS = 3
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
ENV_PATH = Path(".env")
CACHE_DIR = Path("data/llm_cache")
T = TypeVar("T", bound=BaseModel)


def _load_env_file(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#") or "=" not in entry:
            continue
        key, value = entry.split("=", 1)
        value = value.strip().strip("\"'")
        os.environ.setdefault(key.strip(), value)


class GeminiConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key: SecretStr = SecretStr("")
    judgement_model: str = "gemma-4-31b-it"
    extraction_model: str = "gemma-4-26b-a4b-it"
    max_output_tokens: int = Field(default=MAX_OUTPUT_TOKENS, gt=0, le=MAX_TOKENS_PER_MINUTE)
    api_url: str = API_URL

    @classmethod
    def from_environment(cls, env_path: Path = ENV_PATH) -> "GeminiConfig":
        _load_env_file(env_path)
        return cls(
            api_key=(
                os.environ.get("GEMINI_API_KEY")
                or os.environ.get("PVAG_LLM_API_KEY")
                or ""
            ),
            judgement_model=os.environ.get(
                "GEMINI_JUDGEMENT_MODEL",
                os.environ.get("PVAG_LLM_MODEL", "gemini-2.5-flash-lite"),
            ),
            extraction_model=os.environ.get(
                "GEMINI_EXTRACTION_MODEL",
                os.environ.get("PVAG_LLM_MODEL", "gemini-2.5-flash-lite"),
            ),
            max_output_tokens=int(
                os.environ.get("GEMINI_MAX_OUTPUT_TOKENS", MAX_OUTPUT_TOKENS)
            ),
            api_url=os.environ.get("GEMINI_API_URL", API_URL),
        )

    def model_for(self, role: MODEL_ROLE) -> str:
        return self.judgement_model if role == "judgement" else self.extraction_model


def _json_prompt(prompt: str, schema: dict[str, Any]) -> str:
    return (
        f"{prompt.rstrip()}\n\n"
        "Return only valid JSON matching this schema. Do not add Markdown fences "
        "or text outside the JSON object.\n"
        f"JSON schema:\n{json.dumps(schema, ensure_ascii=False)}"
    )


def _response_text(response: dict[str, Any]) -> str:
    candidates = response.get("candidates", [])
    if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
        raise ValueError("Gemini response has no candidates")
    content = candidates[0].get("content", {})
    parts = content.get("parts", []) if isinstance(content, dict) else []
    if not isinstance(parts, list):
        raise ValueError("Gemini response has invalid content parts")
    text = "\n".join(
        part["text"]
        for part in parts
        if (
            isinstance(part, dict)
            and part.get("thought") is not True
            and isinstance(part.get("text"), str)
        )
    )
    if not text.strip():
        raise ValueError("Gemini response has no text")
    return text.strip()


def _estimated_output_text(response: dict[str, Any]) -> str:
    texts = []
    for candidate in response.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content", {})
        parts = content.get("parts", []) if isinstance(content, dict) else []
        if isinstance(parts, list):
            texts.extend(
                part["text"]
                for part in parts
                if (
                    isinstance(part, dict)
                    and part.get("thought") is not True
                    and isinstance(part.get("text"), str)
                )
            )
    return "\n".join(texts)


def _parse_json(text: str, output_model: type[T]) -> T:
    cleaned = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1)
    return output_model.model_validate_json(cleaned)


class GeminiClient:
    def __init__(
        self,
        config: GeminiConfig | None = None,
        *,
        cache_dir: Path = CACHE_DIR,
        usage_path: Path | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config or GeminiConfig.from_environment()
        self.cache_dir = cache_dir
        self.usage_path = usage_path or cache_dir / "usage.json"
        self.clock = clock
        self.sleep = sleep
        self._lock = threading.Lock()

    def generate_json(
        self,
        prompt: str,
        output_model: type[T],
        *,
        role: MODEL_ROLE,
    ) -> T | Literal["invalid"]:
        model = self.config.model_for(role)
        full_prompt = _json_prompt(prompt, output_model.model_json_schema())
        for attempt in range(2):
            cached_prompt = full_prompt
            if attempt:
                cached_prompt = (
                    f"{full_prompt}\n\nThe previous response was invalid: {last_error}\n"
                    "Correct the JSON and return only the corrected JSON."
                )
            response = self._cached_completion(model, cached_prompt)
            try:
                return _parse_json(_response_text(response), output_model)
            except (KeyError, TypeError, ValueError, ValidationError) as error:
                last_error = str(error)
        return "invalid"

    def _cached_completion(self, model: str, prompt: str) -> dict[str, Any]:
        cache_key = hashlib.sha256(f"{model}\0{prompt}".encode("utf-8")).hexdigest()
        cache_path = self.cache_dir / f"{cache_key}.json"
        if cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))
        response = self._request(model, prompt)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(response, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return response

    def _request(self, model: str, prompt: str) -> dict[str, Any]:
        if not self.config.api_key.get_secret_value():
            raise RuntimeError("Set GEMINI_API_KEY or PVAG_LLM_API_KEY before calling Gemini")
        input_tokens = math.ceil(len(prompt) / 4)
        reserved_tokens = input_tokens + self.config.max_output_tokens
        if reserved_tokens > MAX_TOKENS_PER_MINUTE:
            raise ValueError("Prompt and output-token limit exceed the local 60-second budget")
        endpoint = self.config.api_url.format(
            model=urllib.parse.quote(model, safe="-_.")
        )
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(
                {
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0,
                        "maxOutputTokens": self.config.max_output_tokens,
                        "responseMimeType": "application/json",
                    },
                }
            ).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.config.api_key.get_secret_value(),
            },
            method="POST",
        )
        for attempt in range(MAX_REQUEST_ATTEMPTS):
            event_id = self._reserve_budget(reserved_tokens)
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    result = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as error:
                detail = error.read().decode("utf-8", errors="replace")
                detail = detail.replace(self.config.api_key.get_secret_value(), "[redacted]")
                if error.code in TRANSIENT_HTTP_STATUS_CODES and attempt < MAX_REQUEST_ATTEMPTS - 1:
                    self.sleep(2**attempt)
                    continue
                raise RuntimeError(f"Gemini API returned HTTP {error.code}: {detail}") from error
            except urllib.error.URLError as error:
                if attempt < MAX_REQUEST_ATTEMPTS - 1:
                    self.sleep(2**attempt)
                    continue
                raise RuntimeError(f"Could not reach Gemini API: {error.reason}") from error

        if not isinstance(result, dict):
            raise ValueError("Gemini returned a non-object response")
        usage = result.get("usageMetadata", {})
        if not isinstance(usage, dict):
            usage = {}
        actual_tokens = usage.get("totalTokenCount")
        if not isinstance(actual_tokens, int):
            actual_tokens = math.ceil(
                (len(prompt) + len(_estimated_output_text(result))) / 4
            )
        self._update_event(event_id, actual_tokens)
        return result

    def _read_usage(self) -> dict[str, Any]:
        if not self.usage_path.exists():
            return {"date": "", "daily_requests": 0, "events": []}
        state = json.loads(self.usage_path.read_text(encoding="utf-8"))
        if not isinstance(state, dict) or not isinstance(state.get("events"), list):
            raise ValueError(f"Invalid request-budget state in {self.usage_path}")
        return state

    def _write_usage(self, state: dict[str, Any]) -> None:
        self.usage_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.usage_path.with_suffix(".tmp")
        temporary_path.write_text(json.dumps(state), encoding="utf-8")
        temporary_path.replace(self.usage_path)

    def _reserve_budget(self, tokens: int) -> str:
        event_id = hashlib.sha256(os.urandom(32)).hexdigest()
        while True:
            with self._lock:
                now = self.clock()
                today = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
                state = self._read_usage()
                if state.get("date") != today:
                    state = {"date": today, "daily_requests": 0, "events": []}
                events = [
                    event for event in state["events"]
                    if now - event["time"] < 60
                ]
                state["events"] = events
                used_tokens = sum(event["tokens"] for event in events)
                daily_requests = int(state.get("daily_requests", 0))
                if (
                    len(events) < MAX_REQUESTS_PER_MINUTE
                    and used_tokens + tokens <= MAX_TOKENS_PER_MINUTE
                    and daily_requests < MAX_REQUESTS_PER_DAY
                ):
                    events.append({"id": event_id, "time": now, "tokens": tokens})
                    state["daily_requests"] = daily_requests + 1
                    self._write_usage(state)
                    return event_id
                waits = [event["time"] + 60 - now for event in events]
                if daily_requests >= MAX_REQUESTS_PER_DAY:
                    tomorrow = datetime.fromtimestamp(now, timezone.utc).date() + timedelta(days=1)
                    waits.append(
                        datetime.combine(tomorrow, datetime.min.time(), timezone.utc).timestamp()
                        - now
                    )
                wait_seconds = max(0.05, min(wait for wait in waits if wait > 0))
            self.sleep(wait_seconds)

    def _update_event(self, event_id: str, tokens: int) -> None:
        with self._lock:
            state = self._read_usage()
            for event in state["events"]:
                if event["id"] == event_id:
                    event["tokens"] = tokens
                    break
            self._write_usage(state)


class JsonObject(RootModel[dict[str, Any]]):
    pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Call Gemini for validated JSON.")
    parser.add_argument("--role", choices=("judgement", "extraction"), default="extraction")
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt")
    prompt_group.add_argument("--prompt-file", type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the full prompt without making an API request",
    )
    args = parser.parse_args()
    prompt = (
        args.prompt_file.read_text(encoding="utf-8")
        if args.prompt_file is not None
        else args.prompt
    )
    config = GeminiConfig.from_environment()
    full_prompt = _json_prompt(prompt, JsonObject.model_json_schema())
    if args.dry_run:
        print(f"Model: {config.model_for(args.role)}\n\n{full_prompt}")
        return
    try:
        result = GeminiClient(config).generate_json(prompt, JsonObject, role=args.role)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Gemini request failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    if result == "invalid":
        print("Gemini returned invalid JSON after one retry.", file=sys.stderr)
        raise SystemExit(2)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
