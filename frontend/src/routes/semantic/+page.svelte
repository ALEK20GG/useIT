<script lang="ts">
  import { onMount } from 'svelte';

  const BACKEND_URL = 'http://127.0.0.1:8000';

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

<main class="page">
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

      <button class="primary" on:click|preventDefault={ingestNote} disabled={ingestLoading}>
        {ingestLoading ? 'Ingesting…' : 'Save note to Qdrant'}
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

      <button class="primary" on:click|preventDefault={runSearch} disabled={searchLoading}>
        {searchLoading ? 'Searching…' : 'Search'}
      </button>

      {#if searchError}
        <p class="status error">{searchError}</p>
      {/if}

      {#if results.length}
        <div class="results">
          {#each results as hit (hit.id)}
            <article class="result">
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
    padding: 2rem 1.5rem 4rem;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  }

  .hero {
    margin-bottom: 2.5rem;
  }

  .hero-text h1 {
    font-size: 2rem;
    margin-bottom: 0.5rem;
  }

  .hero-text p {
    color: #6b7280;
    max-width: 40rem;
  }

  .grid {
    display: grid;
    gap: 1.75rem;
  }

  @media (min-width: 900px) {
    .grid {
      grid-template-columns: 1fr 1fr;
      align-items: flex-start;
    }
  }

  .card {
    background: #ffffff;
    border-radius: 0.9rem;
    padding: 1.5rem 1.75rem;
    box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
    border: 1px solid #e5e7eb;
  }

  .card h2 {
    margin-bottom: 0.35rem;
    font-size: 1.25rem;
  }

  .muted {
    font-size: 0.9rem;
    color: #6b7280;
    margin-bottom: 1.25rem;
  }

  label {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    margin-bottom: 0.9rem;
    font-size: 0.9rem;
  }

  label span {
    color: #374151;
    font-weight: 500;
  }

  input,
  select,
  textarea {
    border-radius: 0.6rem;
    border: 1px solid #d1d5db;
    padding: 0.6rem 0.7rem;
    font-size: 0.95rem;
    font-family: inherit;
    transition: border-color 0.15s, box-shadow 0.15s, background-color 0.15s;
    background-color: #f9fafb;
  }

  input:focus,
  select:focus,
  textarea:focus {
    outline: none;
    border-color: #4f46e5;
    box-shadow: 0 0 0 1px rgba(79, 70, 229, 0.4);
    background-color: #ffffff;
  }

  textarea {
    resize: vertical;
    min-height: 140px;
  }

  button.primary {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    margin-top: 0.25rem;
    padding: 0.55rem 1.3rem;
    border-radius: 999px;
    border: none;
    font-size: 0.95rem;
    font-weight: 600;
    background: linear-gradient(135deg, #4f46e5, #6366f1);
    color: white;
    cursor: pointer;
    box-shadow: 0 12px 25px rgba(55, 48, 163, 0.45);
    transition: transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease;
  }

  button.primary:hover:enabled {
    transform: translateY(-1px);
    box-shadow: 0 16px 30px rgba(55, 48, 163, 0.55);
    filter: brightness(1.05);
  }

  button.primary:disabled {
    opacity: 0.7;
    cursor: default;
    box-shadow: none;
  }

  .status {
    margin-top: 0.75rem;
    font-size: 0.85rem;
  }

  .status.success {
    color: #166534;
  }

  .status.error {
    color: #b91c1c;
  }

  .results {
    margin-top: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
    max-height: 26rem;
    overflow-y: auto;
  }

  .result {
    padding: 0.85rem 0.75rem;
    border-radius: 0.7rem;
    border: 1px solid #e5e7eb;
    background-color: #f9fafb;
  }

  .result header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.5rem;
    margin-bottom: 0.35rem;
  }

  .result h3 {
    font-size: 1rem;
    margin: 0;
  }

  .score {
    font-size: 0.8rem;
    color: #6b7280;
  }

  .meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-bottom: 0.3rem;
  }

  .pill {
    padding: 0.1rem 0.6rem;
    border-radius: 999px;
    background-color: #e0e7ff;
    color: #4338ca;
    font-size: 0.75rem;
    font-weight: 500;
  }

  .content {
    font-size: 0.9rem;
    color: #374151;
    white-space: pre-wrap;
  }
</style>


