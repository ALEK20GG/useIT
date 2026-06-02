<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/stores';
  import { PUBLIC_BACKEND_URL } from '$env/static/public';
  import { sanitizeHtml } from '$lib/sanitize';
  import Tooltip from '$lib/Tooltip.svelte';
  import DocumentPreview from '$lib/DocumentPreview.svelte';
  import { getDownloadUrl, getPreviewUrl, getFileId } from '$lib/documentUtils';

  const BACKEND_URL = PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

  // ─── Tipi ────────────────────────────────────────────────────────────────

  type Folder = {
    id: string;
    name: string;
    description: string;
    qdrant_collection: string;
  };

  type SearchResult = {
    id: string;
    title: string;
    content: string;
    score: number;
    folder_id: string | null;
    source: string;
    metadata: Record<string, unknown>;
    relative_url?: string;
    filename?: string;
    page_number?: number | null;
    preview_text?: string;
  };

  type SearchResponse = {
    results: SearchResult[];
    total: number;
    query: string;
    folder_filter: string[] | null;
    search_type: string;
  };

  // ─── Preview ──────────────────────────────────────────────────────────────

  let previewResult: SearchResult | null = null;
  let showPreview = false;

  function openPreview(hit: SearchResult) {
    previewResult = hit;
    showPreview = true;
  }

  function closePreview() {
    showPreview = false;
    previewResult = null;
  }

  // ─── Helpers per tipo file ───────────────────────────────────────────────

  function fileTypeBadge(hit: SearchResult): string {
    const ct = hit.metadata?.content_type as string | undefined;
    if (ct) {
      if (ct.includes('pdf')) return 'PDF';
      if (ct.includes('word') || ct.includes('docx')) return 'DOCX';
      if (ct.includes('plain') || ct.includes('text')) return 'TXT';
      if (ct.includes('msword')) return 'DOC';
    }
    const fn = (hit.metadata?.original_filename as string) || hit.filename || '';
    const ext = fn.split('.').pop()?.toUpperCase();
    if (ext && ['PDF', 'DOCX', 'DOC', 'TXT'].includes(ext)) return ext;
    return '';
  }

  // ─── Highlight ────────────────────────────────────────────────────────────

  function highlightContent(text: string, queryStr: string): string {
    const safe = sanitizeHtml(text);
    if (!queryStr.trim()) return safe;
    const words = queryStr.trim().split(/\s+/).filter(Boolean);
    let result = safe;
    for (const word of words) {
      const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      result = result.replace(new RegExp(escaped, 'gi'), (m) => `<mark>${m}</mark>`);
    }
    return result;
  }

  function scoreClass(score: number): string {
    if (score >= 0.7) return 'score-high';
    if (score >= 0.4) return 'score-medium';
    return 'score-low';
  }

  function scorePercent(score: number): number {
    return Math.round(score * 100);
  }

  // ─── Stato cartelle ───────────────────────────────────────────────────────

  let folders: Folder[] = [];
  let foldersLoading = false;
  let selectedFolders: string[] = [];
  let folderFilterEnabled = false;

  // ─── Stato ricerca ────────────────────────────────────────────────────────

  let query = '';
  let searchType: 'semantic' | 'keyword' | 'hybrid' = 'semantic';
  let searchLimit = 10;
  let searchOffset = 0;
  let searchLoading = false;
  let searchError = '';
  let results: SearchResult[] = [];
  let totalResults = 0;

  // ─── Suggerimenti e cronologia ────────────────────────────────────────────

  let suggestions: string[] = [];
  let suggestionsVisible = false;
  let history: Array<{ query: string; folder_filter: string[] }> = [];
  let historyVisible = false;
  let suggestDebounceTimer: ReturnType<typeof setTimeout> | null = null;

  // ─── Prefill da URL (device-based search) ────────────────────────────────

  let devicePrefill = '';

  // ─── Mappa cartelle per badge ─────────────────────────────────────────────

  let folderMap: Record<string, string> = {};

  // ─── Caricamento cartelle ─────────────────────────────────────────────────

  async function loadFolders() {
    foldersLoading = true;
    try {
      const res = await fetch(`${BACKEND_URL}/folders`);
      if (res.ok) {
        const data = await res.json();
        folders = (data.folders ?? []) as Folder[];
        folderMap = {};
        for (const f of folders) {
          folderMap[f.qdrant_collection] = f.name;
          folderMap[f.id] = f.name;
        }
      }
    } catch {
      // ignora
    } finally {
      foldersLoading = false;
    }
  }

  // ─── Caricamento cronologia ───────────────────────────────────────────────

  async function loadHistory() {
    try {
      const res = await fetch(`${BACKEND_URL}/search/history?limit=10`);
      if (res.ok) {
        const data = await res.json();
        history = data.history ?? [];
      }
    } catch {
      // ignora
    }
  }

  // ─── Suggerimenti (debounced) ─────────────────────────────────────────────

  function onQueryInput() {
    if (suggestDebounceTimer) clearTimeout(suggestDebounceTimer);
    if (!query.trim() || query.length < 2) {
      suggestions = [];
      suggestionsVisible = false;
      return;
    }
    suggestDebounceTimer = setTimeout(async () => {
      try {
        const res = await fetch(
          `${BACKEND_URL}/search/suggestions?q=${encodeURIComponent(query)}&limit=5`
        );
        if (res.ok) {
          const data = await res.json();
          suggestions = data.suggestions ?? [];
          suggestionsVisible = suggestions.length > 0;
        }
      } catch {
        suggestions = [];
      }
    }, 300);
  }

  function applySuggestion(s: string) {
    query = s;
    suggestionsVisible = false;
    suggestions = [];
  }

  function applyHistory(entry: { query: string; folder_filter: string[] }) {
    query = entry.query;
    if (entry.folder_filter && entry.folder_filter.length > 0) {
      folderFilterEnabled = true;
      selectedFolders = [...entry.folder_filter];
    }
    historyVisible = false;
    runSearch();
  }

  // ─── Toggle selezione cartella ────────────────────────────────────────────

  function toggleFolder(collectionName: string) {
    if (selectedFolders.includes(collectionName)) {
      selectedFolders = selectedFolders.filter((f) => f !== collectionName);
    } else {
      selectedFolders = [...selectedFolders, collectionName];
    }
  }

  // ─── Ricerca principale ───────────────────────────────────────────────────

  async function runSearch(resetOffset = true) {
    searchError = '';
    if (!query.trim()) {
      searchError = 'Inserisci una query di ricerca.';
      return;
    }
    if (resetOffset) searchOffset = 0;
    suggestionsVisible = false;
    historyVisible = false;

    searchLoading = true;
    try {
      const folderFilter =
        folderFilterEnabled && selectedFolders.length > 0 ? selectedFolders : null;

      const endpointMap: Record<string, string> = {
        semantic: '/search/semantic',
        keyword: '/search/keyword',
        hybrid: '/search/hybrid',
      };
      const endpoint = endpointMap[searchType] ?? '/search/semantic';

      const body = {
        query: query.trim(),
        folder_filter: folderFilter,
        limit: searchLimit,
        offset: searchOffset,
        search_type: searchType,
        semantic_weight: 0.7,
      };

      const res = await fetch(`${BACKEND_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? `Errore dal server (${res.status})`);
      }

      const data: SearchResponse = await res.json();
      results = data.results;
      totalResults = data.total;
      await loadHistory();
    } catch (err) {
      searchError = err instanceof Error ? err.message : 'Errore durante la ricerca.';
      results = [];
      totalResults = 0;
    } finally {
      searchLoading = false;
    }
  }

  // ─── Paginazione ──────────────────────────────────────────────────────────

  function prevPage() {
    if (searchOffset === 0) return;
    searchOffset = Math.max(0, searchOffset - searchLimit);
    runSearch(false);
  }

  function nextPage() {
    if (searchOffset + searchLimit >= totalResults) return;
    searchOffset += searchLimit;
    runSearch(false);
  }

  // ─── Chiudi dropdown al click esterno ────────────────────────────────────

  function handleDocumentClick(e: MouseEvent) {
    const target = e.target as HTMLElement;
    if (!target.closest('.search-input-wrapper')) {
      suggestionsVisible = false;
    }
    if (!target.closest('.history-panel')) {
      historyVisible = false;
    }
  }

  // ─── Lifecycle ────────────────────────────────────────────────────────────

  onMount(async () => {
    await Promise.all([loadFolders(), loadHistory()]);
    const urlQuery = $page.url.searchParams.get('q');
    if (urlQuery) {
      query = urlQuery;
      devicePrefill = urlQuery;
    }
    document.addEventListener('click', handleDocumentClick);
  });

  onDestroy(() => {
    if (suggestDebounceTimer) clearTimeout(suggestDebounceTimer);
    if (typeof document !== 'undefined') {
      document.removeEventListener('click', handleDocumentClick);
    }
  });

  // ─── Helpers ──────────────────────────────────────────────────────────────

  function folderName(folderId: string | null): string {
    if (!folderId) return '';
    return folderMap[folderId] ?? folderId;
  }

  function currentPage(): number {
    return Math.floor(searchOffset / searchLimit) + 1;
  }

  function totalPages(): number {
    return Math.ceil(totalResults / searchLimit);
  }

  function searchTypeLabel(t: string): string {
    const labels: Record<string, string> = {
      semantic: 'Semantica',
      keyword: 'Parole chiave',
      hybrid: 'Ibrida',
    };
    return labels[t] ?? t;
  }
</script>

<svelte:head>
  <title>Ricerca avanzata – UseIt</title>
</svelte:head>

<main class="page page-transition">
  <!-- ── Hero ─────────────────────────────────────────────────────────── -->
  <section class="hero">
    <div class="hero-text">
      <h1>Ricerca avanzata</h1>
      <p>
        Cerca nella documentazione dei dispositivi e nelle tue note con linguaggio naturale.
        Filtra per cartella o cerca in tutte le collezioni disponibili.
      </p>
      <Tooltip textKey="tooltip.semanticSearch" position="bottom" />
    </div>
  </section>

  <!-- ── Pannello ricerca ───────────────────────────────────────────────── -->
  <section class="search-panel" aria-label="Pannello di ricerca">

    {#if devicePrefill}
      <div class="device-prefill-banner" role="status" aria-live="polite">
        <span class="banner-icon" aria-hidden="true">🔍</span>
        Ricerca avviata dal dispositivo riconosciuto: <strong>{devicePrefill}</strong>
      </div>
    {/if}

    <!-- Riga principale: input + pulsante -->
    <div class="search-row">
      <div class="search-input-wrapper">
        <label for="search-query" class="sr-only">Query di ricerca</label>
        <input
          id="search-query"
          class="search-input"
          type="search"
          role="combobox"
          bind:value={query}
          oninput={onQueryInput}
          onkeydown={(e) => {
            if (e.key === 'Enter') runSearch();
            if (e.key === 'Escape') { suggestionsVisible = false; historyVisible = false; }
          }}
          placeholder="Cerca documentazione, note, dispositivi…"
          aria-label="Query di ricerca"
          aria-autocomplete="list"
          aria-controls="suggestions-list"
          aria-expanded={suggestionsVisible}
          aria-haspopup="listbox"
          autocomplete="off"
        />

        {#if suggestionsVisible && suggestions.length > 0}
          <ul
            id="suggestions-list"
            class="suggestions-dropdown"
            role="listbox"
            aria-label="Suggerimenti di ricerca"
          >
            {#each suggestions as s}
              <li
                role="option"
                aria-selected="false"
                class="suggestion-item"
                tabindex="0"
                onclick={() => applySuggestion(s)}
                onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') applySuggestion(s); }}
              >
                <span class="suggestion-icon" aria-hidden="true">🔎</span>
                {s}
              </li>
            {/each}
          </ul>
        {/if}
      </div>

      <button
        class="btn btn-primary search-btn"
        onclick={() => runSearch()}
        disabled={searchLoading}
        aria-busy={searchLoading}
        aria-label="Avvia ricerca"
      >
        {#if searchLoading}
          <span class="spinner spinner-sm" aria-hidden="true"></span>
          <span>Ricerca…</span>
        {:else}
          🔍 Cerca
        {/if}
      </button>
    </div>

    <!-- Riga opzioni: tipo ricerca + cronologia -->
    <div class="options-row">
      <fieldset class="search-type-group" aria-label="Tipo di ricerca">
        <legend class="sr-only">Tipo di ricerca</legend>
        {#each ['semantic', 'keyword', 'hybrid'] as type}
          <label class="radio-pill" class:active={searchType === type}>
            <input
              type="radio"
              name="search-type"
              value={type}
              bind:group={searchType}
              class="sr-only"
              aria-label="Ricerca {searchTypeLabel(type)}"
            />
            {searchTypeLabel(type)}
          </label>
        {/each}
        <Tooltip textKey="tooltip.hybridSearch" position="bottom" />
      </fieldset>

      <div class="history-panel">
        <button
          class="btn btn-secondary btn-sm"
          onclick={() => { historyVisible = !historyVisible; suggestionsVisible = false; }}
          aria-expanded={historyVisible}
          aria-controls="history-dropdown"
          aria-label="Mostra cronologia ricerche"
        >
          🕐 Cronologia
        </button>
        {#if historyVisible && history.length > 0}
          <ul
            id="history-dropdown"
            class="history-dropdown"
            role="listbox"
            aria-label="Cronologia ricerche recenti"
          >
            {#each history as entry}
              <li
                role="option"
                aria-selected="false"
                class="history-item"
                tabindex="0"
                onclick={() => applyHistory(entry)}
                onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') applyHistory(entry); }}
              >
                <span class="history-query">{entry.query}</span>
                {#if entry.folder_filter && entry.folder_filter.length > 0}
                  <span class="history-folders">
                    {entry.folder_filter.map((f) => folderName(f) || f).join(', ')}
                  </span>
                {/if}
              </li>
            {/each}
          </ul>
        {:else if historyVisible}
          <div class="history-dropdown history-empty" role="status">
            Nessuna ricerca recente
          </div>
        {/if}
      </div>
    </div>

    <!-- Filtro cartelle -->
    <div class="folder-filter-section">
      <label class="toggle-label">
        <input
          type="checkbox"
          bind:checked={folderFilterEnabled}
          aria-label="Abilita filtro per cartella"
        />
        <span>Filtra per cartella</span>
        <Tooltip textKey="tooltip.folderFilter" position="right" />
      </label>

      {#if folderFilterEnabled}
        <div class="folder-chips" role="group" aria-label="Selezione cartelle">
          {#if foldersLoading}
            <span class="muted">Caricamento cartelle…</span>
          {:else if folders.length === 0}
            <span class="muted">Nessuna cartella disponibile</span>
          {:else}
            {#each folders as folder}
              <button
                class="folder-chip"
                class:selected={selectedFolders.includes(folder.qdrant_collection)}
                onclick={() => toggleFolder(folder.qdrant_collection)}
                aria-pressed={selectedFolders.includes(folder.qdrant_collection)}
                aria-label="Cartella {folder.name}"
                title={folder.description || folder.name}
              >
                📁 {folder.name}
              </button>
            {/each}
          {/if}
        </div>
        {#if selectedFolders.length === 0 && !foldersLoading}
          <p class="filter-hint">
            Nessuna cartella selezionata — la ricerca coprirà tutte le collezioni.
          </p>
        {/if}
      {/if}
    </div>

    {#if searchError}
      <div class="alert alert-error" role="alert" aria-live="assertive">
        <span aria-hidden="true">⚠️</span> {searchError}
      </div>
    {/if}
  </section>

  <!-- ── Risultati ──────────────────────────────────────────────────────── -->
  {#if searchLoading && results.length === 0}
    <div class="loading-state" role="status" aria-live="polite">
      <span class="spinner" aria-hidden="true"></span>
      <span>Ricerca in corso…</span>
    </div>
  {:else if results.length > 0}
    <section class="results-section" aria-label="Risultati della ricerca" aria-live="polite">
      <div class="results-header">
        <h2 class="results-title">
          {totalResults} risultat{totalResults === 1 ? 'o' : 'i'}
          <span class="results-meta">
            · {searchTypeLabel(searchType)}
            {#if folderFilterEnabled && selectedFolders.length > 0}
              · {selectedFolders.map((f) => folderName(f) || f).join(', ')}
            {/if}
          </span>
        </h2>
      </div>

      <div class="results-list">
        {#each results as hit, index (hit.id)}
          {@const purl = getPreviewUrl(BACKEND_URL, hit)}
          {@const downloadUrl = getDownloadUrl(BACKEND_URL, hit)}
          {@const fileId = getFileId(hit)}
          {@const badge = fileTypeBadge(hit)}
          {@const sc = scorePercent(hit.score)}
          <article
            class="result-card scale-in"
            style="animation-delay: {index * 0.04}s;"
            aria-label="Risultato: {hit.title}"
          >
            <header class="result-header">
              <h3 class="result-title">{hit.title}</h3>
              <div class="result-badges">
                <!-- Score badge -->
                <span
                  class="badge badge-score {scoreClass(hit.score)}"
                  aria-label="Punteggio: {sc}%"
                >
                  {sc}%
                </span>
                <!-- Pagina -->
                {#if hit.page_number != null}
                  <span class="badge badge-page" aria-label="Pagina {hit.page_number}">
                    p.{hit.page_number}
                  </span>
                {/if}
                <!-- Tipo file -->
                {#if badge}
                  <span class="badge badge-type" aria-label="Tipo file: {badge}">
                    {badge}
                  </span>
                {/if}
                <!-- Cartella -->
                {#if hit.folder_id}
                  <span class="badge badge-folder" aria-label="Cartella: {folderName(hit.folder_id)}">
                    📁 {folderName(hit.folder_id) || hit.folder_id}
                  </span>
                {/if}
              </div>
            </header>

            <!-- Barra score -->
            <div class="score-bar-wrapper" aria-hidden="true">
              <div
                class="score-bar {scoreClass(hit.score)}"
                style="width: {sc}%"
                role="presentation"
              ></div>
            </div>

            <!-- Contenuto con highlight -->
            <p class="result-content">
              {@html highlightContent(hit.content, query)}
            </p>

            <!-- Footer azioni -->
            <div class="result-actions">
              {#if purl}
                <button
                  class="btn btn-secondary btn-xs"
                  onclick={() => openPreview(hit)}
                  aria-label="Anteprima '{hit.title}'"
                >
                  👁️ Anteprima
                </button>
              {/if}
              {#if fileId}
                <a
                  href="{BACKEND_URL}/files/{fileId}/download"
                  class="btn btn-secondary btn-xs"
                  download
                  aria-label="Scarica '{hit.title}'"
                >
                  ⬇️ Scarica
                </a>
              {/if}
              <a
                href="/user?save=true&title={encodeURIComponent(hit.title)}&content={encodeURIComponent(hit.content.slice(0, 2000))}&source={encodeURIComponent(hit.source || 'ricerca')}"
                class="btn btn-secondary btn-xs"
                aria-label="Salva '{hit.title}' nell'area personale"
              >
                💾 Salva
              </a>
            </div>
          </article>
        {/each}
      </div>

      {#if totalPages() > 1}
        <nav class="pagination" aria-label="Paginazione risultati">
          <button
            class="btn btn-secondary btn-sm"
            onclick={prevPage}
            disabled={searchOffset === 0 || searchLoading}
            aria-label="Pagina precedente"
          >
            ← Precedente
          </button>
          <span class="pagination-info" aria-current="page">
            Pagina {currentPage()} di {totalPages()}
          </span>
          <button
            class="btn btn-secondary btn-sm"
            onclick={nextPage}
            disabled={searchOffset + searchLimit >= totalResults || searchLoading}
            aria-label="Pagina successiva"
          >
            Successiva →
          </button>
        </nav>
      {/if}
    </section>
  {:else if !searchLoading && query && !searchError}
    <div class="empty-state" role="status" aria-live="polite">
      <span class="empty-icon" aria-hidden="true">🔍</span>
      <p>Nessun risultato trovato per <strong>"{query}"</strong>.</p>
      <p class="muted">Prova con parole chiave diverse o rimuovi il filtro cartella.</p>
    </div>
  {/if}
</main>

<DocumentPreview
  open={showPreview}
  document={previewResult}
  backendUrl={BACKEND_URL}
  onClose={closePreview}
/>

<style>
  .page {
    max-width: 1100px;
    margin: 0 auto;
    padding: var(--space-8) var(--space-6);
  }
  .hero {
    margin-bottom: var(--space-6);
  }
  .hero h1 {
    font-size: var(--font-size-3xl);
    margin-bottom: var(--space-2);
  }
  .hero p {
    color: var(--color-text-muted);
    max-width: 640px;
  }
  .search-panel {
    background: var(--color-card-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--space-3);
    padding: var(--space-5);
    margin-bottom: var(--space-5);
  }
  .search-row {
    display: flex;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
  }
  .search-input-wrapper {
    position: relative;
    flex: 1;
  }
  .search-input {
    width: 100%;
    padding: var(--space-3) var(--space-4);
    border: 2px solid var(--color-border);
    border-radius: var(--space-2);
    background: var(--color-input-bg);
    font-size: var(--font-size-base);
  }
  .search-input:focus {
    outline: none;
    border-color: var(--color-primary);
    box-shadow: 0 0 0 3px var(--color-primary-subtle);
  }
  .suggestions-dropdown,
  .history-dropdown {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    z-index: 50;
    background: var(--color-card-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--space-2);
    list-style: none;
    margin: var(--space-1) 0 0;
    padding: var(--space-1);
    box-shadow: 0 8px 24px var(--color-shadow-medium);
  }
  .history-panel {
    position: relative;
  }
  .history-dropdown {
    right: 0;
    left: auto;
    min-width: 260px;
  }
  .suggestion-item,
  .history-item {
    padding: var(--space-2) var(--space-3);
    cursor: pointer;
    border-radius: var(--space-1);
    font-size: var(--font-size-sm);
  }
  .suggestion-item:hover,
  .history-item:hover {
    background: var(--color-bg-secondary);
  }
  .options-row {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
  }
  .search-type-group {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    border: none;
    margin: 0;
    padding: 0;
  }
  .radio-pill {
    padding: var(--space-2) var(--space-3);
    border-radius: 999px;
    border: 1px solid var(--color-border);
    font-size: var(--font-size-sm);
    cursor: pointer;
  }
  .radio-pill.active {
    background: var(--color-primary);
    color: white;
    border-color: var(--color-primary);
  }
  .folder-chips {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }
  .folder-chip {
    padding: var(--space-1) var(--space-3);
    border-radius: 999px;
    border: 1px solid var(--color-border);
    background: var(--color-bg-secondary);
    cursor: pointer;
    font-size: var(--font-size-sm);
  }
  .folder-chip.selected {
    background: var(--color-primary-subtle);
    border-color: var(--color-primary);
    color: var(--color-primary);
  }
  .results-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  .result-card {
    background: var(--color-card-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--space-3);
    padding: var(--space-4);
  }
  .result-header {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
  }
  .result-title {
    margin: 0;
    font-size: var(--font-size-base);
    font-weight: var(--font-weight-semibold);
  }
  .result-badges {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
  }
  .badge {
    padding: 2px 8px;
    border-radius: var(--space-1);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
  }
  .badge-score.score-high {
    background: var(--color-success-subtle);
    color: var(--color-success);
  }
  .badge-score.score-medium {
    background: var(--color-warning-subtle);
    color: var(--color-warning);
  }
  .badge-score.score-low {
    background: var(--color-bg-tertiary);
    color: var(--color-text-muted);
  }
  .score-bar-wrapper {
    height: 4px;
    background: var(--color-border-subtle);
    border-radius: 2px;
    margin-bottom: var(--space-3);
    overflow: hidden;
  }
  .score-bar {
    height: 100%;
  }
  .score-bar.score-high {
    background: var(--color-success);
  }
  .score-bar.score-medium {
    background: var(--color-warning);
  }
  .score-bar.score-low {
    background: var(--color-text-subtle);
  }
  .result-content {
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
    line-height: var(--line-height-relaxed);
  }
  .result-content :global(mark) {
    background: #fef08a;
    padding: 0 2px;
  }
  .result-actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-top: var(--space-3);
    padding-top: var(--space-3);
    border-top: 1px solid var(--color-border-subtle);
  }
  .pagination {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: var(--space-4);
    margin-top: var(--space-6);
  }
  .loading-state,
  .empty-state {
    text-align: center;
    padding: var(--space-12);
    color: var(--color-text-muted);
  }
  .alert-error {
    padding: var(--space-3);
    background: var(--color-error-subtle);
    color: var(--color-error-text);
    border-radius: var(--space-2);
    margin-top: var(--space-3);
  }
  .muted {
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
  }
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
  }
  @media (max-width: 640px) {
    .search-row {
      flex-direction: column;
    }
  }
</style>
