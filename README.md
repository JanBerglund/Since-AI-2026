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

Open [http://localhost:3000](http://localhost:3000). The frontend's PDF-checking workflow is not compatible with the retained `/chat` API.

## Tests and checks

```powershell
npm run lint
npm run build
```

## API contract

`backend/api.py` exposes `POST /chat`, accepting a JSON `question` and returning an `answer`, a `relevant` flag, and matching `clauses`.

## Project files

- `src/app/page.js` — upload, page selection, and check workflow.
- `src/components/PdfPicker.js` — PDF upload, page previews, and page selection.
- `src/components/ResultsView.js` — summary, report image, and findings table.
- `src/lib/pdf.js` — browser-side PDF rendering and page-range helpers.
- `src/lib/api.js` — backend request and mock results.
- `backend/api.py` — FastAPI question-answering endpoint.
- `backend/data/` — clause data and embeddings.
- `requirements.txt` — Python backend dependencies.
- `scripts/copy-pdf-worker.mjs` — copies the PDF.js worker into `public/` during install.
