# Implementation Plan: PDF Semantic Search Platform

## Overview

Incremental implementation of bug fixes and feature enhancements for the UseIt application. Tasks are ordered so each step builds on the previous: start with backend bug fixes, then add new backend capabilities, then wire up the frontend.

## Tasks

- [x] 1. Fix backend bug fixes (Requirements 1–6)
  - [x] 1.1 Fix `sentence_transformers` typo in `backend/requirements.txt`
    - Change `sentence_tranformers==5.2.2` to `sentence_transformers==5.2.2`
    - _Requirements: 1.1_

  - [x] 1.2 Fix `chunk_text` variable shadowing in `main.py`
    - Rename the loop variable `chunk_text` to `chunk_text_content` inside `upload_pdf` and `index_all_pdfs`
    - Ensure the imported `chunk_text` function remains callable
    - _Requirements: 4.1, 4.2_

  - [x] 1.3 Fix `keyword_boost` NameError in `search_pdfs`
    - Assign `keyword_boost = 0.0` before the `if body.use_keyword_boost` branch so it is always defined
    - _Requirements: 5.1, 5.2_

  - [x] 1.4 Replace deprecated `recreate_collection` calls
    - In `main.py` `/collections` endpoint: replace `client.recreate_collection(...)` with `client.delete_collection(...)` + `client.create_collection(...)`; catch the exception from `delete_collection` when the collection does not exist
    - In `upload_pdf` and `index_all_pdfs`: replace any remaining `recreate_collection` calls with the same pattern
    - _Requirements: 6.1, 6.2_

  - [x] 1.5 Fix semantic ingest to be additive (no collection recreation)
    - In `/semantic/ingest`: check if the Notes_Collection exists with `client.get_collection`; only create it if absent or if vector size differs (using delete + create); never delete an existing correctly-sized collection
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 1.6 Write property test for ingest additivity
    - **Property 7: Ingest is additive (no data loss)**
    - **Validates: Requirements 2.1, 2.2**
    - Use `hypothesis` with a mock Qdrant client; verify point count is non-decreasing after each ingest call

  - [x] 1.7 Fix tab active state in PDF page
    - In `frontend/src/routes/pdf/+page.svelte`: bind `class:active={currentTab === 'upload'}` and `class:active={currentTab === 'search'}` on the tab buttons; remove the hardcoded `active` HTML attribute
    - _Requirements: 3.1, 3.2, 3.3_

- [x] 2. Checkpoint — Ensure all bug fixes are correct
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Configurable settings (Requirements 7–8)
  - [x] 3.1 Add `cors_origins` to `Settings` in `config.py`
    - Add `cors_origins: list[str]` field with default `["http://localhost:5173", "http://127.0.0.1:5173"]`
    - Add a Pydantic `field_validator` that parses a comma-separated `CORS_ORIGINS` env var into a list
    - Update `model_config` to remove the `env_prefix="QDRANT_"` restriction so `CORS_ORIGINS` is read correctly (or use a separate prefix-free field)
    - _Requirements: 7.1, 7.2, 7.3_

  - [x] 3.2 Wire `cors_origins` into the CORS middleware in `main.py`
    - Replace the hardcoded `allow_origins` list with `get_settings().cors_origins`
    - _Requirements: 7.1_

  - [x] 3.3 Replace hardcoded `BACKEND_URL` in all frontend pages
    - In `frontend/src/routes/pdf/+page.svelte`, `semantic/+page.svelte`, and `analyze/+page.svelte`: import `PUBLIC_BACKEND_URL` from `$env/static/public` and set `const BACKEND_URL = PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000'`
    - Also update `+layout.svelte` health check (added in task 9) to use the same pattern
    - _Requirements: 8.1, 8.2, 8.3_

  - [x] 3.4 Create `frontend/.env.example`
    - Add `PUBLIC_BACKEND_URL=http://127.0.0.1:8000` as the documented default
    - _Requirements: 8.4_

- [x] 4. Improve chunking strategy (Requirement 16)
  - [x] 4.1 Rewrite `chunk_text` in `pdf_utils.py`
    - Priority order: split at `\n\n` within last 200 chars → sentence boundary (`.`, `!`, `?`) → nearest whitespace → hard split
    - Merge chunks shorter than 100 characters into the previous chunk (except the final chunk)
    - _Requirements: 16.1, 16.2, 16.3_

  - [x] 4.2 Write property test for chunk round-trip completeness
    - **Property 1: Chunk round-trip completeness**
    - **Validates: Requirements 16.4**
    - Use `hypothesis` `st.text(min_size=1, max_size=5000)`; assert every word in the original text appears in the concatenation of all chunks

  - [x] 4.3 Write property test for chunk minimum length invariant
    - **Property 2: Chunk minimum length invariant**
    - **Validates: Requirements 16.3**
    - Use `hypothesis` `st.text(min_size=101, max_size=5000)`; assert every chunk except the last has `len >= 100`

