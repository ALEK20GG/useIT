<script lang="ts">
  const BACKEND_URL = 'http://127.0.0.1:8000';

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

<main class="page">
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
      on:dragover|preventDefault={onDragOver}
      on:dragleave={onDragLeave}
      on:drop={onDrop}
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

          <label class="button secondary">
            Scegli dalla galleria
            <input type="file" accept="image/*" on:change={onFileChange} />
          </label>

          <p class="hint">
            Su smartphone puoi anche usare la fotocamera:
          </p>

          <label class="button ghost">
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

      <button class="button primary" on:click={analyze} disabled={loading}>
        {loading ? 'Analisi in corso…' : 'Analizza prodotto'}
      </button>

      {#if errorMessage}
        <p class="status error">{errorMessage}</p>
      {/if}

      {#if analysisSummary}
        <div class="analysis-box">
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
    padding: 2rem 1.5rem 4rem;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  }

  .hero {
    margin-bottom: 2rem;
  }

  .hero-text h1 {
    font-size: 2rem;
    margin-bottom: 0.5rem;
  }

  .hero-text p {
    color: #6b7280;
    max-width: 38rem;
  }

  .layout {
    display: grid;
    gap: 1.75rem;
  }

  @media (min-width: 900px) {
    .layout {
      grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
      align-items: flex-start;
    }
  }

  .dropzone {
    background: #f9fafb;
    border-radius: 1rem;
    padding: 1.25rem;
    border: 2px dashed #cbd5f5;
    transition: border-color 0.15s ease-out, background-color 0.15s ease-out,
      box-shadow 0.15s ease-out;
  }

  .dropzone.is-dragging {
    border-color: #4f46e5;
    background-color: #eef2ff;
    box-shadow: 0 18px 40px rgba(79, 70, 229, 0.25);
  }

  .dropzone-inner {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1rem;
  }

  .preview {
    max-width: 100%;
    max-height: 320px;
    border-radius: 0.75rem;
    box-shadow: 0 16px 30px rgba(15, 23, 42, 0.35);
    object-fit: cover;
  }

  .placeholder-icon {
    font-size: 3rem;
  }

  .instructions {
    text-align: center;
  }

  .instructions p {
    margin: 0.25rem 0;
  }

  .instructions .hint {
    margin-top: 0.75rem;
    font-size: 0.85rem;
    color: #6b7280;
  }

  .button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    padding: 0.55rem 1.3rem;
    border-radius: 999px;
    font-size: 0.95rem;
    font-weight: 600;
    border: none;
    cursor: pointer;
    transition: transform 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease,
      color 0.15s ease;
  }

  .button input[type='file'] {
    display: none;
  }

  .button.primary {
    background: linear-gradient(135deg, #4f46e5, #6366f1);
    color: white;
    box-shadow: 0 12px 25px rgba(55, 48, 163, 0.45);
  }

  .button.primary:hover:enabled {
    transform: translateY(-1px);
    box-shadow: 0 16px 30px rgba(55, 48, 163, 0.55);
  }

  .button.secondary {
    background-color: #111827;
    color: white;
  }

  .button.secondary:hover {
    background-color: #020617;
  }

  .button.ghost {
    background-color: transparent;
    color: #111827;
    border: 1px solid #d1d5db;
  }

  .side-card {
    background: #ffffff;
    border-radius: 1rem;
    padding: 1.5rem 1.5rem 1.75rem;
    box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
    border: 1px solid #e5e7eb;
  }

  .side-card h2 {
    margin-bottom: 0.35rem;
    font-size: 1.25rem;
  }

  .muted {
    font-size: 0.9rem;
    color: #6b7280;
    margin-bottom: 1rem;
  }

  .status {
    margin-top: 0.75rem;
    font-size: 0.85rem;
  }

  .status.error {
    color: #b91c1c;
  }

  .analysis-box {
    margin-top: 1rem;
    padding: 0.8rem 0.9rem;
    border-radius: 0.75rem;
    background: #eff6ff;
    border: 1px solid #bfdbfe;
  }

  .analysis-box h3 {
    margin: 0 0 0.35rem;
    font-size: 0.95rem;
  }

  .analysis-box p {
    margin: 0;
    font-size: 0.9rem;
    color: #1f2933;
  }
</style>


