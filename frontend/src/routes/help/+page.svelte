<script lang="ts">
  /**
   * Help and documentation page.
   *
   * Implements Requirements 20.1, 20.3, 20.5:
   * - In-application help text and tooltips
   * - User manuals for device recognition, search, and content management
   * - Available in both Italian and English
   */

  import { t, setLocale, getLocale } from '$lib/i18n';
  import type { Locale } from '$lib/i18n';
  import Tooltip from '$lib/Tooltip.svelte';

  let locale: Locale = getLocale();
  let activeSection = 'deviceRecognition';

  function switchLocale(l: Locale) {
    locale = l;
    setLocale(l);
  }

  const sections = [
    { id: 'deviceRecognition', icon: '📷' },
    { id: 'search', icon: '🔍' },
    { id: 'contentManagement', icon: '📄' },
    { id: 'userArea', icon: '👤' },
    { id: 'api', icon: '⚙️' },
  ];
</script>

<svelte:head>
  <title>{t('help.title')} – UseIt</title>
</svelte:head>

<div class="page page-transition">
  <!-- Hero -->
  <section class="hero">
    <div class="hero-text">
      <h1>{t('help.title')}</h1>
      <p>{t('help.subtitle')}</p>
    </div>

    <!-- Language switcher -->
    <div class="locale-switcher" role="group" aria-label="Seleziona lingua / Select language">
      <button
        class="locale-btn"
        class:active={locale === 'it'}
        type="button"
        on:click={() => switchLocale('it')}
        aria-pressed={locale === 'it'}
      >
        🇮🇹 Italiano
      </button>
      <button
        class="locale-btn"
        class:active={locale === 'en'}
        type="button"
        on:click={() => switchLocale('en')}
        aria-pressed={locale === 'en'}
      >
        🇬🇧 English
      </button>
    </div>
  </section>

  <div class="help-layout">
    <!-- Sidebar navigation -->
    <nav class="help-nav" aria-label="Sezioni della guida">
      {#each sections as section}
        <button
          class="help-nav-item"
          class:active={activeSection === section.id}
          type="button"
          on:click={() => (activeSection = section.id)}
          aria-current={activeSection === section.id ? 'page' : undefined}
        >
          <span class="help-nav-icon" aria-hidden="true">{section.icon}</span>
          <span>{t(`help.section.${section.id}` as import('$lib/i18n').TranslationKey)}</span>
        </button>
      {/each}
    </nav>

    <!-- Content area -->
    <main class="help-content" id="help-main">

      <!-- Device Recognition -->
      {#if activeSection === 'deviceRecognition'}
        <article class="help-article fade-in">
          <div class="article-header">
            <span class="article-icon" aria-hidden="true">📷</span>
            <h2>{t('help.section.deviceRecognition')}</h2>
          </div>

          <p class="intro">{t('help.deviceRecognition.intro')}</p>

          <h3>Come funziona / How it works</h3>
          <ol class="steps">
            <li>{t('help.deviceRecognition.step1')}</li>
            <li>{t('help.deviceRecognition.step2')}</li>
            <li>{t('help.deviceRecognition.step3')}</li>
            <li>{t('help.deviceRecognition.step4')}</li>
          </ol>

          <div class="tip-box">
            <span class="tip-icon" aria-hidden="true">💡</span>
            <p>{t('help.deviceRecognition.fallback')}</p>
          </div>

          <h3>Formati immagine supportati / Supported image formats</h3>
          <ul class="feature-list">
            <li>JPEG / JPG</li>
            <li>PNG</li>
            <li>WebP</li>
            <li>Dimensione massima / Max size: 10 MB</li>
          </ul>

          <h3>Livelli di confidenza / Confidence levels</h3>
          <div class="confidence-guide">
            <div class="confidence-item">
              <span class="confidence-dot confidence-high" aria-hidden="true"></span>
              <div>
                <strong>Alta / High (&gt;80%)</strong>
                <p>Il dispositivo è stato identificato con alta certezza.</p>
              </div>
              <Tooltip textKey="tooltip.confidenceScore" position="right" />
            </div>
            <div class="confidence-item">
              <span class="confidence-dot confidence-medium" aria-hidden="true"></span>
              <div>
                <strong>Media / Medium (50–80%)</strong>
                <p>Identificazione probabile, verifica il risultato.</p>
              </div>
            </div>
            <div class="confidence-item">
              <span class="confidence-dot confidence-low" aria-hidden="true"></span>
              <div>
                <strong>Bassa / Low (&lt;50%)</strong>
                <p>Usa la selezione manuale per confermare.</p>
              </div>
            </div>
          </div>
        </article>

      <!-- Semantic Search -->
      {:else if activeSection === 'search'}
        <article class="help-article fade-in">
          <div class="article-header">
            <span class="article-icon" aria-hidden="true">🔍</span>
            <h2>{t('help.section.search')}</h2>
          </div>

          <p class="intro">{t('help.search.intro')}</p>

          <h3>Come cercare / How to search</h3>
          <ol class="steps">
            <li>{t('help.search.step1')}</li>
            <li>{t('help.search.step2')}</li>
            <li>{t('help.search.step3')}</li>
            <li>{t('help.search.step4')}</li>
          </ol>

          <div class="tip-box">
            <span class="tip-icon" aria-hidden="true">💡</span>
            <p>{t('help.search.tip')}</p>
          </div>

          <h3>Tipi di ricerca / Search types</h3>
          <div class="feature-cards">
            <div class="feature-card">
              <h4>🧠 Semantica / Semantic</h4>
              <p>Comprende il significato della domanda. Ideale per domande in linguaggio naturale.</p>
              <Tooltip textKey="tooltip.semanticSearch" />
            </div>
            <div class="feature-card">
              <h4>🔤 Ibrida / Hybrid</h4>
              <p>Combina ricerca semantica e per parole chiave per risultati più precisi.</p>
              <Tooltip textKey="tooltip.hybridSearch" />
            </div>
            <div class="feature-card">
              <h4>📁 Per cartella / By folder</h4>
              <p>Limita la ricerca a una cartella specifica (Dispositivi, Appunti, Scuola).</p>
              <Tooltip textKey="tooltip.folderFilter" />
            </div>
          </div>
        </article>

      <!-- Content Management -->
      {:else if activeSection === 'contentManagement'}
        <article class="help-article fade-in">
          <div class="article-header">
            <span class="article-icon" aria-hidden="true">📄</span>
            <h2>{t('help.section.contentManagement')}</h2>
          </div>

          <p class="intro">{t('help.contentManagement.intro')}</p>

          <h3>Caricare un documento / Upload a document</h3>
          <ol class="steps">
            <li>{t('help.contentManagement.step1')}</li>
            <li>{t('help.contentManagement.step2')}</li>
            <li>
              {t('help.contentManagement.step3')}
              <Tooltip textKey="tooltip.uploadFolder" />
            </li>
            <li>{t('help.contentManagement.step4')}</li>
          </ol>

          <div class="tip-box">
            <span class="tip-icon" aria-hidden="true">📋</span>
            <p>{t('help.contentManagement.formats')}</p>
          </div>

          <h3>Gestione file / File management</h3>
          <ul class="feature-list">
            <li>Visualizza tutti i file caricati organizzati per cartella.</li>
            <li>Elimina file singoli o multipli.
              <Tooltip textKey="tooltip.bulkDelete" position="right" />
            </li>
            <li>Ogni file mostra nome, dimensione, data di caricamento e cartella.</li>
          </ul>
        </article>

      <!-- User Area -->
      {:else if activeSection === 'userArea'}
        <article class="help-article fade-in">
          <div class="article-header">
            <span class="article-icon" aria-hidden="true">👤</span>
            <h2>{t('help.section.userArea')}</h2>
          </div>

          <p class="intro">{t('help.userArea.intro')}</p>

          <h3>Come usare l'Area Personale / How to use the Personal Area</h3>
          <ol class="steps">
            <li>
              {t('help.userArea.step1')}
              <Tooltip textKey="tooltip.saveContent" />
            </li>
            <li>{t('help.userArea.step2')}</li>
            <li>{t('help.userArea.step3')}</li>
            <li>
              {t('help.userArea.step4')}
              <Tooltip textKey="tooltip.exportContent" />
            </li>
          </ol>

          <h3>Formati di esportazione / Export formats</h3>
          <ul class="feature-list">
            <li><strong>PDF</strong> – Documento stampabile con tutti i contenuti salvati.</li>
            <li><strong>JSON</strong> – Formato strutturato per uso programmatico.</li>
          </ul>
        </article>

      <!-- API Documentation -->
      {:else if activeSection === 'api'}
        <article class="help-article fade-in">
          <div class="article-header">
            <span class="article-icon" aria-hidden="true">⚙️</span>
            <h2>{t('help.section.api')}</h2>
          </div>

          <p class="intro">
            UseIt espone una REST API documentata tramite OpenAPI / Swagger.
            Accedi alla documentazione interattiva all'indirizzo:
          </p>

          <div class="api-links">
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noopener noreferrer"
              class="api-link-card"
            >
              <span class="api-link-icon" aria-hidden="true">📖</span>
              <div>
                <strong>Swagger UI</strong>
                <p>Documentazione interattiva con possibilità di testare gli endpoint.</p>
              </div>
              <span class="external-icon" aria-hidden="true">↗</span>
            </a>

            <a
              href="http://localhost:8000/redoc"
              target="_blank"
              rel="noopener noreferrer"
              class="api-link-card"
            >
              <span class="api-link-icon" aria-hidden="true">📚</span>
              <div>
                <strong>ReDoc</strong>
                <p>Documentazione leggibile e ben formattata per consultazione.</p>
              </div>
              <span class="external-icon" aria-hidden="true">↗</span>
            </a>

            <a
              href="http://localhost:8000/openapi.json"
              target="_blank"
              rel="noopener noreferrer"
              class="api-link-card"
            >
              <span class="api-link-icon" aria-hidden="true">🔧</span>
              <div>
                <strong>OpenAPI JSON Schema</strong>
                <p>Schema machine-readable per generazione di client SDK.</p>
              </div>
              <span class="external-icon" aria-hidden="true">↗</span>
            </a>
          </div>

          <h3>Endpoint principali / Main endpoints</h3>
          <div class="endpoint-list">
            <div class="endpoint">
              <span class="method method-post">POST</span>
              <code>/device/recognize</code>
              <p>Riconosce un dispositivo da un'immagine.</p>
            </div>
            <div class="endpoint">
              <span class="method method-post">POST</span>
              <code>/device/scan-qr</code>
              <p>Decodifica un codice QR da un'immagine.</p>
            </div>
            <div class="endpoint">
              <span class="method method-post">POST</span>
              <code>/files/upload</code>
              <p>Carica e indicizza un documento in una cartella.</p>
            </div>
            <div class="endpoint">
              <span class="method method-post">POST</span>
              <code>/search/semantic</code>
              <p>Ricerca semantica su tutte le collezioni documenti.</p>
            </div>
            <div class="endpoint">
              <span class="method method-post">POST</span>
              <code>/search/hybrid</code>
              <p>Ricerca ibrida (semantica + parole chiave).</p>
            </div>
            <div class="endpoint">
              <span class="method method-get">GET</span>
              <code>/folders</code>
              <p>Elenca tutte le cartelle disponibili.</p>
            </div>
            <div class="endpoint">
              <span class="method method-get">GET</span>
              <code>/health</code>
              <p>Verifica lo stato del servizio.</p>
            </div>
          </div>

          <h3>Autenticazione / Authentication</h3>
          <div class="tip-box">
            <span class="tip-icon" aria-hidden="true">🔒</span>
            <p>
              L'API è attualmente accessibile senza autenticazione per uso locale.
              Per deployment in produzione, implementare autenticazione JWT o API key.
            </p>
          </div>
        </article>
      {/if}

    </main>
  </div>
</div>

<style>
  .page {
    max-width: 1100px;
    margin: 0 auto;
    padding: var(--space-6, 24px) var(--space-4, 16px);
  }

  /* Hero */
  .hero {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-6, 24px);
    margin-bottom: var(--space-8, 32px);
    flex-wrap: wrap;
  }

  .hero-text h1 {
    margin-bottom: var(--space-2, 8px);
  }

  .hero-text p {
    color: var(--color-text-muted, #475569);
    margin: 0;
  }

  /* Locale switcher */
  .locale-switcher {
    display: flex;
    gap: var(--space-2, 8px);
    flex-shrink: 0;
  }

  .locale-btn {
    padding: var(--space-2, 8px) var(--space-4, 16px);
    border: 2px solid var(--color-border, #e2e8f0);
    border-radius: var(--space-2, 8px);
    background: var(--color-bg, #ffffff);
    color: var(--color-text-muted, #475569);
    font-size: var(--font-size-sm, 0.875rem);
    font-weight: var(--font-weight-medium, 500);
    cursor: pointer;
    transition: all 0.15s ease;
    min-height: 44px;
  }

  .locale-btn:hover {
    border-color: var(--color-primary, #2563eb);
    color: var(--color-primary, #2563eb);
  }

  .locale-btn.active {
    border-color: var(--color-primary, #2563eb);
    background: var(--color-primary-subtle, #dbeafe);
    color: var(--color-primary, #2563eb);
    font-weight: var(--font-weight-semibold, 600);
  }

  .locale-btn:focus-visible {
    outline: 2px solid var(--color-primary, #2563eb);
    outline-offset: 2px;
  }

  /* Layout */
  .help-layout {
    display: grid;
    grid-template-columns: 220px 1fr;
    gap: var(--space-8, 32px);
    align-items: start;
  }

  /* Sidebar */
  .help-nav {
    display: flex;
    flex-direction: column;
    gap: var(--space-1, 4px);
    position: sticky;
    top: 80px;
  }

  .help-nav-item {
    display: flex;
    align-items: center;
    gap: var(--space-3, 12px);
    padding: var(--space-3, 12px) var(--space-4, 16px);
    border: none;
    border-radius: var(--space-2, 8px);
    background: transparent;
    color: var(--color-text-muted, #475569);
    font-size: var(--font-size-sm, 0.875rem);
    font-weight: var(--font-weight-medium, 500);
    cursor: pointer;
    text-align: left;
    transition: all 0.15s ease;
    min-height: 44px;
  }

  .help-nav-item:hover {
    background: var(--color-bg-secondary, #f8fafc);
    color: var(--color-text, #0f172a);
  }

  .help-nav-item.active {
    background: var(--color-primary-subtle, #dbeafe);
    color: var(--color-primary, #2563eb);
    font-weight: var(--font-weight-semibold, 600);
  }

  .help-nav-item:focus-visible {
    outline: 2px solid var(--color-primary, #2563eb);
    outline-offset: 2px;
  }

  .help-nav-icon {
    font-size: 1.1em;
    flex-shrink: 0;
  }

  /* Article */
  .help-article {
    background: var(--color-bg, #ffffff);
    border: 1px solid var(--color-border, #e2e8f0);
    border-radius: var(--space-3, 12px);
    padding: var(--space-8, 32px);
  }

  .article-header {
    display: flex;
    align-items: center;
    gap: var(--space-3, 12px);
    margin-bottom: var(--space-6, 24px);
    padding-bottom: var(--space-4, 16px);
    border-bottom: 1px solid var(--color-border-subtle, #f1f5f9);
  }

  .article-icon {
    font-size: 2rem;
  }

  .article-header h2 {
    margin: 0;
    font-size: var(--font-size-2xl, 1.5rem);
  }

  .intro {
    font-size: var(--font-size-base, 1rem);
    color: var(--color-text-muted, #475569);
    line-height: var(--line-height-relaxed, 1.625);
    margin-bottom: var(--space-6, 24px);
  }

  /* Steps */
  .steps {
    padding-left: var(--space-6, 24px);
    margin-bottom: var(--space-6, 24px);
  }

  .steps li {
    margin-bottom: var(--space-3, 12px);
    line-height: var(--line-height-relaxed, 1.625);
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
  }

  /* Feature list */
  .feature-list {
    padding-left: var(--space-6, 24px);
    margin-bottom: var(--space-6, 24px);
  }

  .feature-list li {
    margin-bottom: var(--space-2, 8px);
    line-height: var(--line-height-relaxed, 1.625);
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
  }

  /* Tip box */
  .tip-box {
    display: flex;
    gap: var(--space-3, 12px);
    background: var(--color-primary-subtle, #dbeafe);
    border: 1px solid var(--color-primary-muted, #93c5fd);
    border-radius: var(--space-2, 8px);
    padding: var(--space-4, 16px);
    margin-bottom: var(--space-6, 24px);
  }

  .tip-icon {
    font-size: 1.2em;
    flex-shrink: 0;
    margin-top: 2px;
  }

  .tip-box p {
    margin: 0;
    font-size: var(--font-size-sm, 0.875rem);
    color: var(--color-primary, #2563eb);
    line-height: var(--line-height-relaxed, 1.625);
  }

  /* Confidence guide */
  .confidence-guide {
    display: flex;
    flex-direction: column;
    gap: var(--space-3, 12px);
    margin-bottom: var(--space-6, 24px);
  }

  .confidence-item {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3, 12px);
  }

  .confidence-dot {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    flex-shrink: 0;
    margin-top: 4px;
  }

  .confidence-high { background: var(--color-success, #047857); }
  .confidence-medium { background: var(--color-warning, #b45309); }
  .confidence-low { background: var(--color-error, #dc2626); }

  .confidence-item div p {
    margin: var(--space-1, 4px) 0 0 0;
    font-size: var(--font-size-sm, 0.875rem);
    color: var(--color-text-muted, #475569);
  }

  /* Feature cards */
  .feature-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: var(--space-4, 16px);
    margin-bottom: var(--space-6, 24px);
  }

  .feature-card {
    background: var(--color-bg-secondary, #f8fafc);
    border: 1px solid var(--color-border, #e2e8f0);
    border-radius: var(--space-2, 8px);
    padding: var(--space-4, 16px);
  }

  .feature-card h4 {
    margin: 0 0 var(--space-2, 8px) 0;
    font-size: var(--font-size-base, 1rem);
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
  }

  .feature-card p {
    margin: 0;
    font-size: var(--font-size-sm, 0.875rem);
    color: var(--color-text-muted, #475569);
    line-height: var(--line-height-relaxed, 1.625);
  }

  /* API links */
  .api-links {
    display: flex;
    flex-direction: column;
    gap: var(--space-3, 12px);
    margin-bottom: var(--space-6, 24px);
  }

  .api-link-card {
    display: flex;
    align-items: center;
    gap: var(--space-4, 16px);
    padding: var(--space-4, 16px);
    background: var(--color-bg-secondary, #f8fafc);
    border: 1px solid var(--color-border, #e2e8f0);
    border-radius: var(--space-2, 8px);
    text-decoration: none;
    color: var(--color-text, #0f172a);
    transition: all 0.15s ease;
  }

  .api-link-card:hover {
    border-color: var(--color-primary, #2563eb);
    background: var(--color-primary-subtle, #dbeafe);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.1);
  }

  .api-link-card:focus-visible {
    outline: 2px solid var(--color-primary, #2563eb);
    outline-offset: 2px;
  }

  .api-link-icon {
    font-size: 1.5rem;
    flex-shrink: 0;
  }

  .api-link-card div {
    flex: 1;
  }

  .api-link-card div strong {
    display: block;
    font-size: var(--font-size-base, 1rem);
    margin-bottom: var(--space-1, 4px);
  }

  .api-link-card div p {
    margin: 0;
    font-size: var(--font-size-sm, 0.875rem);
    color: var(--color-text-muted, #475569);
  }

  .external-icon {
    font-size: 1rem;
    color: var(--color-text-subtle, #64748b);
    flex-shrink: 0;
  }

  /* Endpoint list */
  .endpoint-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-3, 12px);
    margin-bottom: var(--space-6, 24px);
  }

  .endpoint {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3, 12px);
    padding: var(--space-3, 12px) var(--space-4, 16px);
    background: var(--color-bg-secondary, #f8fafc);
    border-radius: var(--space-2, 8px);
    border: 1px solid var(--color-border, #e2e8f0);
    flex-wrap: wrap;
  }

  .method {
    font-size: var(--font-size-xs, 0.75rem);
    font-weight: var(--font-weight-bold, 700);
    padding: 2px var(--space-2, 8px);
    border-radius: var(--space-1, 4px);
    flex-shrink: 0;
    font-family: var(--font-family-mono);
    letter-spacing: 0.05em;
  }

  .method-get {
    background: var(--color-success-subtle, #d1fae5);
    color: var(--color-success, #047857);
  }

  .method-post {
    background: var(--color-primary-subtle, #dbeafe);
    color: var(--color-primary, #2563eb);
  }

  .endpoint code {
    font-family: var(--font-family-mono);
    font-size: var(--font-size-sm, 0.875rem);
    color: var(--color-text, #0f172a);
    flex-shrink: 0;
  }

  .endpoint p {
    margin: 0;
    font-size: var(--font-size-sm, 0.875rem);
    color: var(--color-text-muted, #475569);
    flex: 1;
  }

  /* Responsive */
  @media (max-width: 768px) {
    .help-layout {
      grid-template-columns: 1fr;
    }

    .help-nav {
      position: static;
      flex-direction: row;
      flex-wrap: wrap;
      gap: var(--space-2, 8px);
    }

    .help-nav-item {
      flex: 1;
      min-width: 120px;
      justify-content: center;
      text-align: center;
    }

    .hero {
      flex-direction: column;
    }

    .help-article {
      padding: var(--space-4, 16px);
    }

    .feature-cards {
      grid-template-columns: 1fr;
    }
  }
</style>
