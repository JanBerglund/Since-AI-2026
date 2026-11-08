# Mariner AI

An application for extracting measurable requirements from ship specification
PDFs, matching them with a searchable rule library, and reporting pass, fail,
or needs-review results. It includes:

- a Next.js web interface;
- one FastAPI backend for chat and document checking;
- vector search over the bundled rule library;
- an LLM-assisted comparison step with deterministic numeric comparisons where
  the rule and claim are compatible.

The bundled rule data contains the supplied PVAG rules plus two self-added test
rules:

- overall vessel length must not exceed 19.0 m;
- minimum vessel crew is 2 persons.

## Requirements

- Node.js 20.9 or newer
- npm
- Python 3.10 or newer
- A Gemini API key for extraction, judgement, and chat

## Configure the environment

Copy the example environment file:

```sh
cp .env.example .env.local
cp .env.example backend/.env
```

Edit `backend/.env` and set:

```env
PVAG_LLM_PROVIDER=gemini
PVAG_LLM_MODEL=
PVAG_LLM_API_KEY=your_api_key_here
```

`PVAG_LLM_MODEL` may be left empty to use the provider default. The `PVAG_*`
names are retained for compatibility with the current backend; they configure
the general rule-checking model, not only PVAG rules.

Never commit `backend/.env` or expose the API key. If a key has ever been
shared or committed, revoke it and create a replacement.

Optional settings:

```env
BACKEND_API_URL=http://127.0.0.1:8000
SHIPCHECK_API_URL=http://127.0.0.1:8000
SHIPCHECK_MAX_SECTIONS=0
```

Use `SHIPCHECK_MAX_SECTIONS=5` for a fast demo. Use `0` to process all selected
sections.

## Install and run

Install frontend packages from the project root:

```sh
npm install
```

Create and install the Python environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Start the backend in one terminal:

```sh
cd backend
../.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Start the website in a second terminal from the project root:

```sh
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

Use port 8000 for the backend unless both proxy URLs in `.env.local` are
changed to the port you choose. Restart Next.js after changing environment
variables.

## Use the application

1. Open the website.
2. Upload a selectable-text ship specification PDF.
3. Wait for extraction to finish.
4. Review the extracted requirements and include or exclude claims.
5. Start the check.
6. Open the results page and review rule comparisons, evidence, and PDF pages.
7. Use the chat panel to ask questions about the rule library.

Scanned, encrypted, corrupt, and password-protected PDFs are rejected.
Uploads are limited to 25 MiB and 500 pages. Extraction can take several
minutes for a large document.

## Add or change rules

Rules are stored in [backend/data/clauses.json](./backend/data/clauses.json).
Add a JSON object with the same fields as the existing entries:

```json
{
  "id": "CUSTOM.1",
  "chapter": "CUSTOM",
  "title": "Maximum vessel length",
  "text": "The overall length of the vessel shall not exceed 19.0 m.",
  "parent_id": null,
  "source_url": "https://example.com/rules",
  "topics": ["vessel", "length"],
  "advisory": ""
}
```

The rule text should state one clear measurable requirement. `topics` are
optional search hints and are not the mechanism that decides whether a rule
applies.

After editing the JSON, rebuild the vector index:

```sh
cd backend
../.venv/bin/python scripts/revectorize.py
```

The script regenerates
[backend/data/embeddings.npy](./backend/data/embeddings.npy) from the current
rule JSON. The checker then retrieves relevant rules, asks the model whether
they apply to each extracted claim, and compares compatible numeric values in
Python.

## Validation

Run the frontend checks:

```sh
npm run lint
npm run build
```

Rebuild the rule index after rule changes and verify that the new rule appears
in retrieval before testing it with a PDF.

## Project structure

- `src/` — Next.js website and same-origin API proxies.
- `backend/app.py` — combined FastAPI application.
- `backend/shipcheck/` — upload, extraction, review, checking, and reporting.
- `backend/data/clauses.json` — rule library.
- `backend/data/embeddings.npy` — vector index for the rule library.
- `backend/scripts/revectorize.py` — rule-index rebuild command.
- `backend/llm.py` — provider/model selection and validated JSON model calls.
- `backend/retrieval.py` — embedding-based rule retrieval.
- `backend/check_pvag.py` — rule comparison pipeline; the filename is retained
  for compatibility with the existing application.

## Local API

The combined backend serves:

- `POST /chat`
- `POST /jobs`
- `GET /jobs/{job_id}`
- `GET /jobs/{job_id}/claims`
- `POST /jobs/{job_id}/review`
- `POST /jobs/{job_id}/check`
- `GET /jobs/{job_id}/report`

The API is intended for local development and has no authentication. Do not
expose it publicly without adding authentication, rate limiting, and
deployment-specific storage controls.