- [x] 5. Store page number per chunk (Requirement 9)
  - [x] 5.1 Update `extract_text_from_pdf` to return per-page tuples
    - Change return type to `list[tuple[int, str]]` where each tuple is `(page_number, page_text)`
    - Update `extract_text_from_pdf_file` accordingly
    - _Requirements: 9.1_

  - [x] 5.2 Update `upload_pdf` and `index_all_pdfs` to tag chunks with `page_number`
    - Iterate over `(page_number, page_text)` tuples; call `chunk_text` per page; store `page_number` in each point's payload
    - Store `indexed_at` (UTC ISO-8601 timestamp) in each point's payload
    - _Requirements: 9.1, 11.2_

  - [x] 5.3 Add `page_number` and update `PDFSearchResult` in `schemas.py`
    - Add `page_number: int | None = None` to `PDFSearchResult`
    - Add `PDFSearchResponse`, `IndexedPDF` models as specified in the design
    - Add `filename_filter: str | None = None` and `offset: int = Field(default=0, ge=0)` to `PDFSearchRequest`
    - _Requirements: 9.2, 11.2, 13.1, 19.1_

  - [x] 5.4 Return `page_number` from `search_pdfs` in `main.py`
    - Populate `page_number` from the Qdrant point payload in the result mapping
    - _Requirements: 9.2_

- [x] 6. Checkpoint — Ensure page number and chunking work end-to-end
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. New backend endpoints (Requirements 10, 11, 14)
  - [x] 7.1 Implement `GET /pdf/list` endpoint
    - Query Qdrant for all points in the `pdfs` collection; group by filename; return `IndexedPDF` list with `filename`, `relative_url`, `chunk_count`, `indexed_at`
    - Return empty list with HTTP 200 when no PDFs are indexed
    - _Requirements: 11.1, 11.2, 11.3_

  - [x] 7.2 Implement `DELETE /pdf/{filename}` endpoint
    - Delete all Qdrant points whose payload `filename` matches the given filename (use `delete` with a filter)
    - Delete the file from `PDFS_DIR` if it exists
    - Return HTTP 404 if no points found and no file on disk
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [x] 7.3 Implement `POST /pdf/reindex/{filename}` endpoint
    - Return HTTP 404 if the file does not exist in `PDFS_DIR`
    - Delete existing Qdrant points for the filename, then re-extract, re-chunk, re-embed, and re-upsert
    - _Requirements: 14.1, 14.2, 14.3_

- [x] 8. Enhance `search_pdfs` with filtering, pagination, and total (Requirements 12, 13, 19)
  - [x] 8.1 Add `filename_filter` support to `search_pdfs`
    - After building `pdf_map`, exclude entries whose `filename` does not contain `body.filename_filter` (case-insensitive) when the filter is non-null
    - _Requirements: 13.2_

  - [x] 8.2 Write property test for filename filter exclusion
    - **Property 5: Filename filter exclusion**
    - **Validates: Requirements 13.2**
    - Use `hypothesis`; assert every result filename contains the filter string when filter is non-null

  - [x] 8.3 Add pagination (`offset`) and `total` to `search_pdfs`
    - Apply `offset` slicing after sorting; include `total` (count before slicing) in the response
    - Change response model to `PDFSearchResponse`
    - _Requirements: 19.1, 19.2, 19.3_

  - [x] 8.4 Write property test for pagination offset correctness
    - **Property 6: Pagination offset correctness**
    - **Validates: Requirements 19.2**
    - Use `hypothesis`; assert results at `offset=k` equal the full sorted list sliced `[k:k+limit]`

  - [x] 8.5 Ensure `preview_text` is populated with up to 500 characters of the best matching chunk
    - _Requirements: 12.1_

  - [x] 8.6 Write property test for keyword boost bounded
    - **Property 3: Keyword boost is bounded**
    - **Validates: Requirements 5.1, 5.2**
    - Use `hypothesis` `st.text(), st.text()`; assert `calculate_keyword_boost` returns a value in `[0.0, 0.3]`

  - [x] 8.7 Write property test for normalized score bounded
    - **Property 4: Normalized score is bounded**
    - **Validates: Requirements 5.1**
    - Use `hypothesis` `st.floats(min_value=-1.0, max_value=1.0, allow_nan=False)`; assert `normalize_cosine_score` returns a value in `[0.0, 1.0]`

