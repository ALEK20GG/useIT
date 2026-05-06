<script lang="ts">
  import { onMount } from 'svelte';
</script>

<svelte:head>
  <title>UseIt – Riconoscimento prodotti e ricerca semantica</title>
  <meta
    name="description"
    content="Riconosci prodotti tramite codice a barre, crea documentazione completa e trova facilmente ciò che cerchi con ricerca semantica."
  />
</svelte:head>

<div class="homepage page-transition">
  <!-- Hero Section -->
  <section class="hero" aria-labelledby="hero-heading">
    <div class="hero-content">
      <h1 id="hero-heading" class="hero-title">
        Riconosci, documenta e trova prodotti con <span class="gradient-text">UseIt</span>
      </h1>
      <p class="hero-subtitle">
        Scansiona il codice a barre di un prodotto, genera automaticamente una documentazione
        completa e trova facilmente ciò che cerchi grazie alla ricerca semantica avanzata.
      </p>
      <div class="hero-actions">
        <a href="/analyze" class="btn btn-primary btn-lg">
          <span aria-hidden="true">📷</span>
          <span>Scansiona prodotto</span>
        </a>
        <a href="/semantic" class="btn btn-secondary btn-lg">
          <span aria-hidden="true">🔍</span>
          <span>Cerca prodotti</span>
        </a>
      </div>
    </div>
  </section>

  <!-- Main Features Section -->
  <section class="features" aria-labelledby="features-heading">
    <div class="features-container">
      <h2 id="features-heading" class="section-title">Funzionalità principali</h2>
      <p class="section-subtitle">Tutto ciò di cui hai bisogno per gestire la documentazione dei tuoi dispositivi</p>

      <div class="features-grid">
        <!-- Scansiona -->
        <article class="feature-card stagger-item" aria-labelledby="feature-scan-title">
          <div class="feature-icon" aria-hidden="true">📷</div>
          <h3 id="feature-scan-title">Scansiona</h3>
          <p>
            Scatta una foto o scansiona il codice QR di un dispositivo. Il sistema lo riconosce
            automaticamente e recupera tutta la documentazione disponibile.
          </p>
          <a href="/analyze" class="feature-link" aria-label="Vai alla pagina Scansiona">
            Inizia a scansionare <span aria-hidden="true">→</span>
          </a>
        </article>

        <!-- Cerca -->
        <article class="feature-card stagger-item" aria-labelledby="feature-search-title">
          <div class="feature-icon" aria-hidden="true">🔍</div>
          <h3 id="feature-search-title">Cerca</h3>
          <p>
            Trova prodotti e documentazione usando linguaggio naturale. La ricerca semantica
            comprende il contesto e restituisce risultati pertinenti.
          </p>
          <a href="/semantic" class="feature-link" aria-label="Vai alla pagina Cerca">
            Prova la ricerca <span aria-hidden="true">→</span>
          </a>
        </article>

        <!-- File -->
        <article class="feature-card stagger-item" aria-labelledby="feature-files-title">
          <div class="feature-icon" aria-hidden="true">🗂️</div>
          <h3 id="feature-files-title">File</h3>
          <p>
            Carica e gestisci documenti PDF, Word e testo. I file vengono indicizzati
            automaticamente e resi ricercabili tramite ricerca semantica.
          </p>
          <a href="/files" class="feature-link" aria-label="Vai alla pagina File">
            Gestisci i file <span aria-hidden="true">→</span>
          </a>
        </article>

        <!-- Cartelle -->
        <article class="feature-card stagger-item" aria-labelledby="feature-folders-title">
          <div class="feature-icon" aria-hidden="true">📁</div>
          <h3 id="feature-folders-title">Cartelle</h3>
          <p>
            Organizza i contenuti in cartelle tematiche: Dispositivi, Appunti, Scuola e altro.
            La struttura gerarchica rende la navigazione intuitiva.
          </p>
          <a href="/folders" class="feature-link" aria-label="Vai alla pagina Cartelle">
            Esplora le cartelle <span aria-hidden="true">→</span>
          </a>
        </article>

        <!-- Area Personale -->
        <article class="feature-card stagger-item" aria-labelledby="feature-user-title">
          <div class="feature-icon" aria-hidden="true">👤</div>
          <h3 id="feature-user-title">Area Personale</h3>
          <p>
            Salva i risultati di ricerca più utili, organizzali in cartelle personali ed
            esportali in PDF o JSON per un accesso rapido in futuro.
          </p>
          <a href="/user" class="feature-link" aria-label="Vai all'Area Personale">
            Vai all'area personale <span aria-hidden="true">→</span>
          </a>
        </article>

        <!-- PDF -->
        <article class="feature-card stagger-item" aria-labelledby="feature-pdf-title">
          <div class="feature-icon" aria-hidden="true">📄</div>
          <h3 id="feature-pdf-title">PDF</h3>
          <p>
            Carica documenti PDF e rendili ricercabili con la potenza della ricerca semantica.
            Trova informazioni specifiche all'interno di manuali e guide.
          </p>
          <a href="/pdf" class="feature-link" aria-label="Vai alla pagina PDF">
            Carica un PDF <span aria-hidden="true">→</span>
          </a>
        </article>
      </div>
    </div>
  </section>

  <!-- How it works Section -->
  <section class="how-it-works" aria-labelledby="how-it-works-heading">
    <div class="how-it-works-container">
      <h2 id="how-it-works-heading" class="section-title">Come funziona</h2>
      <ol class="steps" aria-label="Passaggi per utilizzare UseIt">
        <li class="step">
          <div class="step-number" aria-hidden="true">1</div>
          <div class="step-content">
            <h3>Scansiona il dispositivo</h3>
            <p>
              Usa la fotocamera per scattare una foto del dispositivo o scansiona il suo codice
              QR per identificarlo automaticamente.
            </p>
          </div>
        </li>

        <li class="step">
          <div class="step-number" aria-hidden="true">2</div>
          <div class="step-content">
            <h3>Documentazione automatica</h3>
            <p>
              Il sistema riconosce il dispositivo, recupera le informazioni da più fonti e crea
              automaticamente una documentazione completa nel database.
            </p>
          </div>
        </li>

        <li class="step">
          <div class="step-number" aria-hidden="true">3</div>
          <div class="step-content">
            <h3>Ricerca intelligente</h3>
            <p>
              Trova facilmente qualsiasi dispositivo usando ricerca semantica: descrivi ciò che
              cerchi in linguaggio naturale e ottieni risultati precisi.
            </p>
          </div>
        </li>
      </ol>
    </div>
  </section>

  <!-- CTA Section -->
  <section class="cta" aria-labelledby="cta-heading">
    <div class="cta-content">
      <h2 id="cta-heading">Pronto per iniziare?</h2>
      <p>Inizia a scansionare dispositivi o cerca nella documentazione esistente</p>
      <div class="cta-actions">
        <a href="/analyze" class="btn btn-primary btn-lg">
          <span aria-hidden="true">📷</span>
          <span>Scansiona dispositivo</span>
        </a>
        <a href="/semantic" class="btn btn-secondary btn-lg">
          <span aria-hidden="true">🔍</span>
          <span>Cerca dispositivi</span>
        </a>
      </div>
    </div>
  </section>
