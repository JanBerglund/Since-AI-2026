# Ship Design Compliance Checker

A prototype web app with a Next.js frontend and a FastAPI question-answering API. The API is in `backend/api.py` and uses the clause index in `backend/data/`.

## Requirements

- Node.js 20 or newer and npm
- Python 3.10 or newer

## Run locally

Install the frontend dependencies and start the frontend:

```powershell
npm install
npm run dev
```

In a second terminal, install the Python dependencies and start the backend from the repository root:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn api:app --app-dir backend --host 127.0.0.1 --port 8000
```

Open [http://localhost:3000](http://localhost:3000). The main page lets you upload a PDF, select pages to check, and open the floating AI chat. When a check finishes or fails, the app navigates to the separate `/results` page. Results and errors are stored in the browser tab's session storage.

The chat is available only on the upload page. It sends requests through the same-origin `/api/chat` route to backend `POST /chat`. The file checker sends multipart requests through `/api/check`, which forwards them to backend `POST /check`. Both routes default to `http://localhost:8000`; set the server-side `BACKEND_API_URL` to use a different backend URL.

**Checker limitation:** the current FastAPI backend implements `POST /chat`, but does not yet implement `POST /check`. Until that backend endpoint is added, check requests reach the backend and return HTTP 404; the error is displayed on `/results`. Setting `NEXT_PUBLIC_MOCK=1` uses sample checker results for frontend demonstrations instead of calling the backend.

## Tests and checks

```powershell
npm run lint
npm run build
```

## API

`backend/api.py` exposes `POST /chat`. It accepts a JSON `question` and returns an `answer`, a `relevant` flag, and matching `clauses`.

## Project files

- `src/app/page.js` — PDF upload, page selection, check workflow, and chat launcher.
- `src/app/results/page.js` — results and checker error page.
- `src/components/ChatPanel.js` — question-and-answer chat and cited clause sources.
- `src/components/PdfPicker.js` — PDF upload, page previews, and page selection.
- `src/components/ResultsView.js` — summary and findings table (no marked drawing is shown).
- `src/lib/pdf.js` — browser-side PDF rendering and page-range helpers.
- `src/lib/api.js` — frontend API requests and optional mock checker results.
- `src/app/api/chat/route.js` — same-origin chat proxy to the FastAPI backend.
- `src/app/api/check/route.js` — same-origin checker proxy to the FastAPI backend.
- `backend/api.py` — FastAPI question-answering endpoint.
- `backend/data/` — clause data and embeddings.
- `requirements.txt` — Python backend dependencies.
- `scripts/copy-pdf-worker.mjs` — copies the PDF.js worker into `public/` during install.
