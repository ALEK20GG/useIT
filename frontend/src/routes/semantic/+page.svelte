<script lang="ts">
  import { onMount } from 'svelte';
  import { PUBLIC_BACKEND_URL } from '$env/static/public';

  const BACKEND_URL = PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

  type Note = {
    title: string;
    content: string;
    type?: string | null;
    tags: string[];
  };

  type SearchHit = {
    id: string | number;
    score: number;
    title: string;
    content: string;
    type?: string | null;
    tags: string[];
  };

  let collectionName = 'notes';

  // Ingest form state
  let noteTitle = '';
  let noteContent = '';
  let noteType = 'school-note';
  let noteTags = '';
  let ingestLoading = false;
  let ingestMessage = '';
  let ingestError = '';

  // Search form state
  let query = '';
  let searchLimit = 5;
  let searchLoading = false;
  let searchError = '';
  let results: SearchHit[] = [];

  async function ingestNote() {
    ingestError = '';
    ingestMessage = '';

    if (!noteTitle.trim() || !noteContent.trim()) {
      ingestError = 'Title and content are required.';
      return;
    }

    ingestLoading = true;
    try {
      const tags = noteTags
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean);

      const body = {
        collection_name: collectionName,
        notes: [
          {
            title: noteTitle,
            content: noteContent,
            type: noteType || null,
            tags
          } satisfies Note
        ]
      };

      const res = await fetch(`${BACKEND_URL}/semantic/ingest`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(body)
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? `Ingest failed with status ${res.status}`);
      }

      const data = await res.json();
      ingestMessage = data.message ?? 'Note ingested successfully.';

      // Clear fields a bit to make repeated entry easier
      noteTitle = '';
      noteContent = '';
      // keep type and tags
    } catch (err) {
      ingestError = err instanceof Error ? err.message : 'Unknown error during ingest.';
    } finally {
      ingestLoading = false;
    }
  }

  async function runSearch() {
    searchError = '';
    results = [];

    if (!query.trim()) {
      searchError = 'Please enter a query.';
      return;
    }

    searchLoading = true;
    try {
      const body = {
        collection_name: collectionName,
        query,
        limit: searchLimit
      };

      const res = await fetch(`${BACKEND_URL}/semantic/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(body)
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? `Search failed with status ${res.status}`);
      }

      const data: SearchHit[] = await res.json();
      results = data;
    } catch (err) {
      searchError = err instanceof Error ? err.message : 'Unknown error during search.';
    } finally {
      searchLoading = false;
    }
  }

  onMount(() => {
    // placeholder: could be used later to auto-load example notes
  });
</script>

<svelte:head>
  <title>Semantic search – UseIt</title>
</svelte:head>

<main class="page page-transition">
  <section class="hero">
    <div class="hero-text">
      <h1>Semantic search for your components &amp; school notes</h1>
      <p>
        Store short notes about UI components or school topics, then find them later with natural
        language search powered by Qdrant.
      </p>
    </div>
  </section>

  <section class="grid">
    <div class="card">
      <h2>Add a note</h2>
      <p class="muted">
        Describe a component or a topic (e.g. “React button component props”, “Derivatives rules
        summary”).
      </p>

      <label>
        <span>Collection</span>
        <input bind:value={collectionName} placeholder="notes" />
      </label>

      <label>
        <span>Title</span>
        <input
          bind:value={noteTitle}
          placeholder="Primary Button component / Limits chapter overview"
        />
      </label>

      <label>
        <span>Type</span>
        <select bind:value={noteType}>
          <option value="component">Component</option>
          <option value="school-note">School note</option>
          <option value="doc">Doc</option>
        </select>
      </label>

      <label>
        <span>Tags (comma separated)</span>
        <input bind:value={noteTags} placeholder="ui, button, math, algebra" />
      </label>

      <label>
        <span>Content</span>
        <textarea
          bind:value={noteContent}
          rows="6"
          placeholder="Write a short description; you can include code or formulas."
        ></textarea>
      </label>

      <button class="btn btn-primary" on:click|preventDefault={ingestNote} disabled={ingestLoading}>
        {#if ingestLoading}
          <span class="spinner spinner-sm"></span>
          <span>Ingesting…</span>
        {:else}
          Save note to Qdrant
        {/if}
      </button>

      {#if ingestMessage}
        <p class="status success">{ingestMessage}</p>
      {/if}
      {#if ingestError}
        <p class="status error">{ingestError}</p>
      {/if}
    </div>

    <div class="card">
      <h2>Search notes</h2>
      <p class="muted">
        Ask questions like “How do I style the primary button?” or “Notes about integrals for
        tomorrow’s test”.
      </p>

      <label>
        <span>Collection</span>
        <input bind:value={collectionName} placeholder="notes" />
      </label>

      <label>
        <span>Query</span>
        <input bind:value={query} placeholder="Find docs about derivatives and tangent lines" />
      </label>

      <label>
        <span>Max results</span>
        <input
          type="number"
          min="1"
          max="20"
          bind:value={searchLimit}
        />
      </label>

      <button class="btn btn-primary" on:click|preventDefault={runSearch} disabled={searchLoading}>
        {#if searchLoading}
          <span class="spinner spinner-sm"></span>
          <span>Searching…</span>
        {:else}
          Search
        {/if}
      </button>

      {#if searchError}
        <p class="status error">{searchError}</p>
      {/if}

      {#if results.length}
        <div class="results fade-in">
          {#each results as hit, index (hit.id)}
            <article class="result scale-in" style="animation-delay: {index * 0.05}s;">
              <header>
                <h3>{hit.title}</h3>
                <span class="score">Score: {hit.score.toFixed(3)}</span>
              </header>
              {#if hit.type || (hit.tags && hit.tags.length)}
                <div class="meta">
                  {#if hit.type}
                    <span class="pill">{hit.type}</span>
                  {/if}
                  {#each hit.tags as tag}
                    <span class="pill">{tag}</span>
                  {/each}
                </div>
              {/if}
              <p class="content">
                {hit.content}
              </p>
            </article>
          {/each}
        </div>
      {/if}
    </div>
  </section>
</main>

<style>
  .page {
    max-width: 1100px;
    margin: 0 auto;
    padding: var(--space-8) var(--space-6) var(--space-16);
    font-family: var(--font-family-sans);
  }

  .hero {
    margin-bottom: var(--space-12);
  }

  .hero-text h1 {
    font-size: var(--font-size-3xl);
    font-weight: var(--font-weight-bold);
    line-height: var(--line-height-tight);
    letter-spacing: var(--letter-spacing-tight);
    margin-bottom: var(--space-4);
    color: var(--color-text);
  }

  .hero-text p {
    color: var(--color-text-muted);
    max-width: 40rem;
    font-size: var(--font-size-base);
    line-height: var(--line-height-relaxed);
  }

  .grid {
    display: grid;
    gap: var(--space-6);
  }

  @media (min-width: 900px) {
    .grid {
      grid-template-columns: 1fr 1fr;
      align-items: flex-start;
    }
  }

  .card {
    background: var(--color-card-bg);
    border-radius: var(--space-3);
    padding: var(--space-6);
    box-shadow: 0 1px var(--space-1) var(--color-shadow);
    border: 1px solid var(--color-border);
    transition: all 0.2s ease;
  }

  .card:hover {
    box-shadow: 0 var(--space-2) var(--space-4) var(--color-shadow-medium);
    transform: translateY(-2px);
  }

  .card:focus-within {
    outline: 2px solid var(--color-primary);
    outline-offset: 2px;
  }

  .card h2 {
    margin-bottom: var(--space-3);
    font-size: var(--font-size-xl);
    font-weight: var(--font-weight-semibold);
    line-height: var(--line-height-snug);
    color: var(--color-text);
  }

  .muted {
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
    margin-bottom: var(--space-5);
    line-height: var(--line-height-relaxed);
  }

  label {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    margin-bottom: var(--space-4);
    font-size: var(--font-size-sm);
  }

  label span {
    color: var(--color-text);
    font-weight: var(--font-weight-medium);
    line-height: var(--line-height-normal);
  }

  input,
  select,
  textarea {
    border-radius: var(--space-2);
    border: 2px solid var(--color-border);
    padding: var(--space-3);
    font-size: var(--font-size-base);
    line-height: var(--line-height-normal);
    font-family: inherit;
    transition: all 0.2s ease;
    background-color: var(--color-input-bg);
    color: var(--color-text);
    min-height: 44px;
  }

  input:hover:not(:focus):not(:disabled),
  select:hover:not(:focus):not(:disabled),
  textarea:hover:not(:focus):not(:disabled) {
    border-color: var(--color-primary-muted);
    background-color: var(--color-bg);
  }

  input:focus,
  select:focus,
  textarea:focus {
    outline: none;
    border-color: var(--color-primary);
    box-shadow: 0 0 0 3px var(--color-primary-subtle);
    background-color: var(--color-bg);
  }

  input:disabled,
  select:disabled,
  textarea:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    background-color: var(--color-bg-tertiary);
  }

  select {
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%2364748b' d='M6 9L1 4h10z'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right var(--space-3) center;
    padding-right: var(--space-8);
    cursor: pointer;
  }

  textarea {
    resize: vertical;
    min-height: 140px;
  }

  .status {
    margin-top: var(--space-3);
    font-size: var(--font-size-sm);
    line-height: var(--line-height-normal);
    padding: var(--space-3);
    border-radius: var(--space-2);
  }

  .status.success {
    background-color: var(--color-success-subtle);
    color: var(--color-success-text);
    border: 1px solid var(--color-success-border);
  }

  .status.error {
    background-color: var(--color-error-subtle);
    color: var(--color-error-text);
    border: 1px solid var(--color-error-border);
  }

  .results {
    margin-top: var(--space-5);
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    max-height: 26rem;
    overflow-y: auto;
  }

  .result {
    padding: var(--space-4);
    border-radius: var(--space-2);
    border: 1px solid var(--color-border);
    background-color: var(--color-bg-secondary);
    transition: all 0.2s ease;
  }

  .result:hover {
    box-shadow: 0 var(--space-1) var(--space-3) var(--color-shadow-medium);
    transform: translateY(-1px);
    border-color: var(--color-primary-muted);
  }

  .result:focus-within {
    outline: 2px solid var(--color-primary);
    outline-offset: 2px;
  }

  .result header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
  }

  .result h3 {
    font-size: var(--font-size-base);
    font-weight: var(--font-weight-semibold);
    line-height: var(--line-height-snug);
    margin: 0;
    color: var(--color-primary);
  }

  .score {
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
    line-height: var(--line-height-tight);
    color: var(--color-text-muted);
  }

  .meta {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
  }

  .pill {
    padding: var(--space-1) var(--space-3);
    border-radius: 999px;
    background-color: var(--color-primary-subtle);
    color: var(--color-primary);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
    line-height: var(--line-height-tight);
    transition: all 0.2s ease;
    cursor: default;
  }

  .pill:hover {
    background-color: var(--color-primary-muted);
    transform: scale(1.05);
  }

  .content {
    font-size: var(--font-size-sm);
    line-height: var(--line-height-relaxed);
    color: var(--color-text);
    white-space: pre-wrap;
    margin: 0;
  }
</style>


