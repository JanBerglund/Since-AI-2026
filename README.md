# Ship Specification Checker

A prototype web app with a Next.js frontend, a Shipcheck specification-checking API, and a separate FastAPI question-answering API.

## Requirements

- Node.js 20 or newer and npm
- Python 3.10 or newer

## Run locally

Install the frontend dependencies and start the frontend:

```powershell
npm install
npm run dev
```

In a second terminal, install the Python dependencies and start Shipcheck from `backend/`:

```powershell
py -3 -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -r requirements.txt
Set-Location backend
.\.venv\Scripts\python.exe -m uvicorn shipcheck.api:app --host 127.0.0.1 --port 8001
```

Shipcheck processes the full PDF, so page selection is not used. It requires selectable text and rejects scanned PDFs. The web app uploads the PDF, waits for extraction, asks you to accept or reject each extracted claim, starts the check, and opens the report when it is complete.

Extraction progress counts the selected specification sections sent to Gemini, not PDF pages. Those sections are processed sequentially, so a large specification can take several minutes. The browser checks job status every five seconds; if extraction fails, **Retry extraction** resumes the existing job from its last saved section.

For a faster demo, set `SHIPCHECK_MAX_SECTIONS=5` in the backend environment before starting Shipcheck. This intentionally checks only the first five configured sections; use `0` for the complete extraction. The backend logs the time spent on each Gemini section request.

The Shipcheck API defaults to `http://127.0.0.1:8001`; set `SHIPCHECK_API_URL` in `.env.local` if it is running elsewhere. Its same-origin proxy is `/api/shipcheck`.

**Backend setup blocker:** the current checkout is missing `backend/claim_models.py` and `backend/units.py`, which Shipcheck imports. Restore those modules before starting the API.

The floating chat uses the separate `backend/api.py` service on port 8000 via `/api/chat`. Start it separately if you want chat; configure `BACKEND_API_URL` if it is running elsewhere.

## Tests and checks

```powershell
npm run lint
npm run build
```

## API

The Shipcheck endpoints and review workflow are documented in [backend/shipcheck/README.md](./backend/shipcheck/README.md). The separate `backend/api.py` exposes `POST /chat`.

## Project files

- `src/app/page.js` — upload, extraction status, human claim review, and chat launcher.
- `src/app/results/page.js` — Shipcheck findings and rendered document pages.
- `src/components/ChatPanel.js` — question-and-answer chat and cited clause sources.
- `src/components/PdfPicker.js` — PDF upload validation.
- `src/components/ShipcheckReview.js` — accept/reject review for extracted claims.
- `src/components/ResultsView.js` — Shipcheck findings with links to report evidence.
- `src/lib/api.js` — frontend API requests and Shipcheck polling.
- `src/app/api/chat/route.js` — same-origin chat proxy to the FastAPI backend.
- `src/app/api/shipcheck/[...segments]/route.js` — same-origin proxy to Shipcheck.
- `backend/api.py` — FastAPI question-answering endpoint.
- `backend/data/` — clause data and embeddings.
- `requirements.txt` — Python backend dependencies.
- `scripts/copy-pdf-worker.mjs` — copies the PDF.js worker into `public/` during install.
