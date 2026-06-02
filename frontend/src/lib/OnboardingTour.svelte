<script lang="ts">
  /**
   * Guided onboarding tour component for new users.
   *
   * Implements Requirement 20.2: guided tours or onboarding flows when users access new features.
   * Implements Requirement 20.5: available in both Italian and English via i18n.
   *
   * Usage:
   *   <OnboardingTour />
   *
   * The tour is shown automatically on first visit (localStorage flag).
   * It can also be triggered programmatically via the exported `startTour()` function.
   */

  import { onMount } from 'svelte';
  import { t } from './i18n';

  /** Whether the tour is currently visible. */
  export let visible = false;

  /** Called when the tour is completed or skipped. */
  export let onComplete: (() => void) | null = null;

  /** Storage key used to track whether the tour has been shown. */
  export let storageKey = 'useit-tour-completed';

  /** Whether to auto-show on first visit. */
  export let autoShow = true;

  // ─── Tour steps ─────────────────────────────────────────────────────────────

  $: steps = [
    {
      id: 'welcome',
      icon: '📦',
      title: t('tour.welcome.title'),
      body: t('tour.welcome.body'),
      highlight: null,
    },
    {
      id: 'scan',
      icon: '📷',
      title: t('tour.scan.title'),
      body: t('tour.scan.body'),
      highlight: '/analyze',
    },
    {
      id: 'search',
      icon: '🔍',
      title: t('tour.search.title'),
      body: t('tour.search.body'),
      highlight: '/semantic',
    },
    {
      id: 'folders',
      icon: '📁',
      title: t('tour.folders.title'),
      body: t('tour.folders.body'),
      highlight: '/folders',
    },
    {
      id: 'user',
      icon: '👤',
      title: t('tour.user.title'),
      body: t('tour.user.body'),
      highlight: '/user',
    },
  ];

  let currentStep = 0;

  $: totalSteps = steps.length;
  $: currentStepData = steps[currentStep];
  $: isFirst = currentStep === 0;
  $: isLast = currentStep === totalSteps - 1;
  $: progressPercent = ((currentStep + 1) / totalSteps) * 100;

  // ─── Lifecycle ───────────────────────────────────────────────────────────────

  onMount(() => {
    if (autoShow && typeof localStorage !== 'undefined') {
      const completed = localStorage.getItem(storageKey);
      if (!completed) {
        visible = true;
      }
    }
  });

  // ─── Actions ─────────────────────────────────────────────────────────────────

  export function startTour() {
    currentStep = 0;
    visible = true;
  }

  function next() {
    if (currentStep < totalSteps - 1) {
      currentStep += 1;
    } else {
      complete();
    }
  }

  function prev() {
    if (currentStep > 0) {
      currentStep -= 1;
    }
  }

  function skip() {
    complete();
  }

  function complete() {
    visible = false;
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(storageKey, 'true');
    }
    onComplete?.();
  }

  function handleOverlayClick(event: MouseEvent) {
    // Only close if clicking the backdrop, not the card
    if ((event.target as HTMLElement).classList.contains('tour-overlay')) {
      skip();
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    if (!visible) return;
    switch (event.key) {
      case 'Escape':
        skip();
        break;
      case 'ArrowRight':
      case 'ArrowDown':
        event.preventDefault();
        next();
        break;
      case 'ArrowLeft':
      case 'ArrowUp':
        event.preventDefault();
        prev();
        break;
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if visible}
  <!-- Backdrop -->
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    class="tour-overlay"
    role="dialog"
    aria-modal="true"
    tabindex="-1"
    aria-label={currentStepData.title}
    on:click={handleOverlayClick}
  >
    <!-- Tour card -->
    <div class="tour-card slide-in-up" role="document">
      <!-- Header -->
      <div class="tour-header">
        <span class="tour-step-label" aria-live="polite">
          {t('tour.step', { current: currentStep + 1, total: totalSteps })}
        </span>
        <button
          class="tour-skip-btn"
          type="button"
          on:click={skip}
          aria-label={t('tour.skip')}
        >
          {t('tour.skip')}
        </button>
      </div>

      <!-- Progress bar -->
      <div
        class="tour-progress"
        role="progressbar"
        aria-valuenow={currentStep + 1}
        aria-valuemin={1}
        aria-valuemax={totalSteps}
        aria-label="Progresso tour"
      >
        <div class="tour-progress-fill" style="width: {progressPercent}%;"></div>
      </div>

      <!-- Step dots -->
      <div class="tour-dots" aria-hidden="true">
        {#each steps as step, i}
          <button
            class="tour-dot"
            class:active={i === currentStep}
            class:completed={i < currentStep}
            type="button"
            aria-label="Vai al passo {i + 1}"
            on:click={() => (currentStep = i)}
          ></button>
        {/each}
      </div>

      <!-- Content -->
      <div class="tour-content" aria-live="polite">
        <div class="tour-icon" aria-hidden="true">{currentStepData.icon}</div>
        <h2 class="tour-title">{currentStepData.title}</h2>
        <p class="tour-body">{currentStepData.body}</p>
      </div>

      <!-- Navigation -->
      <div class="tour-nav">
        {#if !isFirst}
          <button
            class="btn btn-secondary"
            type="button"
            on:click={prev}
            aria-label={t('tour.prev')}
          >
            ← {t('tour.prev')}
          </button>
        {:else}
          <span></span>
        {/if}

        <button
          class="btn btn-primary"
          type="button"
          on:click={next}
          aria-label={isLast ? t('tour.done') : t('tour.next')}
        >
          {#if isLast}
            {t('tour.done')} ✓
          {:else}
            {t('tour.next')} →
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .tour-overlay {
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9000;
    padding: var(--space-4, 16px);
    backdrop-filter: blur(2px);
  }

  .tour-card {
    background: var(--color-bg, #ffffff);
    border-radius: var(--space-4, 16px);
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    width: 100%;
    max-width: 480px;
    padding: var(--space-6, 24px);
    display: flex;
    flex-direction: column;
    gap: var(--space-4, 16px);
  }

  /* Header */
  .tour-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .tour-step-label {
    font-size: var(--font-size-xs, 0.75rem);
    color: var(--color-text-muted, #475569);
    font-weight: var(--font-weight-medium, 500);
    letter-spacing: var(--letter-spacing-wide, 0.025em);
    text-transform: uppercase;
  }

  .tour-skip-btn {
    background: none;
    border: none;
    cursor: pointer;
    color: var(--color-text-subtle, #64748b);
    font-size: var(--font-size-sm, 0.875rem);
    padding: var(--space-1, 4px) var(--space-2, 8px);
    border-radius: var(--space-1, 4px);
    transition: color 0.15s, background 0.15s;
  }

  .tour-skip-btn:hover {
    color: var(--color-text, #0f172a);
    background: var(--color-bg-secondary, #f8fafc);
  }

  .tour-skip-btn:focus-visible {
    outline: 2px solid var(--color-primary, #2563eb);
    outline-offset: 2px;
  }

  /* Progress bar */
  .tour-progress {
    height: 4px;
    background: var(--color-border, #e2e8f0);
    border-radius: 2px;
    overflow: hidden;
  }

  .tour-progress-fill {
    height: 100%;
    background: var(--color-primary, #2563eb);
    border-radius: 2px;
    transition: width 0.3s ease;
  }

  /* Step dots */
  .tour-dots {
    display: flex;
    gap: var(--space-2, 8px);
    justify-content: center;
  }

  .tour-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    border: none;
    background: var(--color-border, #e2e8f0);
    cursor: pointer;
    padding: 0;
    transition: all 0.2s ease;
  }

  .tour-dot.active {
    background: var(--color-primary, #2563eb);
    transform: scale(1.3);
  }

  .tour-dot.completed {
    background: var(--color-primary-muted, #93c5fd);
  }

  .tour-dot:focus-visible {
    outline: 2px solid var(--color-primary, #2563eb);
    outline-offset: 2px;
  }

  /* Content */
  .tour-content {
    text-align: center;
    padding: var(--space-4, 16px) 0;
  }

  .tour-icon {
    font-size: 3rem;
    margin-bottom: var(--space-4, 16px);
    display: block;
  }

  .tour-title {
    font-size: var(--font-size-2xl, 1.5rem);
    font-weight: var(--font-weight-bold, 700);
    color: var(--color-text, #0f172a);
    margin: 0 0 var(--space-3, 12px) 0;
    line-height: var(--line-height-tight, 1.25);
  }

  .tour-body {
    font-size: var(--font-size-base, 1rem);
    color: var(--color-text-muted, #475569);
    line-height: var(--line-height-relaxed, 1.625);
    margin: 0;
  }

  /* Navigation */
  .tour-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3, 12px);
    padding-top: var(--space-2, 8px);
    border-top: 1px solid var(--color-border-subtle, #f1f5f9);
  }

  /* Responsive */
  @media (max-width: 480px) {
    .tour-card {
      padding: var(--space-4, 16px);
      border-radius: var(--space-3, 12px);
    }

    .tour-title {
      font-size: var(--font-size-xl, 1.25rem);
    }

    .tour-icon {
      font-size: 2.5rem;
    }
  }

  /* Reduced motion */
  @media (prefers-reduced-motion: reduce) {
    .tour-progress-fill {
      transition: none;
    }

    .tour-dot {
      transition: none;
    }
  }
</style>
