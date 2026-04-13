# Requirements Document

## Introduction

This document covers improvements and new features for the existing **UseIt** application — a SvelteKit + FastAPI + Qdrant platform for PDF management and semantic search. The work falls into two categories:

1. **Bug fixes** — correctness issues already present in the codebase that must be resolved before new features are layered on top.
2. **Feature enhancements** — new capabilities that make the platform significantly more useful for discovering and navigating a large corpus of PDFs (e.g. 100 Raspberry Pi magazine issues).

The system is multilingual (Italian + English) and runs locally with an embedded Qdrant instance or a Docker-hosted Qdrant server.

---

## Glossary

- **System**: The combined SvelteKit frontend + FastAPI backend application.
- **Backend**: The FastAPI Python service (`backend/app/main.py` and related modules).
- **Frontend**: The SvelteKit application under `frontend/src/`.
- **Qdrant**: The vector database used for semantic search (embedded or Docker).
- **PDF_Collection**: The Qdrant collection named `"pdfs"` that stores PDF chunk vectors.
- **Notes_Collection**: The Qdrant collection named `"notes"` that stores semantic notes.
- **Chunk**: A segment of text extracted from a PDF page, stored as a single Qdrant point.
- **Embedding**: A fixed-length float vector produced by the sentence-transformer model representing the semantic meaning of a text.
- **BACKEND_URL**: The base URL of the FastAPI service, configurable via a SvelteKit environment variable.
- **PDF_Source_Dir**: The directory `frontend/static/pdf-source/` where PDF files are stored and served statically.
- **Keyword_Boost**: An additive score bonus applied when a search result chunk contains exact query words.
- **Health_Indicator**: A UI element in the navigation bar that shows whether the Backend is reachable.

---

## Requirements

### Requirement 1: Fix requirements.txt typo

**User Story:** As a developer, I want the Python dependency file to be correct, so that `pip install` succeeds without errors.

#### Acceptance Criteria

1. THE Backend SHALL list `sentence_transformers==5.2.2` (with the letter `s` present) in `backend/requirements.txt`.

---

### Requirement 2: Fix semantic ingest collection recreation

**User Story:** As a user, I want to add notes to the semantic search collection without losing previously ingested notes, so that my knowledge base grows over time.

#### Acceptance Criteria

1. WHEN the `/semantic/ingest` endpoint is called, THE Backend SHALL create the Notes_Collection only if it does not already exist.
2. WHEN the Notes_Collection already exists with the correct vector size, THE Backend SHALL upsert new points without deleting existing points.
3. IF the Notes_Collection exists with a different vector size, THEN THE Backend SHALL recreate the collection using `delete_collection` followed by `create_collection`.

---

### Requirement 3: Fix tab switching active state in PDF page

**User Story:** As a user, I want the active tab to be visually highlighted when I switch between "Carica PDF" and "Cerca PDF", so that I always know which tab I am on.

#### Acceptance Criteria

1. WHEN the user clicks the "Carica PDF" tab button, THE Frontend SHALL apply the `active` CSS class to that button and remove it from all other tab buttons.
2. WHEN the user clicks the "Cerca PDF" tab button, THE Frontend SHALL apply the `active` CSS class to that button and remove it from all other tab buttons.
3. THE Frontend SHALL derive the `active` class from the reactive `currentTab` state variable, not from a hardcoded HTML attribute.

---

### Requirement 4: Fix chunk_text variable shadowing in main.py

**User Story:** As a developer, I want the backend code to be free of variable shadowing bugs, so that the `chunk_text` utility function is always callable.

#### Acceptance Criteria

1. THE Backend SHALL use a distinct local variable name (e.g. `chunk_text_content`) for the loop variable that holds individual chunk strings inside `upload_pdf` and `index_all_pdfs`.
2. THE Backend SHALL retain the import of the `chunk_text` function from `pdf_utils` and call it without `NameError`.

---

### Requirement 5: Fix keyword_boost NameError

**User Story:** As a user, I want PDF search to work correctly regardless of whether keyword boost is enabled or disabled, so that I always get results.

#### Acceptance Criteria

1. WHEN `use_keyword_boost` is `False`, THE Backend SHALL assign `keyword_boost = 0.0` before referencing it in the result dictionary inside `search_pdfs`.
2. THE Backend SHALL not raise a `NameError` for `keyword_boost` under any combination of `use_keyword_boost` values.

---

### Requirement 6: Replace deprecated recreate_collection calls

**User Story:** As a developer, I want the backend to use the current Qdrant client API, so that the application does not break when the deprecated method is removed.

#### Acceptance Criteria

1. THE Backend SHALL replace every call to `client.recreate_collection(...)` with a sequence of `client.delete_collection(...)` followed by `client.create_collection(...)`.
2. WHEN `delete_collection` is called on a collection that does not exist, THE Backend SHALL catch the resulting exception and proceed to `create_collection` without raising an error.

