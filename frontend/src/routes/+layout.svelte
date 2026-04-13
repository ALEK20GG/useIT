<script lang="ts">
	import favicon from '$lib/assets/favicon.svg';
	import { page } from '$app/stores';
	import HealthIndicator from '$lib/HealthIndicator.svelte';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<nav class="navbar">
	<div class="nav-container">
		<a href="/" class="nav-logo">
			<span class="logo-icon">📦</span>
			<span class="logo-text">UseIt</span>
		</a>
		<div class="nav-links">
			<a href="/" class="nav-link" class:active={$page.url.pathname === '/'}>Home</a>
			<a href="/analyze" class="nav-link" class:active={$page.url.pathname === '/analyze'}>Scansiona</a>
			<a href="/semantic" class="nav-link" class:active={$page.url.pathname === '/semantic'}>Cerca</a>
			<a href="/pdf" class="nav-link" class:active={$page.url.pathname === '/pdf'}>PDF</a>
			<HealthIndicator />
		</div>
	</div>
</nav>

<main>
	{@render children()}
</main>

<style>
	:global(:root) {
		--color-bg: #ffffff;
		--color-bg-secondary: #f9fafb;
		--color-text: #111827;
		--color-text-muted: #6b7280;
		--color-border: #e5e7eb;
		--color-shadow: rgba(0, 0, 0, 0.1);
		--color-primary: #4f46e5;
		--color-primary-hover: #4338ca;
		--color-success-bg: #d1fae5;
		--color-success-text: #065f46;
		--color-success-border: #a7f3d0;
		--color-error-bg: #fee2e2;
		--color-error-text: #991b1b;
		--color-error-border: #fecaca;
		--color-card-bg: #ffffff;
		--color-input-bg: #f9fafb;
	}

	@media (prefers-color-scheme: dark) {
		:global(:root) {
			--color-bg: #111827;
			--color-bg-secondary: #1f2937;
			--color-text: #f9fafb;
			--color-text-muted: #9ca3af;
			--color-border: #374151;
			--color-shadow: rgba(0, 0, 0, 0.4);
			--color-primary: #818cf8;
			--color-primary-hover: #6366f1;
			--color-success-bg: #064e3b;
			--color-success-text: #6ee7b7;
			--color-success-border: #065f46;
			--color-error-bg: #7f1d1d;
			--color-error-text: #fca5a5;
			--color-error-border: #991b1b;
			--color-card-bg: #1f2937;
			--color-input-bg: #374151;
		}
	}

	nav {
		background: var(--color-bg);
		border-bottom: 1px solid var(--color-border);
		box-shadow: 0 1px 3px var(--color-shadow);
		position: sticky;
		top: 0;
		z-index: 100;
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
		color: var(--color-text);
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
		color: var(--color-text-muted);
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
		min-height: calc(100vh - 60px);
		background: var(--color-bg);
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
