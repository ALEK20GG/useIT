# Python Backend (FastAPI + Qdrant)

This backend exposes a small FastAPI service that proxies collection management and vector search operations to a Qdrant instance.

## Prerequisites

- Python 3.11+
- Access to a running Qdrant cluster (local Docker or managed)

## Setup

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy env.example .env
# edit .env with your Qdrant URL / API key
```

If you're on macOS/Linux replace the activation command with `source .venv/bin/activate`.

## Run the API

```powershell
uvicorn app.main:app --reload
```

The server listens on `http://127.0.0.1:8000` by default. Open `http://127.0.0.1:8000/docs` for interactive OpenAPI docs.

## Available endpoints

- `GET /health` – Verifies connectivity with Qdrant.
- `POST /collections` – Creates or recreates a collection with the requested vector size and distance metric.
- `POST /points` – Upserts a single vector plus optional metadata.
- `POST /search` – Runs a similarity search and returns the best matches.

### Semantic search endpoints

These use OpenAI embeddings (`text-embedding-3-small`) under the hood:

- `POST /semantic/ingest` – Ingest one or more notes/documents.
  - Each note has `title`, `content`, optional `type` (e.g. `component`, `school-note`), and `tags`.
- `POST /semantic/search` – Given a natural language query, returns the most relevant notes.

You must set `OPENAI_API_KEY` in your `.env` file for these routes to work.

Update or extend these routes as your application requirements evolve. Cheers!

