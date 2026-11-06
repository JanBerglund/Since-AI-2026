# Ship Design Compliance Checker

A prototype web app for uploading a general-arrangement PDF, selecting pages, and checking extracted measurements against rules. The frontend is Next.js; the API is FastAPI. Verdicts are produced by deterministic comparisons in `backend/checker.py`, not by an AI/LLM.

## Requirements

- Node.js 20 or newer and npm
- Python 3.10 or newer
- Tesseract OCR 5 installed separately from Python packages for scanned-page OCR

On Windows, the backend looks for Tesseract using `TESSERACT_PATH`, `E:\OCR\tesseract.exe`, common Program Files locations, and then `PATH`. To keep the OCR installation on E:, set `TESSERACT_PATH` as shown below. The Python virtual environment and its packages are installed inside this repository's `.venv` folder.

## Run locally

Start the backend in one PowerShell terminal from the repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:TESSERACT_PATH = 'E:\OCR\tesseract.exe'
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

The `TESSERACT_PATH` line is only needed when Tesseract is not already in one of the detected locations or on `PATH`. Check the API at [http://localhost:8000/health](http://localhost:8000/health).

In a second terminal, install and start the frontend:

```powershell
npm install
Copy-Item .env.example .env.local
```

Set `.env.local` to use the real API:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_MOCK=0
```

Then run:

```powershell
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The checked-in `.env.example` uses mock results by default; changing `.env.local` requires restarting the frontend dev server. The API allows CORS from localhost ports 3000 and 3001.

## Tests and checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend -p 'test_*.py' -v
npm run lint
npm run build
```

## Current extraction limits

The PDF extractor currently recognizes door labels when a door ID and a width in millimeters appear together, such as `D-214 780 mm`. It first reads embedded PDF text and uses Tesseract on pages where that text does not produce a match. It does not yet interpret drawing geometry, associate separate dimension callouts with doors, or check corridor widths. The generated report images are placeholders, not annotations of the uploaded drawing.

Rules and thresholds live in `rules.json`; entries currently marked `"verified": false` are not validated compliance guidance. Treat all output as experimental and have a qualified reviewer verify the source drawing and applicable standards.

## API contract

The frontend sends `POST {NEXT_PUBLIC_API_URL}/check` as multipart form data with `file` and `pages` (comma-separated, 1-based page numbers). The response contains a `summary`, `findings`, and `images` array. Each finding's `verdict` is `fine`, `not_fine`, or `unknown`. `GET /health` is available for a basic API health check.

Page previews are rendered in the browser; the PDF is sent to the backend only after pressing **Check**.

## Project files

- `src/app/page.js` — upload, page selection, and check workflow.
- `src/components/PdfPicker.js` — PDF upload, page previews, and page selection.
- `src/components/ResultsView.js` — summary, report image, and findings table.
- `src/lib/pdf.js` — browser-side PDF rendering and page-range helpers.
- `src/lib/api.js` — backend request and mock results.
- `backend/app.py` — FastAPI endpoints and PDF processing.
- `backend/ocr.py` — text extraction and Tesseract OCR fallback.
- `backend/checker.py` — deterministic rule evaluation.
- `rules.json` — rule definitions and thresholds.
- `requirements.txt` — Python backend dependencies.
- `scripts/copy-pdf-worker.mjs` — copies the PDF.js worker into `public/` during install.
