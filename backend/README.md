# Python Backend (FastAPI + Qdrant)

This backend exposes a small FastAPI service that proxies collection management and vector search operations to a Qdrant instance.

## Prerequisites

- Python 3.11+
- Docker (opzionale - solo se vuoi usare Qdrant come server separato)
  - [Scarica Docker Desktop](https://www.docker.com/products/docker-desktop/)
  - **Nota:** Se non hai Docker, il backend userà automaticamente Qdrant in modalità embedded (locale, senza server)

## Setup

### 1. Avvia Qdrant (opzionale)

**Opzione A: Con Docker (consigliato per produzione)**
Dalla root del progetto (dove si trova `docker-compose.yml`):

```powershell
docker-compose up -d
```

Questo avvierà Qdrant su `http://localhost:6333`. Puoi verificare che sia in esecuzione visitando http://localhost:6333/dashboard

**Per fermare Qdrant:**
```powershell
docker-compose down
```

**Opzione B: Modalità Embedded (automatica, nessun setup richiesto)**
Se Docker non è disponibile, il backend userà automaticamente Qdrant in modalità embedded (locale).
Non è necessario fare nulla - funziona automaticamente! I dati verranno salvati nella cartella `qdrant_local/`.

### 2. Configura il backend Python

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**Nota:** Non è necessario configurare un file `.env` - Qdrant funziona senza autenticazione in locale di default.

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

These use sentence-transformers (multilingual model) for embeddings - **no API key required, completely free!**

- `POST /semantic/ingest` – Ingest one or more notes/documents.
  - Each note has `title`, `content`, optional `type` (e.g. `component`, `school-note`), and `tags`.
- `POST /semantic/search` – Given a natural language query, returns the most relevant notes.
- `POST /pdf/upload` – Upload and index a PDF file.
- `POST /pdf/index-all` – Index all PDFs in the pdf-source directory.
- `POST /pdf/search` – Search semantically across indexed PDFs.

The embedding model will be automatically downloaded (~500MB) on first use. It supports multiple languages including Italian and English.

Update or extend these routes as your application requirements evolve. Cheers!

