"""Isolated per-upload workflow for specification checking."""

from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Literal

import pymupdf
from pydantic import BaseModel, ConfigDict, Field

from build_report import build_report
from check_pvag import check_claims
from claim_models import (
    ClaimDraft,
    SpecClaim,
    load_sections,
    quote_is_verbatim,
    select_sections,
    write_json,
)
from consistency import find_contradictions
from extract_claims import extract_claims
from ingest_spec import extract_sections
from llm import GeminiClient
from pvag_scope import determine_scope, scope_facts_from_job
from retrieval import CLAUSES_PATH, EMBEDDINGS_PATH, PVAGRetriever
from vessel_facts import extract_and_save_vessel_facts


MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_PDF_PAGES = 500
UPLOAD_CHUNK_BYTES = 1024 * 1024
JOB_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
JobStatusName = Literal[
    "extracting",
    "review_required",
    "checking",
    "complete",
    "extraction_failed",
    "check_failed",
]
UNSUPPORTED_PDF_MESSAGE = (
    "This PDF format is not supported. Upload a ship specification PDF with "
    "numbered sections that match the configured accessibility-specification "
    "structure (for example 1, 2.3, 6.3, 7.1, or 8)."
)


class ClaimDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0)
    decision: Literal["accept", "reject"]


class ReviewSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decisions: list[ClaimDecision]


class VesselFactsOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_passengers: int | None = Field(default=None, ge=0)
    overnight_passengers: int | None = Field(default=None, ge=0)
    crew: int | None = Field(default=None, ge=0)
    is_ferry: bool | None = None
    is_tender: bool | None = None


class CheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    acknowledge_incomplete_extraction: bool = False
    hypothetical: bool = True
    vessel_facts: VesselFactsOverride = Field(default_factory=VesselFactsOverride)


