<script lang="ts">
	let { data } = $props();
</script>

<svelte:head>
	<title>Accesso SSO – UseIt</title>
</svelte:head>

<div class="wrap">
	{#if data?.error}
		<div class="card">
			<div class="icon">🔒</div>
			<h1>Accesso non riuscito</h1>
			<p class="msg">{data.error}</p>
			<a class="btn" href={data.portalUrl}>Torna al portale SSO</a>
		</div>
	{:else}
		<div class="card muted">
			<p>Accesso in corso…</p>
		</div>
	{/if}
</div>

<style>
	.wrap {
		min-height: 70vh;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 2rem 1rem;
		font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
	}

	.card {
		background: white;
		border-radius: 16px;
		box-shadow: 0 24px 64px rgba(0, 0, 0, 0.12);
		max-width: 440px;
		width: 100%;
		padding: 2.5rem 2rem;
		text-align: center;
		border: 1px solid #e5e7eb;
	}

	.card.muted {
		color: #6b7280;
	}

	.icon {
		font-size: 2.5rem;
		margin-bottom: 0.75rem;
	}

	h1 {
		color: #111827;
		font-size: 1.25rem;
		font-weight: 600;
		margin-bottom: 0.75rem;
	}

	.msg {
		color: #4b5563;
		font-size: 0.95rem;
		line-height: 1.6;
		margin-bottom: 1.75rem;
	}

	.btn {
		display: inline-block;
		background: linear-gradient(135deg, #4f46e5, #6366f1);
		color: white;
		padding: 0.65rem 1.5rem;
		border-radius: 8px;
		text-decoration: none;
		font-weight: 600;
		font-size: 0.95rem;
	}

	.btn:hover {
		opacity: 0.92;
	}
</style>
