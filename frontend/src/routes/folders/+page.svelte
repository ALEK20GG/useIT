<script lang="ts">
  import { onMount } from 'svelte';
  import { PUBLIC_BACKEND_URL } from '$env/static/public';

  const BACKEND_URL = PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

  // ---- Types ----
  interface Folder {
    id: string;
    name: string;
    description: string | null;
    parent_id: string | null;
    path: string;
    content_types: string[];
    qdrant_collection: string;
    metadata: Record<string, unknown>;
    created_at: string;
    updated_at: string;
    content_count: number;
  }

  interface FolderTreeNode {
    folder: Folder;
    children: FolderTreeNode[];
    content_summary: {
      total_documents: number;
      last_updated: string | null;
    };
  }

  // ---- State ----
  let folders: Folder[] = [];
  let treeNodes: FolderTreeNode[] = [];
  let loading = false;
  let treeLoading = false;
  let error = '';

  // Selected folder for detail view
  let selectedFolder: Folder | null = null;

  // Create form
  let showCreateForm = false;
  let createName = '';
  let createDescription = '';
  let createParentId = '';
  let createContentTypes: string[] = ['pdf_documents'];
  let creating = false;
  let createError = '';
  let createSuccess = '';

  // Edit form
  let editingFolder: Folder | null = null;
  let editName = '';
  let editDescription = '';
  let editError = '';
  let editSuccess = '';
  let saving = false;

  // Delete
  let folderToDelete: Folder | null = null;
  let deleteError = '';
  let deleting = false;

  // Expanded tree nodes
  let expandedNodes: Set<string> = new Set();

  const CONTENT_TYPE_LABELS: Record<string, string> = {
    device_documentation: 'Documentazione dispositivi',
    pdf_documents: 'Documenti PDF',
    notes: 'Appunti',
    school_materials: 'Materiale scolastico',
    user_content: 'Contenuto utente',
  };

  const ALL_CONTENT_TYPES = Object.keys(CONTENT_TYPE_LABELS);

  // ---- Helpers ----
  function formatDate(iso: string): string {
    try {
      return new Date(iso).toLocaleString('it-IT', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit',
      });
    } catch {
      return iso;
    }
  }

  function contentTypeLabel(ct: string): string {
    return CONTENT_TYPE_LABELS[ct] ?? ct;
  }

  function getDepth(folder: Folder): number {
    return (folder.path.match(/\//g) || []).length - 1;
  }

  function toggleExpand(id: string) {
    const next = new Set(expandedNodes);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    expandedNodes = next;
  }

  // ---- Data loading ----
  async function loadFolders() {
    loading = true;
    error = '';
    try {
      const res = await fetch(`${BACKEND_URL}/folders`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      folders = data.folders ?? [];
    } catch (e) {
      error = e instanceof Error ? e.message : 'Errore nel caricamento delle cartelle.';
    } finally {
      loading = false;
    }
  }

  async function loadTree() {
    treeLoading = true;
    try {
      const res = await fetch(`${BACKEND_URL}/folders/hierarchy`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      treeNodes = await res.json();
      // Auto-expand root nodes
      for (const node of treeNodes) {
        expandedNodes = new Set([...expandedNodes, node.folder.id]);
      }
    } catch (e) {
      console.error('Failed to load folder tree:', e);
    } finally {
      treeLoading = false;
    }
  }

  onMount(async () => {
    await Promise.all([loadFolders(), loadTree()]);
  });

  // ---- Create folder ----
  function openCreateForm() {
    showCreateForm = true;
    createName = '';
    createDescription = '';
    createParentId = '';
    createContentTypes = ['pdf_documents'];
    createError = '';
    createSuccess = '';
  }

  function closeCreateForm() {
    showCreateForm = false;
  }

  function toggleContentType(ct: string) {
    if (createContentTypes.includes(ct)) {
      createContentTypes = createContentTypes.filter(c => c !== ct);
    } else {
      createContentTypes = [...createContentTypes, ct];
    }
  }

  async function handleCreate() {
    createError = '';
    createSuccess = '';
    if (!createName.trim()) {
      createError = 'Il nome della cartella è obbligatorio.';
      return;
    }
    if (createContentTypes.length === 0) {
      createError = 'Seleziona almeno un tipo di contenuto.';
      return;
    }
    creating = true;
    try {
      const body: Record<string, unknown> = {
        name: createName.trim(),
        description: createDescription.trim() || null,
        content_types: createContentTypes,
        metadata: {},
      };
      if (createParentId) body.parent_id = createParentId;

      const res = await fetch(`${BACKEND_URL}/folders`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? `Errore HTTP ${res.status}`);
      }
      createSuccess = `Cartella "${createName.trim()}" creata con successo.`;
      createName = '';
      createDescription = '';
      createParentId = '';
      createContentTypes = ['pdf_documents'];
      await Promise.all([loadFolders(), loadTree()]);
    } catch (e) {
      createError = e instanceof Error ? e.message : 'Errore durante la creazione.';
    } finally {
      creating = false;
    }
  }

  // ---- Edit folder ----
  function startEdit(folder: Folder) {
    editingFolder = folder;
    editName = folder.name;
    editDescription = folder.description ?? '';
    editError = '';
    editSuccess = '';
  }

  function cancelEdit() {
    editingFolder = null;
  }

  async function handleSave() {
    if (!editingFolder) return;
    editError = '';
    editSuccess = '';
    if (!editName.trim()) {
      editError = 'Il nome è obbligatorio.';
      return;
    }
    saving = true;
    try {
      const res = await fetch(`${BACKEND_URL}/folders/${editingFolder.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: editName.trim(),
          description: editDescription.trim() || null,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? `Errore HTTP ${res.status}`);
      }
      editSuccess = 'Cartella aggiornata.';
      editingFolder = null;
      if (selectedFolder) {
        const updated: Folder = await res.json();
        selectedFolder = updated;
      }
      await Promise.all([loadFolders(), loadTree()]);
    } catch (e) {
      editError = e instanceof Error ? e.message : 'Errore durante il salvataggio.';
    } finally {
      saving = false;
    }
  }

  // ---- Delete folder ----
  function requestDelete(folder: Folder) {
    folderToDelete = folder;
    deleteError = '';
  }

  function cancelDelete() {
    folderToDelete = null;
  }

  async function confirmDelete() {
    if (!folderToDelete) return;
    deleteError = '';
    deleting = true;
    try {
      const res = await fetch(`${BACKEND_URL}/folders/${folderToDelete.id}`, {
        method: 'DELETE',
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? `Errore HTTP ${res.status}`);
      }
      if (selectedFolder?.id === folderToDelete.id) selectedFolder = null;
      folderToDelete = null;
      await Promise.all([loadFolders(), loadTree()]);
    } catch (e) {
      deleteError = e instanceof Error ? e.message : 'Errore durante l\'eliminazione.';
    } finally {
      deleting = false;
    }
  }

  // ---- Select folder ----
  function selectFolder(folder: Folder) {
    selectedFolder = selectedFolder?.id === folder.id ? null : folder;
    editingFolder = null;
  }
</script>

<svelte:head>
  <title>Gestione Cartelle – UseIt</title>
</svelte:head>

<main class="page page-transition">
  <!-- Page header -->
  <section class="page-header">
    <div class="header-text">
      <h1>Gestione Cartelle</h1>
      <p>Organizza i contenuti in cartelle gerarchiche. Ogni cartella corrisponde a una collezione Qdrant dedicata.</p>
    </div>
    <button class="btn btn-primary" on:click={openCreateForm} aria-label="Crea nuova cartella">
      + Nuova cartella
    </button>
  </section>

  {#if error}
    <p class="status error" role="alert">{error}</p>
  {/if}

  <div class="layout">
    <!-- Left: folder tree -->
    <aside class="tree-panel" aria-label="Albero delle cartelle">
      <div class="panel-header">
        <h2>🌳 Struttura</h2>
        {#if treeLoading}
          <span class="spinner spinner-sm" aria-label="Caricamento albero"></span>
        {/if}
      </div>

      {#if treeNodes.length === 0 && !treeLoading}
        <p class="empty-hint">Nessuna cartella trovata.</p>
      {:else}
        <nav aria-label="Navigazione cartelle">
          <ul class="tree-list" role="tree">
            {#each treeNodes as node (node.folder.id)}
              <li role="treeitem" aria-expanded={expandedNodes.has(node.folder.id)} aria-selected={selectedFolder?.id === node.folder.id}>
                <div
                  class="tree-item"
                  class:tree-item-selected={selectedFolder?.id === node.folder.id}
                  role="button"
                  tabindex="0"
                  aria-label={`Cartella ${node.folder.name}, ${node.folder.content_count} elementi`}
                  on:click={() => selectFolder(node.folder)}
                  on:keydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectFolder(node.folder); } }}
                >
                  {#if node.children.length > 0}
                    <button
                      class="expand-btn"
                      on:click|stopPropagation={() => toggleExpand(node.folder.id)}
                      aria-label={expandedNodes.has(node.folder.id) ? 'Comprimi' : 'Espandi'}
                    >
                      {expandedNodes.has(node.folder.id) ? '▾' : '▸'}
                    </button>
                  {:else}
                    <span class="expand-placeholder"></span>
                  {/if}
                  <span class="folder-icon">📁</span>
                  <span class="folder-name">{node.folder.name}</span>
                  <span class="folder-count" aria-label="{node.folder.content_count} elementi">{node.folder.content_count}</span>
                </div>

                {#if node.children.length > 0 && expandedNodes.has(node.folder.id)}
                  <ul class="tree-list tree-list-nested" role="group">
                    {#each node.children as child (child.folder.id)}
                      <li role="treeitem" aria-expanded={expandedNodes.has(child.folder.id)} aria-selected={selectedFolder?.id === child.folder.id}>
                        <div
                          class="tree-item tree-item-child"
                          class:tree-item-selected={selectedFolder?.id === child.folder.id}
                          role="button"
                          tabindex="0"
                          aria-label={`Sottocartella ${child.folder.name}, ${child.folder.content_count} elementi`}
                          on:click={() => selectFolder(child.folder)}
                          on:keydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectFolder(child.folder); } }}
                        >
                          {#if child.children.length > 0}
                            <button
                              class="expand-btn"
                              on:click|stopPropagation={() => toggleExpand(child.folder.id)}
                              aria-label={expandedNodes.has(child.folder.id) ? 'Comprimi' : 'Espandi'}
                            >
                              {expandedNodes.has(child.folder.id) ? '▾' : '▸'}
                            </button>
                          {:else}
                            <span class="expand-placeholder"></span>
                          {/if}
                          <span class="folder-icon">��</span>
                          <span class="folder-name">{child.folder.name}</span>
                          <span class="folder-count">{child.folder.content_count}</span>
                        </div>

                        {#if child.children.length > 0 && expandedNodes.has(child.folder.id)}
                          <ul class="tree-list tree-list-nested" role="group">
                            {#each child.children as grandchild (grandchild.folder.id)}
                              <li role="treeitem" aria-selected={selectedFolder?.id === grandchild.folder.id}>
                                <div
                                  class="tree-item tree-item-grandchild"
                                  class:tree-item-selected={selectedFolder?.id === grandchild.folder.id}
                                  role="button"
                                  tabindex="0"
                                  aria-label={`Cartella ${grandchild.folder.name}, ${grandchild.folder.content_count} elementi`}
                                  on:click={() => selectFolder(grandchild.folder)}
                                  on:keydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectFolder(grandchild.folder); } }}
                                >
                                  <span class="expand-placeholder"></span>
                                  <span class="folder-icon">📄</span>
                                  <span class="folder-name">{grandchild.folder.name}</span>
                                  <span class="folder-count">{grandchild.folder.content_count}</span>
                                </div>
                              </li>
                            {/each}
                          </ul>
                        {/if}
                      </li>
                    {/each}
                  </ul>
                {/if}
              </li>
            {/each}
          </ul>
        </nav>
      {/if}
    </aside>

    <!-- Right: main content area -->
    <div class="main-panel">
      <!-- Create folder form -->
      {#if showCreateForm}
        <section class="card" aria-labelledby="create-form-title">
          <h2 id="create-form-title">➕ Nuova cartella</h2>

          <div class="form-row">
            <label for="create-name" class="form-label">Nome <span aria-hidden="true">*</span></label>
            <input
              id="create-name"
              type="text"
              class="form-input"
              bind:value={createName}
              placeholder="es. Manuali, Schede tecniche…"
              maxlength="100"
              required
              aria-required="true"
            />
          </div>

          <div class="form-row">
            <label for="create-desc" class="form-label">Descrizione</label>
            <textarea
              id="create-desc"
              class="form-textarea"
              bind:value={createDescription}
              placeholder="Descrizione opzionale della cartella"
              maxlength="500"
              rows="2"
            ></textarea>
          </div>

          <div class="form-row">
            <label for="create-parent" class="form-label">Cartella padre</label>
            <select id="create-parent" class="form-select" bind:value={createParentId}>
              <option value="">— Nessuna (cartella radice) —</option>
              {#each folders as f}
                {#if getDepth(f) < 2}
                  <option value={f.id}>{f.path}</option>
                {/if}
              {/each}
            </select>
            <span class="form-hint">Massimo 3 livelli di profondità.</span>
          </div>

          <fieldset class="form-fieldset">
            <legend class="form-label">Tipi di contenuto supportati <span aria-hidden="true">*</span></legend>
            <div class="checkbox-group" role="group" aria-label="Tipi di contenuto">
              {#each ALL_CONTENT_TYPES as ct}
                <label class="checkbox-label">
                  <input
                    type="checkbox"
                    checked={createContentTypes.includes(ct)}
                    on:change={() => toggleContentType(ct)}
                    aria-label={contentTypeLabel(ct)}
                  />
                  <span>{contentTypeLabel(ct)}</span>
                </label>
              {/each}
            </div>
          </fieldset>

          {#if createError}
            <p class="status error" role="alert">{createError}</p>
          {/if}
          {#if createSuccess}
            <p class="status success" role="status">{createSuccess}</p>
          {/if}

          <div class="form-actions">
            <button class="btn btn-secondary" on:click={closeCreateForm} disabled={creating}>Annulla</button>
            <button
              class="btn btn-primary"
              on:click={handleCreate}
              disabled={creating}
              aria-busy={creating}
            >
              {#if creating}
                <span class="spinner spinner-sm"></span>
                <span>Creazione…</span>
              {:else}
                Crea cartella
              {/if}
            </button>
          </div>
        </section>
      {/if}
      <!-- Folder detail / edit panel -->
      {#if selectedFolder}
        <section class="card folder-detail" aria-labelledby="folder-detail-title">
          {#if editingFolder?.id === selectedFolder.id}
            <!-- Edit mode -->
            <h2 id="folder-detail-title">✏️ Modifica cartella</h2>

            <div class="form-row">
              <label for="edit-name" class="form-label">Nome <span aria-hidden="true">*</span></label>
              <input
                id="edit-name"
                type="text"
                class="form-input"
                bind:value={editName}
                maxlength="100"
                required
                aria-required="true"
              />
            </div>

            <div class="form-row">
              <label for="edit-desc" class="form-label">Descrizione</label>
              <textarea
                id="edit-desc"
                class="form-textarea"
                bind:value={editDescription}
                maxlength="500"
                rows="2"
              ></textarea>
            </div>

            {#if editError}
              <p class="status error" role="alert">{editError}</p>
            {/if}
            {#if editSuccess}
              <p class="status success" role="status">{editSuccess}</p>
            {/if}

            <div class="form-actions">
              <button class="btn btn-secondary" on:click={cancelEdit} disabled={saving}>Annulla</button>
              <button
                class="btn btn-primary"
                on:click={handleSave}
                disabled={saving}
                aria-busy={saving}
              >
                {#if saving}
                  <span class="spinner spinner-sm"></span>
                  <span>Salvataggio…</span>
                {:else}
                  Salva modifiche
                {/if}
              </button>
            </div>
          {:else}
            <!-- View mode -->
            <div class="detail-header">
              <div>
                <h2 id="folder-detail-title">
                  <span aria-hidden="true">📁</span>
                  {selectedFolder.name}
                </h2>
                <p class="detail-path" aria-label="Percorso: {selectedFolder.path}">{selectedFolder.path}</p>
              </div>
              <div class="detail-actions">
                <button
                  class="btn btn-secondary btn-sm"
                  on:click={() => startEdit(selectedFolder!)}
                  aria-label="Modifica cartella {selectedFolder.name}"
                >
                  ✏️ Modifica
                </button>
                <button
                  class="btn btn-danger btn-sm"
                  on:click={() => requestDelete(selectedFolder!)}
                  aria-label="Elimina cartella {selectedFolder.name}"
                >
                  🗑 Elimina
                </button>
              </div>
            </div>

            {#if selectedFolder.description}
              <p class="detail-desc">{selectedFolder.description}</p>
            {/if}

            <dl class="metadata-grid">
              <div class="meta-item">
                <dt>Collezione Qdrant</dt>
                <dd><code class="code-badge">{selectedFolder.qdrant_collection}</code></dd>
              </div>
              <div class="meta-item">
                <dt>Documenti</dt>
                <dd>{selectedFolder.content_count}</dd>
              </div>
              <div class="meta-item">
                <dt>Creata il</dt>
                <dd>{formatDate(selectedFolder.created_at)}</dd>
              </div>
              <div class="meta-item">
                <dt>Aggiornata il</dt>
                <dd>{formatDate(selectedFolder.updated_at)}</dd>
              </div>
              <div class="meta-item meta-item-full">
                <dt>Tipi di contenuto</dt>
                <dd class="content-types-list">
                  {#each selectedFolder.content_types as ct}
                    <span class="content-type-badge">{contentTypeLabel(ct)}</span>
                  {/each}
                </dd>
              </div>
            </dl>

            <!-- Link to files in this folder -->
            <div class="folder-link-section">
              <a
                href="/files?folder_id={selectedFolder.id}"
                class="btn btn-secondary"
                aria-label="Visualizza i file nella cartella {selectedFolder.name}"
              >
                📄 Visualizza file in questa cartella
              </a>
            </div>
          {/if}
        </section>
      {:else if !showCreateForm}
        <!-- Empty state when no folder selected -->
        <div class="empty-state">
          <div class="empty-icon" aria-hidden="true">📂</div>
          <p>Seleziona una cartella dall'albero per visualizzarne i dettagli.</p>
          <p class="hint">Oppure crea una nuova cartella con il pulsante in alto.</p>
        </div>
      {/if}

      <!-- Folder cards grid -->
      {#if !selectedFolder && !showCreateForm}
        <section aria-labelledby="all-folders-title">
          <h2 id="all-folders-title" class="section-title">📋 Tutte le cartelle</h2>
          {#if loading}
            <div class="loading-state">
              <span class="spinner" aria-label="Caricamento"></span>
              <span>Caricamento cartelle…</span>
            </div>
          {:else if folders.length === 0}
            <div class="empty-state">
              <div class="empty-icon" aria-hidden="true">📭</div>
              <p>Nessuna cartella presente.</p>
            </div>
          {:else}
            <div class="folder-grid">
              {#each folders as folder (folder.id)}
                <article
                  class="folder-card"
                  aria-label="Cartella {folder.name}"
                >
                  <div class="folder-card-header">
                    <span class="folder-card-icon" aria-hidden="true">📁</span>
                    <div class="folder-card-title-group">
                      <h3 class="folder-card-name">{folder.name}</h3>
                      <span class="folder-card-path">{folder.path}</span>
                    </div>
                  </div>

                  {#if folder.description}
                    <p class="folder-card-desc">{folder.description}</p>
                  {/if}

                  <dl class="folder-card-meta">
                    <div class="meta-row">
                      <dt>Documenti</dt>
                      <dd>{folder.content_count}</dd>
                    </div>
                    <div class="meta-row">
                      <dt>Creata</dt>
                      <dd>{formatDate(folder.created_at)}</dd>
                    </div>
                    <div class="meta-row">
                      <dt>Collezione</dt>
                      <dd><code class="code-badge code-badge-sm">{folder.qdrant_collection}</code></dd>
                    </div>
                  </dl>

                  <div class="folder-card-types">
                    {#each folder.content_types as ct}
                      <span class="content-type-badge content-type-badge-sm">{contentTypeLabel(ct)}</span>
                    {/each}
                  </div>

                  <div class="folder-card-actions">
                    <button
                      class="btn btn-secondary btn-sm"
                      on:click={() => selectFolder(folder)}
                      aria-label="Dettagli cartella {folder.name}"
                    >
                      Dettagli
                    </button>
                    <a
                      href="/files?folder_id={folder.id}"
                      class="btn btn-secondary btn-sm"
                      aria-label="File nella cartella {folder.name}"
                    >
                      📄 File
                    </a>
                    <button
                      class="btn btn-secondary btn-sm"
                      on:click={() => startEdit(folder)}
                      aria-label="Modifica {folder.name}"
                    >
                      ✏️
                    </button>
                    <button
                      class="btn btn-danger btn-sm"
                      on:click={() => requestDelete(folder)}
                      aria-label="Elimina {folder.name}"
                    >
                      🗑
                    </button>
                  </div>
                </article>
              {/each}
            </div>
          {/if}
        </section>
      {/if}

    </div><!-- end main-panel -->
  </div><!-- end layout -->
</main>

<!-- Delete confirmation modal -->
{#if folderToDelete}
  <div
    class="modal-overlay"
    role="dialog"
    aria-modal="true"
    aria-labelledby="delete-modal-title"
  >
    <div class="modal">
      <h3 id="delete-modal-title">Conferma eliminazione</h3>
      <p>
        Sei sicuro di voler eliminare la cartella
        <strong>{folderToDelete.name}</strong>?
        La collezione Qdrant associata verrà rimossa. L'operazione è irreversibile.
      </p>
      {#if folderToDelete.content_count > 0}
        <p class="status error" role="alert">
          ⚠️ Questa cartella contiene {folderToDelete.content_count} documento/i.
          Non è possibile eliminarla finché non è vuota.
        </p>
      {/if}
      {#if deleteError}
        <p class="status error" role="alert">{deleteError}</p>
      {/if}
      <div class="modal-actions">
        <button class="btn btn-secondary" on:click={cancelDelete} disabled={deleting}>Annulla</button>
        <button
          class="btn btn-danger"
          on:click={confirmDelete}
          disabled={deleting || folderToDelete.content_count > 0}
          aria-busy={deleting}
        >
          {#if deleting}
            <span class="spinner spinner-sm"></span>
            <span>Eliminazione…</span>
          {:else}
            Elimina
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .page {
    max-width: 1200px;
    margin: 0 auto;
    padding: var(--space-8) var(--space-6) var(--space-16);
    font-family: var(--font-family-sans);
  }

  /* Page header */
  .page-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--space-4);
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

  /* Layout */
  .layout {
    display: grid;
    grid-template-columns: 260px 1fr;
    gap: var(--space-6);
    align-items: start;
  }

  @media (max-width: 768px) {
    .layout {
      grid-template-columns: 1fr;
    }
  }

  /* Tree panel */
  .tree-panel {
    background: var(--color-card-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--space-3);
    padding: var(--space-4);
    box-shadow: 0 1px var(--space-1) var(--color-shadow);
    position: sticky;
    top: calc(60px + var(--space-4));
  }

  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-3);
  }

  .panel-header h2 {
    font-size: var(--font-size-base);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text);
    margin: 0;
  }

  .empty-hint {
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
    text-align: center;
    padding: var(--space-4) 0;
  }

  /* Tree list */
  .tree-list {
    list-style: none;
    padding: 0;
    margin: 0;
  }

  .tree-list-nested {
    padding-left: var(--space-4);
  }

  .tree-item {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-2) var(--space-2);
    border-radius: var(--space-2);
    cursor: pointer;
    transition: background 0.15s ease;
    font-size: var(--font-size-sm);
    color: var(--color-text);
    user-select: none;
  }

  .tree-item:hover {
    background: var(--color-bg-secondary);
  }

  .tree-item:focus {
    outline: 2px solid var(--color-primary);
    outline-offset: 1px;
  }

  .tree-item-selected {
    background: var(--color-primary-subtle);
    color: var(--color-primary);
    font-weight: var(--font-weight-medium);
  }

  .tree-item-child {
    font-size: var(--font-size-sm);
  }

  .tree-item-grandchild {
    font-size: var(--font-size-xs);
  }

  .expand-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: 0 var(--space-1);
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
    line-height: 1;
    flex-shrink: 0;
  }

  .expand-btn:focus {
    outline: 2px solid var(--color-primary);
    border-radius: 2px;
  }

  .expand-placeholder {
    display: inline-block;
    width: 1.25rem;
    flex-shrink: 0;
  }

  .folder-icon {
    flex-shrink: 0;
  }

  .folder-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .folder-count {
    font-size: var(--font-size-xs);
    color: var(--color-text-subtle);
    background: var(--color-bg-tertiary);
    border-radius: 9999px;
    padding: 0 var(--space-2);
    min-width: 1.5rem;
    text-align: center;
    flex-shrink: 0;
  }

  /* Main panel */
  .main-panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
  }

  /* Cards */
  .card {
    background: var(--color-card-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--space-3);
    padding: var(--space-6);
    box-shadow: 0 1px var(--space-1) var(--color-shadow);
  }

  .card h2 {
    font-size: var(--font-size-xl);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text);
    margin-bottom: var(--space-4);
  }

  /* Form elements */
  .form-row {
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

  .form-input,
  .form-textarea,
  .form-select {
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--space-2);
    background: var(--color-input-bg);
    color: var(--color-text);
    font-size: var(--font-size-sm);
    font-family: var(--font-family-sans);
    transition: border-color 0.2s ease;
    width: 100%;
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
    min-height: 4rem;
  }

  .form-hint {
    font-size: var(--font-size-xs);
    color: var(--color-text-subtle);
  }

  .form-fieldset {
    border: 1px solid var(--color-border);
    border-radius: var(--space-2);
    padding: var(--space-3);
    margin-bottom: var(--space-4);
  }

  .form-fieldset legend {
    padding: 0 var(--space-2);
  }

  .checkbox-group {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    margin-top: var(--space-2);
  }

  .checkbox-label {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--font-size-sm);
    color: var(--color-text);
    cursor: pointer;
  }

  .form-actions {
    display: flex;
    gap: var(--space-3);
    justify-content: flex-end;
    margin-top: var(--space-2);
  }

  /* Folder detail */
  .folder-detail {
    container-type: inline-size;
  }

  .detail-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
  }

  .detail-header h2 {
    font-size: var(--font-size-2xl);
    font-weight: var(--font-weight-bold);
    color: var(--color-text);
    margin: 0 0 var(--space-1);
  }

  .detail-path {
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
    font-family: var(--font-family-mono);
  }

  .detail-actions {
    display: flex;
    gap: var(--space-2);
    flex-shrink: 0;
  }

  .detail-desc {
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
    line-height: var(--line-height-relaxed);
    margin-bottom: var(--space-4);
  }

  .metadata-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: var(--space-3);
    margin-bottom: var(--space-4);
  }

  .meta-item {
    background: var(--color-bg-secondary);
    border-radius: var(--space-2);
    padding: var(--space-3);
  }

  .meta-item-full {
    grid-column: 1 / -1;
  }

  .meta-item dt {
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: var(--letter-spacing-wide);
    margin-bottom: var(--space-1);
  }

  .meta-item dd {
    font-size: var(--font-size-sm);
    color: var(--color-text);
    margin: 0;
  }

  .content-types-list {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin: 0;
  }

  .content-type-badge {
    display: inline-block;
    padding: var(--space-1) var(--space-2);
    background: var(--color-primary-subtle);
    color: var(--color-primary);
    border-radius: var(--space-1);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
  }

  .content-type-badge-sm {
    font-size: 0.65rem;
    padding: 2px var(--space-1);
  }

  .folder-link-section {
    margin-top: var(--space-4);
    padding-top: var(--space-4);
    border-top: 1px solid var(--color-border-subtle);
  }

  /* Section title */
  .section-title {
    font-size: var(--font-size-xl);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text);
    margin-bottom: var(--space-4);
  }

  /* Folder grid */
  .folder-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: var(--space-4);
  }

  .folder-card {
    background: var(--color-card-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--space-3);
    padding: var(--space-4);
    box-shadow: 0 1px var(--space-1) var(--color-shadow);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    transition: box-shadow 0.2s ease, border-color 0.2s ease;
  }

  .folder-card:hover {
    box-shadow: 0 var(--space-2) var(--space-4) var(--color-shadow-medium);
    border-color: var(--color-primary-muted);
  }

  .folder-card-header {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
  }

  .folder-card-icon {
    font-size: var(--font-size-2xl);
    line-height: 1;
    flex-shrink: 0;
  }

  .folder-card-title-group {
    flex: 1;
    min-width: 0;
  }

  .folder-card-name {
    font-size: var(--font-size-base);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text);
    margin: 0 0 var(--space-1);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .folder-card-path {
    font-size: var(--font-size-xs);
    color: var(--color-text-subtle);
    font-family: var(--font-family-mono);
  }

  .folder-card-desc {
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
    line-height: var(--line-height-relaxed);
    margin: 0;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .folder-card-meta {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    margin: 0;
  }

  .meta-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: var(--font-size-xs);
  }

  .meta-row dt {
    color: var(--color-text-muted);
    font-weight: var(--font-weight-medium);
  }

  .meta-row dd {
    color: var(--color-text);
    margin: 0;
    text-align: right;
  }

  .folder-card-types {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
  }

  .folder-card-actions {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
    margin-top: auto;
    padding-top: var(--space-2);
    border-top: 1px solid var(--color-border-subtle);
  }

  /* Code badge */
  .code-badge {
    font-family: var(--font-family-mono);
    font-size: var(--font-size-xs);
    background: var(--color-bg-tertiary);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--space-1);
    color: var(--color-text-muted);
    word-break: break-all;
  }

  .code-badge-sm {
    font-size: 0.65rem;
    padding: 1px var(--space-1);
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
    line-height: var(--line-height-normal);
    margin-bottom: var(--space-3);
  }

  .status.error {
    background: var(--color-error-subtle);
    color: var(--color-error-text);
    border: 1px solid var(--color-error-border);
  }

  .status.success {
    background: var(--color-success-subtle);
    color: var(--color-success-text);
    border: 1px solid var(--color-success-border);
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
    max-width: 480px;
    width: 100%;
    box-shadow: 0 var(--space-4) var(--space-8) var(--color-shadow-strong);
  }

  .modal h3 {
    font-size: var(--font-size-xl);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text);
    margin-bottom: var(--space-3);
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
  }

  /* Responsive */
  @media (max-width: 640px) {
    .page {
      padding: var(--space-4) var(--space-4) var(--space-12);
    }

    .page-header {
      flex-direction: column;
    }

    .folder-grid {
      grid-template-columns: 1fr;
    }

    .metadata-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