</div>

<style>
  .homepage {
    min-height: 100vh;
    font-family: var(--font-family-sans);
    background: var(--color-bg);
  }

  /* ===== Hero Section ===== */
  .hero {
    background: linear-gradient(135deg, var(--color-primary) 0%, #764ba2 100%);
    color: white;
    padding: var(--space-16) var(--space-6);
    text-align: center;
  }

  .hero-content {
    max-width: 900px;
    margin: 0 auto;
  }

  .hero-title {
    font-size: var(--font-size-5xl);
    font-weight: var(--font-weight-black);
    line-height: var(--line-height-tight);
    letter-spacing: var(--letter-spacing-tight);
    margin-bottom: var(--space-6);
    color: white;
  }

  .gradient-text {
    background: linear-gradient(135deg, #fbbf24, #f59e0b);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .hero-subtitle {
    font-size: var(--font-size-xl);
    line-height: var(--line-height-relaxed);
    letter-spacing: var(--letter-spacing-normal);
    margin-bottom: var(--space-10);
    opacity: 0.95;
    max-width: 700px;
    margin-left: auto;
    margin-right: auto;
  }

  .hero-actions {
    display: flex;
    gap: var(--space-4);
    justify-content: center;
    flex-wrap: wrap;
  }

  /* ===== Features Section ===== */
  .features {
    padding: var(--space-16) var(--space-6);
    background: var(--color-bg);
  }

  .features-container {
    max-width: 1200px;
    margin: 0 auto;
  }

  .section-title {
    font-size: var(--font-size-4xl);
    font-weight: var(--font-weight-black);
    line-height: var(--line-height-tight);
    letter-spacing: var(--letter-spacing-tight);
    text-align: center;
    margin-bottom: var(--space-4);
    color: var(--color-text);
  }

  .section-subtitle {
    font-size: var(--font-size-lg);
    line-height: var(--line-height-relaxed);
    color: var(--color-text-muted);
    text-align: center;
    margin-bottom: var(--space-12);
    max-width: 600px;
    margin-left: auto;
    margin-right: auto;
  }

  .features-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--space-6);
  }

  @media (min-width: 640px) {
    .features-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  @media (min-width: 1024px) {
    .features-grid {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  .feature-card {
    background: var(--color-card-bg);
    border-radius: var(--space-3);
    padding: var(--space-8);
    box-shadow: 0 1px var(--space-2) var(--color-shadow);
    border: 1px solid var(--color-border);
    transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
    display: flex;
    flex-direction: column;
  }

  .feature-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 24px var(--color-shadow-medium);
    border-color: var(--color-primary-muted);
  }

  .feature-icon {
    font-size: 2.5rem;
    line-height: 1;
    margin-bottom: var(--space-4);
  }

  .feature-card h3 {
    font-size: var(--font-size-xl);
    font-weight: var(--font-weight-bold);
    line-height: var(--line-height-snug);
    margin-bottom: var(--space-3);
    color: var(--color-text);
  }

  .feature-card p {
    color: var(--color-text-muted);
    line-height: var(--line-height-relaxed);
    margin-bottom: var(--space-5);
    font-size: var(--font-size-base);
    flex: 1;
  }

  .feature-link {
    color: var(--color-primary);
    text-decoration: none;
    font-weight: var(--font-weight-semibold);
    font-size: var(--font-size-sm);
    line-height: var(--line-height-normal);
    transition: color 0.2s ease, gap 0.2s ease;
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    align-self: flex-start;
    padding: var(--space-1) 0;
  }

  .feature-link:hover {
    color: var(--color-primary-hover);
    text-decoration: underline;
  }

  .feature-link:focus-visible {
    outline: 2px solid var(--color-primary);
    outline-offset: 2px;
    border-radius: var(--space-1);
  }

  /* ===== How it works Section ===== */
  .how-it-works {
    padding: var(--space-16) var(--space-6);
    background: var(--color-bg-secondary);
  }

  .how-it-works-container {
    max-width: 1200px;
    margin: 0 auto;
  }

  .steps {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--space-10);
    list-style: none;
    padding: 0;
    margin: 0;
  }

  @media (min-width: 768px) {
    .steps {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  .step {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
  }

  .step-number {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--color-primary), var(--color-primary-hover));
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: var(--font-size-2xl);
    font-weight: var(--font-weight-bold);
    line-height: var(--line-height-tight);
    margin-bottom: var(--space-6);
    box-shadow: 0 4px 12px var(--color-shadow-medium);
    flex-shrink: 0;
  }

  .step-content h3 {
    font-size: var(--font-size-xl);
    font-weight: var(--font-weight-bold);
    line-height: var(--line-height-snug);
    margin-bottom: var(--space-3);
    color: var(--color-text);
  }

  .step-content p {
    color: var(--color-text-muted);
    line-height: var(--line-height-relaxed);
    font-size: var(--font-size-base);
  }

  /* ===== CTA Section ===== */
  .cta {
    padding: var(--space-16) var(--space-6);
    background: var(--color-bg);
    text-align: center;
  }

  .cta-content {
    max-width: 700px;
    margin: 0 auto;
  }

  .cta h2 {
    font-size: var(--font-size-4xl);
    font-weight: var(--font-weight-black);
    line-height: var(--line-height-tight);
    letter-spacing: var(--letter-spacing-tight);
    margin-bottom: var(--space-4);
    color: var(--color-text);
  }

  .cta p {
    font-size: var(--font-size-xl);
    line-height: var(--line-height-relaxed);
    color: var(--color-text-muted);
    margin-bottom: var(--space-10);
  }

  .cta-actions {
    display: flex;
    gap: var(--space-4);
    justify-content: center;
    flex-wrap: wrap;
  }

  /* ===== Responsive adjustments ===== */
  @media (max-width: 640px) {
    .hero {
      padding: var(--space-12) var(--space-4);
    }

    .hero-title {
      font-size: var(--font-size-3xl);
    }

    .hero-subtitle {
      font-size: var(--font-size-base);
    }

    .section-title {
      font-size: var(--font-size-3xl);
    }

    .cta h2 {
      font-size: var(--font-size-3xl);
    }

    .cta p {
      font-size: var(--font-size-base);
    }

    .features,
    .how-it-works,
    .cta {
      padding: var(--space-12) var(--space-4);
    }
  }

  @media (max-width: 768px) {
    .hero-title {
      font-size: var(--font-size-4xl);
    }
  }

  /* ===== Print styles ===== */
  @media print {
    .hero {
      background: none;
      color: var(--color-text);
      padding: var(--space-8) 0;
    }

    .hero-title {
      color: var(--color-text);
    }

    .gradient-text {
      -webkit-text-fill-color: var(--color-primary);
      background: none;
    }

    .hero-actions,
    .cta-actions {
      display: none;
    }

    .feature-card {
      break-inside: avoid;
      box-shadow: none;
      border: 1px solid #ccc;
    }

    .feature-link {
      display: none;
    }
  }

  /* ===== Reduced motion ===== */
  @media (prefers-reduced-motion: reduce) {
    .feature-card {
      transition: none;
    }

    .feature-card:hover {
      transform: none;
    }
  }
</style>
