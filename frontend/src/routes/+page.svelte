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

<main class="homepage page-transition">
  <!-- Hero Section -->
  <section class="hero">
    <div class="hero-content">
      <h1 class="hero-title">
        Riconosci, documenta e trova prodotti con <span class="gradient-text">UseIt</span>
      </h1>
      <p class="hero-subtitle">
        Scansiona il codice a barre di un prodotto, genera automaticamente una documentazione
        completa e trova facilmente ciò che cerchi grazie alla ricerca semantica avanzata.
      </p>
      <div class="hero-actions">
        <a href="/analyze" class="btn btn-primary btn-lg">
          <span>📷 Scansiona prodotto</span>
        </a>
        <a href="/semantic" class="btn btn-secondary btn-lg">
          <span>🔍 Cerca prodotti</span>
        </a>
      </div>
    </div>
  </section>

  <!-- Features Section -->
  <section class="features">
    <div class="features-grid">
      <div class="feature-card">
        <div class="feature-icon">📸</div>
        <h3>Riconoscimento automatico</h3>
        <p>
          Scatta una foto del codice a barre del prodotto. Il sistema lo riconosce automaticamente
          e recupera tutte le informazioni necessarie.
        </p>
        <a href="/analyze" class="feature-link">Inizia ora →</a>
      </div>

      <div class="feature-card">
        <div class="feature-icon">📚</div>
        <h3>Documentazione completa</h3>
        <p>
          Genera automaticamente una documentazione dettagliata del prodotto con tutte le
          informazioni rilevanti per il tuo team.
        </p>
      </div>

      <div class="feature-card">
        <div class="feature-icon">🧠</div>
        <h3>Ricerca semantica</h3>
        <p>
          Trova prodotti usando linguaggio naturale. Descrivi ciò che cerchi e il sistema ti
          mostrerà i risultati più rilevanti.
        </p>
        <a href="/semantic" class="feature-link">Prova la ricerca →</a>
      </div>
    </div>
  </section>

  <!-- How it works Section -->
  <section class="how-it-works">
    <h2 class="section-title">Come funziona</h2>
    <div class="steps">
      <div class="step">
        <div class="step-number">1</div>
        <div class="step-content">
          <h3>Scansiona il codice a barre</h3>
          <p>
            Usa la fotocamera del tuo dispositivo per scattare una foto del codice a barre del
            prodotto che vuoi documentare.
          </p>
        </div>
      </div>

      <div class="step">
        <div class="step-number">2</div>
        <div class="step-content">
          <h3>Riconoscimento e documentazione</h3>
          <p>
            Il sistema riconosce il prodotto, recupera le informazioni e crea automaticamente una
            documentazione completa salvata nel database.
          </p>
        </div>
      </div>

      <div class="step">
        <div class="step-number">3</div>
        <div class="step-content">
          <h3>Ricerca intelligente</h3>
          <p>
            Altri utenti possono trovare facilmente il prodotto usando ricerca semantica: descrivi
            ciò che cerchi in linguaggio naturale e ottieni risultati precisi.
          </p>
        </div>
      </div>
    </div>
  </section>

  <!-- CTA Section -->
  <section class="cta">
    <div class="cta-content">
      <h2>Pronto per iniziare?</h2>
      <p>Inizia a scansionare prodotti o cerca nella documentazione esistente</p>
      <div class="cta-actions">
        <a href="/analyze" class="btn btn-primary btn-lg">Scansiona prodotto</a>
        <a href="/semantic" class="btn btn-secondary btn-lg">Cerca prodotti</a>
      </div>
    </div>
  </section>
</main>

<style>
  .homepage {
    min-height: 100vh;
    font-family: var(--font-family-sans);
    background: var(--color-bg);
  }

  /* Hero Section */
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

  /* Features Section */
  .features {
    padding: var(--space-16) var(--space-6);
    max-width: 1200px;
    margin: 0 auto;
  }

  .features-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--space-8);
  }

  @media (min-width: 768px) {
    .features-grid {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  .feature-card {
    background: var(--color-card-bg);
    border-radius: var(--space-3);
    padding: var(--space-8);
    box-shadow: 0 1px var(--space-1) var(--color-shadow);
    border: 1px solid var(--color-border);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    animation: scale-in 0.3s ease-out backwards;
  }

  .feature-card:nth-child(1) { animation-delay: 0.1s; }
  .feature-card:nth-child(2) { animation-delay: 0.2s; }
  .feature-card:nth-child(3) { animation-delay: 0.3s; }

  .feature-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 1px var(--space-3) var(--color-shadow-medium);
  }

  .feature-icon {
    font-size: var(--font-size-5xl);
    line-height: var(--line-height-tight);
    margin-bottom: var(--space-4);
  }

  .feature-card h3 {
    font-size: var(--font-size-2xl);
    font-weight: var(--font-weight-bold);
    line-height: var(--line-height-snug);
    letter-spacing: var(--letter-spacing-normal);
    margin-bottom: var(--space-3);
    color: var(--color-text);
  }

  .feature-card p {
    color: var(--color-text-muted);
    line-height: var(--line-height-relaxed);
    margin-bottom: var(--space-4);
    font-size: var(--font-size-base);
  }

  .feature-link {
    color: var(--color-primary);
    text-decoration: none;
    font-weight: var(--font-weight-semibold);
    font-size: var(--font-size-base);
    line-height: var(--line-height-normal);
    transition: color 0.2s ease;
  }

  .feature-link:hover {
    color: var(--color-primary-hover);
  }

  /* How it works Section */
  .how-it-works {
    padding: var(--space-16) var(--space-6);
    background: var(--color-bg-secondary);
    max-width: 1200px;
    margin: 0 auto;
  }

  .section-title {
    font-size: var(--font-size-4xl);
    font-weight: var(--font-weight-black);
    line-height: var(--line-height-tight);
    letter-spacing: var(--letter-spacing-tight);
    text-align: center;
    margin-bottom: var(--space-12);
    color: var(--color-text);
  }

  .steps {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--space-10);
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
    animation: fade-in 0.5s ease-out backwards;
  }

  .step:nth-child(1) { animation-delay: 0.2s; }
  .step:nth-child(2) { animation-delay: 0.4s; }
  .step:nth-child(3) { animation-delay: 0.6s; }

  .step-number {
    width: 60px;
    height: 60px;
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
    box-shadow: 0 1px var(--space-3) var(--color-shadow-medium);
  }

  .step-content h3 {
    font-size: var(--font-size-xl);
    font-weight: var(--font-weight-bold);
    line-height: var(--line-height-snug);
    letter-spacing: var(--letter-spacing-normal);
    margin-bottom: var(--space-3);
    color: var(--color-text);
  }

  .step-content p {
    color: var(--color-text-muted);
    line-height: var(--line-height-relaxed);
    font-size: var(--font-size-base);
  }

  /* CTA Section */
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

  /* Responsive adjustments */
  @media (max-width: 768px) {
    .hero-title {
      font-size: var(--font-size-3xl);
    }

    .hero-subtitle {
      font-size: var(--font-size-lg);
    }

    .section-title {
      font-size: var(--font-size-3xl);
    }

    .cta h2 {
      font-size: var(--font-size-3xl);
    }
  }
</style>
