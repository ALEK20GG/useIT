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

<main class="homepage">
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
        <a href="/analyze" class="button primary large">
          <span>📷 Scansiona prodotto</span>
        </a>
        <a href="/semantic" class="button secondary large">
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
        <a href="/analyze" class="button primary large">Scansiona prodotto</a>
        <a href="/semantic" class="button outline large">Cerca prodotti</a>
      </div>
    </div>
  </section>
</main>

<style>
  .homepage {
    min-height: 100vh;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: linear-gradient(to bottom, #ffffff 0%, #f9fafb 100%);
  }

  /* Hero Section */
  .hero {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 5rem 1.5rem;
    text-align: center;
  }

  .hero-content {
    max-width: 900px;
    margin: 0 auto;
  }

  .hero-title {
    font-size: 3rem;
    font-weight: 800;
    margin-bottom: 1.5rem;
    line-height: 1.2;
  }

  .gradient-text {
    background: linear-gradient(135deg, #fbbf24, #f59e0b);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .hero-subtitle {
    font-size: 1.25rem;
    margin-bottom: 2.5rem;
    opacity: 0.95;
    line-height: 1.6;
    max-width: 700px;
    margin-left: auto;
    margin-right: auto;
  }

  .hero-actions {
    display: flex;
    gap: 1rem;
    justify-content: center;
    flex-wrap: wrap;
  }

  /* Buttons */
  .button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    padding: 0.75rem 2rem;
    border-radius: 999px;
    font-size: 1rem;
    font-weight: 600;
    text-decoration: none;
    transition: all 0.2s ease;
    border: none;
    cursor: pointer;
  }

  .button.large {
    padding: 1rem 2.5rem;
    font-size: 1.1rem;
  }

  .button.primary {
    background: linear-gradient(135deg, #4f46e5, #6366f1);
    color: white;
    box-shadow: 0 12px 25px rgba(55, 48, 163, 0.45);
  }

  .button.primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 16px 30px rgba(55, 48, 163, 0.55);
  }

  .button.secondary {
    background: rgba(255, 255, 255, 0.2);
    color: white;
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.3);
  }

  .button.secondary:hover {
    background: rgba(255, 255, 255, 0.3);
    transform: translateY(-2px);
  }

  .button.outline {
    background: transparent;
    color: #4f46e5;
    border: 2px solid #4f46e5;
  }

  .button.outline:hover {
    background: #4f46e5;
    color: white;
    transform: translateY(-2px);
  }

  /* Features Section */
  .features {
    padding: 5rem 1.5rem;
    max-width: 1200px;
    margin: 0 auto;
  }

  .features-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 2rem;
  }

  @media (min-width: 768px) {
    .features-grid {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  .feature-card {
    background: white;
    border-radius: 1rem;
    padding: 2rem;
    box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
    border: 1px solid #e5e7eb;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
  }

  .feature-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 24px 50px rgba(15, 23, 42, 0.12);
  }

  .feature-icon {
    font-size: 3rem;
    margin-bottom: 1rem;
  }

  .feature-card h3 {
    font-size: 1.5rem;
    font-weight: 700;
    margin-bottom: 0.75rem;
    color: #111827;
  }

  .feature-card p {
    color: #6b7280;
    line-height: 1.6;
    margin-bottom: 1rem;
  }

  .feature-link {
    color: #4f46e5;
    text-decoration: none;
    font-weight: 600;
    font-size: 0.95rem;
    transition: color 0.2s ease;
  }

  .feature-link:hover {
    color: #6366f1;
  }

  /* How it works Section */
  .how-it-works {
    padding: 5rem 1.5rem;
    background: white;
    max-width: 1200px;
    margin: 0 auto;
  }

  .section-title {
    font-size: 2.5rem;
    font-weight: 800;
    text-align: center;
    margin-bottom: 3rem;
    color: #111827;
  }

  .steps {
    display: grid;
    grid-template-columns: 1fr;
    gap: 2.5rem;
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
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: linear-gradient(135deg, #4f46e5, #6366f1);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
    font-weight: 700;
    margin-bottom: 1.5rem;
    box-shadow: 0 8px 20px rgba(79, 70, 229, 0.3);
  }

  .step-content h3 {
    font-size: 1.25rem;
    font-weight: 700;
    margin-bottom: 0.75rem;
    color: #111827;
  }

  .step-content p {
    color: #6b7280;
    line-height: 1.6;
  }

  /* CTA Section */
  .cta {
    padding: 5rem 1.5rem;
    background: linear-gradient(135deg, #f9fafb 0%, #ffffff 100%);
    text-align: center;
  }

  .cta-content {
    max-width: 700px;
    margin: 0 auto;
  }

  .cta h2 {
    font-size: 2.5rem;
    font-weight: 800;
    margin-bottom: 1rem;
    color: #111827;
  }

  .cta p {
    font-size: 1.25rem;
    color: #6b7280;
    margin-bottom: 2.5rem;
  }

  .cta-actions {
    display: flex;
    gap: 1rem;
    justify-content: center;
    flex-wrap: wrap;
  }

  /* Responsive adjustments */
  @media (max-width: 768px) {
    .hero-title {
      font-size: 2rem;
    }

    .hero-subtitle {
      font-size: 1.1rem;
    }

    .section-title {
      font-size: 2rem;
    }

    .cta h2 {
      font-size: 2rem;
    }
  }
</style>
