<script lang="ts">
	import favicon from '$lib/assets/favicon.svg';
	import { page } from '$app/stores';
	import HealthIndicator from '$lib/HealthIndicator.svelte';
	import '$lib/styles/design-system.css';

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
		/* Typography Scale - Based on modular scale */
		--font-size-xs: 0.75rem;     /* 12px */
		--font-size-sm: 0.875rem;    /* 14px */
		--font-size-base: 1rem;      /* 16px */
		--font-size-lg: 1.125rem;    /* 18px */
		--font-size-xl: 1.25rem;     /* 20px */
		--font-size-2xl: 1.5rem;     /* 24px */
		--font-size-3xl: 1.875rem;   /* 30px */
		--font-size-4xl: 2.25rem;    /* 36px */
		--font-size-5xl: 3rem;       /* 48px */
		
		/* Line Heights - Optimized for readability */
		--line-height-tight: 1.25;
		--line-height-snug: 1.375;
		--line-height-normal: 1.5;
		--line-height-relaxed: 1.625;
		--line-height-loose: 2;
		
		/* Letter Spacing - Subtle improvements */
		--letter-spacing-tighter: -0.05em;
		--letter-spacing-tight: -0.025em;
		--letter-spacing-normal: 0em;
		--letter-spacing-wide: 0.025em;
		--letter-spacing-wider: 0.05em;
		--letter-spacing-widest: 0.1em;
		
		/* Spacing Scale - 8px base unit system */
		--space-0: 0;
		--space-1: 0.25rem;    /* 4px */
		--space-2: 0.5rem;     /* 8px */
		--space-3: 0.75rem;    /* 12px */
		--space-4: 1rem;       /* 16px */
		--space-5: 1.25rem;    /* 20px */
		--space-6: 1.5rem;     /* 24px */
		--space-8: 2rem;       /* 32px */
		--space-10: 2.5rem;    /* 40px */
		--space-12: 3rem;      /* 48px */
		--space-16: 4rem;      /* 64px */
		--space-20: 5rem;      /* 80px */
		--space-24: 6rem;      /* 96px */
		
		/* Font Families */
		--font-family-sans: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji';
		--font-family-mono: ui-monospace, SFMono-Regular, 'SF Mono', Consolas, 'Liberation Mono', Menlo, monospace;
		
		/* Font Weights */
		--font-weight-thin: 100;
		--font-weight-light: 300;
		--font-weight-normal: 400;
		--font-weight-medium: 500;
		--font-weight-semibold: 600;
		--font-weight-bold: 700;
		--font-weight-extrabold: 800;
		--font-weight-black: 900;

		/* Base colors - Light mode */
		--color-bg: #ffffff;
		--color-bg-secondary: #f8fafc;
		--color-bg-tertiary: #f1f5f9;
		--color-text: #0f172a;
		--color-text-muted: #475569;
		--color-text-subtle: #64748b;
		--color-border: #e2e8f0;
		--color-border-subtle: #f1f5f9;
		--color-shadow: rgba(15, 23, 42, 0.08);
		--color-shadow-medium: rgba(15, 23, 42, 0.12);
		--color-shadow-strong: rgba(15, 23, 42, 0.16);
		
		/* Semantic color tokens - Light mode */
		--color-primary: #2563eb;
		--color-primary-hover: #1d4ed8;
		--color-primary-active: #1e40af;
		--color-primary-subtle: #dbeafe;
		--color-primary-muted: #93c5fd;
		
		--color-secondary: #64748b;
		--color-secondary-hover: #475569;
		--color-secondary-active: #334155;
		--color-secondary-subtle: #f1f5f9;
		--color-secondary-muted: #cbd5e1;
		
		--color-success: #047857;
		--color-success-hover: #059669;
		--color-success-active: #065f46;
		--color-success-subtle: #d1fae5;
		--color-success-muted: #6ee7b7;
		
		--color-warning: #b45309;
		--color-warning-hover: #d97706;
		--color-warning-active: #92400e;
		--color-warning-subtle: #fef3c7;
		--color-warning-muted: #fbbf24;
		
		--color-error: #dc2626;
		--color-error-hover: #b91c1c;
		--color-error-active: #991b1b;
		--color-error-subtle: #fee2e2;
		--color-error-muted: #f87171;
		
		/* Legacy compatibility - mapped to semantic tokens */
		--color-success-bg: var(--color-success-subtle);
		--color-success-text: var(--color-success);
		--color-success-border: var(--color-success-muted);
		--color-error-bg: var(--color-error-subtle);
		--color-error-text: var(--color-error);
		--color-error-border: var(--color-error-muted);
		--color-card-bg: var(--color-bg);
		--color-input-bg: var(--color-bg-secondary);
	}

	@media (prefers-color-scheme: dark) {
		:global(:root) {
			/* Base colors - Dark mode */
			--color-bg: #0f172a;
			--color-bg-secondary: #1e293b;
			--color-bg-tertiary: #334155;
			--color-text: #f8fafc;
			--color-text-muted: #cbd5e1;
			--color-text-subtle: #94a3b8;
			--color-border: #475569;
			--color-border-subtle: #334155;
			--color-shadow: rgba(0, 0, 0, 0.3);
			--color-shadow-medium: rgba(0, 0, 0, 0.4);
			--color-shadow-strong: rgba(0, 0, 0, 0.5);
			
			/* Semantic color tokens - Dark mode */
			--color-primary: #3b82f6;
			--color-primary-hover: #60a5fa;
			--color-primary-active: #2563eb;
			--color-primary-subtle: #1e3a8a;
			--color-primary-muted: #1d4ed8;
			
			--color-secondary: #94a3b8;
			--color-secondary-hover: #cbd5e1;
			--color-secondary-active: #e2e8f0;
			--color-secondary-subtle: #334155;
			--color-secondary-muted: #64748b;
			
			--color-success: #10b981;
			--color-success-hover: #34d399;
			--color-success-active: #059669;
			--color-success-subtle: #064e3b;
			--color-success-muted: #047857;
			
			--color-warning: #f59e0b;
			--color-warning-hover: #fbbf24;
			--color-warning-active: #d97706;
			--color-warning-subtle: #78350f;
			--color-warning-muted: #b45309;
			
			--color-error: #ef4444;
			--color-error-hover: #f87171;
			--color-error-active: #dc2626;
			--color-error-subtle: #7f1d1d;
			--color-error-muted: #b91c1c;
			
			/* Legacy compatibility - mapped to semantic tokens */
			--color-success-bg: var(--color-success-subtle);
			--color-success-text: var(--color-success);
			--color-success-border: var(--color-success-muted);
			--color-error-bg: var(--color-error-subtle);
			--color-error-text: var(--color-error);
			--color-error-border: var(--color-error-muted);
			--color-card-bg: var(--color-bg-secondary);
			--color-input-bg: var(--color-bg-tertiary);
		}
	}

	nav {
		background: var(--color-bg);
		border-bottom: 1px solid var(--color-border);
		box-shadow: 0 1px var(--space-1) var(--color-shadow);
		position: sticky;
		top: 0;
		z-index: 100;
	}

	.nav-container {
		max-width: 1200px;
		margin: 0 auto;
		padding: var(--space-4) var(--space-6);
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.nav-logo {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		text-decoration: none;
		color: var(--color-text);
		font-weight: var(--font-weight-bold);
		font-size: var(--font-size-xl);
		line-height: var(--line-height-tight);
		transition: opacity 0.2s ease;
	}

	.nav-logo:hover {
		opacity: 0.8;
	}

	.logo-icon {
		font-size: var(--font-size-2xl);
	}

	.logo-text {
		background: var(--color-primary);
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
		background-clip: text;
	}

	.nav-links {
		display: flex;
		gap: var(--space-8);
		align-items: center;
	}

	.nav-link {
		text-decoration: none;
		color: var(--color-text-muted);
		font-weight: var(--font-weight-medium);
		font-size: var(--font-size-sm);
		line-height: var(--line-height-normal);
		padding: var(--space-2) 0;
		position: relative;
		transition: color 0.2s ease;
	}

	.nav-link:hover {
		color: var(--color-primary);
	}

	.nav-link.active {
		color: var(--color-primary);
	}

	.nav-link.active::after {
		content: '';
		position: absolute;
		bottom: 0;
		left: 0;
		right: 0;
		height: 2px;
		background: var(--color-primary);
		border-radius: 2px 2px 0 0;
	}

	main {
		min-height: calc(100vh - 60px);
		background: var(--color-bg);
	}

	@media (max-width: 640px) {
		.nav-container {
			padding: var(--space-3) var(--space-4);
		}

		.nav-links {
			gap: var(--space-4);
		}

		.nav-link {
			font-size: var(--font-size-xs);
		}
	}
</style>
