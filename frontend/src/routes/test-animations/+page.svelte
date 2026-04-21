<script lang="ts">
  let showModal = false;
  let loading = false;
  
  function simulateLoading() {
    loading = true;
    setTimeout(() => {
      loading = false;
    }, 2000);
  }
</script>

<svelte:head>
  <title>Test Animazioni - UseIt</title>
</svelte:head>

<main class="page page-transition">
  <section class="hero">
    <h1>Test Animazioni e Transizioni</h1>
    <p>Questa pagina dimostra tutte le animazioni implementate nel task 15.4</p>
  </section>

  <section class="test-section">
    <h2>1. Loading Spinners</h2>
    <div class="demo-grid">
      <div class="demo-item">
        <h3>Spinner Small</h3>
        <span class="spinner spinner-sm"></span>
      </div>
      <div class="demo-item">
        <h3>Spinner Normal</h3>
        <span class="spinner"></span>
      </div>
      <div class="demo-item">
        <h3>Spinner Large</h3>
        <span class="spinner spinner-lg"></span>
      </div>
    </div>
  </section>

  <section class="test-section">
    <h2>2. Button Loading States</h2>
    <div class="demo-grid">
      <button class="btn btn-primary" on:click={simulateLoading} disabled={loading}>
        {#if loading}
          <span class="spinner spinner-sm"></span>
          <span>Caricamento...</span>
        {:else}
          Simula Caricamento
        {/if}
      </button>
    </div>
  </section>

  <section class="test-section">
    <h2>3. Skeleton Loading</h2>
    <div class="demo-grid">
      <div class="skeleton" style="height: 20px; width: 200px;"></div>
      <div class="skeleton" style="height: 40px; width: 100%;"></div>
      <div class="skeleton" style="height: 100px; width: 100%;"></div>
    </div>
  </section>

  <section class="test-section">
    <h2>4. Pulse Animation</h2>
    <div class="demo-grid">
      <div class="pulse" style="padding: 20px; background: var(--color-primary); color: white; border-radius: 8px;">
        Elemento con pulse
      </div>
    </div>
  </section>

  <section class="test-section">
    <h2>5. Fade In Animation</h2>
    <div class="demo-grid">
      <div class="fade-in card">
        <h3>Card con Fade In</h3>
        <p>Questa card appare con un'animazione di dissolvenza</p>
      </div>
    </div>
  </section>

  <section class="test-section">
    <h2>6. Scale In Animation</h2>
    <div class="demo-grid">
      <div class="scale-in card">
        <h3>Card con Scale In</h3>
        <p>Questa card appare con un'animazione di ingrandimento</p>
      </div>
    </div>
  </section>

  <section class="test-section">
    <h2>7. Stagger Animation</h2>
    <div class="demo-grid">
      {#each [1, 2, 3, 4, 5] as item, index}
        <div class="scale-in card" style="animation-delay: {index * 0.1}s;">
          <h3>Item {item}</h3>
          <p>Animazione scaglionata</p>
        </div>
      {/each}
    </div>
  </section>

  <section class="test-section">
    <h2>8. Modal Animations</h2>
    <button class="btn btn-primary" on:click={() => showModal = true}>
      Apri Modal
    </button>
  </section>

  <section class="test-section">
    <h2>9. Prefers Reduced Motion</h2>
    <div class="card">
      <h3>Test Accessibilità</h3>
      <p>Per testare il supporto <code>prefers-reduced-motion</code>:</p>
      <ol>
        <li>Apri le impostazioni del browser</li>
        <li>Cerca "Reduce motion" o "Movimento ridotto"</li>
        <li>Attiva l'opzione</li>
        <li>Ricarica questa pagina</li>
        <li>Tutte le animazioni dovrebbero essere disabilitate</li>
      </ol>
      <p><strong>Oppure</strong> usa DevTools:</p>
      <pre>Cmd/Ctrl + Shift + P → "Emulate CSS prefers-reduced-motion"</pre>
    </div>
  </section>
</main>

{#if showModal}
  <div class="modal-overlay fade-in" on:click={() => showModal = false}>
    <div class="modal-content slide-in-up" on:click|stopPropagation>
      <div class="modal-header">
        <h2>Modal di Test</h2>
        <button class="close-button" on:click={() => showModal = false}>✕</button>
      </div>
      <div class="modal-body">
        <p>Questo modal appare con animazioni:</p>
        <ul>
          <li>Overlay: fade-in</li>
          <li>Content: slide-in-up</li>
        </ul>
        <button class="btn btn-primary" on:click={() => showModal = false}>
          Chiudi
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .page {
    max-width: 1200px;
    margin: 0 auto;
    padding: var(--space-8) var(--space-6);
  }

  .hero {
    text-align: center;
    margin-bottom: var(--space-12);
  }

  .hero h1 {
    font-size: var(--font-size-4xl);
    font-weight: var(--font-weight-bold);
    margin-bottom: var(--space-4);
    color: var(--color-text);
  }

  .hero p {
    font-size: var(--font-size-lg);
    color: var(--color-text-muted);
  }

  .test-section {
    margin-bottom: var(--space-12);
  }

  .test-section h2 {
    font-size: var(--font-size-2xl);
    font-weight: var(--font-weight-semibold);
    margin-bottom: var(--space-6);
    color: var(--color-text);
  }

  .demo-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: var(--space-6);
  }

  .demo-item {
    padding: var(--space-6);
    background: var(--color-card-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--space-3);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-4);
  }

  .demo-item h3 {
    font-size: var(--font-size-base);
    font-weight: var(--font-weight-medium);
    color: var(--color-text);
    margin: 0;
  }

  .card {
    padding: var(--space-6);
    background: var(--color-card-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--space-3);
    box-shadow: 0 1px var(--space-1) var(--color-shadow);
  }

  .card h3 {
    font-size: var(--font-size-lg);
    font-weight: var(--font-weight-semibold);
    margin-bottom: var(--space-3);
    color: var(--color-text);
  }

  .card p {
    color: var(--color-text-muted);
    margin: 0;
  }

  .card ol, .card ul {
    margin: var(--space-4) 0;
    padding-left: var(--space-6);
    color: var(--color-text-muted);
  }

  .card li {
    margin-bottom: var(--space-2);
  }

  .card code {
    background: var(--color-bg-secondary);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--space-1);
    font-family: var(--font-family-mono);
    font-size: var(--font-size-sm);
  }

  .card pre {
    background: var(--color-bg-secondary);
    padding: var(--space-3);
    border-radius: var(--space-2);
    overflow-x: auto;
    font-family: var(--font-family-mono);
    font-size: var(--font-size-sm);
    margin: var(--space-4) 0;
  }

  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.75);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: var(--space-8);
  }

  .modal-content {
    background: var(--color-card-bg);
    border-radius: var(--space-3);
    width: 100%;
    max-width: 600px;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-6);
    border-bottom: 1px solid var(--color-border);
  }

  .modal-header h2 {
    margin: 0;
    color: var(--color-text);
    font-size: var(--font-size-xl);
  }

  .close-button {
    background: none;
    border: none;
    font-size: var(--font-size-xl);
    cursor: pointer;
    color: var(--color-text-muted);
    padding: 0;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--space-1);
    transition: background-color 0.2s;
  }

  .close-button:hover {
    background-color: var(--color-bg-secondary);
  }

  .modal-body {
    padding: var(--space-6);
  }

  .modal-body ul {
    margin: var(--space-4) 0;
    padding-left: var(--space-6);
  }

  .modal-body li {
    margin-bottom: var(--space-2);
  }
</style>