---

### Requirement 7: Configurable CORS origins

**User Story:** As a developer, I want CORS allowed origins to be configurable via environment variables, so that the backend works in both development and production without code changes.

#### Acceptance Criteria

1. THE Backend SHALL read a `CORS_ORIGINS` environment variable (comma-separated list of URLs) and add each entry to the CORS allowed-origins list.
2. WHEN `CORS_ORIGINS` is not set, THE Backend SHALL default to allowing `http://localhost:5173` and `http://127.0.0.1:5173`.
3. THE Backend SHALL expose `CORS_ORIGINS` as a field in the `Settings` Pydantic model in `config.py`.

---

### Requirement 8: Configurable BACKEND_URL in frontend

**User Story:** As a developer, I want the frontend to read the backend URL from a SvelteKit environment variable, so that I can deploy to different environments without editing source files.

#### Acceptance Criteria

1. THE Frontend SHALL read `PUBLIC_BACKEND_URL` from SvelteKit's `$env/static/public` module.
2. WHEN `PUBLIC_BACKEND_URL` is not set, THE Frontend SHALL fall back to `http://127.0.0.1:8000`.
3. THE Frontend SHALL replace every hardcoded `http://127.0.0.1:8000` string with the value derived from the environment variable.
4. THE System SHALL document the `PUBLIC_BACKEND_URL` variable in a `.env.example` file at the frontend root.

---

### Requirement 9: Store page number per chunk

**User Story:** As a user, I want search results to show which page of the PDF the matching text comes from, so that I can navigate directly to the relevant section.

#### Acceptance Criteria

1. WHEN a PDF is indexed (via upload or index-all), THE Backend SHALL store the 1-based page number of each Chunk in the Qdrant point payload under the key `"page_number"`.
2. WHEN a PDF search result is returned, THE Backend SHALL include the `page_number` field in the `PDFSearchResult` response model.
3. THE Frontend SHALL display the page number alongside each search result card (e.g. "Page 12").

---

### Requirement 10: PDF deletion endpoint

**User Story:** As a user, I want to delete a PDF and its indexed vectors, so that I can keep the search index clean and up to date.

#### Acceptance Criteria

1. THE Backend SHALL expose a `DELETE /pdf/{filename}` endpoint.
2. WHEN the endpoint is called with a valid filename, THE Backend SHALL delete all Qdrant points whose payload `filename` field matches the given filename.
3. WHEN the endpoint is called with a valid filename and the file exists on disk in PDF_Source_Dir, THE Backend SHALL delete the file from disk.
4. WHEN the endpoint is called with a filename that has no indexed points and no file on disk, THE Backend SHALL return HTTP 404.
5. THE Frontend SHALL display a delete button on each search result card that calls this endpoint and removes the card from the results list on success.

---

### Requirement 11: Indexed PDFs listing endpoint

**User Story:** As a user, I want to see a list of all indexed PDFs with metadata, so that I know what is available for search without having to run a query.

#### Acceptance Criteria

1. THE Backend SHALL expose a `GET /pdf/list` endpoint.
2. WHEN called, THE Backend SHALL return a list of objects each containing: `filename`, `relative_url`, `chunk_count`, and `indexed_at` (ISO-8601 timestamp stored at index time).
3. WHEN no PDFs are indexed, THE Backend SHALL return an empty list with HTTP 200.
4. THE Frontend SHALL display the indexed PDF list in a dedicated "Libreria" tab on the PDF page.
5. THE Frontend SHALL show `filename`, `chunk_count`, and `indexed_at` for each entry in the list.

---

### Requirement 12: Search result highlighting

**User Story:** As a user, I want the matching chunk text in search results to have the query terms visually highlighted, so that I can quickly see why a result was returned.

#### Acceptance Criteria

1. WHEN a PDF search result is returned, THE Backend SHALL include the full matching chunk text (up to 500 characters) in the `preview_text` field.
2. THE Frontend SHALL wrap each occurrence of a query word (case-insensitive) in the `preview_text` with a `<mark>` element.
3. THE Frontend SHALL render the highlighted preview using `{@html ...}` with the query terms marked.
4. THE Frontend SHALL sanitize the `preview_text` string before injecting it as HTML to prevent XSS.

---

### Requirement 13: Search filter by filename pattern

**User Story:** As a user, I want to filter PDF search results by filename pattern, so that I can restrict my search to a specific subset of documents (e.g. only issues 1–10).

#### Acceptance Criteria

