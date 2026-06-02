<script lang="ts">
  import {
    getDownloadUrl,
    getPreviewUrl,
    getOriginalFilename,
    getPreviewMode,
    type DocumentLike
  } from '$lib/documentUtils';

  export let open = false;
  export let document: DocumentLike | null = null;
  export let backendUrl: string;
  export let onClose: () => void = () => {};

  let textPreview = '';
  let textLoading = false;
  let textError = '';

  $: downloadUrl = document ? getDownloadUrl(backendUrl, document) : null;
  $: previewUrl = document ? getPreviewUrl(backendUrl, document) : null;
  $: previewMode = document ? getPreviewMode(document) : 'none';
  $: title = document ? getOriginalFilename(document) : '';

  $: if (open && document && previewMode === 'text' && downloadUrl) {
    loadTextPreview(downloadUrl);
  } else if (!open) {
    textPreview = '';
    textError = '';
  }

  async function loadTextPreview(url: string) {
    textLoading = true;
    textError = '';
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const text = await res.text();
      textPreview = text.length > 12000 ? text.slice(0, 12000) + '\n\n…' : text;
    } catch {
      textError = "Impossibile caricare l'anteprima.";
    } finally {
      textLoading = false;
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') onClose();
  }
</script>

{#if open && document}
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div
    class="preview-overlay fade-in"
    role="dialog"
    aria-modal="true"
    tabindex="-1"
    onclick={onClose}
    onkeydown={handleKeydown}
  >
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div
      class="preview-panel slide-in-up"
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => e.stopPropagation()}
    >
      <header class="preview-header">
        <h2>Anteprima: {title}</h2>
        <button type="button" class="close-button" onclick={onClose} aria-label="Chiudi">✕</button>
      </header>
      <div class="preview-body">
        {#if previewMode === 'embed' && previewUrl}
          <iframe src={previewUrl} class="preview-embed" title="Anteprima – {title}"></iframe>
        {:else if previewMode === 'text' && textLoading}
          <div class="preview-loading">
            <span class="spinner"></span>
            <span>Caricamento testo…</span>
          </div>
        {:else if previewMode === 'text' && textPreview}
          <pre class="preview-text">{textPreview}</pre>
        {:else if previewMode === 'text' && textError}
          <p class="preview-error">{textError}</p>
        {:else if document.content}
          <div class="preview-excerpt">
            <p>{document.content}</p>
          </div>
        {:else}
          <p class="muted preview-none">Anteprima non disponibile per questo tipo di file.</p>
        {/if}
      </div>
      <footer class="preview-footer">
        {#if previewUrl}
          <a class="btn btn-primary" href={previewUrl} target="_blank" rel="noopener noreferrer">Apri in nuova scheda</a>
        {/if}
        {#if downloadUrl}
          <a class="btn btn-secondary" href={downloadUrl} download={title}>Scarica</a>
        {/if}
        <button type="button" class="btn btn-secondary" onclick={onClose}>Chiudi</button>
      </footer>
    </div>
  </div>
{/if}

<style>
  .preview-overlay {
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.55);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 300;
    padding: var(--space-4);
  }
  .preview-panel {
    background: var(--color-card-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--space-3);
    width: min(1100px, 96vw);
    height: 92vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 var(--space-4) var(--space-8) var(--color-shadow-strong);
  }
  .preview-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-4);
    border-bottom: 1px solid var(--color-border);
    flex-shrink: 0;
  }
  .preview-header h2 {
    margin: 0;
    font-size: var(--font-size-lg);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .close-button {
    background: none;
    border: none;
    font-size: var(--font-size-xl);
    cursor: pointer;
    color: var(--color-text-muted);
    padding: var(--space-1);
    border-radius: var(--space-1);
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .close-button:hover { background: var(--color-bg-secondary); }
  .close-button:focus { outline: 2px solid var(--color-primary); outline-offset: 2px; }
  .preview-body {
    flex: 1;
    overflow: auto;
    min-height: 200px;
    display: flex;
    flex-direction: column;
  }
  .preview-embed {
    width: 100%;
    height: 100%;
    border: none;
    flex: 1;
    min-height: 0;
  }
  .preview-text {
    padding: var(--space-4);
    margin: 0;
    white-space: pre-wrap;
    font-size: var(--font-size-sm);
    font-family: var(--font-family-mono);
    color: var(--color-text);
    line-height: var(--line-height-relaxed);
  }
  .preview-excerpt {
    padding: var(--space-4);
  }
  .preview-excerpt p {
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
    line-height: var(--line-height-relaxed);
    margin: 0;
  }
  .preview-loading {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-8);
    color: var(--color-text-muted);
    justify-content: center;
  }
  .preview-error {
    padding: var(--space-4);
    color: var(--color-error);
    background: var(--color-error-subtle);
    margin: var(--space-4);
    border-radius: var(--space-2);
  }
  .preview-none {
    padding: var(--space-8);
    text-align: center;
    color: var(--color-text-muted);
  }
  .muted { color: var(--color-text-muted); font-size: var(--font-size-sm); }
  .preview-footer {
    display: flex;
    gap: var(--space-2);
    justify-content: flex-end;
    padding: var(--space-4);
    border-top: 1px solid var(--color-border);
    flex-shrink: 0;
  }
  .btn {
    display: inline-flex; align-items: center; gap: var(--space-2);
    padding: var(--space-2) var(--space-4); border-radius: var(--space-2);
    font-size: var(--font-size-sm); font-weight: var(--font-weight-medium);
    cursor: pointer; border: none; transition: all 0.2s ease; text-decoration: none;
  }
  .btn:focus { outline: 2px solid var(--color-primary); outline-offset: 2px; }
  .btn-primary { background: var(--color-primary); color: white; }
  .btn-primary:hover { background: var(--color-primary-hover); }
  .btn-secondary { background: var(--color-bg-secondary); color: var(--color-text); border: 1px solid var(--color-border); }
  .btn-secondary:hover { background: var(--color-bg-tertiary); }
  .spinner {
    display: inline-block; width: 1rem; height: 1rem;
    border: 2px solid currentColor; border-top-color: transparent;
    border-radius: 50%; animation: spin 0.7s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
