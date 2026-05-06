<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { PUBLIC_BACKEND_URL } from '$env/static/public';

  const BACKEND_URL = PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

  let isOnline: boolean | null = null; // null = checking
  let intervalId: ReturnType<typeof setInterval> | null = null;

  async function checkHealth() {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);
    try {
      const res = await fetch(`${BACKEND_URL}/health`, { signal: controller.signal });
      isOnline = res.ok;
    } catch {
      isOnline = false;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  onMount(() => {
    checkHealth();
    intervalId = setInterval(checkHealth, 30000);
  });

  onDestroy(() => {
    if (intervalId !== null) clearInterval(intervalId);
  });
</script>

{#if isOnline === null}
  <span class="health-indicator checking">
    <span class="dot"></span>
    <span class="label">Checking...</span>
  </span>
{:else if isOnline}
  <span class="health-indicator online">
    <span class="dot"></span>
    <span class="label">Online</span>
  </span>
{:else}
  <span class="health-indicator offline">
    <span class="dot"></span>
    <span class="label">Offline</span>
  </span>
{/if}

<style>
  .health-indicator {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    line-height: var(--line-height-tight);
    transition: all 0.2s ease;
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
    transition: all 0.2s ease;
  }

  .online .dot {
    background-color: var(--color-success);
    box-shadow: 0 0 var(--space-2) var(--color-success);
  }

  .offline .dot {
    background-color: var(--color-error);
    box-shadow: 0 0 var(--space-2) var(--color-error);
  }

  .checking .dot {
    background-color: var(--color-secondary-muted);
    animation: pulse 2s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% {
      opacity: 1;
    }
    50% {
      opacity: 0.5;
    }
  }

  .online .label {
    color: var(--color-success);
  }

  .offline .label {
    color: var(--color-error);
  }

  .checking .label {
    color: var(--color-text-subtle);
  }

  .label {
    transition: color 0.2s ease;
  }
</style>