1. THE Backend `PDFSearchRequest` model SHALL include an optional `filename_filter` field (string, default `null`).
2. WHEN `filename_filter` is provided, THE Backend SHALL exclude from results any PDF whose filename does not contain the filter string (case-insensitive substring match).
3. THE Frontend SHALL display a text input labeled "Filtra per nome file" above the search results.
4. WHEN the filter input is non-empty, THE Frontend SHALL pass its value as `filename_filter` in the search request body.

---

### Requirement 14: Re-index single PDF endpoint

**User Story:** As a user, I want to re-index a specific PDF without re-indexing the entire collection, so that I can update a single document quickly.

#### Acceptance Criteria

1. THE Backend SHALL expose a `POST /pdf/reindex/{filename}` endpoint.
2. WHEN called, THE Backend SHALL delete all existing Qdrant points for that filename, re-extract text, re-chunk, re-embed, and re-upsert the points.
3. WHEN the file does not exist in PDF_Source_Dir, THE Backend SHALL return HTTP 404.
4. THE Frontend SHALL display a "Re-indicizza" button on each entry in the indexed PDF list that calls this endpoint.

---

### Requirement 15: Health check UI indicator

**User Story:** As a user, I want to see the backend connection status in the navigation bar, so that I immediately know if the service is unavailable.

#### Acceptance Criteria

1. THE Frontend SHALL poll the `GET /health` endpoint once on page load and once every 30 seconds.
2. WHEN the health check succeeds, THE Frontend SHALL display a green indicator dot labeled "Online" in the navbar.
3. WHEN the health check fails or times out (after 5 seconds), THE Frontend SHALL display a red indicator dot labeled "Offline" in the navbar.
4. THE Frontend SHALL not block page rendering while the health check is in progress.

---

### Requirement 16: Better chunking strategy (paragraph/sentence boundaries)

**User Story:** As a user, I want search results to contain coherent, readable text chunks, so that the preview text makes sense in context.

#### Acceptance Criteria

1. THE Backend `chunk_text` function SHALL split text preferentially at paragraph boundaries (`\n\n`) before falling back to sentence boundaries (`.`, `!`, `?`).
2. WHEN no paragraph or sentence boundary exists within the last 200 characters of a chunk window, THE Backend SHALL split at the nearest whitespace.
3. THE Backend SHALL produce chunks of at least 100 characters (except for the final chunk) to avoid very short, low-quality chunks.
4. FOR ALL non-empty input texts, the concatenation of all chunks (ignoring overlap) SHALL contain every word present in the original text (round-trip completeness property).

---

### Requirement 17: Mobile-responsive PDF page

**User Story:** As a user on a mobile device, I want the PDF page layout to be usable on small screens, so that I can search and manage PDFs from my phone.

#### Acceptance Criteria

1. WHILE the viewport width is less than 768 px, THE Frontend SHALL stack the upload dropzone and side card vertically (single-column layout).
2. WHILE the viewport width is less than 768 px, THE Frontend SHALL display the search form inputs and button in a single column.
3. WHILE the viewport width is less than 768 px, THE Frontend SHALL display the results grid as a single column.
4. THE Frontend SHALL ensure all interactive elements (buttons, inputs) have a minimum touch target height of 44 px on mobile viewports.

---

### Requirement 18: Dark mode support

**User Story:** As a user, I want the application to respect my system dark mode preference, so that I can use it comfortably in low-light environments.

#### Acceptance Criteria

1. THE Frontend SHALL define CSS custom properties (variables) for all background, text, border, and shadow colors used across all pages.
2. WHEN the user's system preference is `prefers-color-scheme: dark`, THE Frontend SHALL apply a dark color palette via a `@media (prefers-color-scheme: dark)` block on the `:root` selector.
3. THE Frontend SHALL ensure text contrast ratios meet WCAG AA guidelines (4.5:1 for normal text, 3:1 for large text) in both light and dark modes.

---

### Requirement 19: Pagination for PDF search results

**User Story:** As a user, I want to paginate through search results when there are many matches, so that I am not overwhelmed by a long list.

#### Acceptance Criteria

1. THE Backend `PDFSearchRequest` model SHALL include an `offset` field (integer, default `0`, minimum `0`).
2. WHEN `offset` is provided, THE Backend SHALL skip the first `offset` results before returning `limit` results.
3. THE Backend search response SHALL include a `total` field indicating the total number of unique matching PDFs before pagination.
4. THE Frontend SHALL display "Previous" and "Next" pagination buttons below the results grid.
5. WHEN the user clicks "Next", THE Frontend SHALL increment the offset by `limit` and re-run the search.
6. WHEN the user clicks "Previous", THE Frontend SHALL decrement the offset by `limit` (minimum 0) and re-run the search.
7. WHEN on the first page, THE Frontend SHALL disable the "Previous" button.
8. WHEN on the last page (offset + limit >= total), THE Frontend SHALL disable the "Next" button.
