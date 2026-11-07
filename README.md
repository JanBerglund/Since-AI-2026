# Ship Design Compliance Checker

A prototype web app with a Next.js frontend and a FastAPI question-answering API. The retained API is in `backend/api.py` and uses clause data from `backend/data/`.

## Requirements

- Node.js 20 or newer and npm
- Python 3.10 or newer

The retained API currently imports `answer`, `rag_answer`, and `retrieval` modules that are not in this repository, so it cannot be started as-is.

## Run locally

Install and start the frontend:

```powershell
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The page includes a question-and-answer chat that calls the backend `POST /chat` endpoint; the separate PDF-checking workflow uses `POST /check`.

Chat requests are sent to the same-origin Next.js `/api/chat` route, which forwards them to the FastAPI backend. Configure the server-only `BACKEND_API_URL` when the backend is not at `http://localhost:8000`; it defaults to `NEXT_PUBLIC_API_URL`. The chat always calls the backend and does not use mock responses.

## Tests and checks

```powershell
npm run lint
npm run build
```

## API contract

`backend/api.py` exposes `POST /chat`, accepting a JSON `question` and returning an `answer`, a `relevant` flag, and matching `clauses`.

## Project files

- `src/app/page.js` — chat, upload, page selection, and check workflow.
- `src/components/ChatPanel.js` — question-and-answer chat and cited clause sources.
- `src/components/PdfPicker.js` — PDF upload, page previews, and page selection.
- `src/components/ResultsView.js` — summary and findings table (no marked drawing is shown).
- `src/lib/pdf.js` — browser-side PDF rendering and page-range helpers.
- `src/lib/api.js` — backend request and mock results.
- `backend/api.py` — FastAPI question-answering endpoint.
- `backend/data/` — clause data and embeddings.
- `requirements.txt` — Python backend dependencies.
- `scripts/copy-pdf-worker.mjs` — copies the PDF.js worker into `public/` during install.
