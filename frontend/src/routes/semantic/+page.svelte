<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/stores';
  import { PUBLIC_BACKEND_URL } from '$env/static/public';
  import Tooltip from '$lib/Tooltip.svelte';

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
  };

  type SearchResponse = {
    results: SearchResult[];
    total: number;
    query: string;
    folder_filter: string[] | null;
    search_type: string;
  };

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
      // Ignora errori di rete per le cartelle
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
      // Ignora errori
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

      // Aggiorna cronologia
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

    // Prefill da parametro URL ?q= (device-based search)
    const urlQuery = $page.url.searchParams.get('q');
    if (urlQuery) {
      query = urlQuery;
      devicePrefill = urlQuery;
    }

    document.addEventListener('click', handleDocumentClick);
  });

  onDestroy(() => {
    if (suggestDebounceTimer) clearTimeout(suggestDebounceTimer);
    document.removeEventListener('click', handleDocumentClick);
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
        <Tooltip textKey="tooltip.semanticSearch" position="bottom" />
      </p>
    </div>
  </section>

  <!-- ── Pannello ricerca ───────────────────────────────────────────────── -->
  <section class="search-panel" aria-label="Pannello di ricerca">

    <!-- Prefill da dispositivo -->
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
          on:input={onQueryInput}
          on:keydown={(e) => {
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

        <!-- Suggerimenti dropdown -->
        {#if suggestionsVisible && suggestions.length > 0}
          <ul
            id="suggestions-list"
            class="suggestions-dropdown"
            role="listbox"
            aria-label="Suggerimenti di ricerca"
          >
            {#each suggestions as s, i}
              <li
                role="option"
                aria-selected="false"
                class="suggestion-item"
                tabindex="0"
                on:click={() => applySuggestion(s)}
                on:keydown={(e) => { if (e.key === 'Enter' || e.key === ' ') applySuggestion(s); }}
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
        on:click={() => runSearch()}
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
      <!-- Tipo di ricerca -->
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

      <!-- Cronologia -->
      <div class="history-panel">
        <button
          class="btn btn-secondary btn-sm"
          on:click={() => { historyVisible = !historyVisible; suggestionsVisible = false; }}
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
            {#each history as entry, i}
              <li
                role="option"
                aria-selected="false"
                class="history-item"
                tabindex="0"
                on:click={() => applyHistory(entry)}
                on:keydown={(e) => { if (e.key === 'Enter' || e.key === ' ') applyHistory(entry); }}
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
                on:click={() => toggleFolder(folder.qdrant_collection)}
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

    <!-- Errore ricerca -->
    {#if searchError}
      <div class="alert alert-error" role="alert" aria-live="assertive">
        <span aria-hidden="true">⚠️</span> {searchError}
      </div>
    {/if}
  </section>

  <!-- ── Risultati ──────────────────────────────────────────────────────── -->
  {#if results.length > 0}
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
          <article
            class="result-card scale-in"
            style="animation-delay: {index * 0.04}s;"
            aria-label="Risultato: {hit.title}"
          >
            <header class="result-header">
              <h3 class="result-title">{hit.title}</h3>
              <div class="result-badges">
                {#if hit.folder_id}
                  <span class="badge badge-folder" aria-label="Cartella: {folderName(hit.folder_id)}">
                    📁 {folderName(hit.folder_id) || hit.folder_id}
                  </span>
                {/if}
                <span class="badge badge-score" aria-label="Punteggio: {hit.score.toFixed(3)}">
                  {hit.score.toFixed(3)}
                </span>
                {#if hit.source && hit.source !== 'qdrant'}
                  <span class="badge badge-source" aria-label="Fonte: {hit.source}">
                    {hit.source}
                  </span>
                {/if}
              </div>
            </header>
            <p class="result-content">{hit.content}</p>
            <div class="result-actions">
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

      <!-- Paginazione -->
      {#if totalPages() > 1}
        <nav class="pagination" aria-label="Paginazione risultati">
          <button
            class="btn btn-secondary btn-sm"
            on:click={prevPage}
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
            on:click={nextPage}
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

<style>
  /* ── Layout ──────────────────────────────────────────────────────────── */
  .page {
    max-width: 900px;
    margin: 0 auto;
    padding: var(--space-8) var(--space-6) var(--space-16);
    font-family: var(--font-family-sans);
  }

  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

  /* ── Hero ────────────────────────────────────────────────────────────── */
  .hero {
    margin-bottom: var(--space-8);
  }

  .hero-text h1 {
    font-size: var(--font-size-3xl);
    font-weight: var(--font-weight-bold);
    line-height: var(--line-height-tight);
    letter-spacing: var(--letter-spacing-tight);
    margin-bottom: var(--space-3);
    color: var(--color-text);
  }

  .hero-text p {
    color: var(--color-text-muted);
    max-width: 42rem;
    font-size: var(--font-size-base);
    line-height: var(--line-height-relaxed);
  }

  /* ── Pannello ricerca ────────────────────────────────────────────────── */
  .search-panel {
    background: var(--color-card-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--space-3);
    padding: var(--space-6);
    box-shadow: 0 1px var(--space-1) var(--color-shadow);
    margin-bottom: var(--space-8);
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  /* ── Banner prefill dispositivo ──────────────────────────────────────── */
  .device-prefill-banner {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-4);
    background: var(--color-primary-subtle);
    border: 1px solid var(--color-primary-muted);
    border-radius: var(--space-2);
    font-size: var(--font-size-sm);
    color: var(--color-primary);
  }

  .banner-icon {
    font-size: var(--font-size-base);
  }

  /* ── Riga ricerca ────────────────────────────────────────────────────── */
  .search-row {
    display: flex;
    gap: var(--space-3);
    align-items: stretch;
  }

  .search-input-wrapper {
    position: relative;
    flex: 1;
  }

  .search-input {
    width: 100%;
    border-radius: var(--space-2);
    border: 2px solid var(--color-border);
    padding: var(--space-3) var(--space-4);
    font-size: var(--font-size-base);
    font-family: inherit;
    background: var(--color-input-bg);
    color: var(--color-text);
    min-height: 48px;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
    box-sizing: border-box;
  }

  .search-input:focus {
    outline: none;
    border-color: var(--color-primary);
    box-shadow: 0 0 0 3px var(--color-primary-subtle);
  }

  .search-input:hover:not(:focus) {
    border-color: var(--color-primary-muted);
  }

  .search-btn {
    white-space: nowrap;
    min-height: 48px;
    padding: 0 var(--space-6);
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  /* ── Suggerimenti ────────────────────────────────────────────────────── */
  .suggestions-dropdown {
    position: absolute;
    top: calc(100% + var(--space-1));
    left: 0;
    right: 0;
    background: var(--color-card-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--space-2);
    box-shadow: 0 var(--space-2) var(--space-6) var(--color-shadow-medium);
    list-style: none;
    margin: 0;
    padding: var(--space-1) 0;
    z-index: 200;
    max-height: 240px;
    overflow-y: auto;
  }

  .suggestion-item {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-4);
    font-size: var(--font-size-sm);
    color: var(--color-text);
    cursor: pointer;
    transition: background 0.15s ease;
  }

  .suggestion-item:hover,
  .suggestion-item:focus {
    background: var(--color-bg-secondary);
    outline: none;
  }

  .suggestion-icon {
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  /* ── Riga opzioni ────────────────────────────────────────────────────── */
  .options-row {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    flex-wrap: wrap;
  }

  /* ── Tipo ricerca ────────────────────────────────────────────────────── */
  .search-type-group {
    display: flex;
    gap: var(--space-2);
    border: none;
    padding: 0;
    margin: 0;
    flex-wrap: wrap;
  }

  .radio-pill {
    display: inline-flex;
    align-items: center;
    padding: var(--space-2) var(--space-4);
    border-radius: 999px;
    border: 1.5px solid var(--color-border);
    background: var(--color-bg-secondary);
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    cursor: pointer;
    transition: all 0.15s ease;
    user-select: none;
  }

  .radio-pill:hover {
    border-color: var(--color-primary-muted);
    color: var(--color-primary);
  }

  .radio-pill.active {
    background: var(--color-primary-subtle);
    border-color: var(--color-primary);
    color: var(--color-primary);
    font-weight: var(--font-weight-semibold);
  }

  /* ── Cronologia ──────────────────────────────────────────────────────── */
  .history-panel {
    position: relative;
    margin-left: auto;
  }

  .btn-sm {
    padding: var(--space-2) var(--space-3);
    font-size: var(--font-size-sm);
    min-height: 36px;
  }

  .btn-secondary {
    background: var(--color-bg-secondary);
    border: 1.5px solid var(--color-border);
    color: var(--color-text-muted);
    border-radius: var(--space-2);
    cursor: pointer;
    font-family: inherit;
    font-weight: var(--font-weight-medium);
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    transition: all 0.15s ease;
  }

  .btn-secondary:hover:not(:disabled) {
    border-color: var(--color-primary-muted);
    color: var(--color-primary);
    background: var(--color-primary-subtle);
  }

  .btn-secondary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .history-dropdown {
    position: absolute;
    top: calc(100% + var(--space-1));
    right: 0;
    min-width: 280px;
    background: var(--color-card-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--space-2);
    box-shadow: 0 var(--space-2) var(--space-6) var(--color-shadow-medium);
    list-style: none;
    margin: 0;
    padding: var(--space-1) 0;
    z-index: 200;
    max-height: 280px;
    overflow-y: auto;
  }

  .history-empty {
    padding: var(--space-4);
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
    text-align: center;
  }

  .history-item {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    padding: var(--space-3) var(--space-4);
    cursor: pointer;
    transition: background 0.15s ease;
  }

  .history-item:hover,
  .history-item:focus {
    background: var(--color-bg-secondary);
    outline: none;
  }

  .history-query {
    font-size: var(--font-size-sm);
    color: var(--color-text);
    font-weight: var(--font-weight-medium);
  }

  .history-folders {
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }

  /* ── Filtro cartelle ─────────────────────────────────────────────────── */
  .folder-filter-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .toggle-label {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    color: var(--color-text);
    cursor: pointer;
    user-select: none;
  }

  .toggle-label input[type='checkbox'] {
    width: 18px;
    height: 18px;
    accent-color: var(--color-primary);
    cursor: pointer;
  }

  .folder-chips {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }

  .folder-chip {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-2) var(--space-3);
    border-radius: 999px;
    border: 1.5px solid var(--color-border);
    background: var(--color-bg-secondary);
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .folder-chip:hover {
    border-color: var(--color-primary-muted);
    color: var(--color-primary);
  }

  .folder-chip.selected {
    background: var(--color-primary-subtle);
    border-color: var(--color-primary);
    color: var(--color-primary);
    font-weight: var(--font-weight-semibold);
  }

  .filter-hint {
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
    margin: 0;
  }

  .muted {
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
  }

  /* ── Alert ───────────────────────────────────────────────────────────── */
  .alert {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-4);
    border-radius: var(--space-2);
    font-size: var(--font-size-sm);
  }

  .alert-error {
    background: var(--color-error-subtle);
    border: 1px solid var(--color-error-muted);
    color: var(--color-error);
  }

  /* ── Risultati ───────────────────────────────────────────────────────── */
  .results-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .results-header {
    display: flex;
    align-items: baseline;
    gap: var(--space-3);
  }

  .results-title {
    font-size: var(--font-size-lg);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text);
    margin: 0;
  }

  .results-meta {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-normal);
    color: var(--color-text-muted);
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
    padding: var(--space-5);
    transition: all 0.2s ease;
  }

  .result-card:hover {
    box-shadow: 0 var(--space-1) var(--space-3) var(--color-shadow-medium);
    transform: translateY(-1px);
    border-color: var(--color-primary-muted);
  }

  .result-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
    flex-wrap: wrap;
  }

  .result-title {
    font-size: var(--font-size-base);
    font-weight: var(--font-weight-semibold);
    color: var(--color-primary);
    margin: 0;
    line-height: var(--line-height-snug);
  }

  .result-badges {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: center;
    flex-shrink: 0;
  }

  .badge {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-1) var(--space-2);
    border-radius: 999px;
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
    line-height: var(--line-height-tight);
  }

  .badge-folder {
    background: var(--color-primary-subtle);
    color: var(--color-primary);
    border: 1px solid var(--color-primary-muted);
  }

  .badge-score {
    background: var(--color-bg-tertiary);
    color: var(--color-text-muted);
    border: 1px solid var(--color-border);
    font-variant-numeric: tabular-nums;
  }

  .badge-source {
    background: var(--color-warning-subtle);
    color: var(--color-warning);
    border: 1px solid var(--color-warning-muted);
  }

  .result-content {
    font-size: var(--font-size-sm);
    line-height: var(--line-height-relaxed);
    color: var(--color-text);
    white-space: pre-wrap;
    margin: 0;
    display: -webkit-box;
    -webkit-line-clamp: 4;
    line-clamp: 4;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .result-actions {
    display: flex;
    gap: var(--space-2);
    margin-top: var(--space-3);
    padding-top: var(--space-2);
    border-top: 1px solid var(--color-border-subtle);
  }

  .btn-xs {
    padding: var(--space-1) var(--space-2);
    font-size: var(--font-size-xs);
  }

  /* ── Paginazione ─────────────────────────────────────────────────────── */
  .pagination {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-4);
    padding-top: var(--space-4);
  }

  .pagination-info {
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
    font-variant-numeric: tabular-nums;
  }

  /* ── Stato vuoto ─────────────────────────────────────────────────────── */
  .empty-state {
    text-align: center;
    padding: var(--space-16) var(--space-6);
    color: var(--color-text-muted);
  }

  .empty-icon {
    font-size: var(--font-size-5xl);
    display: block;
    margin-bottom: var(--space-4);
  }

  .empty-state p {
    font-size: var(--font-size-base);
    margin: 0 0 var(--space-2);
  }

  /* ── Spinner ─────────────────────────────────────────────────────────── */
  .spinner {
    display: inline-block;
    border: 2px solid transparent;
    border-top-color: currentColor;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  .spinner-sm {
    width: 14px;
    height: 14px;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  /* ── Animazioni ──────────────────────────────────────────────────────── */
  .scale-in {
    animation: scaleIn 0.2s ease both;
  }

  @keyframes scaleIn {
    from { opacity: 0; transform: scale(0.97) translateY(4px); }
    to   { opacity: 1; transform: scale(1) translateY(0); }
  }

  /* ── Responsive ──────────────────────────────────────────────────────── */
  @media (max-width: 640px) {
    .search-row {
      flex-direction: column;
    }

    .search-btn {
      width: 100%;
      justify-content: center;
    }

    .options-row {
      flex-direction: column;
      align-items: flex-start;
    }

    .history-panel {
      margin-left: 0;
    }

    .history-dropdown {
      right: auto;
      left: 0;
    }

    .result-header {
      flex-direction: column;
    }
  }
</style>
