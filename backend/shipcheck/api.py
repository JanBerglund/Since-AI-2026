"""HTTP API for uploading and reviewing isolated ship-specification jobs."""

from __future__ import annotations

from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict

from shipcheck.service import CheckRequest, ReviewSubmission, ShipCheckService


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JOBS_ROOT = ROOT / "data/ship_jobs"


class JobCreated(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: str
    page_count: int


def create_app(service: ShipCheckService | None = None) -> FastAPI:
    app = FastAPI(title="Ship Specification Checker API")
    app.state.shipcheck_service = service or ShipCheckService(DEFAULT_JOBS_ROOT)

    @app.post("/jobs", response_model=JobCreated, status_code=202)
    async def create_job(
        background_tasks: BackgroundTasks,
        request: Request,
        file: UploadFile = File(...),
    ) -> JobCreated:
        checker: ShipCheckService = request.app.state.shipcheck_service
        try:
            job_id, page_count = checker.create_job(file.file)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except OSError as error:
            raise HTTPException(status_code=500, detail="Could not store uploaded PDF") from error
        finally:
            await file.close()
        background_tasks.add_task(checker.prepare_job, job_id)
        return JobCreated(job_id=job_id, status="extracting", page_count=page_count)

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str, request: Request) -> dict[str, object]:
        checker: ShipCheckService = request.app.state.shipcheck_service
        try:
            return checker.status_detail(job_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Job not found") from error

    @app.post("/jobs/{job_id}/extract", status_code=202)
    def retry_extraction(
        job_id: str,
        background_tasks: BackgroundTasks,
        request: Request,
    ) -> dict[str, str]:
        checker: ShipCheckService = request.app.state.shipcheck_service
        try:
            status = checker.read_status(job_id)
            if status["status"] != "extraction_failed":
                raise RuntimeError("Only failed extraction jobs can be retried")
            checker.write_status(
                job_id,
                status="extracting",
                page_count=status["page_count"],
                error=None,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Job not found") from error
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        background_tasks.add_task(checker.prepare_job, job_id)
        return {"job_id": job_id, "status": "extracting"}

    @app.get("/jobs/{job_id}/claims")
    def get_claims(job_id: str, request: Request) -> dict[str, object]:
        checker: ShipCheckService = request.app.state.shipcheck_service
        try:
            return checker.claims(job_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Job not found") from error
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/jobs/{job_id}/review")
    def review_claims(
        job_id: str,
        submission: ReviewSubmission,
        request: Request,
    ) -> dict[str, object]:
        checker: ShipCheckService = request.app.state.shipcheck_service
        try:
            return checker.review(job_id, submission)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Job not found") from error
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/jobs/{job_id}/check", status_code=202)
    def start_check(
        job_id: str,
        payload: CheckRequest,
        background_tasks: BackgroundTasks,
        request: Request,
    ) -> dict[str, str]:
        checker: ShipCheckService = request.app.state.shipcheck_service
        try:
            status = checker.validate_check_request(job_id, payload)
            checker.write_status(
                job_id,
                status="checking",
                page_count=status["page_count"],
                error=None,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Job not found") from error
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        background_tasks.add_task(checker.run_checks, job_id, payload)
        return {"job_id": job_id, "status": "checking"}

    @app.get("/jobs/{job_id}/report")
    def get_report(job_id: str, request: Request) -> dict[str, object]:
        checker: ShipCheckService = request.app.state.shipcheck_service
        try:
            return checker.report(job_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Job not found") from error
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/jobs/{job_id}/pages/{image_name}")
    def get_report_page(
        job_id: str,
        image_name: str,
        request: Request,
    ) -> FileResponse:
        checker: ShipCheckService = request.app.state.shipcheck_service
        try:
            job_dir = checker.job_dir(job_id)
            status = checker.read_status(job_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Job not found") from error
        if status["status"] != "complete":
            raise HTTPException(status_code=409, detail="Report pages are not ready")
        if not image_name.startswith("p") or not image_name.endswith(".png"):
            raise HTTPException(status_code=404, detail="Report page not found")
        page_path = (job_dir / "report/pages" / image_name).resolve()
        if page_path.parent != (job_dir / "report/pages").resolve() or not page_path.is_file():
            raise HTTPException(status_code=404, detail="Report page not found")
        return FileResponse(page_path, media_type="image/png")

    @app.get("/jobs/{job_id}/pdf")
    def get_uploaded_pdf(job_id: str, request: Request) -> FileResponse:
        checker: ShipCheckService = request.app.state.shipcheck_service
        try:
            pdf_path = checker.job_dir(job_id) / "upload.pdf"
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Job not found") from error
        return FileResponse(pdf_path, media_type="application/pdf")

    return app


app = create_app()
