<script lang="ts">
  /**
   * Reusable error display component with retry support.
   *
   * Implements Requirements 17.1, 17.3, 17.5:
   * - Shows user-friendly error messages
   * - Displays retry options when available
   * - Supports structured error responses from the backend
   */

  export interface ErrorSuggestion {
    action: string;
    description: string;
    can_retry: boolean;
  }

  export interface StructuredError {
    error_code?: string;
    category?: string;
    user_message: string;
    suggestions?: ErrorSuggestion[];
    can_retry?: boolean;
    retry_after_seconds?: number | null;
  }

  /** Simple string message or structured error object */
  export let error: string | StructuredError | null = null;

  /** Called when the user clicks the retry button */
  export let onRetry: (() => void) | null = null;

  /** Called when the user dismisses the error */
  export let onDismiss: (() => void) | null = null;

  /** Visual variant */
  export let variant: 'error' | 'warning' | 'info' = 'error';

  /** Whether to show the suggestions list */
  export let showSuggestions = true;

  $: isStructured = error !== null && typeof error === 'object';
  $: userMessage = isStructured
    ? (error as StructuredError).user_message
    : (error as string) ?? '';
  $: suggestions = isStructured ? (error as StructuredError).suggestions ?? [] : [];
  $: canRetry =
    (isStructured ? (error as StructuredError).can_retry : false) || onRetry !== null;
  $: hasError = error !== null && userMessage.length > 0;

  const icons: Record<string, string> = {
    error: '⚠️',
    warning: '⚡',
    info: 'ℹ️',
  };
</script>

{#if hasError}
  <div
    class="error-display error-display--{variant}"
    role="alert"
    aria-live="assertive"
    aria-atomic="true"
  >
    <div class="error-display__header">
      <span class="error-display__icon" aria-hidden="true">{icons[variant]}</span>
      <p class="error-display__message">{userMessage}</p>
      {#if onDismiss}
        <button
          class="error-display__dismiss"
          on:click={onDismiss}
          aria-label="Chiudi messaggio di errore"
          type="button"
        >
          ✕
        </button>
      {/if}
    </div>

    {#if showSuggestions && suggestions.length > 0}
      <ul class="error-display__suggestions" aria-label="Suggerimenti per risolvere il problema">
        {#each suggestions as suggestion}
          <li class="error-display__suggestion">
            <strong>{suggestion.action}:</strong>
            {suggestion.description}
          </li>
        {/each}
      </ul>
    {/if}

    {#if canRetry && onRetry}
      <div class="error-display__actions">
        <button
          class="btn btn-sm error-display__retry-btn"
          on:click={onRetry}
          type="button"
          aria-label="Riprova l'operazione"
        >
          🔄 Riprova
        </button>
      </div>
    {/if}
  </div>
{/if}

<style>
  .error-display {
    border-radius: var(--space-2, 8px);
    padding: var(--space-4, 16px);
    margin: var(--space-3, 12px) 0;
    border: 1px solid;
  }

  .error-display--error {
    background-color: var(--color-error-bg, #fef2f2);
    border-color: var(--color-error-border, #fca5a5);
    color: var(--color-error-text, #991b1b);
  }

  .error-display--warning {
    background-color: var(--color-warning-bg, #fffbeb);
    border-color: var(--color-warning-border, #fcd34d);
    color: var(--color-warning-text, #92400e);
  }

  .error-display--info {
    background-color: var(--color-info-bg, #eff6ff);
    border-color: var(--color-info-border, #93c5fd);
    color: var(--color-info-text, #1e40af);
  }

  .error-display__header {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2, 8px);
  }

  .error-display__icon {
    flex-shrink: 0;
    font-size: 1.1em;
    margin-top: 1px;
  }

  .error-display__message {
    flex: 1;
    margin: 0;
    font-size: var(--font-size-sm, 0.875rem);
    line-height: var(--line-height-relaxed, 1.625);
    font-weight: var(--font-weight-medium, 500);
  }

  .error-display__dismiss {
    flex-shrink: 0;
    background: none;
    border: none;
    cursor: pointer;
    color: inherit;
    opacity: 0.6;
    padding: 0;
    font-size: 0.9em;
    line-height: 1;
    transition: opacity 0.15s;
  }

  .error-display__dismiss:hover {
    opacity: 1;
  }

  .error-display__dismiss:focus-visible {
    outline: 2px solid currentColor;
    outline-offset: 2px;
    border-radius: 2px;
  }

  .error-display__suggestions {
    margin: var(--space-3, 12px) 0 0 var(--space-6, 24px);
    padding: 0;
    list-style: disc;
    font-size: var(--font-size-sm, 0.875rem);
    line-height: var(--line-height-relaxed, 1.625);
    opacity: 0.9;
  }

  .error-display__suggestion {
    margin-bottom: var(--space-1, 4px);
  }

  .error-display__actions {
    margin-top: var(--space-3, 12px);
    display: flex;
    gap: var(--space-2, 8px);
  }

  .error-display__retry-btn {
    background: transparent;
    border: 1px solid currentColor;
    color: inherit;
    padding: var(--space-1, 4px) var(--space-3, 12px);
    border-radius: var(--space-1, 4px);
    cursor: pointer;
    font-size: var(--font-size-sm, 0.875rem);
    font-weight: var(--font-weight-medium, 500);
    transition: background-color 0.15s;
  }

  .error-display__retry-btn:hover {
    background-color: rgba(0, 0, 0, 0.08);
  }

  .error-display__retry-btn:focus-visible {
    outline: 2px solid currentColor;
    outline-offset: 2px;
  }
</style>
