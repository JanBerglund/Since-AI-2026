# Ship specification API

From the project root, create the environment and install dependencies, then run the API from `backend/` so its local data paths resolve correctly:

```sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r requirements.txt
cd backend
.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

For a faster demo, set `SHIPCHECK_MAX_SECTIONS=5` before starting the API. This
limits extraction to the first five configured sections; leave it at `0` for a
complete check. Extraction logs include the elapsed Gemini time for each section.

Upload a selectable-text PDF:

```sh
curl -F "file=@spec.pdf" http://127.0.0.1:8000/jobs
```

The API validates the PDF, stores it under `data/ship_jobs/<job_id>/`, then
extracts sections and draft claims in the background. Poll `GET /jobs/{job_id}`
until the status is `review_required`. See `GET /jobs/{job_id}/claims`, then
submit an accept or reject decision for every claim to
`POST /jobs/{job_id}/review`:

```json
{"decisions":[{"index":0,"decision":"accept"},{"index":1,"decision":"reject"}]}
```

Only accepted claims are checked. If extraction had invalid sections, the
check endpoint requires `acknowledge_incomplete_extraction: true`; otherwise
the job cannot proceed as if extraction were complete. Start checks with
`POST /jobs/{job_id}/check` and poll status until `complete`, then retrieve
`GET /jobs/{job_id}/report`. Report page image URLs and the uploaded PDF URL
are served from the same job.

The check can label a reviewed internal contradiction as `fail`. A rule
comparison is an actual `fail` only when both models agree, the quote and
threshold validate, the Python comparison fails, and scope is `in_scope`.
Out-of-scope or uncertain comparisons have actual verdict `unknown`; the
hypothetical verdict is retained separately. This does not guarantee
detection of every wrong specification value: model extraction is fallible,
and a person must review each drafted claim.

Uploads are limited to 25 MiB and 500 pages. Encrypted, corrupt, and scanned
PDFs without selectable text are rejected. The API has no authentication and
is intended for local development; do not expose it publicly without adding
authentication, rate limiting, and deployment-specific storage controls.
