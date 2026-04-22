<script lang="ts">
  import { onMount } from 'svelte';
  import { PUBLIC_BACKEND_URL } from '$env/static/public';
  import Tooltip from '$lib/Tooltip.svelte';

  const BACKEND_URL = PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

  // ---- Types ----
  interface Folder {
    id: string;
    name: string;
    description: string | null;
    content_types: string[];
    content_count: number;
  }

  interface FileRecord {
    id: string;
    filename: string;
    original_filename: string;
    folder_id: string;
    file_size: number;
    content_type: string;
    upload_date: string;
    chunk_count: number;
    status: string;
    file_path: string;
  }

  // ---- State ----
  let folders: Folder[] = [];
  let files: FileRecord[] = [];
  let selectedFolderId: string = '';
  let uploadFile: File | null = null;
  let uploadFolderId: string = '';
  let isDragging = false;
  let uploading = false;
  let loadingFiles = false;
  let loadingFolders = false;
  let uploadError = '';
  let uploadSuccess = '';
  let deleteError = '';
  let selectedFileIds: Set<string> = new Set();
  let showDeleteConfirm = false;
  let fileToDelete: FileRecord | null = null;
  let showBulkDeleteConfirm = false;
  let bulkDeleteResult: { deleted_count: number; failed_count: number } | null = null;

  // ---- Helpers ----
  function formatBytes(bytes: number): string {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

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

  function getFolderName(folderId: string): string {
    return folders.find(f => f.id === folderId)?.name ?? folderId;
  }

  function statusLabel(status: string): string {
    switch (status) {
      case 'indexed': return 'Indicizzato';
      case 'processing': return 'In elaborazione';
      case 'failed': return 'Errore';
      default: return status;
    }
  }

  function statusClass(status: string): string {
    switch (status) {
      case 'indexed': return 'status-indexed';
      case 'processing': return 'status-processing';
      case 'failed': return 'status-failed';
      default: return '';
    }
  }

  // ---- Data loading ----
  async function loadFolders() {
    loadingFolders = true;
    try {
      const res = await fetch(`${BACKEND_URL}/folders`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      folders = data.folders ?? [];
      if (!uploadFolderId && folders.length > 0) {
        uploadFolderId = folders[0].id;
      }
    } catch (e) {
      console.error('Failed to load folders:', e);
    } finally {
      loadingFolders = false;
    }
  }

  async function loadFiles(folderId?: string) {
    loadingFiles = true;
    try {
      const url = folderId
        ? `${BACKEND_URL}/files?folder_id=${encodeURIComponent(folderId)}`
        : `${BACKEND_URL}/files`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      files = data.files ?? [];
      selectedFileIds = new Set();
    } catch (e) {
      console.error('Failed to load files:', e);
    } finally {
      loadingFiles = false;
    }
  }

  onMount(async () => {
    await loadFolders();
    await loadFiles();
  });

  // ---- Filter ----
  async function applyFolderFilter() {
    await loadFiles(selectedFolderId || undefined);
  }

  // ---- Upload ----
  function onFileInputChange(event: Event) {
    const target = event.target as HTMLInputElement;
    uploadFile = target.files?.[0] ?? null;
    uploadError = '';
    uploadSuccess = '';
  }

  function onDragOver(event: DragEvent) {
    event.preventDefault();
    isDragging = true;
  }

  function onDragLeave(event: DragEvent) {
    event.preventDefault();
    isDragging = false;
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    isDragging = false;
    const file = event.dataTransfer?.files?.[0];
    if (file) {
      uploadFile = file;
      uploadError = '';
      uploadSuccess = '';
    }
  }

  async function handleUpload() {
    uploadError = '';
    uploadSuccess = '';

    if (!uploadFile) {
      uploadError = 'Seleziona un file da caricare.';
      return;
    }
    if (!uploadFolderId) {
      uploadError = 'Seleziona una cartella di destinazione.';
      return;
    }

    uploading = true;
    try {
      const formData = new FormData();
      formData.append('file', uploadFile);

      const res = await fetch(
        `${BACKEND_URL}/files/upload?folder_id=${encodeURIComponent(uploadFolderId)}`,
        { method: 'POST', body: formData }
      );

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? `Errore HTTP ${res.status}`);
      }

      const record: FileRecord = await res.json();
      uploadSuccess = `File "${record.original_filename}" caricato con successo (${record.chunk_count} chunk indicizzati).`;
      uploadFile = null;
      // Reload file list
      await loadFiles(selectedFolderId || undefined);
    } catch (e) {
      uploadError = e instanceof Error ? e.message : 'Errore durante il caricamento.';
    } finally {
      uploading = false;
    }
  }

  // ---- Delete single ----
  function requestDelete(file: FileRecord) {
    fileToDelete = file;
    showDeleteConfirm = true;
    deleteError = '';
  }

  function cancelDelete() {
    fileToDelete = null;
    showDeleteConfirm = false;
  }

  async function confirmDelete() {
    if (!fileToDelete) return;
    deleteError = '';
    try {
      const res = await fetch(`${BACKEND_URL}/files/${fileToDelete.id}`, { method: 'DELETE' });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? `Errore HTTP ${res.status}`);
      }
      showDeleteConfirm = false;
      fileToDelete = null;
      await loadFiles(selectedFolderId || undefined);
    } catch (e) {
      deleteError = e instanceof Error ? e.message : 'Errore durante l\'eliminazione.';
    }
  }

  // ---- Bulk selection ----
  function toggleSelectFile(id: string) {
    const next = new Set(selectedFileIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    selectedFileIds = next;
  }

  function toggleSelectAll() {
    if (selectedFileIds.size === files.length) {
      selectedFileIds = new Set();
    } else {
      selectedFileIds = new Set(files.map(f => f.id));
    }
  }

  // ---- Bulk delete ----
  function requestBulkDelete() {
    if (selectedFileIds.size === 0) return;
    showBulkDeleteConfirm = true;
    deleteError = '';
    bulkDeleteResult = null;
  }

  function cancelBulkDelete() {
    showBulkDeleteConfirm = false;
  }

  async function confirmBulkDelete() {
    deleteError = '';
    bulkDeleteResult = null;
    try {
      const res = await fetch(`${BACKEND_URL}/files/bulk-delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_ids: Array.from(selectedFileIds) })
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? `Errore HTTP ${res.status}`);
      }
      const result = await res.json();
      bulkDeleteResult = result;
      showBulkDeleteConfirm = false;
      selectedFileIds = new Set();
      await loadFiles(selectedFolderId || undefined);
    } catch (e) {
      deleteError = e instanceof Error ? e.message : 'Errore durante l\'eliminazione multipla.';
      showBulkDeleteConfirm = false;
    }
  }
</script>

<svelte:head>
  <title>Gestione File – UseIt</title>
</svelte:head>

<main class="page page-transition">
  <!-- Header -->
  <section class="page-header">
    <div class="header-text">
      <h1>Gestione File</h1>
      <p>Carica documenti nelle cartelle e gestisci i file indicizzati.</p>
    </div>
  </section>

  <!-- Upload Section -->
  <section class="card upload-section">
    <h2>📤 Carica un documento</h2>
    <p class="section-desc">
      Formati supportati: PDF, DOC, DOCX, TXT. Il testo verrà estratto automaticamente e indicizzato.
    </p>

    <!-- Folder selector -->
    <div class="form-row">
      <label for="upload-folder" class="form-label">
        Cartella di destinazione
        <Tooltip textKey="tooltip.uploadFolder" position="right" />
      </label>
      {#if loadingFolders}
        <span class="spinner spinner-sm"></span>
      {:else}
        <select id="upload-folder" class="form-select" bind:value={uploadFolderId}>
          {#each folders as folder}
            <option value={folder.id}>{folder.name}</option>
          {/each}
        </select>
      {/if}
    </div>

    <!-- Drop zone -->
    <div
      class="dropzone"
      class:is-dragging={isDragging}
      role="button"
      tabindex="0"
      aria-label="Area di caricamento file - trascina qui o clicca per selezionare"
      on:dragover|preventDefault={onDragOver}
      on:dragleave={onDragLeave}
      on:drop={onDrop}
      on:keydown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          (document.getElementById('file-input') as HTMLInputElement)?.click();
        }
      }}
      on:click={() => (document.getElementById('file-input') as HTMLInputElement)?.click()}
    >
      <div class="dropzone-inner">
        <div class="dropzone-icon">📄</div>
        {#if uploadFile}
          <p class="file-selected"><strong>{uploadFile.name}</strong> ({formatBytes(uploadFile.size)})</p>
        {:else}
          <p>Trascina qui un file oppure <strong>clicca per selezionare</strong></p>
          <p class="hint">PDF, DOC, DOCX, TXT</p>
        {/if}
        <input
          id="file-input"
          type="file"
          accept=".pdf,.doc,.docx,.txt"
          on:change={onFileInputChange}
          style="display:none"
        />
      </div>
    </div>

    <button
      class="btn btn-primary"
      on:click={handleUpload}
      disabled={uploading || !uploadFile}
      aria-busy={uploading}
    >
      {#if uploading}
        <span class="spinner spinner-sm"></span>
        <span>Caricamento in corso…</span>
      {:else}
        Carica e indicizza
      {/if}
    </button>

    {#if uploadError}
      <p class="status error" role="alert">{uploadError}</p>
    {/if}
    {#if uploadSuccess}
      <p class="status success" role="status">{uploadSuccess}</p>
    {/if}
  </section>

  <!-- File List Section -->
  <section class="card file-list-section">
    <div class="list-header">
      <h2>📁 File caricati</h2>
      <div class="list-controls">
        <!-- Folder filter -->
        <select
          class="form-select form-select-sm"
          bind:value={selectedFolderId}
          on:change={applyFolderFilter}
          aria-label="Filtra per cartella"
        >
          <option value="">Tutte le cartelle</option>
          {#each folders as folder}
            <option value={folder.id}>{folder.name}</option>
          {/each}
        </select>

        <!-- Bulk delete button -->
        {#if selectedFileIds.size > 0}
          <button class="btn btn-danger btn-sm" on:click={requestBulkDelete}>
            🗑 Elimina selezionati ({selectedFileIds.size})
          </button>
          <Tooltip textKey="tooltip.bulkDelete" position="left" />
        {/if}
      </div>
    </div>

    {#if bulkDeleteResult}
      <p class="status success" role="status">
        Eliminati {bulkDeleteResult.deleted_count} file.
        {#if bulkDeleteResult.failed_count > 0}
          {bulkDeleteResult.failed_count} non eliminati.
        {/if}
      </p>
    {/if}

    {#if deleteError}
      <p class="status error" role="alert">{deleteError}</p>
    {/if}

    {#if loadingFiles}
      <div class="loading-state">
        <span class="spinner"></span>
        <span>Caricamento file…</span>
      </div>
    {:else if files.length === 0}
      <div class="empty-state">
        <div class="empty-icon">📭</div>
        <p>Nessun file caricato{selectedFolderId ? ' in questa cartella' : ''}.</p>
        <p class="hint">Usa il modulo sopra per caricare il primo documento.</p>
      </div>
    {:else}
      <!-- Select all row -->
      <div class="select-all-row">
        <label class="checkbox-label">
          <input
            type="checkbox"
            checked={selectedFileIds.size === files.length && files.length > 0}
            indeterminate={selectedFileIds.size > 0 && selectedFileIds.size < files.length}
            on:change={toggleSelectAll}
            aria-label="Seleziona tutti i file"
          />
          <span>Seleziona tutti ({files.length})</span>
        </label>
      </div>

      <div class="file-table-wrapper">
        <table class="file-table" aria-label="Lista file caricati">
          <thead>
            <tr>
              <th scope="col" class="col-check" aria-label="Selezione"></th>
              <th scope="col">Nome file</th>
              <th scope="col">Cartella</th>
              <th scope="col">Dimensione</th>
              <th scope="col">Data caricamento</th>
              <th scope="col">Chunk</th>
              <th scope="col">Stato</th>
              <th scope="col" aria-label="Azioni"></th>
            </tr>
          </thead>
          <tbody>
            {#each files as file (file.id)}
              <tr class:selected={selectedFileIds.has(file.id)}>
                <td class="col-check">
                  <input
                    type="checkbox"
                    checked={selectedFileIds.has(file.id)}
                    on:change={() => toggleSelectFile(file.id)}
                    aria-label={`Seleziona ${file.original_filename}`}
                  />
                </td>
                <td class="col-name" title={file.original_filename}>
                  <span class="file-icon">📄</span>
                  {file.original_filename}
                </td>
                <td>{getFolderName(file.folder_id)}</td>
                <td>{formatBytes(file.file_size)}</td>
                <td>{formatDate(file.upload_date)}</td>
                <td>{file.chunk_count}</td>
                <td>
                  <span class="status-badge {statusClass(file.status)}">
                    {statusLabel(file.status)}
                  </span>
                </td>
                <td class="col-actions">
                  <a
                    href="{BACKEND_URL}/files/{file.id}/download"
                    class="btn btn-secondary btn-xs"
                    download={file.original_filename}
                    aria-label={`Scarica ${file.original_filename}`}
                  >⬇</a>
                  <button
                    class="btn btn-danger btn-xs"
                    on:click={() => requestDelete(file)}
                    aria-label={`Elimina ${file.original_filename}`}
                  >🗑</button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </section>
</main>

<!-- Delete confirmation modal -->
{#if showDeleteConfirm && fileToDelete}
  <div class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="delete-modal-title">
    <div class="modal">
      <h3 id="delete-modal-title">Conferma eliminazione</h3>
      <p>
        Sei sicuro di voler eliminare <strong>{fileToDelete.original_filename}</strong>?
        Il file verrà rimosso dal disco e dall'indice Qdrant.
      </p>
      {#if deleteError}
        <p class="status error" role="alert">{deleteError}</p>
      {/if}
      <div class="modal-actions">
        <button class="btn btn-secondary" on:click={cancelDelete}>Annulla</button>
        <button class="btn btn-danger" on:click={confirmDelete}>Elimina</button>
      </div>
    </div>
  </div>
{/if}

<!-- Bulk delete confirmation modal -->
{#if showBulkDeleteConfirm}
  <div class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="bulk-delete-modal-title">
    <div class="modal">
      <h3 id="bulk-delete-modal-title">Conferma eliminazione multipla</h3>
      <p>
        Sei sicuro di voler eliminare <strong>{selectedFileIds.size} file</strong>?
        Questa operazione non può essere annullata.
      </p>
      <div class="modal-actions">
        <button class="btn btn-secondary" on:click={cancelBulkDelete}>Annulla</button>
        <button class="btn btn-danger" on:click={confirmBulkDelete}>Elimina tutti</button>
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

  /* Cards */
  .card {
    background: var(--color-card-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--space-3);
    padding: var(--space-6);
    box-shadow: 0 1px var(--space-1) var(--color-shadow);
    margin-bottom: var(--space-6);
  }

  .card h2 {
    font-size: var(--font-size-xl);
    font-weight: var(--font-weight-semibold);
    line-height: var(--line-height-snug);
    color: var(--color-text);
    margin-bottom: var(--space-2);
  }

  .section-desc {
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
    line-height: var(--line-height-relaxed);
    margin-bottom: var(--space-4);
  }

  /* Form elements */
  .form-row {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    margin-bottom: var(--space-4);
  }

  .form-label {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    color: var(--color-text);
  }

  .form-select {
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--space-2);
    background: var(--color-input-bg);
    color: var(--color-text);
    font-size: var(--font-size-sm);
    font-family: var(--font-family-sans);
    cursor: pointer;
    transition: border-color 0.2s ease;
    max-width: 320px;
  }

  .form-select:focus {
    outline: 2px solid var(--color-primary);
    outline-offset: 2px;
    border-color: var(--color-primary);
  }

  .form-select-sm {
    padding: var(--space-1) var(--space-2);
    font-size: var(--font-size-xs);
    max-width: 200px;
  }

  /* Drop zone */
  .dropzone {
    background: var(--color-bg-secondary);
    border: 2px dashed var(--color-border);
    border-radius: var(--space-3);
    padding: var(--space-8) var(--space-6);
    cursor: pointer;
    transition: all 0.2s ease;
    margin-bottom: var(--space-4);
    text-align: center;
  }

  .dropzone:hover:not(.is-dragging) {
    border-color: var(--color-primary-muted);
    background: var(--color-primary-subtle);
  }

  .dropzone:focus {
    outline: 2px solid var(--color-primary);
    outline-offset: 2px;
  }

  .dropzone.is-dragging {
    border-color: var(--color-primary);
    background: var(--color-primary-subtle);
    transform: scale(1.01);
  }

  .dropzone-inner {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-2);
  }

  .dropzone-icon {
    font-size: var(--font-size-5xl);
    line-height: var(--line-height-tight);
  }

  .dropzone p {
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
    line-height: var(--line-height-relaxed);
    margin: 0;
  }

  .file-selected {
    color: var(--color-text) !important;
    font-size: var(--font-size-base) !important;
  }

  .hint {
    font-size: var(--font-size-xs) !important;
    color: var(--color-text-subtle) !important;
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

  .btn-xs {
    padding: var(--space-1) var(--space-2);
    font-size: var(--font-size-xs);
  }

  /* Status messages */
  .status {
    margin-top: var(--space-3);
    padding: var(--space-3);
    border-radius: var(--space-2);
    font-size: var(--font-size-sm);
    line-height: var(--line-height-normal);
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

  /* File list header */
  .list-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
  }

  .list-controls {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    flex-wrap: wrap;
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

  /* Select all row */
  .select-all-row {
    margin-bottom: var(--space-3);
  }

  .checkbox-label {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
    cursor: pointer;
  }

  /* File table */
  .file-table-wrapper {
    overflow-x: auto;
  }

  .file-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--font-size-sm);
  }

  .file-table th {
    text-align: left;
    padding: var(--space-2) var(--space-3);
    border-bottom: 2px solid var(--color-border);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-muted);
    white-space: nowrap;
  }

  .file-table td {
    padding: var(--space-3);
    border-bottom: 1px solid var(--color-border-subtle);
    vertical-align: middle;
    color: var(--color-text);
  }

  .file-table tr:last-child td {
    border-bottom: none;
  }

  .file-table tr:hover td {
    background: var(--color-bg-secondary);
  }

  .file-table tr.selected td {
    background: var(--color-primary-subtle);
  }

  .col-check {
    width: 40px;
  }

  .col-name {
    max-width: 240px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .file-icon {
    margin-right: var(--space-1);
  }

  .col-actions {
    white-space: nowrap;
    display: flex;
    gap: var(--space-1);
  }

  /* Status badges */
  .status-badge {
    display: inline-block;
    padding: var(--space-1) var(--space-2);
    border-radius: var(--space-1);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
  }

  .status-indexed {
    background: var(--color-success-subtle);
    color: var(--color-success-text);
  }

  .status-processing {
    background: var(--color-warning-subtle);
    color: var(--color-warning);
  }

  .status-failed {
    background: var(--color-error-subtle);
    color: var(--color-error-text);
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

    .list-header {
      flex-direction: column;
      align-items: flex-start;
    }

    .file-table th:nth-child(4),
    .file-table td:nth-child(4),
    .file-table th:nth-child(5),
    .file-table td:nth-child(5),
    .file-table th:nth-child(6),
    .file-table td:nth-child(6) {
      display: none;
    }
  }
</style>
