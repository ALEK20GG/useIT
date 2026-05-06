<script lang="ts">
  import { onDestroy } from 'svelte';
  import { PUBLIC_BACKEND_URL } from '$env/static/public';
  import Tooltip from '$lib/Tooltip.svelte';
  const BACKEND_URL = PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

  // ─── Mode switcher ────────────────────────────────────────────────────────
  type Mode = 'foto' | 'qr';
  let activeMode: Mode = 'foto';

  // ─── Shared state ─────────────────────────────────────────────────────────
  let loading = false;
  let errorMessage = '';

  // ─── Photo capture state ──────────────────────────────────────────────────
  let selectedFile: File | null = null;
  let previewUrl: string | null = null;
  let isDragging = false;
  let cameraStream: MediaStream | null = null;
  let cameraActive = false;
  let videoEl: HTMLVideoElement | null = null;
  let canvasEl: HTMLCanvasElement | null = null;
  let capturedPhotoBlob: Blob | null = null;

  // ─── Device recognition result ────────────────────────────────────────────
  type AlternativeMatch = {
    device_id: string;
    device_name: string;
    manufacturer: string;
    model: string;
    confidence: number;
    similarity_reasons: string[];
  };
  type RecognitionResult = {
    device_id: string | null;
    device_name: string | null;
    manufacturer: string | null;
    model: string | null;
    confidence: number;
    alternative_matches: AlternativeMatch[];
    processing_time_ms: number | null;
    error_message: string | null;
    is_mock: boolean;
  };
  let recognitionResult: RecognitionResult | null = null;
  let showManualFallback = false;

  // ─── Manual device selection ──────────────────────────────────────────────
  const DEVICE_CATEGORIES = [
    'Microcontrollore',
    'Single-board computer',
    'Sensore',
    'Attuatore',
    'Modulo wireless',
    'Display',
    'Alimentatore',
    'Altro',
  ];
  let manualDeviceName = '';
  let manualManufacturer = '';
  let manualCategory = '';
  let manualSearchLoading = false;
  let manualSearchResult: string | null = null;

  // ─── QR scanner state ─────────────────────────────────────────────────────
  let qrCameraStream: MediaStream | null = null;
  let qrCameraActive = false;
  let qrVideoEl: HTMLVideoElement | null = null;
  let qrCanvasEl: HTMLCanvasElement | null = null;
  let qrScanInterval: ReturnType<typeof setInterval> | null = null;
  let qrFeedback = '';
  let qrFeedbackType: 'idle' | 'scanning' | 'success' | 'error' = 'idle';
  let qrSelectedFile: File | null = null;
  let qrPreviewUrl: string | null = null;

  type QRResult = {
    content: string;
    format: string;
    confidence: number;
    bounding_box: [number, number, number, number] | null;
    is_mock: boolean;
    device_match: {
      id: string;
      name: string;
      manufacturer: string;
      model: string;
      category: string;
      documentation_urls: string[];
    } | null;
    documentation_urls: string[];
  };
  let qrResult: QRResult | null = null;

  // ─── Photo mode helpers ───────────────────────────────────────────────────

  function handleNewFile(file: File | null) {
    errorMessage = '';
    recognitionResult = null;
    showManualFallback = false;

    if (!file) {
      selectedFile = null;
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      previewUrl = null;
      capturedPhotoBlob = null;
      return;
    }

    const allowed = ['image/jpeg', 'image/png', 'image/webp'];
    if (!allowed.includes(file.type)) {
      errorMessage = 'Formato non supportato. Usa JPEG, PNG o WebP.';
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      errorMessage = 'Il file supera il limite di 10 MB.';
      return;
    }

    selectedFile = file;
    capturedPhotoBlob = null;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(file);
  }

  function onFileChange(event: Event) {
    const target = event.target as HTMLInputElement;
    handleNewFile(target.files?.[0] ?? null);
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
    handleNewFile(event.dataTransfer?.files?.[0] ?? null);
  }

  async function startCamera() {
    errorMessage = '';
    try {
      cameraStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
      });
      cameraActive = true;
      // Bind stream after DOM update
      setTimeout(() => {
        if (videoEl && cameraStream) {
          videoEl.srcObject = cameraStream;
          videoEl.play();
        }
      }, 50);
    } catch {
      errorMessage = 'Impossibile accedere alla fotocamera. Controlla i permessi del browser.';
    }
  }

  function stopCamera() {
    cameraStream?.getTracks().forEach((t) => t.stop());
    cameraStream = null;
    cameraActive = false;
  }

  function capturePhoto() {
    if (!videoEl || !canvasEl) return;
    canvasEl.width = videoEl.videoWidth;
    canvasEl.height = videoEl.videoHeight;
    const ctx = canvasEl.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(videoEl, 0, 0);
    canvasEl.toBlob(
      (blob) => {
        if (!blob) return;
        capturedPhotoBlob = blob;
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        previewUrl = URL.createObjectURL(blob);
        selectedFile = null;
        stopCamera();
        recognitionResult = null;
        showManualFallback = false;
        errorMessage = '';
      },
      'image/jpeg',
      0.92,
    );
  }

  async function recognizeDevice() {
    errorMessage = '';
    recognitionResult = null;
    showManualFallback = false;

    const imageSource = capturedPhotoBlob ?? selectedFile;
    if (!imageSource) {
      errorMessage = 'Prima carica o scatta una foto del dispositivo.';
      return;
    }

    loading = true;
    try {
      const formData = new FormData();
      formData.append('file', imageSource, capturedPhotoBlob ? 'capture.jpg' : (selectedFile?.name ?? 'image.jpg'));

      const res = await fetch(`${BACKEND_URL}/device/recognize`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? `Errore dal server (${res.status})`);
      }

      recognitionResult = await res.json();

      // Show manual fallback if confidence is low or there's an error
      if (
        recognitionResult &&
        (recognitionResult.error_message ||
          recognitionResult.confidence < 0.5 ||
          !recognitionResult.device_name)
      ) {
        showManualFallback = true;
      }
    } catch (err) {
      errorMessage = err instanceof Error ? err.message : 'Errore durante il riconoscimento.';
      showManualFallback = true;
    } finally {
      loading = false;
    }
  }

  async function submitManualSelection() {
    if (!manualDeviceName.trim()) return;
    manualSearchLoading = true;
    manualSearchResult = null;
    try {
      // Search the device database by name
      const res = await fetch(
        `${BACKEND_URL}/device/search?q=${encodeURIComponent(manualDeviceName)}&limit=5`,
      );
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          manualSearchResult = `Trovato: ${data[0].name} (${data[0].manufacturer ?? ''})`;
        } else {
          manualSearchResult = 'Nessun dispositivo trovato nel database. Prova con un altro nome.';
        }
      } else {
        manualSearchResult = 'Ricerca completata. Dispositivo non trovato nel database locale.';
      }
    } catch {
      manualSearchResult = 'Impossibile contattare il server. Riprova più tardi.';
    } finally {
      manualSearchLoading = false;
    }
  }

  // ─── QR scanner helpers ───────────────────────────────────────────────────

  async function startQRCamera() {
    qrFeedback = '';
    qrFeedbackType = 'idle';
    qrResult = null;
    errorMessage = '';
    try {
      qrCameraStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
      });
      qrCameraActive = true;
      setTimeout(() => {
        if (qrVideoEl && qrCameraStream) {
          qrVideoEl.srcObject = qrCameraStream;
          qrVideoEl.play();
          startQRScanLoop();
        }
      }, 50);
    } catch {
      errorMessage = 'Impossibile accedere alla fotocamera. Controlla i permessi del browser.';
    }
  }

  function stopQRCamera() {
    if (qrScanInterval) {
      clearInterval(qrScanInterval);
      qrScanInterval = null;
    }
    qrCameraStream?.getTracks().forEach((t) => t.stop());
    qrCameraStream = null;
    qrCameraActive = false;
    qrFeedbackType = 'idle';
    qrFeedback = '';
  }

  function startQRScanLoop() {
    qrFeedbackType = 'scanning';
    qrFeedback = 'Inquadra il codice QR con la fotocamera…';
    // Capture a frame every 2 seconds and send to backend
    qrScanInterval = setInterval(async () => {
      if (!qrVideoEl || !qrCanvasEl || !qrCameraActive) return;
      if (qrVideoEl.readyState < 2) return; // not ready yet

      qrCanvasEl.width = qrVideoEl.videoWidth;
      qrCanvasEl.height = qrVideoEl.videoHeight;
      const ctx = qrCanvasEl.getContext('2d');
      if (!ctx) return;
      ctx.drawImage(qrVideoEl, 0, 0);

      qrCanvasEl.toBlob(
        async (blob) => {
          if (!blob) return;
          await sendQRFrame(blob);
        },
        'image/jpeg',
        0.85,
      );
    }, 2000);
  }

  async function sendQRFrame(blob: Blob, filename = 'qr-frame.jpg') {
    loading = true;
    try {
      const formData = new FormData();
      formData.append('file', blob, filename);

      const res = await fetch(`${BACKEND_URL}/device/scan-qr`, {
        method: 'POST',
        body: formData,
      });

      if (res.status === 422) {
        // No QR code detected – keep scanning
        qrFeedbackType = 'scanning';
        qrFeedback = 'Nessun QR rilevato. Continua a inquadrare…';
        return;
      }

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        qrFeedbackType = 'error';
        qrFeedback = data.detail ?? `Errore dal server (${res.status})`;
        stopQRCamera();
        return;
      }

      qrResult = await res.json();
      qrFeedbackType = 'success';
      qrFeedback = 'QR rilevato con successo!';
      stopQRCamera();
    } catch {
      qrFeedbackType = 'error';
      qrFeedback = 'Errore di rete durante la scansione.';
    } finally {
      loading = false;
    }
  }

  function onQRFileChange(event: Event) {
    const target = event.target as HTMLInputElement;
    const file = target.files?.[0] ?? null;
    if (!file) return;
    qrSelectedFile = file;
    if (qrPreviewUrl) URL.revokeObjectURL(qrPreviewUrl);
    qrPreviewUrl = URL.createObjectURL(file);
    qrResult = null;
    qrFeedback = '';
    qrFeedbackType = 'idle';
    errorMessage = '';
  }

  async function scanQRFromFile() {
    if (!qrSelectedFile) return;
    qrFeedbackType = 'scanning';
    qrFeedback = 'Analisi del QR in corso…';
    await sendQRFrame(qrSelectedFile, qrSelectedFile.name);
  }

  // ─── Mode switch cleanup ──────────────────────────────────────────────────

  function switchMode(mode: Mode) {
    if (mode === activeMode) return;
    // Stop any active camera
    stopCamera();
    stopQRCamera();
    activeMode = mode;
    errorMessage = '';
  }

  // ─── Lifecycle ────────────────────────────────────────────────────────────

  onDestroy(() => {
    stopCamera();
    stopQRCamera();
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    if (qrPreviewUrl) URL.revokeObjectURL(qrPreviewUrl);
  });

  function confidenceColor(c: number): string {
    if (c >= 0.8) return 'var(--color-success)';
    if (c >= 0.5) return 'var(--color-warning)';
    return 'var(--color-error)';
  }

  function confidenceLabel(c: number): string {
    if (c >= 0.8) return 'Alta';
    if (c >= 0.5) return 'Media';
    return 'Bassa';
  }
