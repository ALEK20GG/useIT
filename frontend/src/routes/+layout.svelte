<script lang="ts">
	import favicon from '$lib/assets/favicon.svg';
	import { page } from '$app/stores';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<nav class="navbar">
	<div class="nav-container">
		<a href="/" class="nav-logo">
			<span class="logo-text">UseIt</span>
		</a>
		<div class="nav-links">
			<a href="/" class="nav-link" class:active={$page.url.pathname === '/'}>Home</a>
			<a href="/analyze" class="nav-link" class:active={$page.url.pathname === '/analyze'}>Scansiona</a>
			<a href="/semantic" class="nav-link" class:active={$page.url.pathname === '/semantic'}>Cerca</a>
		</div>
	</div>
</nav>

<main>
	{@render children()}
</main>

<style>
	:global(html, body) {
		height: 100%;
		width: 100%;
	}

	:global(body) {
		display: flex;
		flex-direction: column;
		overflow: visible;
	}

	:global(#svelte) {
		display: flex;
		flex-direction: column;
		height: 100vh;
		width: 100%;
	}

	:global(::-webkit-scrollbar) {
		width: 8px;
	}

	:global(::-webkit-scrollbar-track) {
		background: transparent;
	}

	:global(::-webkit-scrollbar-thumb) {
		background: #cbd5f5;
		border-radius: 4px;
	}

	:global(::-webkit-scrollbar-thumb:hover) {
		background: #a5b4fc;
	}

	nav {
		background: white;
		border-bottom: 1px solid #e5e7eb;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
		position: sticky;
		top: 0;
		z-index: 100;
		flex-shrink: 0;
	}

	.nav-container {
		max-width: 1200px;
		margin: 0 auto;
		padding: 1rem 1.5rem;
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.nav-logo {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		text-decoration: none;
		color: #111827;
		font-weight: 700;
		font-size: 1.25rem;
		transition: opacity 0.2s ease;
	}

	.nav-logo:hover {
		opacity: 0.8;
	}

	.logo-icon {
		font-size: 1.5rem;
	}

	.logo-text {
		background: linear-gradient(135deg, #4f46e5, #6366f1);
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
		background-clip: text;
	}

	.nav-links {
		display: flex;
		gap: 2rem;
		align-items: center;
	}

	.nav-link {
		text-decoration: none;
		color: #6b7280;
		font-weight: 500;
		font-size: 0.95rem;
		padding: 0.5rem 0;
		position: relative;
		transition: color 0.2s ease;
	}

	.nav-link:hover {
		color: #4f46e5;
	}

	.nav-link.active {
		color: #4f46e5;
	}

	.nav-link.active::after {
		content: '';
		position: absolute;
		bottom: 0;
		left: 0;
		right: 0;
		height: 2px;
		background: linear-gradient(135deg, #4f46e5, #6366f1);
		border-radius: 2px 2px 0 0;
	}

	main {
		flex: 1;
		overflow-y: auto;
		overflow-x: hidden;
		display: flex;
		flex-direction: column;
		min-height: 0;
	}

	@media (max-width: 640px) {
		.nav-container {
			padding: 0.75rem 1rem;
		}

		.nav-links {
			gap: 1rem;
		}

		.nav-link {
			font-size: 0.85rem;
		}
	}
</style>