class ShipCheckService:
    def __init__(
        self,
        jobs_root: Path,
        *,
        clauses_path: Path = CLAUSES_PATH,
        embeddings_path: Path = EMBEDDINGS_PATH,
    ) -> None:
        self.jobs_root = jobs_root.resolve()
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self.clauses_path = clauses_path
        self.embeddings_path = embeddings_path

    def create_job(self, source: BinaryIO) -> tuple[str, int]:
        job_id = uuid.uuid4().hex
        job_dir = self.jobs_root / job_id
        job_dir.mkdir(mode=0o700)
        pdf_path = job_dir / "upload.pdf"
        size = 0
        try:
            with pdf_path.open("wb") as target:
                while True:
                    chunk = source.read(UPLOAD_CHUNK_BYTES)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise ValueError(
                            f"PDF exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB upload limit"
                        )
                    target.write(chunk)
            page_count = self.validate_pdf(pdf_path)
            self.write_status(
                job_id,
                status="extracting",
                page_count=page_count,
                error=None,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        except Exception:
            shutil.rmtree(job_dir)
            raise
        return job_id, page_count

    @staticmethod
    def validate_pdf(pdf_path: Path) -> int:
        with pdf_path.open("rb") as pdf_file:
            if pdf_file.read(5) != b"%PDF-":
                raise ValueError("Uploaded file is not a PDF")
        try:
            document = pymupdf.open(pdf_path)
        except (pymupdf.FileDataError, RuntimeError) as error:
            raise ValueError("PDF is corrupted or cannot be opened") from error
        with document:
            if document.needs_pass:
                raise ValueError("Password-protected PDFs are not supported")
            if document.page_count < 1:
                raise ValueError("PDF must contain at least one page")
            if document.page_count > MAX_PDF_PAGES:
                raise ValueError(f"PDF exceeds the {MAX_PDF_PAGES}-page limit")
            if not any(page.get_text("text").strip() for page in document):
                raise ValueError(
                    "PDF has no selectable text; scanned PDFs require OCR and are not supported"
                )
            return document.page_count

    def job_dir(self, job_id: str) -> Path:
        if not JOB_ID_PATTERN.fullmatch(job_id):
            raise KeyError("Unknown job")
        path = (self.jobs_root / job_id).resolve()
        if path.parent != self.jobs_root or not path.is_dir():
            raise KeyError("Unknown job")
        return path

    def read_status(self, job_id: str) -> dict[str, Any]:
        path = self.job_dir(job_id) / "status.json"
        if not path.exists():
            raise KeyError("Unknown job")
        return json.loads(path.read_text(encoding="utf-8"))

    def write_status(
        self,
        job_id: str,
        *,
        status: JobStatusName,
        page_count: int,
        error: str | None,
        created_at: str | None = None,
        progress_stage: str | None = None,
        progress_current: int | None = None,
        progress_total: int | None = None,
    ) -> None:
        job_dir = self.job_dir(job_id)
        existing: dict[str, Any] = {}
        status_path = job_dir / "status.json"
        if status_path.exists():
            existing = json.loads(status_path.read_text(encoding="utf-8"))
        status_data = {
            "job_id": job_id,
            "status": status,
            "page_count": page_count,
            "error": error,
            "created_at": created_at or existing.get("created_at"),
            "progress_stage": progress_stage or existing.get("progress_stage"),
            "progress_current": (
                progress_current
                if progress_current is not None
                else existing.get("progress_current", 0)
            ),
            "progress_total": (
                progress_total
                if progress_total is not None
                else existing.get("progress_total", 0)
            ),
        }
        write_json(status_path, status_data)

    def prepare_job(self, job_id: str) -> None:
        job_dir = self.job_dir(job_id)
        status = self.read_status(job_id)
        try:
            pdf_path = job_dir / "upload.pdf"
            sections_path = job_dir / "spec_sections.json"
            sections = extract_sections(pdf_path)
            write_json(
                sections_path,
                [section.model_dump(mode="json") for section in sections],
            )
            extract_and_save_vessel_facts(
                sections_path,
                job_dir / "vessel_facts.json",
            )
            draft_path = job_dir / "claims/draft.json"
            extract_claims(sections_path, draft_path)
            self.write_status(
                job_id,
                status="review_required",
                page_count=status["page_count"],
                error=None,
            )
        except Exception as error:
            error_message = str(error)
            if (
                isinstance(error, ValueError)
                and "No sections matched the configured include-list" in error_message
            ):
                error_message = UNSUPPORTED_PDF_MESSAGE
            self.write_status(
                job_id,
                status="extraction_failed",
                page_count=status["page_count"],
                error=error_message,
            )

    def claims(self, job_id: str) -> dict[str, Any]:
        job_dir = self.job_dir(job_id)
        status = self.read_status(job_id)
        if status["status"] not in {"review_required", "checking", "complete", "check_failed"}:
            raise RuntimeError("Claims are not ready; check the job status first")
        draft_path = job_dir / "claims/draft.json"
        if not draft_path.exists():
            raise RuntimeError("Claim draft is not available")
        draft = ClaimDraft.model_validate_json(draft_path.read_text(encoding="utf-8"))
        decisions_path = job_dir / "claims/review.json"
        decisions = (
            json.loads(decisions_path.read_text(encoding="utf-8"))
            if decisions_path.exists()
            else {}
        )
        return {
            "claims": [
                {
                    "index": index,
                    "claim": claim.model_dump(mode="json"),
                    "decision": decisions.get(str(index)),
                }
                for index, claim in enumerate(draft.claims)
            ],
            "invalid_sections": [
                item.model_dump(mode="json") for item in draft.invalid_sections
            ],
            "processed_sections": draft.processed_sections,
            "vessel_facts": self.read_vessel_facts(job_id),
        }

    def read_vessel_facts(self, job_id: str) -> dict[str, Any]:
        path = self.job_dir(job_id) / "vessel_facts.json"
        if not path.exists():
            raise RuntimeError("Vessel facts are not available")
        return json.loads(path.read_text(encoding="utf-8"))

    def apply_vessel_fact_overrides(
        self,
        job_id: str,
        overrides: VesselFactsOverride,
    ) -> dict[str, Any]:
        facts = self.read_vessel_facts(job_id)
        for field_name in overrides.model_fields_set:
            value = getattr(overrides, field_name)
            facts[field_name] = {
                "value": value,
                "quote": None,
                "section_id": None,
                "source": "user",
            }
        write_json(self.job_dir(job_id) / "vessel_facts.json", facts)
        return facts

    def status_detail(self, job_id: str) -> dict[str, Any]:
        status = self.read_status(job_id)
        details = dict(status)
        details.update(
            {
                "claim_count": 0,
                "pending_review_count": 0,
                "invalid_section_count": 0,
                "processed_section_count": 0,
                "section_count": 0,
            }
        )
        if status["status"] in {"extracting", "extraction_failed", "review_required"}:
            job_dir = self.job_dir(status["job_id"])
            sections_path = job_dir / "spec_sections.json"
            draft_path = job_dir / "claims/draft.json"
            if sections_path.exists():
                details["section_count"] = len(select_sections(load_sections(sections_path)))
                configured_limit = int(os.environ.get("SHIPCHECK_MAX_SECTIONS", "0"))
                if configured_limit:
                    details["section_count"] = min(details["section_count"], configured_limit)
            if draft_path.exists():
                draft = ClaimDraft.model_validate_json(
                    draft_path.read_text(encoding="utf-8")
                )
                details["processed_section_count"] = len(draft.processed_sections)
        if status["status"] in {
            "review_required",
            "checking",
            "complete",
            "check_failed",
        }:
            claim_data = self.claims(job_id)
            details["claim_count"] = len(claim_data["claims"])
            details["pending_review_count"] = sum(
                item["decision"] is None for item in claim_data["claims"]
            )
            details["invalid_section_count"] = len(claim_data["invalid_sections"])
        return details

    def validate_check_request(
        self,
        job_id: str,
        request: CheckRequest,
        *,
        allow_checking: bool = False,
    ) -> dict[str, Any]:
        status = self.read_status(job_id)
        allowed_statuses = {"review_required", "check_failed"}
        if allow_checking:
            allowed_statuses.add("checking")
        if status["status"] not in allowed_statuses:
            raise RuntimeError("Job is not ready to check")
        claim_data = self.claims(job_id)
        pending = [
            item for item in claim_data["claims"] if item["decision"] is None
        ]
        if pending:
            raise RuntimeError(
                f"{len(pending)} claim(s) still need an accept/reject decision"
            )
        if (
            claim_data["invalid_sections"]
            and not request.acknowledge_incomplete_extraction
        ):
            raise RuntimeError(
                "Some sections had invalid model responses; explicitly acknowledge "
                "incomplete extraction to continue"
            )
        return status

    def review(self, job_id: str, submission: ReviewSubmission) -> dict[str, Any]:
        job_dir = self.job_dir(job_id)
        status = self.read_status(job_id)
        if status["status"] != "review_required":
            raise RuntimeError("Claims can only be reviewed while the job requires review")
        draft_path = job_dir / "claims/draft.json"
        if not draft_path.exists():
            raise RuntimeError("Claim draft is not available")
        draft = ClaimDraft.model_validate_json(draft_path.read_text(encoding="utf-8"))
        sections = {section.id: section for section in load_sections(job_dir / "spec_sections.json")}
        decisions_path = job_dir / "claims/review.json"
        decisions = (
            json.loads(decisions_path.read_text(encoding="utf-8"))
            if decisions_path.exists()
            else {}
        )
        for item in submission.decisions:
            if item.index >= len(draft.claims):
                raise ValueError(f"Claim index {item.index} does not exist")
            claim = draft.claims[item.index]
            section = sections.get(claim.section_id)
            if section is None or not quote_is_verbatim(claim.quote, section.text):
                raise ValueError(
                    f"Claim {item.index} does not have a verifiable source quote"
                )
            decisions[str(item.index)] = item.decision

        write_json(decisions_path, decisions)
        accepted = [
            draft.claims[int(index)].model_dump(mode="json")
            for index, decision in decisions.items()
            if decision == "accept"
        ]
        write_json(job_dir / "claims/accepted.json", accepted)
        return self.claims(job_id)

    def run_checks(self, job_id: str, request: CheckRequest) -> None:
        job_dir = self.job_dir(job_id)
        status = self.read_status(job_id)
        if status["status"] not in {"checking", "review_required", "check_failed"}:
            raise RuntimeError("Job is not ready to check")
        self.validate_check_request(job_id, request, allow_checking=True)
        self.apply_vessel_fact_overrides(job_id, request.vessel_facts)
        accepted = [
            SpecClaim.model_validate(item)
            for item in json.loads(
                (job_dir / "claims/accepted.json").read_text(encoding="utf-8")
            )
        ]
        if status["status"] != "checking":
            self.write_status(
                job_id,
                status="checking",
                page_count=status["page_count"],
                error=None,
                progress_stage="checking",
                progress_current=0,
                progress_total=len(accepted),
            )
        try:
            consistency = find_contradictions(accepted, GeminiClient())
            consistency_path = job_dir / "claims/consistency.json"
            write_json(
                consistency_path,
                [item.model_dump(mode="json") for item in consistency],
            )

            retriever = PVAGRetriever(
                clauses_path=self.clauses_path,
                embeddings_path=self.embeddings_path,
            )
            scope_facts = scope_facts_from_job(self.read_vessel_facts(job_id))
            scope = determine_scope(scope_facts, retriever.clauses)
            def update_check_progress(current: int, total: int) -> None:
                self.write_status(
                    job_id,
                    status="checking",
                    page_count=status["page_count"],
                    error=None,
                    progress_stage="checking",
                    progress_current=current,
                    progress_total=total,
                )

            pvag = check_claims(
                accepted,
                retriever,
                GeminiClient(),
                GeminiClient(),
                scope_decision=scope,
                run_hypothetical=request.hypothetical,
                on_progress=update_check_progress,
            )
            pvag_path = job_dir / "claims/pvag_findings.json"
            write_json(pvag_path, [item.model_dump(mode="json") for item in pvag])
            build_report(
                job_dir / "upload.pdf",
                job_dir / "spec_sections.json",
                consistency_path,
                pvag_path,
                job_dir / "report/report.json",
                job_dir / "report/pages",
                scope=scope.model_dump(mode="json"),
            )
            self.write_status(
                job_id,
                status="complete",
                page_count=status["page_count"],
                error=None,
            )
        except Exception as error:
            self.write_status(
                job_id,
                status="check_failed",
                page_count=status["page_count"],
                error=f"{type(error).__name__}: {error}",
            )
            raise

    def report(self, job_id: str) -> dict[str, Any]:
        job_dir = self.job_dir(job_id)
        status = self.read_status(job_id)
        if status["status"] != "complete":
            raise RuntimeError("Report is not ready; check the job status first")
        report_path = job_dir / "report/report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["pdf"] = f"/jobs/{job_id}/pdf"
        for page in report["pages"]:
            page["image"] = f"/jobs/{job_id}/pages/{Path(page['image']).name}"
        return report
