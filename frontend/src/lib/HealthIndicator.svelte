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
    gap: 0.4rem;
    font-size: 0.85rem;
    font-weight: 500;
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
  }

  .online .dot {
    background-color: #22c55e;
  }

  .offline .dot {
    background-color: #ef4444;
  }

  .checking .dot {
    background-color: #d1d5db;
  }

  .online .label {
    color: #16a34a;
  }

  .offline .label {
    color: #dc2626;
  }

  .checking .label {
    color: #9ca3af;
  }
</style>
