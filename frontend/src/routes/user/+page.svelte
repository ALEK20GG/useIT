<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { PUBLIC_BACKEND_URL } from '$env/static/public';

  const BACKEND_URL = PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

  // ---- Types ----
  interface SavedItem {
    id: string;
    title: string;
    content: string;
    source: string;
    notes: string;
    tags: string[];
    folder_path: string;
    saved_at: string;
  }

  // ---- State ----
  let items: SavedItem[] = [];
  let total = 0;
  let loading = false;
  let error = '';
  let searchQuery = '';
  let folderFilter: string | null = null;
  let folders: string[] = [];

  // Save modal
  let showSaveModal = false;
  let saveForm = { title: '', content: '', source: '', notes: '', tags: '', folder_path: '' };
  let saving = false;
  let saveError = '';

  // Edit modal
  let editingItem: SavedItem | null = null;
  let editForm = { title: '', notes: '', tags: '', folder_path: '' };
  let updating = false;
  let updateError = '';

  // Delete
  let deleteConfirmId: string | null = null;
  let deleting = false;

  // Export
  let exportingJson = false;
  let exportingPdf = false;

  // Pagination
  let currentPage = 1;
  const pageSize = 20;

  // ---- Helpers ----
  function formatDate(iso: string): string {
    try {
      return new Date(iso).toLocaleString('it-IT', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit'
      });
    } catch {
      return iso;
    }
  }

  function parseTags(raw: string): string[] {
    return raw.split(',').map(t => t.trim()).filter(Boolean);
  }

  // ---- Data loading ----
  async function loadFolders() {
    try {
      const res = await fetch(`${BACKEND_URL}/user/saved/folders`);
      if (res.ok) {
        const data = await res.json();
        folders = data.folders ?? [];
      }
    } catch {
      // ignore
    }
  }

  async function loadItems(reset = true) {
    if (reset) currentPage = 1;
    loading = true;
    error = '';
    try {
      const offset = (currentPage - 1) * pageSize;
      const params = new URLSearchParams();
      if (searchQuery.trim()) params.set('search', searchQuery.trim());
      if (folderFilter !== null) params.set('folder_path', folderFilter);
      params.set('limit', String(pageSize));
      params.set('offset', String(offset));
      const res = await fetch(`${BACKEND_URL}/user/saved?${params}`);
      if (!res.ok) throw new Error(`Errore HTTP ${res.status}`);
      const data = await res.json();
      items = data.items ?? [];
      total = data.total ?? 0;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Errore nel caricamento.';
    } finally {
      loading = false;
    }
  }

  // ---- Save ----
  function openSaveModal() {
    saveForm = { title: '', content: '', source: '', notes: '', tags: '', folder_path: '' };
    saveError = '';
    showSaveModal = true;
  }

  function closeSaveModal() {
    showSaveModal = false;
    saveError = '';
  }

  async function handleSave() {
    saveError = '';
    if (!saveForm.title.trim()) { saveError = 'Il titolo è obbligatorio.'; return; }
    if (!saveForm.content.trim()) { saveError = 'Il contenuto è obbligatorio.'; return; }
    saving = true;
    try {
      const res = await fetch(`${BACKEND_URL}/user/saved`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: saveForm.title.trim(),
          content: saveForm.content.trim(),
          source: saveForm.source.trim(),
          notes: saveForm.notes.trim(),
          tags: parseTags(saveForm.tags),
          folder_path: saveForm.folder_path.trim(),
        }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail ?? `Errore HTTP ${res.status}`);
      }
      showSaveModal = false;
      await loadFolders();
      await loadItems();
    } catch (e) {
      saveError = e instanceof Error ? e.message : 'Errore nel salvataggio.';
    } finally {
      saving = false;
    }
  }

  // ---- Edit ----
  function startEdit(item: SavedItem) {
    editingItem = item;
    editForm = {
      title: item.title,
      notes: item.notes,
      tags: item.tags.join(', '),
      folder_path: item.folder_path,
    };
    updateError = '';
  }

  function cancelEdit() {
    editingItem = null;
    updateError = '';
  }

  async function handleUpdate() {
    if (!editingItem) return;
    updateError = '';
    updating = true;
    try {
      const res = await fetch(`${BACKEND_URL}/user/saved/${editingItem.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: editForm.title.trim() || undefined,
          notes: editForm.notes.trim(),
          tags: parseTags(editForm.tags),
          folder_path: editForm.folder_path.trim(),
        }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail ?? `Errore HTTP ${res.status}`);
      }
      editingItem = null;
      await loadFolders();
      await loadItems(false);
    } catch (e) {
      updateError = e instanceof Error ? e.message : 'Errore nell’aggiornamento.';
    } finally {
      updating = false;
    }
  }

  // ---- Delete ----
  function requestDelete(id: string) {
    deleteConfirmId = id;
  }

  function cancelDelete() {
    deleteConfirmId = null;
  }

  async function confirmDelete() {
    if (!deleteConfirmId) return;
    deleting = true;
    try {
      const res = await fetch(`${BACKEND_URL}/user/saved/${deleteConfirmId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error(`Errore HTTP ${res.status}`);
      deleteConfirmId = null;
      await loadFolders();
      await loadItems(false);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Errore nell’eliminazione.';
      deleteConfirmId = null;
    } finally {
      deleting = false;
    }
  }

  // ---- Export ----
  async function exportJson() {
    exportingJson = true;
    try {
      const res = await fetch(`${BACKEND_URL}/user/saved/export?format=json`);
      if (!res.ok) throw new Error('Errore esportazione');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'area_personale.json';
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Errore esportazione JSON.';
    } finally {
      exportingJson = false;
    }
  }

  async function exportPdf() {
    exportingPdf = true;
    try {
      const res = await fetch(`${BACKEND_URL}/user/saved/export?format=pdf`);
      if (!res.ok) throw new Error('Errore esportazione');
      const isPdf = res.headers.get('Content-Type')?.includes('pdf');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = isPdf ? 'area_personale.pdf' : 'area_personale.txt';
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Errore esportazione PDF.';
    } finally {
      exportingPdf = false;
    }
  }

  // ---- Pagination ----
  function prevPage() {
    if (currentPage <= 1) return;
    currentPage--;
    loadItems(false);
  }

  function nextPage() {
    if (currentPage * pageSize >= total) return;
    currentPage++;
    loadItems(false);
  }

  function totalPages(): number {
    return Math.ceil(total / pageSize);
  }

  // ---- Group by folder ----
  function groupByFolder(its: SavedItem[]): Map<string, SavedItem[]> {
    const map = new Map<string, SavedItem[]>();
    for (const item of its) {
      const key = item.folder_path || '';
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(item);
    }
    return map;
  }

  // ---- Lifecycle ----
  onMount(async () => {
    const urlParams = $page.url.searchParams;
    if (urlParams.get('save') === 'true') {
      saveForm.title = urlParams.get('title') ?? '';
      saveForm.content = urlParams.get('content') ?? '';
      saveForm.source = urlParams.get('source') ?? '';
      showSaveModal = true;
    }
    await loadFolders();
    await loadItems();
  });

  $: grouped = groupByFolder(items);
  $: folderKeys = Array.from(grouped.keys()).sort((a, b) => {
    if (!a) return 1;
    if (!b) return -1;
    return a.localeCompare(b);
  });
</script>
<svelte:head>
  <title>Area Personale – UseIt</title>
</svelte:head>

<main class="page page-transition">

  <!-- Header -->
  <section class="page-header">
    <div class="header-text">
      <h1>📌 Area Personale</h1>
      <p>Salva, organizza ed esporta i contenuti che ti interessano.</p>
    </div>
  </section>

  <!-- Toolbar -->
  <section class="toolbar card">
    <div class="toolbar-left">
      <label for="search-saved" class="sr-only">Cerca nei salvati</label>
      <input
        id="search-saved"
        class="form-input search-input"
        type="search"
        placeholder="Cerca nei salvati…"
        bind:value={searchQuery}
        on:input={() => loadItems()}
        aria-label="Cerca nei contenuti salvati"
      />
      <label for="folder-filter" class="sr-only">Filtra per cartella</label>
      <select
        id="folder-filter"
        class="form-select"
        bind:value={folderFilter}
        on:change={() => loadItems()}
        aria-label="Filtra per cartella"
      >
        <option value={null}>Tutte le cartelle</option>
        <option value="">Senza cartella</option>
        {#each folders as folder}
          <option value={folder}>{folder}</option>
        {/each}
      </select>
    </div>
    <div class="toolbar-right">
      <button class="btn btn-primary" on:click={openSaveModal} aria-label="Salva nuovo contenuto">
        💾 Nuovo salvataggio
      </button>
      <button
        class="btn btn-secondary"
        on:click={exportJson}
        disabled={exportingJson}
        aria-busy={exportingJson}
        aria-label="Esporta come JSON"
      >
        {#if exportingJson}<span class="spinner spinner-sm" aria-hidden="true"></span>{/if}
        📥 JSON
      </button>
      <button
        class="btn btn-secondary"
        on:click={exportPdf}
        disabled={exportingPdf}
        aria-busy={exportingPdf}
        aria-label="Esporta come PDF o testo"
      >
        {#if exportingPdf}<span class="spinner spinner-sm" aria-hidden="true"></span>{/if}
        📄 PDF/Testo
      </button>
    </div>
  </section>

  <!-- Error -->
  {#if error}
    <div class="status error" role="alert" aria-live="assertive">{error}</div>
  {/if}

  <!-- Loading -->
  {#if loading}
    <div class="loading-state" role="status" aria-live="polite">
      <span class="spinner" aria-hidden="true"></span>
      <span>Caricamento…</span>
    </div>
  {:else if items.length === 0}
    <div class="empty-state" role="status">
      <div class="empty-icon" aria-hidden="true">📋</div>
      <p>Nessun contenuto salvato.</p>
      <p class="hint">Usa il pulsante “Nuovo salvataggio” o il tasto “Salva” nei risultati di ricerca.</p>
    </div>
  {:else}
    <!-- Items grouped by folder -->
    <div class="items-container" aria-label="Contenuti salvati">
      {#each folderKeys as folderKey}
        <section class="folder-section" aria-label="Cartella: {folderKey || 'Senza cartella'}">
          <h2 class="folder-heading">
            <span aria-hidden="true">📁</span>
            {folderKey || 'Senza cartella'}
            <span class="folder-count">({grouped.get(folderKey)?.length ?? 0})</span>
          </h2>
          <div class="folder-items">
            {#each grouped.get(folderKey) ?? [] as item (item.id)}
              <article class="item-card" aria-label="Elemento salvato: {item.title}">
                <header class="item-header">
                  <h3 class="item-title">{item.title}</h3>
                  <div class="item-badges">
                    {#if item.source}
                      <span class="badge badge-source" aria-label="Fonte: {item.source}">{item.source}</span>
                    {/if}
                    <span class="badge badge-date" aria-label="Salvato il {formatDate(item.saved_at)}">{formatDate(item.saved_at)}</span>
                  </div>
                </header>
                {#if item.tags.length > 0}
                  <div class="item-tags" aria-label="Tag">
                    {#each item.tags as tag}
                      <span class="tag-chip">{tag}</span>
                    {/each}
                  </div>
                {/if}
                <p class="content-preview">
                  {item.content.length > 200 ? item.content.slice(0, 200) + '…' : item.content}
                </p>
                {#if item.notes}
                  <p class="item-notes"><em>Note: {item.notes}</em></p>
                {/if}
                <div class="item-actions">
                  <button
                    class="btn btn-secondary btn-sm"
                    on:click={() => startEdit(item)}
                    aria-label="Modifica {item.title}"
                  >✏️ Modifica</button>
                  <button
                    class="btn btn-danger btn-sm"
                    on:click={() => requestDelete(item.id)}
                    aria-label="Elimina {item.title}"
                  >🗑️ Elimina</button>
                </div>
              </article>
            {/each}
          </div>
        </section>
      {/each}
    </div>

    <!-- Pagination -->
    {#if totalPages() > 1}
      <nav class="pagination" aria-label="Paginazione">
        <button class="btn btn-secondary btn-sm" on:click={prevPage} disabled={currentPage <= 1} aria-label="Pagina precedente">← Precedente</button>
        <span class="pagination-info" aria-current="page">Pagina {currentPage} di {totalPages()}</span>
        <button class="btn btn-secondary btn-sm" on:click={nextPage} disabled={currentPage * pageSize >= total} aria-label="Pagina successiva">Successiva →</button>
      </nav>
    {/if}
  {/if}
</main>

{#if showSaveModal}
  <div class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="save-modal-title">
    <div class="modal">
      <h2 id="save-modal-title">Salva contenuto</h2>
      {#if saveError}
        <p class="status error" role="alert">{saveError}</p>
      {/if}
      <div class="form-group">
        <label for="save-title" class="form-label">Titolo *</label>
        <input id="save-title" class="form-input" type="text" bind:value={saveForm.title} required aria-required="true" />
      </div>
      <div class="form-group">
        <label for="save-content" class="form-label">Contenuto *</label>
        <textarea id="save-content" class="form-textarea" bind:value={saveForm.content} rows="5" required aria-required="true"></textarea>
      </div>
      <div class="form-group">
        <label for="save-source" class="form-label">Fonte</label>
        <input id="save-source" class="form-input" type="text" bind:value={saveForm.source} />
      </div>
      <div class="form-group">
        <label for="save-notes" class="form-label">Note personali</label>
        <textarea id="save-notes" class="form-textarea" bind:value={saveForm.notes} rows="3"></textarea>
      </div>
      <div class="form-group">
        <label for="save-tags" class="form-label">Tag (separati da virgola)</label>
        <input id="save-tags" class="form-input" type="text" bind:value={saveForm.tags} placeholder="es. arduino, motore, tutorial" />
      </div>
      <div class="form-group">
        <label for="save-folder" class="form-label">Cartella personale</label>
        <input id="save-folder" class="form-input" type="text" bind:value={saveForm.folder_path} list="folders-datalist" placeholder="es. Preferiti" />
        <datalist id="folders-datalist">
          {#each folders as f}<option value={f}>{f}</option>{/each}
        </datalist>
      </div>
      <div class="modal-actions">
        <button class="btn btn-secondary" on:click={closeSaveModal} aria-label="Annulla salvataggio">Annulla</button>
        <button class="btn btn-primary" on:click={handleSave} disabled={saving} aria-busy={saving} aria-label="Conferma salvataggio">
          {#if saving}<span class="spinner spinner-sm" aria-hidden="true"></span>{/if}
          Salva
        </button>
      </div>
    </div>
  </div>
{/if}

{#if editingItem}
  <div class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="edit-modal-title">
    <div class="modal">
      <h2 id="edit-modal-title">Modifica elemento</h2>
      {#if updateError}
        <p class="status error" role="alert">{updateError}</p>
      {/if}
      <div class="form-group">
        <label for="edit-title" class="form-label">Titolo</label>
        <input id="edit-title" class="form-input" type="text" bind:value={editForm.title} />
      </div>
      <div class="form-group">
        <label for="edit-notes" class="form-label">Note personali</label>
        <textarea id="edit-notes" class="form-textarea" bind:value={editForm.notes} rows="3"></textarea>
      </div>
      <div class="form-group">
        <label for="edit-tags" class="form-label">Tag (separati da virgola)</label>
        <input id="edit-tags" class="form-input" type="text" bind:value={editForm.tags} />
      </div>
      <div class="form-group">
        <label for="edit-folder" class="form-label">Cartella personale</label>
        <input id="edit-folder" class="form-input" type="text" bind:value={editForm.folder_path} list="folders-datalist" />
      </div>
      <div class="modal-actions">
        <button class="btn btn-secondary" on:click={cancelEdit}>Annulla</button>
        <button class="btn btn-primary" on:click={handleUpdate} disabled={updating} aria-busy={updating}>
          {#if updating}<span class="spinner spinner-sm" aria-hidden="true"></span>{/if}
          Salva modifiche
        </button>
      </div>
    </div>
  </div>
{/if}

{#if deleteConfirmId}
  <div class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="delete-modal-title">
    <div class="modal">
      <h2 id="delete-modal-title">Conferma eliminazione</h2>
      <p>Sei sicuro di voler eliminare questo elemento? L’operazione non può essere annullata.</p>
      <div class="modal-actions">
        <button class="btn btn-secondary" on:click={cancelDelete}>Annulla</button>
        <button class="btn btn-danger" on:click={confirmDelete} disabled={deleting} aria-busy={deleting}>
          {#if deleting}<span class="spinner spinner-sm" aria-hidden="true"></span>{/if}
          Elimina
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .page {
    max-width: 1100px;
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

  /* Page header */
  .page-header {
    margin-bottom: var(--space-8);
  }

  .page-header h1 {
    font-size: var(--font-size-3xl);
    font-weight: var(--font-weight-bold);
    line-height: var(--line-height-tight);
    letter-spacing: var(--letter-spacing-tight);
    color: var(--color-text);
    margin-bottom: var(--space-2);
  }

  .page-header p {
    color: var(--color-text-muted);
    font-size: var(--font-size-base);
    line-height: var(--line-height-relaxed);
  }

  /* Card */
  .card {
    background: var(--color-card-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--space-3);
    padding: var(--space-4) var(--space-6);
    box-shadow: 0 1px var(--space-1) var(--color-shadow);
    margin-bottom: var(--space-6);
  }

  /* Toolbar */
  .toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--space-3);
  }

  .toolbar-left {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    flex-wrap: wrap;
    flex: 1;
  }

  .toolbar-right {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .search-input {
    min-width: 200px;
    max-width: 320px;
  }

  /* Form elements */
  .form-input,
  .form-textarea,
  .form-select {
    width: 100%;
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--space-2);
    background: var(--color-input-bg);
    color: var(--color-text);
    font-size: var(--font-size-sm);
    font-family: var(--font-family-sans);
    transition: border-color 0.2s ease;
    box-sizing: border-box;
  }

  .form-input:focus,
  .form-textarea:focus,
  .form-select:focus {
    outline: 2px solid var(--color-primary);
    outline-offset: 2px;
    border-color: var(--color-primary);
  }

  .form-textarea {
    resize: vertical;
    min-height: 80px;
  }

  .form-select {
    cursor: pointer;
    max-width: 200px;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    margin-bottom: var(--space-4);
  }

  .form-label {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    color: var(--color-text);
  }

  /* Buttons */
  .btn {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-4);
    border-radius: var(--space-2);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    font-family: var(--font-family-sans);
    cursor: pointer;
    border: none;
    transition: all 0.2s ease;
    text-decoration: none;
    white-space: nowrap;
  }

  .btn:focus {
    outline: 2px solid var(--color-primary);
    outline-offset: 2px;
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-primary {
    background: var(--color-primary);
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    background: var(--color-primary-hover);
  }

  .btn-secondary {
    background: var(--color-bg-secondary);
    color: var(--color-text);
    border: 1px solid var(--color-border);
  }

  .btn-secondary:hover:not(:disabled) {
    background: var(--color-bg-tertiary);
  }

  .btn-danger {
    background: var(--color-error);
    color: white;
  }

  .btn-danger:hover:not(:disabled) {
    background: var(--color-error-hover);
  }

  .btn-sm {
    padding: var(--space-1) var(--space-3);
    font-size: var(--font-size-xs);
  }

  /* Status messages */
  .status {
    padding: var(--space-3);
    border-radius: var(--space-2);
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-4);
  }

  .status.error {
    background: var(--color-error-subtle);
    color: var(--color-error-text);
    border: 1px solid var(--color-error-border);
  }

  /* Loading / empty states */
  .loading-state,
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-12) var(--space-6);
    color: var(--color-text-muted);
    text-align: center;
  }

  .empty-icon {
    font-size: var(--font-size-5xl);
    line-height: var(--line-height-tight);
  }

  .hint {
    font-size: var(--font-size-sm);
    color: var(--color-text-subtle);
  }

  /* Items container */
  .items-container {
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
  }

  /* Folder section */
  .folder-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .folder-heading {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--font-size-lg);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text);
    padding-bottom: var(--space-2);
    border-bottom: 2px solid var(--color-border);
    margin-bottom: var(--space-2);
  }

  .folder-count {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-normal);
    color: var(--color-text-muted);
  }

  .folder-items {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  /* Item card */
  .item-card {
    background: var(--color-card-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--space-3);
    padding: var(--space-5);
    transition: all 0.2s ease;
  }

  .item-card:hover {
    box-shadow: 0 var(--space-1) var(--space-3) var(--color-shadow-medium);
    border-color: var(--color-primary-muted);
  }

  .item-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
    flex-wrap: wrap;
  }

  .item-title {
    font-size: var(--font-size-base);
    font-weight: var(--font-weight-semibold);
    color: var(--color-primary);
    margin: 0;
    line-height: var(--line-height-snug);
  }

  .item-badges {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: center;
    flex-shrink: 0;
  }

  /* Badges */
  .badge {
    display: inline-flex;
    align-items: center;
    padding: var(--space-1) var(--space-2);
    border-radius: 999px;
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
  }

  .badge-source {
    background: var(--color-primary-subtle);
    color: var(--color-primary);
  }

  .badge-date {
    background: var(--color-bg-secondary);
    color: var(--color-text-muted);
    border: 1px solid var(--color-border);
  }

  /* Tags */
  .item-tags {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    margin-bottom: var(--space-2);
  }

  .tag-chip {
    display: inline-flex;
    align-items: center;
    padding: var(--space-1) var(--space-2);
    border-radius: 999px;
    font-size: var(--font-size-xs);
    background: var(--color-bg-tertiary);
    color: var(--color-text-muted);
    border: 1px solid var(--color-border-subtle);
  }

  /* Content preview */
  .content-preview {
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
    line-height: var(--line-height-relaxed);
    margin-bottom: var(--space-2);
    white-space: pre-wrap;
    word-break: break-word;
  }

  .item-notes {
    font-size: var(--font-size-xs);
    color: var(--color-text-subtle);
    margin-bottom: var(--space-2);
  }

  /* Item actions */
  .item-actions {
    display: flex;
    gap: var(--space-2);
    margin-top: var(--space-3);
    padding-top: var(--space-3);
    border-top: 1px solid var(--color-border-subtle);
  }

  /* Pagination */
  .pagination {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-4);
    margin-top: var(--space-6);
  }

  .pagination-info {
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
  }

  /* Spinner */
  .spinner {
    display: inline-block;
    width: 1.25rem;
    height: 1.25rem;
    border: 2px solid currentColor;
    border-top-color: transparent;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }

  .spinner-sm {
    width: 1rem;
    height: 1rem;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  /* Modal */
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 200;
    padding: var(--space-4);
  }

  .modal {
    background: var(--color-card-bg);
    border-radius: var(--space-3);
    padding: var(--space-6);
    max-width: 560px;
    width: 100%;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 var(--space-4) var(--space-8) var(--color-shadow-strong);
  }

  .modal h2 {
    font-size: var(--font-size-xl);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text);
    margin-bottom: var(--space-4);
  }

  .modal p {
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
    line-height: var(--line-height-relaxed);
    margin-bottom: var(--space-4);
  }

  .modal-actions {
    display: flex;
    gap: var(--space-3);
    justify-content: flex-end;
    margin-top: var(--space-4);
  }

  /* Responsive */
  @media (max-width: 640px) {
    .page {
      padding: var(--space-4) var(--space-4) var(--space-12);
    }

    .toolbar {
      flex-direction: column;
      align-items: stretch;
    }

    .toolbar-left,
    .toolbar-right {
      width: 100%;
    }

    .search-input {
      max-width: 100%;
    }

    .form-select {
      max-width: 100%;
    }

    .item-header {
      flex-direction: column;
    }
  }
</style>
