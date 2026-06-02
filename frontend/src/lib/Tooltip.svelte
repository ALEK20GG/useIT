<script lang="ts">
  /**
   * Reusable tooltip component for in-application help text.
   *
   * Implements Requirement 20.1: in-application help text and tooltips for complex features.
   * Implements Requirement 20.5: available in both Italian and English via i18n.
   *
   * Usage:
   *   <Tooltip text="Descrizione della funzionalità" />
   *   <Tooltip textKey="tooltip.deviceRecognition" />
   *   <Tooltip text="Help text" position="bottom">
   *     <button>Hover me</button>
   *   </Tooltip>
   */

  import { t } from './i18n';
  import type { TranslationKey } from './i18n';

  /** Plain text to show in the tooltip. Takes precedence over textKey. */
  export let text: string = '';

  /** i18n key to look up the tooltip text. Used when text is not provided. */
  export let textKey: TranslationKey | '' = '';

  /** Tooltip position relative to the trigger element. */
  export let position: 'top' | 'bottom' | 'left' | 'right' = 'top';

  /** Maximum width of the tooltip bubble (CSS value). */
  export let maxWidth: string = '260px';

  /** Whether to show a small help icon (?) when no slot content is provided. */
  export let showIcon: boolean = true;

  /** Accessible label for the help icon button. */
  export let iconLabel: string = 'Mostra aiuto';

  $: resolvedText = text || (textKey ? t(textKey as TranslationKey) : '');

  let visible = false;
  let tooltipEl: HTMLDivElement | null = null;
  let triggerEl: HTMLSpanElement | null = null;

  function show() {
    visible = true;
  }

  function hide() {
    visible = false;
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      visible = false;
      triggerEl?.focus();
    }
  }

  function toggleOnClick() {
    visible = !visible;
  }
</script>

<!-- Tooltip wrapper: role="group" with aria-label groups the trigger + bubble accessibly -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<span
  class="tooltip-wrapper"
  bind:this={triggerEl}
  role="group"
  aria-label={resolvedText ? `${iconLabel}: ${resolvedText}` : iconLabel}
  onmouseenter={show}
  onmouseleave={hide}
  onfocusin={show}
  onfocusout={hide}
  onkeydown={handleKeydown}
>
  <!-- Slot for custom trigger content; falls back to a help icon -->
  {#if $$slots.default}
    <slot />
  {:else if showIcon}
    <button
      class="tooltip-icon"
      type="button"
      aria-label={iconLabel}
      aria-describedby={visible ? 'tooltip-bubble' : undefined}
      onclick={(e) => { e.stopPropagation(); toggleOnClick(); }}
    >
      <span aria-hidden="true">?</span>
    </button>
  {/if}

  <!-- Tooltip bubble -->
  {#if visible && resolvedText}
    <div
      id="tooltip-bubble"
      bind:this={tooltipEl}
      class="tooltip-bubble tooltip-bubble--{position}"
      role="tooltip"
      style="max-width: {maxWidth};"
      aria-live="polite"
    >
      {resolvedText}
      <span class="tooltip-arrow tooltip-arrow--{position}" aria-hidden="true"></span>
    </div>
  {/if}
</span>

<style>
  .tooltip-wrapper {
    position: relative;
    display: inline-flex;
    align-items: center;
  }

  /* Help icon button */
  .tooltip-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    border: 1.5px solid var(--color-text-subtle, #64748b);
    background: transparent;
    color: var(--color-text-subtle, #64748b);
    font-size: 11px;
    font-weight: var(--font-weight-bold, 700);
    line-height: 1;
    cursor: pointer;
    padding: 0;
    transition: all 0.15s ease;
    flex-shrink: 0;
  }

  .tooltip-icon:hover {
    border-color: var(--color-primary, #2563eb);
    color: var(--color-primary, #2563eb);
    background: var(--color-primary-subtle, #dbeafe);
  }

  .tooltip-icon:focus-visible {
    outline: 2px solid var(--color-primary, #2563eb);
    outline-offset: 2px;
  }

  /* Tooltip bubble */
  .tooltip-bubble {
    position: absolute;
    z-index: 1000;
    background: var(--color-text, #0f172a);
    color: var(--color-bg, #ffffff);
    font-size: var(--font-size-xs, 0.75rem);
    line-height: var(--line-height-relaxed, 1.625);
    padding: var(--space-2, 8px) var(--space-3, 12px);
    border-radius: var(--space-2, 8px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    pointer-events: none;
    white-space: normal;
    word-break: break-word;
    animation: tooltip-fade-in 0.15s ease-out;
  }

  @keyframes tooltip-fade-in {
    from {
      opacity: 0;
      transform: scale(0.95);
    }
    to {
      opacity: 1;
      transform: scale(1);
    }
  }

  /* Position variants */
  .tooltip-bubble--top {
    bottom: calc(100% + 8px);
    left: 50%;
    transform: translateX(-50%);
  }

  .tooltip-bubble--bottom {
    top: calc(100% + 8px);
    left: 50%;
    transform: translateX(-50%);
  }

  .tooltip-bubble--left {
    right: calc(100% + 8px);
    top: 50%;
    transform: translateY(-50%);
  }

  .tooltip-bubble--right {
    left: calc(100% + 8px);
    top: 50%;
    transform: translateY(-50%);
  }

  /* Arrow */
  .tooltip-arrow {
    position: absolute;
    width: 0;
    height: 0;
  }

  .tooltip-arrow--top {
    top: 100%;
    left: 50%;
    transform: translateX(-50%);
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid var(--color-text, #0f172a);
  }

  .tooltip-arrow--bottom {
    bottom: 100%;
    left: 50%;
    transform: translateX(-50%);
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-bottom: 5px solid var(--color-text, #0f172a);
  }

  .tooltip-arrow--left {
    left: 100%;
    top: 50%;
    transform: translateY(-50%);
    border-top: 5px solid transparent;
    border-bottom: 5px solid transparent;
    border-left: 5px solid var(--color-text, #0f172a);
  }

  .tooltip-arrow--right {
    right: 100%;
    top: 50%;
    transform: translateY(-50%);
    border-top: 5px solid transparent;
    border-bottom: 5px solid transparent;
    border-right: 5px solid var(--color-text, #0f172a);
  }

  /* Reduced motion */
  @media (prefers-reduced-motion: reduce) {
    .tooltip-bubble {
      animation: none;
    }
  }
</style>
