<script lang="ts">
  /**
   * Reusable loading indicator component.
   *
   * Implements Requirement 17.4:
   * - Provides loading indicators for all asynchronous operations exceeding 1 second
   * - Shows after a configurable delay to avoid flicker for fast operations
   * - Supports different sizes and display modes
   */

  import { onMount, onDestroy } from 'svelte';

  /** Whether the loading state is active */
  export let loading = false;

  /** Delay in ms before showing the indicator (avoids flicker for fast ops) */
  export let delayMs = 300;

  /** Accessible label for screen readers */
  export let label = 'Caricamento in corso…';

  /** Visual size variant */
  export let size: 'sm' | 'md' | 'lg' = 'md';

  /** Display mode: inline (next to content) or overlay (full-area) */
  export let mode: 'inline' | 'overlay' | 'fullscreen' = 'inline';

  /** Optional message to show below the spinner */
  export let message = '';

  let visible = false;
  let timer: ReturnType<typeof setTimeout> | null = null;

  $: {
    if (loading) {
      if (delayMs <= 0) {
        visible = true;
      } else {
        timer = setTimeout(() => {
          visible = true;
        }, delayMs);
      }
    } else {
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
      visible = false;
    }
  }

  onDestroy(() => {
    if (timer) clearTimeout(timer);
  });
</script>

{#if visible}
  {#if mode === 'inline'}
    <div
      class="loading-indicator loading-indicator--inline loading-indicator--{size}"
      role="status"
      aria-live="polite"
      aria-label={label}
    >
      <span class="spinner spinner-{size}" aria-hidden="true"></span>
      {#if message}
        <span class="loading-indicator__message">{message}</span>
      {/if}
    </div>
  {:else if mode === 'overlay'}
    <div
      class="loading-indicator loading-indicator--overlay"
      role="status"
      aria-live="polite"
      aria-label={label}
    >
      <div class="loading-indicator__content">
        <span class="spinner spinner-{size}" aria-hidden="true"></span>
        {#if message}
          <p class="loading-indicator__message">{message}</p>
        {/if}
      </div>
    </div>
  {:else if mode === 'fullscreen'}
    <div
      class="loading-indicator loading-indicator--fullscreen"
      role="status"
      aria-live="polite"
      aria-label={label}
    >
      <div class="loading-indicator__content">
        <span class="spinner spinner-lg" aria-hidden="true"></span>
        {#if message}
          <p class="loading-indicator__message">{message}</p>
        {/if}
      </div>
    </div>
  {/if}
{/if}

<style>
  .loading-indicator--inline {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 8px);
  }

  .loading-indicator__message {
    color: var(--color-text-muted, #6b7280);
    font-size: var(--font-size-sm, 0.875rem);
    margin: 0;
  }

  .loading-indicator--overlay {
    position: absolute;
    inset: 0;
    background: rgba(255, 255, 255, 0.8);
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: inherit;
    z-index: 10;
  }

  .loading-indicator--fullscreen {
    position: fixed;
    inset: 0;
    background: rgba(255, 255, 255, 0.9);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
  }

  .loading-indicator__content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-4, 16px);
  }

  .loading-indicator--overlay .loading-indicator__message,
  .loading-indicator--fullscreen .loading-indicator__message {
    font-size: var(--font-size-base, 1rem);
    color: var(--color-text-muted, #6b7280);
    text-align: center;
  }
</style>
