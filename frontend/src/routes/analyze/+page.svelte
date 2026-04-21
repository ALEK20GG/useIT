<script lang="ts">
  import { PUBLIC_BACKEND_URL } from '$env/static/public';
  const BACKEND_URL = PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

  let selectedFile: File | null = null;
  let previewUrl: string | null = null;
  let isDragging = false;
  let loading = false;
  let errorMessage = '';
  let analysisSummary = '';

  function onFileChange(event: Event) {
    const target = event.target as HTMLInputElement;
    const file = target.files?.[0];
    handleNewFile(file ?? null);
  }

  function handleNewFile(file: File | null) {
    errorMessage = '';
    analysisSummary = '';

    if (!file) {
      selectedFile = null;
      previewUrl = null;
      return;
    }

    if (!file.type.startsWith('image/')) {
      errorMessage = 'Per favore seleziona un file immagine.';
      return;
    }

    selectedFile = file;
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    previewUrl = URL.createObjectURL(file);
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
    handleNewFile(file ?? null);
  }

  async function analyze() {
    errorMessage = '';
    analysisSummary = '';

    if (!selectedFile) {
      errorMessage = 'Prima carica o scatta una foto del prodotto.';
      return;
    }

    loading = true;
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const res = await fetch(`${BACKEND_URL}/analyze/image`, {
        method: 'POST',
        body: formData
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? `Errore durante l\'analisi (status ${res.status})`);
      }

      const data = (await res.json()) as { summary?: string; filename?: string };
      analysisSummary =
        data.summary ??
        'Analisi ricevuta dal backend. Quando collegheremo il modello vedrai i dettagli qui.';
    } catch (err) {
      errorMessage =
        err instanceof Error ? err.message : 'Si è verificato un errore durante l\'analisi.';
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head>
  <title>Analisi prodotto da foto – UseIt</title>
</svelte:head>

<main class="page page-transition">
  <section class="hero">
    <div class="hero-text">
      <h1>Analizza un prodotto con una foto</h1>
      <p>
        Scatta una foto al prodotto oppure caricala dalla galleria. Il software la invierà al
        backend per l'analisi.
      </p>
    </div>
  </section>

  <section class="layout">
    <div
      class="dropzone"
      class:is-dragging={isDragging}
      role="button"
      tabindex="0"
      aria-label="Area di caricamento immagine - trascina qui i file o clicca per selezionare"
      on:dragover|preventDefault={onDragOver}
      on:dragleave={onDragLeave}
      on:drop={onDrop}
      on:keydown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
          fileInput?.click();
        }
      }}
      on:click={() => {
        const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
        fileInput?.click();
      }}
    >
      <div class="dropzone-inner">
        {#if previewUrl}
          <img src={previewUrl} alt="Anteprima foto prodotto" class="preview" />
        {:else}
          <div class="placeholder-icon">📷</div>
        {/if}

        <div class="instructions">
          <p>
            <strong>Trascina qui</strong> una foto del prodotto<br />
            oppure
          </p>

          <label class="btn btn-secondary">
            Scegli dalla galleria
            <input type="file" accept="image/*" on:change={onFileChange} />
          </label>

          <p class="hint">
            Su smartphone puoi anche usare la fotocamera:
          </p>

          <label class="btn btn-secondary">
            Scatta una foto
            <input type="file" accept="image/*" capture="environment" on:change={onFileChange} />
          </label>
        </div>
      </div>
    </div>

    <div class="side-card">
      <h2>Risultato analisi</h2>
      <p class="muted">
        Dopo aver scelto o scattato una foto, premi <strong>Analizza prodotto</strong> per inviarla
        al backend.
      </p>

      <button class="btn btn-primary" on:click={analyze} disabled={loading}>
        {#if loading}
          <span class="spinner spinner-sm"></span>
          <span>Analisi in corso…</span>
        {:else}
          Analizza prodotto
        {/if}
      </button>

      {#if errorMessage}
        <p class="status error">{errorMessage}</p>
      {/if}

      {#if analysisSummary}
        <div class="analysis-box fade-in">
          <h3>Analisi</h3>
          <p>{analysisSummary}</p>
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
    margin-bottom: var(--space-8);
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
    max-width: 38rem;
    font-size: var(--font-size-base);
    line-height: var(--line-height-relaxed);
  }

  .layout {
    display: grid;
    gap: var(--space-6);
  }

  @media (min-width: 900px) {
    .layout {
      grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
      align-items: flex-start;
    }
  }

  .dropzone {
    background: var(--color-bg-secondary);
    border-radius: var(--space-3);
    padding: var(--space-8) var(--space-6);
    border: 2px dashed var(--color-border);
    transition: all 0.2s ease;
    cursor: pointer;
  }

  .dropzone:hover:not(.is-dragging) {
    border-color: var(--color-primary-muted);
    background-color: var(--color-primary-subtle);
    transform: scale(1.01);
  }

  .dropzone:focus {
    outline: 2px solid var(--color-primary);
    outline-offset: var(--space-1);
  }

  .dropzone.is-dragging {
    border-color: var(--color-primary);
    background-color: var(--color-primary-subtle);
    box-shadow: 0 var(--space-2) var(--space-4) var(--color-shadow-medium);
    transform: scale(1.02);
  }

  .dropzone-inner {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-4);
  }

  .preview {
    max-width: 100%;
    max-height: 320px;
    border-radius: var(--space-2);
    box-shadow: 0 1px var(--space-3) var(--color-shadow-medium);
    object-fit: cover;
  }

  .placeholder-icon {
    font-size: var(--font-size-5xl);
    line-height: var(--line-height-tight);
  }

  .instructions {
    text-align: center;
  }

  .instructions p {
    margin: var(--space-1) 0;
    font-size: var(--font-size-base);
    line-height: var(--line-height-relaxed);
    color: var(--color-text-muted);
  }

  .instructions .hint {
    margin-top: var(--space-3);
    font-size: var(--font-size-sm);
    line-height: var(--line-height-normal);
    color: var(--color-text-muted);
  }

  :global(.btn input[type='file']) {
    display: none;
  }

  .side-card {
    background: var(--color-card-bg);
    border-radius: var(--space-3);
    padding: var(--space-6);
    box-shadow: 0 1px var(--space-1) var(--color-shadow);
    border: 1px solid var(--color-border);
    transition: all 0.2s ease;
  }

  .side-card:hover {
    box-shadow: 0 var(--space-2) var(--space-4) var(--color-shadow-medium);
    transform: translateY(-2px);
  }

  .side-card:focus-within {
    outline: 2px solid var(--color-primary);
    outline-offset: 2px;
  }

  .side-card h2 {
    margin-bottom: var(--space-3);
    font-size: var(--font-size-xl);
    font-weight: var(--font-weight-semibold);
    line-height: var(--line-height-snug);
    color: var(--color-text);
  }

  .muted {
    font-size: var(--font-size-sm);
    line-height: var(--line-height-relaxed);
    color: var(--color-text-muted);
    margin-bottom: var(--space-4);
  }

  .status {
    margin-top: var(--space-3);
    font-size: var(--font-size-sm);
    line-height: var(--line-height-normal);
    padding: var(--space-3);
    border-radius: var(--space-2);
  }

  .status.error {
    background-color: var(--color-error-subtle);
    color: var(--color-error-text);
    border: 1px solid var(--color-error-border);
  }

  .analysis-box {
    margin-top: var(--space-4);
    padding: var(--space-4);
    border-radius: var(--space-2);
    background: var(--color-primary-subtle);
    border: 1px solid var(--color-primary-muted);
    transition: all 0.2s ease;
  }

  .analysis-box:hover {
    box-shadow: 0 var(--space-1) var(--space-2) var(--color-shadow-medium);
    transform: translateY(-1px);
  }

  .analysis-box h3 {
    margin: 0 0 var(--space-2) 0;
    font-size: var(--font-size-base);
    font-weight: var(--font-weight-semibold);
    line-height: var(--line-height-snug);
    color: var(--color-primary);
  }

  .analysis-box p {
    margin: 0;
    font-size: var(--font-size-sm);
    line-height: var(--line-height-relaxed);
    color: var(--color-text);
  }
</style>


