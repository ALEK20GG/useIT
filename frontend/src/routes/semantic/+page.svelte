<script lang="ts">
  import { onMount } from 'svelte';
  import PdfPreview from '$lib/PdfPreview.svelte';

  const BACKEND_URL = 'http://127.0.0.1:8000';

  type SearchHit = {
    id: string | number;
    score: number;
    title: string;
    content?: string;
    type?: string | null;
    tags?: string[];
    pdf_path?: string;
  };

  let query = '';
  let searchLoading = false;
  let searchError = '';
  let results: SearchHit[] = [];
  let selectedPdf: SearchHit | null = null;

  async function runSearch() {
    searchError = '';
    results = [];
    selectedPdf = null;
    if (!query.trim()) {
      searchError = 'Inserisci una query di ricerca.';
      return;
    }
    searchLoading = true;
    try {
      const res = await fetch(`${BACKEND_URL}/semantic/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ collection_name: 'notes', query, limit: 20 })
      });
      if (!res.ok) throw new Error('Ricerca fallita');
      const data = await res.json();
      results = data;
      if (results.length) selectedPdf = results[0];
    } catch (err) {
      searchError = err instanceof Error ? err.message : String(err);
    } finally {
      searchLoading = false;
    }
  }

  function handleKeyPress(e: KeyboardEvent) {
    if (e.key === 'Enter' && !searchLoading) runSearch();
  }

  function selectPdf(hit: SearchHit) {
    selectedPdf = hit;
  }

  onMount(() => {});
</script>

<svelte:head>
  <title>Ricerca semantica – UseIt</title>
</svelte:head>

<main class="search-page">
  <header class="search-header">
    <div class="container">
      <h1>Cerca nella documentazione</h1>
      <p class="hint">Usa linguaggio naturale per trovare PDF e documenti rilevanti.</p>

      <div class="search-row">
        <input
          class="search-input"
          type="text"
          placeholder="Es: specifiche prodotto"
          bind:value={query}
          on:keypress={handleKeyPress}
        />
        <button class="btn primary" on:click={runSearch} disabled={searchLoading}>
          {searchLoading ? 'Cercando…' : 'Cerca'}
        </button>
      </div>
      {#if searchError}<p class="error">{searchError}</p>{/if}
    </div>
  </header>

  {#if results.length > 0}
    <section class="results">
      <aside class="results-sidebar">
        <div class="sidebar-inner">
          <div class="sidebar-title">
            Risultati <span class="count">{results.length}</span>
          </div>
          <div class="list">
            {#each results as r (r.id)}
              <button
                class="item {selectedPdf?.id === r.id ? 'active' : ''}"
                on:click={() => selectPdf(r)}
              >
                <div class="title">{r.title}</div>
                <div class="meta">{Math.round((r.score || 0) * 100)}%</div>
              </button>
            {/each}
          </div>
        </div>
      </aside>

      <div class="preview">
        {#if selectedPdf}
          <div class="preview-head">
            <h2>{selectedPdf.title}</h2>
            {#if selectedPdf.pdf_path}
              <a class="external" href={selectedPdf.pdf_path} target="_blank" rel="noopener noreferrer">
                Apri ↗
              </a>
            {/if}
          </div>
          <div class="preview-body">
            <PdfPreview src={selectedPdf.pdf_path ?? null} />
          </div>
        {:else}
          <div class="empty">Seleziona un risultato per vedere l'anteprima</div>
        {/if}
      </div>
    </section>
  {:else}
    <section class="empty-state">
      <div class="container">
        <p>Nessun risultato — esegui una ricerca.</p>
      </div>
    </section>
  {/if}
</main>

<style>
  .search-page {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    background: #f9fafb;
  }

  .container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 1rem;
  }

  .search-header {
    background: white;
    border-bottom: 1px solid #e5e7eb;
  }

  h1 {
    font-size: 1.25rem;
    margin: 0 0 0.25rem 0;
  }

  .hint {
    color: #6b7280;
    margin: 0 0 0.5rem 0;
  }

  .search-row {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }

  .search-input {
    flex: 1;
    padding: 0.6rem 0.9rem;
    border-radius: 8px;
    border: 1px solid #e5e7eb;
  }

  .btn {
    padding: 0.56rem 0.9rem;
    border-radius: 8px;
    cursor: pointer;
    border: none;
  }

  .btn.primary {
    background: linear-gradient(135deg, #4f46e5, #6366f1);
    color: white;
  }

  .btn.ghost {
    background: transparent;
    border: 1px solid #d1d5db;
  }

  .error {
    color: #b91c1c;
    margin-top: 0.5rem;
  }

  .results {
    flex: 1;
    display: grid;
    grid-template-columns: minmax(240px, 320px) 1fr;
    gap: 1rem;
    align-items: start;
    min-height: 0;
  }

  .results-sidebar {
    background: white;
    border-right: 1px solid #e5e7eb;
    overflow: auto;
    min-height: 0;
  }

  .sidebar-inner {
    padding: 0.75rem;
  }

  .sidebar-title {
    font-weight: 700;
    margin-bottom: 0.5rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .count {
    font-size: 0.85rem;
    color: #6b7280;
    font-weight: 600;
  }

  .list {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }

  .item {
    text-align: left;
    padding: 0.6rem;
    border-radius: 8px;
    border: 1px solid #e5e7eb;
    background: white;
    display: flex;
    justify-content: space-between;
    align-items: center;
    cursor: pointer;
  }

  .item.active {
    background: #eef2ff;
    border-color: #4f46e5;
  }

  .title {
    font-size: 0.95rem;
    font-weight: 600;
  }

  .meta {
    font-size: 0.75rem;
    color: #4f46e5;
  }

  .preview {
    background: white;
    padding: 0.6rem;
    min-height: 0;
  }

  .preview-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    border-bottom: 1px solid #e5e7eb;
    padding-bottom: 0.5rem;
    margin-bottom: 0.5rem;
  }

  .preview-head h2 {
    margin: 0;
    font-size: 1rem;
  }

  .external {
    font-size: 0.75rem;
    color: #4f46e5;
    text-decoration: none;
    white-space: nowrap;
  }

  .preview-body {
    min-height: 200px;
  }

  .empty {
    padding: 2rem;
    color: #6b7280;
    text-align: center;
  }

  .empty-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 3rem;
  }

  .empty-state p {
    color: #6b7280;
  }

  @media (max-width: 768px) {
    .results {
      grid-template-columns: 1fr;
      grid-auto-rows: auto;
    }

    .results-sidebar {
      border-right: none;
      border-bottom: 1px solid #e5e7eb;
      max-height: 260px;
    }

    .search-row {
      flex-direction: column;
      align-items: stretch;
    }
  }
</style>
