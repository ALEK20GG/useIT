<script lang="ts">
	let { data } = $props();

	const profile = $derived(
		data.user
			? {
					email: data.user.email,
					name: data.user.name,
					googleId: data.user.googleId,
					picture: data.user.picture
				}
			: null
	);
</script>

<svelte:head>
	<title>Sessione SSO – UseIt</title>
</svelte:head>

<div class="wrap">
	<h1>Sessione (test produzione)</h1>
	<p class="lead">
		Il client ha <strong>verificato la firma</strong> del JWT del portale (stesso <code>JWT_SECRET</code>,
		<code>iss</code>, <code>aud</code>) e ha salvato in sessione i campi utente più uno snapshot dei
		<strong>claims</strong> decodificati.
	</p>

	{#if data.user}
		<section class="card">
			<h2>Profilo (dal JWT)</h2>
			<pre>{JSON.stringify(profile, null, 2)}</pre>
		</section>
		<section class="card">
			<h2>Claims portale (snapshot)</h2>
			<pre>{JSON.stringify(data.user.portalClaims ?? {}, null, 2)}</pre>
		</section>
	{:else}
		<p>Non autenticato.</p>
	{/if}
</div>

<style>
	.wrap {
		max-width: 800px;
		margin: 0 auto;
		padding: 1.5rem 1rem 3rem;
		font-family: system-ui, sans-serif;
	}
	h1 {
		font-size: 1.5rem;
		margin-bottom: 0.5rem;
	}
	.lead {
		color: #4b5563;
		line-height: 1.6;
		margin-bottom: 1.5rem;
		font-size: 0.95rem;
	}
	.card {
		background: #fff;
		border: 1px solid #e5e7eb;
		border-radius: 12px;
		padding: 1rem 1.25rem;
		margin-bottom: 1.25rem;
		box-shadow: 0 4px 14px rgba(0, 0, 0, 0.04);
	}
	h2 {
		font-size: 1rem;
		margin: 0 0 0.75rem;
		color: #111827;
	}
	pre {
		margin: 0;
		font-size: 0.8rem;
		line-height: 1.45;
		overflow: auto;
		background: #f9fafb;
		padding: 1rem;
		border-radius: 8px;
		border: 1px solid #e5e7eb;
	}
	code {
		font-size: 0.85em;
		background: #f3f4f6;
		padding: 0.1em 0.35em;
		border-radius: 4px;
	}
</style>