- [x] 9. Checkpoint — Ensure all backend endpoints and search enhancements work
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Health check UI indicator (Requirement 15)
  - [x] 10.1 Create `HealthIndicator` component in `frontend/src/lib/HealthIndicator.svelte`
    - On mount, call `GET /health`; repeat every 30 seconds via `setInterval`; use `AbortController` with 5-second timeout
    - Render a green dot + "Online" or red dot + "Offline" label
    - Do not block rendering (async, non-blocking)
    - _Requirements: 15.1, 15.2, 15.3, 15.4_

  - [x] 10.2 Add `HealthIndicator` to `+layout.svelte` navbar
    - Import and render `<HealthIndicator>` in the nav bar next to the nav links
    - _Requirements: 15.1_

- [x] 11. Frontend PDF page enhancements (Requirements 9, 10, 11, 12, 13, 17, 19)
  - [x] 11.1 Add "Libreria" tab to the PDF page
    - Add a third tab button `Libreria` driven by `currentTab === 'library'`
    - On tab activation, call `GET /pdf/list` and display `filename`, `chunk_count`, `indexed_at` for each entry
    - Add "Re-indicizza" button per entry that calls `POST /pdf/reindex/{filename}`
    - Add delete button per entry that calls `DELETE /pdf/{filename}` and removes the entry on success
    - _Requirements: 11.4, 11.5, 14.4_

  - [x] 11.2 Add filename filter input to "Cerca PDF" tab
    - Add a text input labeled "Filtra per nome file" above the search results
    - Pass its value as `filename_filter` in the search request body when non-empty
    - _Requirements: 13.3, 13.4_

  - [x] 11.3 Add pagination controls to "Cerca PDF" tab
    - Track `offset` state; display "Previous" and "Next" buttons below the results grid
    - Disable "Previous" when `offset === 0`; disable "Next" when `offset + limit >= total`
    - On click, update `offset` and re-run the search
    - Update search result type to use `PDFSearchResponse` wrapper
    - _Requirements: 19.4, 19.5, 19.6, 19.7, 19.8_

  - [x] 11.4 Display page number on search result cards
    - Show "Pagina {page_number}" on each result card when `page_number` is non-null
    - _Requirements: 9.3_

  - [x] 11.5 Add delete button to search result cards
    - Add a delete button on each result card; call `DELETE /pdf/{filename}` on click; disable while in-flight; remove card from results on success
    - _Requirements: 10.5_

  - [x] 11.6 Implement search result highlighting with sanitization
    - Create a `sanitizeHtml(text: string): string` helper that escapes `<`, `>`, `&`, `"` in `preview_text`
    - After sanitizing, wrap each occurrence of a query word (case-insensitive) in `<mark>` tags
    - Render the result using `{@html highlightedText}`
    - _Requirements: 12.2, 12.3, 12.4_

  - [x] 11.7 Write Vitest unit tests for `sanitizeHtml`
    - **Property 8: Preview text sanitization safety**
    - **Validates: Requirements 12.4**
    - Test XSS payloads (`<script>`, `<iframe>`), normal text, empty string; assert no unescaped `<script` or `<iframe` in output

- [x] 12. Mobile responsiveness and dark mode (Requirements 17–18)
  - [x] 12.1 Add mobile-responsive CSS to the PDF page
    - Below 768 px: stack upload dropzone and side card vertically (single column)
    - Below 768 px: stack search form inputs and button in a single column
    - Below 768 px: display results grid as a single column
    - Ensure all buttons and inputs have `min-height: 44px` on mobile
    - _Requirements: 17.1, 17.2, 17.3, 17.4_

  - [x] 12.2 Add CSS custom properties and dark mode support across all pages
    - Define CSS custom properties for all background, text, border, and shadow colors on `:root` in `+layout.svelte` or a global CSS file
    - Add a `@media (prefers-color-scheme: dark)` block on `:root` with a dark color palette
    - Apply the custom properties in `+layout.svelte`, `pdf/+page.svelte`, `semantic/+page.svelte`, and `analyze/+page.svelte`
    - _Requirements: 18.1, 18.2_

- [x] 13. Final checkpoint — Ensure all tests pass and features are wired together
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. Correzione errori di accessibilità (Requirements 20–22)
  - [x] 14.1 Aggiungere ruoli ARIA per elementi drag-and-drop
    - Aggiungere `role="button"` a tutti gli elementi `<div>` con handler `on:dragover`, `on:dragleave`, o `on:drop` in `frontend/src/routes/pdf/+page.svelte` e `frontend/src/routes/analyze/+page.svelte`
    - Aggiungere `tabindex="0"` per rendere le aree accessibili da tastiera
    - Aggiungere attributi `aria-label` descrittivi (es. "Area di caricamento PDF - trascina qui i file o clicca per selezionare")
    - _Requirements: 20.1, 20.2, 20.3_

  - [x] 14.2 Implementare supporto tastiera per elementi clickabili
    - Aggiungere `role="button"` a tutti gli elementi `<div>` con handler `on:click` che non sono bottoni semantici
    - Implementare handler `on:keydown` per supportare attivazione con tasti Enter e Spazio
    - Assicurare che tutti gli elementi clickabili abbiano valori `tabindex` appropriati per la navigazione da tastiera
    - Aggiungere attributi `aria-label` descrittivi dove il contesto visuale potrebbe non essere chiaro per screen reader
    - _Requirements: 21.1, 21.2, 21.3, 21.4_

  - [x] 14.3 Aggiungere title per iframe PDF
    - Aggiungere attributo `title` all'elemento `<iframe>` nel modal di anteprima PDF in `frontend/src/routes/pdf/+page.svelte`
    - Impostare il title a un valore descrittivo come "Anteprima del documento PDF" o includere dinamicamente il nome del file PDF
    - _Requirements: 22.1, 22.2_

  - [x] 14.4 Scrivere test per conformità accessibilità ARIA
    - **Property 9: ARIA accessibility compliance**
    - **Validates: Requirements 20.1, 20.2, 20.3, 21.1, 21.2, 21.4**
    - Testare che elementi interattivi abbiano ruoli ARIA appropriati, handler tastiera e label descrittive