</script>

<svelte:head>
  <title>Riconosci dispositivo – UseIt</title>
</svelte:head>

<main class="page page-transition">
  <!-- ── Hero ─────────────────────────────────────────────────────────── -->
  <section class="hero">
    <div class="hero-text">
      <h1>
        Riconosci il tuo dispositivo
        <Tooltip textKey="tooltip.deviceRecognition" position="right" />
      </h1>
      <p>
        Scatta una foto al dispositivo oppure scansiona il suo codice QR per identificarlo
        automaticamente e accedere alla documentazione.
      </p>
    </div>
  </section>

  <!-- ── Mode tabs ─────────────────────────────────────────────────────── -->
  <div class="tabs" role="tablist" aria-label="Modalità di riconoscimento">
    <button
      class="tab-btn"
      class:active={activeMode === 'foto'}
      role="tab"
      aria-selected={activeMode === 'foto'}
      aria-controls="panel-foto"
      id="tab-foto"
      on:click={() => switchMode('foto')}
    >
      📷 Foto dispositivo
    </button>
    <button
      class="tab-btn"
      class:active={activeMode === 'qr'}
      role="tab"
      aria-selected={activeMode === 'qr'}
      aria-controls="panel-qr"
      id="tab-qr"
      on:click={() => switchMode('qr')}
    >
      🔲 Scansiona QR
      <Tooltip textKey="tooltip.qrScanner" position="bottom" />
    </button>
  </div>

  <!-- ── Global error ───────────────────────────────────────────────────── -->
  {#if errorMessage}
    <div class="alert alert-error" role="alert" aria-live="assertive">
      <span class="alert-icon" aria-hidden="true">⚠️</span>
      {errorMessage}
    </div>
  {/if}

  <!-- ══════════════════════════════════════════════════════════════════════
       PANEL: Foto dispositivo
  ══════════════════════════════════════════════════════════════════════ -->
  {#if activeMode === 'foto'}
    <section
      id="panel-foto"
      role="tabpanel"
      aria-labelledby="tab-foto"
      class="panel layout"
    >
      <!-- Left: capture area -->
      <div class="capture-area">
        <!-- Camera live view -->
        {#if cameraActive}
          <div class="camera-container" aria-label="Anteprima fotocamera">
            <!-- svelte-ignore a11y-media-has-caption -->
            <video
              bind:this={videoEl}
              class="camera-video"
              autoplay
              playsinline
              aria-label="Flusso video fotocamera"
            ></video>
            <canvas bind:this={canvasEl} class="hidden-canvas" aria-hidden="true"></canvas>
            <div class="camera-controls">
              <button
                class="btn btn-primary btn-lg"
                on:click={capturePhoto}
                aria-label="Scatta foto"
              >
                📸 Scatta foto
              </button>
              <button
                class="btn btn-secondary"
                on:click={stopCamera}
                aria-label="Chiudi fotocamera"
              >
                ✕ Chiudi
              </button>
            </div>
          </div>
        {:else}
          <!-- Drop zone / preview -->
          <div
            class="dropzone"
            class:is-dragging={isDragging}
            role="button"
            tabindex="0"
            aria-label="Area di caricamento immagine – trascina qui o clicca per selezionare"
            on:dragover|preventDefault={onDragOver}
            on:dragleave={onDragLeave}
            on:drop={onDrop}
            on:keydown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                document.getElementById('file-input-foto')?.click();
              }
            }}
          >
            <div class="dropzone-inner">
              {#if previewUrl}
                <img src={previewUrl} alt="Anteprima foto dispositivo" class="preview" />
                <p class="preview-hint">Immagine pronta. Premi <strong>Riconosci dispositivo</strong>.</p>
              {:else}
                <div class="placeholder-icon" aria-hidden="true">📷</div>
                <p class="dropzone-text">
                  <strong>Trascina qui</strong> una foto del dispositivo
                </p>
              {/if}
            </div>
          </div>

          <!-- Upload / camera buttons -->
          <div class="upload-actions">
            <label class="btn btn-secondary" for="file-input-foto">
              🖼️ Scegli dalla galleria
            </label>
            <input
              id="file-input-foto"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              class="sr-only"
              on:change={onFileChange}
              aria-label="Seleziona immagine dalla galleria"
            />

            <button class="btn btn-secondary" on:click={startCamera} aria-label="Apri fotocamera">
              📷 Usa fotocamera
            </button>
          </div>
          <p class="upload-hint">Formati supportati: JPEG, PNG, WebP · Max 10 MB</p>
        {/if}
      </div>

      <!-- Right: results panel -->
      <div class="side-card">
        <h2>Riconoscimento dispositivo</h2>
        <p class="muted">
          Carica o scatta una foto del dispositivo, poi premi il pulsante per identificarlo.
        </p>

        <button
          class="btn btn-primary"
          on:click={recognizeDevice}
          disabled={loading || (!selectedFile && !capturedPhotoBlob)}
          aria-busy={loading}
        >
          {#if loading}
            <span class="spinner spinner-sm" aria-hidden="true"></span>
            <span>Riconoscimento in corso…</span>
          {:else}
            🔍 Riconosci dispositivo
          {/if}
        </button>

        <!-- Recognition result -->
        {#if recognitionResult}
          <div class="result-box fade-in" aria-live="polite" aria-label="Risultato riconoscimento">
            {#if recognitionResult.device_name && !recognitionResult.error_message}
              <div class="result-header">
                <h3 class="result-device-name">{recognitionResult.device_name}</h3>
                <span
                  class="confidence-badge"
                  style="background-color: {confidenceColor(recognitionResult.confidence)}20; color: {confidenceColor(recognitionResult.confidence)}; border-color: {confidenceColor(recognitionResult.confidence)}40;"
                  aria-label="Confidenza: {confidenceLabel(recognitionResult.confidence)} ({Math.round(recognitionResult.confidence * 100)}%)"
                >
                  {confidenceLabel(recognitionResult.confidence)} · {Math.round(recognitionResult.confidence * 100)}%
                </span>
              </div>

              {#if recognitionResult.manufacturer}
                <p class="result-meta">
                  <span class="meta-label">Produttore:</span>
                  {recognitionResult.manufacturer}
                </p>
              {/if}
              {#if recognitionResult.model}
                <p class="result-meta">
                  <span class="meta-label">Modello:</span>
                  {recognitionResult.model}
                </p>
              {/if}
              {#if recognitionResult.processing_time_ms}
                <p class="result-meta result-meta-subtle">
                  Elaborato in {recognitionResult.processing_time_ms.toFixed(0)} ms
                  {#if recognitionResult.is_mock}
                    <span class="pill-mock" aria-label="Servizio simulato attivo">simulato</span>
                    <Tooltip textKey="tooltip.mockService" position="top" />
                  {/if}
                </p>
              {/if}

              <!-- Alternative matches -->
              {#if recognitionResult.alternative_matches.length > 0}
                <details class="alternatives">
                  <summary>Altre possibilità ({recognitionResult.alternative_matches.length})</summary>
                  <ul class="alt-list" role="list">
                    {#each recognitionResult.alternative_matches as alt}
                      <li class="alt-item">
                        <span class="alt-name">{alt.device_name}</span>
                        <span class="alt-conf">{Math.round(alt.confidence * 100)}%</span>
                      </li>
                    {/each}
                  </ul>
                </details>
              {/if}
            {:else}
              <div class="result-error" role="alert">
                <p>
                  {recognitionResult.error_message ?? 'Dispositivo non riconosciuto con sufficiente certezza.'}
                </p>
              </div>
            {/if}
          </div>
        {/if}

        <!-- Manual fallback -->
        {#if showManualFallback}
          <div class="manual-fallback fade-in" aria-label="Selezione manuale dispositivo">
            <h3>Selezione manuale</h3>
            <p class="muted">
              Il riconoscimento automatico non ha prodotto risultati certi. Inserisci i dati
              manualmente per trovare la documentazione.
            </p>

            <label class="field-label" for="manual-device-name">Nome dispositivo</label>
            <input
              id="manual-device-name"
              class="field-input"
              type="text"
              bind:value={manualDeviceName}
              placeholder="es. Arduino Uno, Raspberry Pi 4…"
              aria-required="true"
            />

            <label class="field-label" for="manual-manufacturer">Produttore (opzionale)</label>
            <input
              id="manual-manufacturer"
              class="field-input"
              type="text"
              bind:value={manualManufacturer}
              placeholder="es. Arduino, Raspberry Pi Foundation…"
            />

            <label class="field-label" for="manual-category">Categoria</label>
            <select id="manual-category" class="field-input" bind:value={manualCategory}>
              <option value="">-- Seleziona categoria --</option>
              {#each DEVICE_CATEGORIES as cat}
                <option value={cat}>{cat}</option>
              {/each}
            </select>

            <button
              class="btn btn-primary"
              on:click={submitManualSelection}
              disabled={manualSearchLoading || !manualDeviceName.trim()}
              aria-busy={manualSearchLoading}
            >
              {#if manualSearchLoading}
                <span class="spinner spinner-sm" aria-hidden="true"></span>
                <span>Ricerca in corso…</span>
              {:else}
                🔎 Cerca nel database
              {/if}
            </button>

            {#if manualSearchResult}
              <p class="manual-result fade-in" aria-live="polite">{manualSearchResult}</p>
            {/if}
          </div>
        {/if}
      </div>
    </section>
  {/if}

  <!-- ══════════════════════════════════════════════════════════════════════
       PANEL: Scansiona QR
  ══════════════════════════════════════════════════════════════════════ -->
  {#if activeMode === 'qr'}
    <section
      id="panel-qr"
      role="tabpanel"
      aria-labelledby="tab-qr"
      class="panel layout"
    >
      <!-- Left: QR scanner area -->
      <div class="capture-area">
        {#if qrCameraActive}
          <div class="camera-container" aria-label="Scanner QR attivo">
            <!-- svelte-ignore a11y-media-has-caption -->
            <video
              bind:this={qrVideoEl}
              class="camera-video"
              autoplay
              playsinline
              aria-label="Flusso video scanner QR"
            ></video>
            <canvas bind:this={qrCanvasEl} class="hidden-canvas" aria-hidden="true"></canvas>

            <!-- Real-time feedback overlay -->
            <div
              class="qr-overlay"
              class:qr-overlay-scanning={qrFeedbackType === 'scanning'}
              class:qr-overlay-success={qrFeedbackType === 'success'}
              class:qr-overlay-error={qrFeedbackType === 'error'}
              aria-live="polite"
              aria-label="Stato scansione QR"
            >
              <div class="qr-viewfinder" aria-hidden="true">
                <div class="qr-corner qr-corner-tl"></div>
                <div class="qr-corner qr-corner-tr"></div>
                <div class="qr-corner qr-corner-bl"></div>
                <div class="qr-corner qr-corner-br"></div>
                {#if qrFeedbackType === 'scanning'}
                  <div class="qr-scan-line" aria-hidden="true"></div>
                {/if}
              </div>
              {#if qrFeedback}
                <p class="qr-feedback-text">{qrFeedback}</p>
              {/if}
            </div>

            <div class="camera-controls">
              <button
                class="btn btn-secondary"
                on:click={stopQRCamera}
                aria-label="Ferma scansione QR"
              >
                ✕ Ferma scansione
              </button>
            </div>
          </div>
        {:else}
          <div class="qr-start-area">
            <div class="qr-icon" aria-hidden="true">🔲</div>
            <p class="qr-start-text">
              Avvia la fotocamera per scansionare un codice QR in tempo reale, oppure carica
              un'immagine contenente il QR.
            </p>
          </div>

          <div class="upload-actions">
            <button
              class="btn btn-primary"
              on:click={startQRCamera}
              aria-label="Avvia scanner QR con fotocamera"
            >
              📷 Avvia scanner QR
            </button>

            <label class="btn btn-secondary" for="file-input-qr">
              🖼️ Carica immagine QR
            </label>
            <input
              id="file-input-qr"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              class="sr-only"
              on:change={onQRFileChange}
              aria-label="Seleziona immagine con codice QR"
            />
          </div>

          {#if qrPreviewUrl}
            <div class="qr-file-preview fade-in">
              <img src={qrPreviewUrl} alt="Anteprima immagine QR" class="preview" />
              <button
                class="btn btn-primary"
                on:click={scanQRFromFile}
                disabled={loading}
                aria-busy={loading}
              >
                {#if loading}
                  <span class="spinner spinner-sm" aria-hidden="true"></span>
                  <span>Scansione in corso…</span>
                {:else}
                  🔍 Scansiona QR dall'immagine
                {/if}
              </button>
            </div>
          {/if}
        {/if}

        <!-- Feedback when not in camera mode -->
        {#if !qrCameraActive && qrFeedback}
          <div
            class="qr-status-bar"
            class:qr-status-success={qrFeedbackType === 'success'}
            class:qr-status-error={qrFeedbackType === 'error'}
            class:qr-status-scanning={qrFeedbackType === 'scanning'}
            role="status"
            aria-live="polite"
          >
            {qrFeedback}
          </div>
        {/if}
      </div>

      <!-- Right: QR result panel -->
      <div class="side-card">
        <h2>Risultato scansione QR</h2>
        <p class="muted">
          Inquadra il codice QR del dispositivo con la fotocamera. La scansione avviene
          automaticamente ogni 2 secondi.
        </p>

        {#if qrResult}
          <div class="result-box fade-in" aria-live="polite" aria-label="Risultato QR">
            <div class="qr-content-box">
              <p class="meta-label">Contenuto QR:</p>
              <p class="qr-content-value">{qrResult.content}</p>
              <p class="result-meta result-meta-subtle">
                Formato: {qrResult.format} · Confidenza: {Math.round(qrResult.confidence * 100)}%
                {#if qrResult.is_mock}
                  <span class="pill-mock" aria-label="Servizio simulato attivo">simulato</span>
                {/if}
              </p>
            </div>

            {#if qrResult.device_match}
              <div class="device-match-box">
                <h3 class="result-device-name">{qrResult.device_match.name}</h3>
                {#if qrResult.device_match.manufacturer}
                  <p class="result-meta">
                    <span class="meta-label">Produttore:</span>
                    {qrResult.device_match.manufacturer}
                  </p>
                {/if}
                {#if qrResult.device_match.model}
                  <p class="result-meta">
                    <span class="meta-label">Modello:</span>
                    {qrResult.device_match.model}
                  </p>
                {/if}
                {#if qrResult.device_match.category}
                  <p class="result-meta">
                    <span class="meta-label">Categoria:</span>
                    {qrResult.device_match.category}
                  </p>
                {/if}

                {#if qrResult.documentation_urls.length > 0}
                  <div class="doc-links">
                    <p class="meta-label">Documentazione:</p>
                    <ul role="list" class="doc-list">
                      {#each qrResult.documentation_urls as url}
                        <li>
                          <a href={url} target="_blank" rel="noopener noreferrer" class="doc-link">
                            📄 {url}
                          </a>
                        </li>
                      {/each}
                    </ul>
                  </div>
                {/if}
              </div>
            {:else}
              <div class="qr-no-device" role="status">
                <p>
                  QR decodificato, ma nessun dispositivo corrispondente trovato nel database.
                </p>
                <p class="muted">
                  Prova la modalità <strong>Foto dispositivo</strong> o la selezione manuale.
                </p>
              </div>
            {/if}
          </div>
        {:else if !qrCameraActive && qrFeedbackType === 'error'}
          <div class="alert alert-error" role="alert">
            <p>QR non valido o non riconosciuto.</p>
            <p class="muted">
              Assicurati che il codice QR sia leggibile e riprova, oppure usa la modalità
              <strong>Foto dispositivo</strong>.
            </p>
          </div>
        {:else}
          <p class="muted">
            Il risultato della scansione apparirà qui dopo aver rilevato un codice QR valido.
          </p>
        {/if}
      </div>
    </section>
  {/if}
</main>

<style>
  /* ── Page layout ─────────────────────────────────────────────────────── */
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
    max-width: 42rem;
    font-size: var(--font-size-base);
    line-height: var(--line-height-relaxed);
  }

  /* ── Tabs ────────────────────────────────────────────────────────────── */
  .tabs {
    display: flex;
    gap: var(--space-2);
    margin-bottom: var(--space-6);
    border-bottom: 2px solid var(--color-border);
    padding-bottom: 0;
  }

  .tab-btn {
    padding: var(--space-3) var(--space-5);
    border: none;
    background: transparent;
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    color: var(--color-text-muted);
    cursor: pointer;
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
    border-radius: var(--space-2) var(--space-2) 0 0;
    transition: all 0.2s ease;
    min-height: 44px;
  }

  .tab-btn:hover:not(.active) {
    color: var(--color-primary);
    background-color: var(--color-primary-subtle);
  }

  .tab-btn:focus-visible {
    outline: 2px solid var(--color-primary);
    outline-offset: 2px;
  }

  .tab-btn.active {
    color: var(--color-primary);
    border-bottom-color: var(--color-primary);
    font-weight: var(--font-weight-semibold);
  }

  /* ── Alert ───────────────────────────────────────────────────────────── */
  .alert {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    border-radius: var(--space-2);
    margin-bottom: var(--space-4);
    font-size: var(--font-size-sm);
    line-height: var(--line-height-relaxed);
  }

  .alert-error {
    background-color: var(--color-error-subtle);
    color: var(--color-error);
    border: 1px solid var(--color-error-muted);
  }

  .alert-icon {
    flex-shrink: 0;
    font-size: var(--font-size-base);
  }

  /* ── Panel layout ────────────────────────────────────────────────────── */
  .panel {
    display: grid;
    gap: var(--space-6);
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

  /* ── Capture area ────────────────────────────────────────────────────── */
  .capture-area {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  /* ── Camera view ─────────────────────────────────────────────────────── */
  .camera-container {
    position: relative;
    border-radius: var(--space-3);
    overflow: hidden;
    background: #000;
    aspect-ratio: 16 / 9;
  }

  .camera-video {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .hidden-canvas {
    display: none;
  }

  .camera-controls {
    position: absolute;
    bottom: var(--space-4);
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    gap: var(--space-3);
    z-index: 10;
  }

  /* ── Drop zone ───────────────────────────────────────────────────────── */
  .dropzone {
    background: var(--color-bg-secondary);
    border-radius: var(--space-3);
    padding: var(--space-8) var(--space-6);
    border: 2px dashed var(--color-border);
    transition: all 0.2s ease;
    cursor: pointer;
    min-height: 200px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .dropzone:hover:not(.is-dragging) {
    border-color: var(--color-primary-muted);
    background-color: var(--color-primary-subtle);
  }

  .dropzone:focus-visible {
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
    gap: var(--space-3);
    text-align: center;
  }

  .placeholder-icon {
    font-size: var(--font-size-5xl);
    line-height: var(--line-height-tight);
  }

  .dropzone-text {
    font-size: var(--font-size-base);
    color: var(--color-text-muted);
    margin: 0;
  }

  .preview {
    max-width: 100%;
    max-height: 300px;
    border-radius: var(--space-2);
    box-shadow: 0 1px var(--space-3) var(--color-shadow-medium);
    object-fit: contain;
  }

  .preview-hint {
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
    margin: 0;
  }

  /* ── Upload actions ──────────────────────────────────────────────────── */
  .upload-actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
  }

  .upload-hint {
    font-size: var(--font-size-xs);
    color: var(--color-text-subtle);
    margin: 0;
  }

  /* ── Side card ───────────────────────────────────────────────────────── */
  .side-card {
    background: var(--color-card-bg);
    border-radius: var(--space-3);
    padding: var(--space-6);
    box-shadow: 0 1px var(--space-1) var(--color-shadow);
    border: 1px solid var(--color-border);
    transition: all 0.2s ease;
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .side-card:hover {
    box-shadow: 0 var(--space-2) var(--space-4) var(--color-shadow-medium);
  }

  .side-card h2 {
    margin: 0;
    font-size: var(--font-size-xl);
    font-weight: var(--font-weight-semibold);
    line-height: var(--line-height-snug);
    color: var(--color-text);
  }

  .muted {
    font-size: var(--font-size-sm);
    line-height: var(--line-height-relaxed);
    color: var(--color-text-muted);
    margin: 0;
  }

  /* ── Result box ──────────────────────────────────────────────────────── */
  .result-box {
    padding: var(--space-4);
    border-radius: var(--space-2);
    background: var(--color-bg-secondary);
    border: 1px solid var(--color-border);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .result-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .result-device-name {
    margin: 0;
    font-size: var(--font-size-lg);
    font-weight: var(--font-weight-semibold);
    color: var(--color-primary);
    line-height: var(--line-height-snug);
  }

  .confidence-badge {
    display: inline-flex;
    align-items: center;
    padding: var(--space-1) var(--space-3);
    border-radius: 999px;
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-semibold);
    border: 1px solid;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .result-meta {
    font-size: var(--font-size-sm);
    color: var(--color-text);
    margin: 0;
    line-height: var(--line-height-normal);
  }

  .result-meta-subtle {
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .meta-label {
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-muted);
    margin-right: var(--space-1);
  }

  .pill-mock {
    display: inline-block;
    padding: 1px var(--space-2);
    border-radius: 999px;
    background: var(--color-warning-subtle);
    color: var(--color-warning);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
    border: 1px solid var(--color-warning-muted);
  }

  /* ── Alternatives ────────────────────────────────────────────────────── */
  .alternatives {
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
  }

  .alternatives summary {
    cursor: pointer;
    font-weight: var(--font-weight-medium);
    color: var(--color-primary);
    padding: var(--space-1) 0;
  }

  .alternatives summary:focus-visible {
    outline: 2px solid var(--color-primary);
    outline-offset: 2px;
    border-radius: var(--space-1);
  }

  .alt-list {
    list-style: none;
    padding: var(--space-2) 0 0 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .alt-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-2) var(--space-3);
    background: var(--color-bg-tertiary);
    border-radius: var(--space-1);
    font-size: var(--font-size-xs);
  }

  .alt-name {
    color: var(--color-text);
    font-weight: var(--font-weight-medium);
  }

  .alt-conf {
    color: var(--color-text-muted);
  }

  .result-error {
    padding: var(--space-3);
    background: var(--color-error-subtle);
    border: 1px solid var(--color-error-muted);
    border-radius: var(--space-2);
    color: var(--color-error);
    font-size: var(--font-size-sm);
  }

  .result-error p {
    margin: 0;
  }

  /* ── Manual fallback ─────────────────────────────────────────────────── */
  .manual-fallback {
    padding: var(--space-4);
    border-radius: var(--space-2);
    background: var(--color-bg-secondary);
    border: 1px solid var(--color-border);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .manual-fallback h3 {
    margin: 0;
    font-size: var(--font-size-base);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text);
  }

  .field-label {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    color: var(--color-text);
    display: block;
    margin-bottom: var(--space-1);
  }

  .field-input {
    width: 100%;
    padding: var(--space-3);
    border: 2px solid var(--color-border);
    border-radius: var(--space-2);
    font-size: var(--font-size-sm);
    background: var(--color-input-bg);
    color: var(--color-text);
    transition: border-color 0.2s ease;
    box-sizing: border-box;
    min-height: 44px;
    font-family: inherit;
  }

  .field-input:focus {
    outline: none;
    border-color: var(--color-primary);
    box-shadow: 0 0 0 3px var(--color-primary-subtle);
  }

  .field-input:hover:not(:focus) {
    border-color: var(--color-primary-muted);
  }

  .manual-result {
    font-size: var(--font-size-sm);
    padding: var(--space-3);
    border-radius: var(--space-2);
    background: var(--color-success-subtle);
    color: var(--color-success);
    border: 1px solid var(--color-success-muted);
    margin: 0;
  }

  /* ── QR scanner ──────────────────────────────────────────────────────── */
  .qr-start-area {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-4);
    padding: var(--space-8) var(--space-6);
    background: var(--color-bg-secondary);
    border-radius: var(--space-3);
    border: 2px dashed var(--color-border);
    text-align: center;
  }

  .qr-icon {
    font-size: 4rem;
    line-height: 1;
  }

  .qr-start-text {
    font-size: var(--font-size-base);
    color: var(--color-text-muted);
    max-width: 28rem;
    margin: 0;
    line-height: var(--line-height-relaxed);
  }

  /* QR overlay on camera */
  .qr-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-4);
    pointer-events: none;
  }

  .qr-viewfinder {
    position: relative;
    width: 200px;
    height: 200px;
  }

  .qr-corner {
    position: absolute;
    width: 24px;
    height: 24px;
    border-color: white;
    border-style: solid;
    opacity: 0.9;
  }

  .qr-corner-tl { top: 0; left: 0; border-width: 3px 0 0 3px; }
  .qr-corner-tr { top: 0; right: 0; border-width: 3px 3px 0 0; }
  .qr-corner-bl { bottom: 0; left: 0; border-width: 0 0 3px 3px; }
  .qr-corner-br { bottom: 0; right: 0; border-width: 0 3px 3px 0; }

  .qr-overlay-success .qr-corner {
    border-color: var(--color-success);
  }

  .qr-overlay-error .qr-corner {
    border-color: var(--color-error);
  }

  .qr-scan-line {
    position: absolute;
    left: 4px;
    right: 4px;
    height: 2px;
    background: var(--color-primary);
    animation: qr-scan 2s linear infinite;
    opacity: 0.8;
  }

  @keyframes qr-scan {
    0% { top: 4px; }
    100% { top: calc(100% - 6px); }
  }

  .qr-feedback-text {
    background: rgba(0, 0, 0, 0.65);
    color: white;
    padding: var(--space-2) var(--space-4);
    border-radius: 999px;
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    margin: 0;
    backdrop-filter: blur(4px);
  }

  .qr-status-bar {
    padding: var(--space-3) var(--space-4);
    border-radius: var(--space-2);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    text-align: center;
  }

  .qr-status-scanning {
    background: var(--color-primary-subtle);
    color: var(--color-primary);
    border: 1px solid var(--color-primary-muted);
  }

  .qr-status-success {
    background: var(--color-success-subtle);
    color: var(--color-success);
    border: 1px solid var(--color-success-muted);
  }

  .qr-status-error {
    background: var(--color-error-subtle);
    color: var(--color-error);
    border: 1px solid var(--color-error-muted);
  }

  .qr-file-preview {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-4);
  }

  /* ── QR result ───────────────────────────────────────────────────────── */
  .qr-content-box {
    padding: var(--space-3);
    background: var(--color-bg-tertiary);
    border-radius: var(--space-2);
    border: 1px solid var(--color-border);
  }

  .qr-content-value {
    font-family: var(--font-family-mono);
    font-size: var(--font-size-xs);
    color: var(--color-text);
    word-break: break-all;
    margin: var(--space-1) 0 0 0;
  }

  .device-match-box {
    padding: var(--space-3);
    background: var(--color-primary-subtle);
    border-radius: var(--space-2);
    border: 1px solid var(--color-primary-muted);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .doc-links {
    margin-top: var(--space-2);
  }

  .doc-list {
    list-style: none;
    padding: 0;
    margin: var(--space-2) 0 0 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .doc-link {
    font-size: var(--font-size-xs);
    color: var(--color-primary);
    word-break: break-all;
    text-decoration: underline;
  }

  .doc-link:hover {
    color: var(--color-primary-hover);
  }

  .qr-no-device {
    padding: var(--space-3);
    background: var(--color-warning-subtle);
    border: 1px solid var(--color-warning-muted);
    border-radius: var(--space-2);
    font-size: var(--font-size-sm);
    color: var(--color-warning);
  }

  .qr-no-device p {
    margin: 0 0 var(--space-2) 0;
  }

  .qr-no-device p:last-child {
    margin: 0;
  }

  /* ── Accessibility ───────────────────────────────────────────────────── */
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

  /* ── Reduced motion ──────────────────────────────────────────────────── */
  @media (prefers-reduced-motion: reduce) {
    .qr-scan-line {
      animation: none;
      top: 50%;
    }
  }
</style>


