# ═══════════════════════════════════════════════════════════════════════════════
# UseIt – Single-container build (frontend + backend)
#
# Stage 1 (node-builder): builds the SvelteKit frontend into a standalone
#                         Node.js server (adapter-node → build/index.js)
# Stage 2 (app):          Python 3.11 image that runs both:
#                           • uvicorn  (FastAPI backend)  on port 8000
#                           • node     (SvelteKit SSR)    on port 3000
#                         supervised by supervisord
#
# Qdrant runs on a SEPARATE server — configure QDRANT_URL in the environment.
# ═══════════════════════════════════════════════════════════════════════════════

# ── Stage 1: build SvelteKit frontend ────────────────────────────────────────
FROM node:22-alpine AS node-builder

WORKDIR /frontend

# PUBLIC_BACKEND_URL must be known at build time because SvelteKit bakes
# $env/static/public variables into the client bundle.
# Default points to the backend running in the same container.
ARG PUBLIC_BACKEND_URL=http://localhost:8000
ENV PUBLIC_BACKEND_URL=${PUBLIC_BACKEND_URL}

# Copy package files.
# The project uses an npm workspace: package-lock.json lives at the repo root,
# not inside frontend/. We copy both so that npm ci can use the lockfile.
COPY frontend/package.json ./package.json
COPY package-lock.json ./package-lock.json

# Install dependencies using the root lockfile
RUN npm ci --ignore-scripts

# Copy source and build for production (adapter-node)
COPY frontend/ ./
RUN npm run build

# Prune devDependencies — only keep what the Node server needs at runtime
RUN npm prune --omit=dev


# ── Stage 2: final application image ─────────────────────────────────────────
FROM python:3.11-slim AS app

# ── System dependencies ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Required by sentence-transformers / tokenizers
    build-essential \
    # Required to run Node.js (for the SvelteKit server)
    curl \
    # Process supervisor — runs uvicorn + node side by side
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 22 (LTS) into the Python image
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# ── Python backend ────────────────────────────────────────────────────────────
WORKDIR /app/backend

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the embedding model so the container works offline at runtime.
# This adds ~500 MB to the image. Remove this line if image size is a concern
# (the model will be downloaded on first request instead).
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"

COPY backend/ ./

# Safety: remove any .env files that may have slipped through .dockerignore
# (secrets must come from docker-compose environment, never baked into the image)
RUN rm -f .env

# In the container, embedded Qdrant fallback is always disabled.
# The app must connect to the external Qdrant server or fail fast.
ENV QDRANT_ALLOW_EMBEDDED=false

# Create persistent storage directories
RUN mkdir -p storage/folders storage/user_area storage/audit storage/search

# Create the PDF storage directory (matches PDFS_DIR env var in docker-compose)
RUN mkdir -p /app/frontend/static/pdf-source

# ── SvelteKit frontend ────────────────────────────────────────────────────────
WORKDIR /app/frontend

# Copy the built output and production node_modules from the node-builder stage
COPY --from=node-builder /frontend/build ./build
COPY --from=node-builder /frontend/node_modules ./node_modules
COPY --from=node-builder /frontend/package.json ./package.json

# Copy the data directory (whitelist.json, etc.)
COPY frontend/data ./data

# ── Supervisord configuration ─────────────────────────────────────────────────
WORKDIR /app

COPY supervisord.conf /etc/supervisor/conf.d/useit.conf

# ── Ports ─────────────────────────────────────────────────────────────────────
# 3000 → SvelteKit (SSR + SSO)
# 8000 → FastAPI backend
EXPOSE 3000 8000

# ── Entrypoint ────────────────────────────────────────────────────────────────
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/useit.conf"]