- [x] 15. Miglioramenti design system e UI (Requirement 23)
  - [x] 15.1 Implementare nuovo sistema di colori
    - Definire palette di colori migliorata con rapporti di contrasto migliori per modalità chiara e scura
    - Implementare token di colore semantici: `--color-primary`, `--color-secondary`, `--color-success`, `--color-warning`, `--color-error`
    - Assicurare conformità WCAG AA (4.5:1 per testo normale, 3:1 per testo grande)
    - _Requirements: 23.1, 18.3_

  - [x] 15.2 Migliorare tipografia e sistema di spaziatura
    - Implementare scala tipografica consistente usando proprietà CSS personalizzate
    - Definire sistema di spaziatura basato su unità di 8px (0.5rem, 1rem, 1.5rem, 2rem, 3rem, 4rem)
    - Ottimizzare altezza di riga e spaziatura lettere per leggibilità
    - Applicare margini e padding consistenti su tutti i componenti
    - _Requirements: 23.3_

  - [x] 15.3 Implementare stati hover/focus/active migliorati
    - Migliorare stili dei bottoni con gerarchia visuale chiara
    - Implementare stati hover con transizioni di colore sottili (200ms ease)
    - Aggiungere indicatori di focus con outline di 2px e contrasto appropriato
    - Implementare stati attivi con feedback visuale
    - Gestire stati disabilitati con opacità ridotta
    - _Requirements: 23.2, 23.5_

  - [x] 15.4 Aggiungere animazioni e transizioni
    - Implementare transizioni sottili per stati hover/focus (200ms ease)
    - Aggiungere animazioni per stati di caricamento
    - Rispettare media query `prefers-reduced-motion` per accessibilità
    - Implementare transizioni di pagina che non interferiscono con la navigazione
    - _Requirements: 23.4_

  - [x] 15.5 Scrivere test per conformità contrasto colori
    - **Property 10: Color contrast compliance**
    - **Validates: Requirements 18.3, 23.1**
    - Testare che le combinazioni di colori rispettino le linee guida WCAG AA in entrambe le modalità

- [x] 16. Creazione documentazione architetturale (Requirement 24)
  - [x] 16.1 Creare documentazione struttura frontend
    - Documentare la struttura delle route SvelteKit e componenti principali
    - Spiegare il sistema di gestione dello stato e le variabili reattive
    - Documentare l'implementazione dell'accessibilità e responsive design
    - Spiegare la gestione delle chiamate API e degli stati di errore
    - _Requirements: 24.2_

  - [x] 16.2 Creare documentazione struttura backend
    - Documentare la struttura dei moduli FastAPI e endpoint principali
    - Spiegare il processo di elaborazione dei documenti (estrazione, chunking, embedding)
    - Documentare la strategia di indicizzazione e gestione delle collezioni Qdrant
    - Spiegare la gestione degli errori e delle configurazioni
    - _Requirements: 24.3_

  - [x] 16.3 Documentare flussi di dati e architettura
    - Creare diagrammi di sequenza per i flussi principali (caricamento PDF, ricerca semantica)
    - Documentare l'architettura generale del sistema e le interazioni tra componenti
    - Spiegare la strategia di deployment e configurazione per diversi ambienti
    - Documentare considerazioni di sicurezza e performance
    - _Requirements: 24.1, 24.4_

  - [x] 16.4 Finalizzare documentazione in italiano
    - Assicurare che tutta la documentazione sia scritta in italiano
    - Includere esempi pratici e casi d'uso
    - Aggiungere sezioni di troubleshooting e FAQ
    - Creare indice e struttura navigabile
    - _Requirements: 24.5_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Property tests use `hypothesis` (Python) and `vitest` (TypeScript)
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at logical boundaries
- I nuovi task 14-16 coprono accessibilità, design system e documentazione architetturale
