<script lang="ts">
	import favicon from '$lib/assets/favicon.svg';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import HealthIndicator from '$lib/HealthIndicator.svelte';
	import OnboardingTour from '$lib/OnboardingTour.svelte';
	import { loadPersistedLocale } from '$lib/i18n';
	import '$lib/styles/design-system.css';

	let { children } = $props();

	// Load persisted locale on app init (Requirement 20.5)
	onMount(() => {
		loadPersistedLocale();
	});

	let mobileMenuOpen = $state(false);
	let menuButtonRef: HTMLButtonElement | null = $state(null);
	let firstMenuLinkRef: HTMLAnchorElement | null = $state(null);

	function toggleMobileMenu() {
		mobileMenuOpen = !mobileMenuOpen;
	}

	function closeMobileMenu() {
		mobileMenuOpen = false;
	}

	function handleMenuKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			mobileMenuOpen = false;
			menuButtonRef?.focus();
		}
	}

	// Close menu on route change
	$effect(() => {
		// Accessing $page.url.pathname triggers re-run on navigation
		const _ = $page.url.pathname;
		mobileMenuOpen = false;
	});

	// Trap focus in mobile menu when open
	onMount(() => {
		// nothing needed here; handled via keyboard events
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<!-- Skip to main content link for keyboard/screen reader users -->
<a href="#main-content" class="skip-link">Vai al contenuto principale</a>

<nav class="navbar" aria-label="Navigazione principale">
	<div class="nav-container">
		<a href="/" class="nav-logo" aria-label="UseIt – Home">
			<span class="logo-icon" aria-hidden="true">📦</span>
			<span class="logo-text">UseIt</span>
		</a>

		<!-- Desktop navigation -->
		<div class="nav-links">
			<a href="/" class="nav-link" class:active={$page.url.pathname === '/'} aria-current={$page.url.pathname === '/' ? 'page' : undefined}>Home</a>
			<a href="/analyze" class="nav-link" class:active={$page.url.pathname === '/analyze'} aria-current={$page.url.pathname === '/analyze' ? 'page' : undefined}>Scansiona</a>
			<a href="/semantic" class="nav-link" class:active={$page.url.pathname === '/semantic'} aria-current={$page.url.pathname === '/semantic' ? 'page' : undefined}>Cerca</a>
			<a href="/pdf" class="nav-link" class:active={$page.url.pathname === '/pdf'} aria-current={$page.url.pathname === '/pdf' ? 'page' : undefined}>PDF</a>
			<a href="/files" class="nav-link" class:active={$page.url.pathname === '/files'} aria-current={$page.url.pathname === '/files' ? 'page' : undefined}>File</a>
			<a href="/folders" class="nav-link" class:active={$page.url.pathname.startsWith('/folders')} aria-current={$page.url.pathname.startsWith('/folders') ? 'page' : undefined}>Cartelle</a>
			<a href="/user" class="nav-link" class:active={$page.url.pathname.startsWith('/user')} aria-current={$page.url.pathname.startsWith('/user') ? 'page' : undefined}>Area Personale</a>
			<a href="/help" class="nav-link" class:active={$page.url.pathname.startsWith('/help')} aria-current={$page.url.pathname.startsWith('/help') ? 'page' : undefined}>Guida</a>
			<HealthIndicator />
		</div>

		<!-- Hamburger button for mobile -->
		<button
			bind:this={menuButtonRef}
			class="hamburger-btn"
			aria-label={mobileMenuOpen ? 'Chiudi menu' : 'Apri menu'}
			aria-expanded={mobileMenuOpen}
			aria-controls="mobile-menu"
			onclick={toggleMobileMenu}
		>
			<span class="hamburger-line" class:open={mobileMenuOpen}></span>
			<span class="hamburger-line" class:open={mobileMenuOpen}></span>
			<span class="hamburger-line" class:open={mobileMenuOpen}></span>
		</button>
	</div>

	<!-- Mobile menu -->
	{#if mobileMenuOpen}
		<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
		<div
			id="mobile-menu"
			class="mobile-menu"
			role="navigation"
			aria-label="Menu mobile"
			onkeydown={handleMenuKeydown}
		>
			<a bind:this={firstMenuLinkRef} href="/" class="mobile-nav-link" class:active={$page.url.pathname === '/'} aria-current={$page.url.pathname === '/' ? 'page' : undefined} onclick={closeMobileMenu}>Home</a>
			<a href="/analyze" class="mobile-nav-link" class:active={$page.url.pathname === '/analyze'} aria-current={$page.url.pathname === '/analyze' ? 'page' : undefined} onclick={closeMobileMenu}>📷 Scansiona</a>
			<a href="/semantic" class="mobile-nav-link" class:active={$page.url.pathname === '/semantic'} aria-current={$page.url.pathname === '/semantic' ? 'page' : undefined} onclick={closeMobileMenu}>🔍 Cerca</a>
			<a href="/pdf" class="mobile-nav-link" class:active={$page.url.pathname === '/pdf'} aria-current={$page.url.pathname === '/pdf' ? 'page' : undefined} onclick={closeMobileMenu}>📄 PDF</a>
			<a href="/files" class="mobile-nav-link" class:active={$page.url.pathname === '/files'} aria-current={$page.url.pathname === '/files' ? 'page' : undefined} onclick={closeMobileMenu}>🗂️ File</a>
			<a href="/folders" class="mobile-nav-link" class:active={$page.url.pathname.startsWith('/folders')} aria-current={$page.url.pathname.startsWith('/folders') ? 'page' : undefined} onclick={closeMobileMenu}>📁 Cartelle</a>
			<a href="/user" class="mobile-nav-link" class:active={$page.url.pathname.startsWith('/user')} aria-current={$page.url.pathname.startsWith('/user') ? 'page' : undefined} onclick={closeMobileMenu}>👤 Area Personale</a>
			<a href="/help" class="mobile-nav-link" class:active={$page.url.pathname.startsWith('/help')} aria-current={$page.url.pathname.startsWith('/help') ? 'page' : undefined} onclick={closeMobileMenu}>❓ Guida</a>
			<div class="mobile-health">
				<HealthIndicator />
			</div>
		</div>
	{/if}
</nav>

<!-- Onboarding tour – shown automatically on first visit (Requirement 20.2) -->
<OnboardingTour autoShow={true} />

<main id="main-content" class="page-transition">
	{@render children()}
</main>

<style>
	/* Skip link for keyboard/screen reader accessibility */
	.skip-link {
		position: absolute;
		top: -100%;
		left: var(--space-4);
		z-index: 9999;
		background: var(--color-primary);
		color: white;
		padding: var(--space-3) var(--space-6);
		border-radius: 0 0 var(--space-2) var(--space-2);
		font-weight: var(--font-weight-semibold);
		font-size: var(--font-size-sm);
		text-decoration: none;
		transition: top 0.2s ease;
	}

	.skip-link:focus {
		top: 0;
		outline: 2px solid white;
		outline-offset: 2px;
	}

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
		min-height: 44px; /* WCAG touch target */
	}

	.nav-logo:hover {
		opacity: 0.8;
	}

	.nav-logo:focus-visible {
		outline: 2px solid var(--color-primary);
		outline-offset: 2px;
		border-radius: var(--space-1);
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

	/* Desktop nav links */
	.nav-links {
		display: flex;
		gap: var(--space-6);
		align-items: center;
	}

	.nav-link {
		text-decoration: none;
		color: var(--color-text-muted);
		font-weight: var(--font-weight-medium);
		font-size: var(--font-size-sm);
		line-height: var(--line-height-normal);
		padding: var(--space-2) var(--space-1);
		position: relative;
		transition: color 0.2s ease;
		min-height: 44px; /* WCAG touch target */
		display: inline-flex;
		align-items: center;
	}

	.nav-link:hover {
		color: var(--color-primary);
	}

	.nav-link:focus-visible {
		outline: 2px solid var(--color-primary);
		outline-offset: 2px;
		border-radius: var(--space-1);
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

	/* Hamburger button - hidden on desktop */
	.hamburger-btn {
		display: none;
		flex-direction: column;
		justify-content: center;
		align-items: center;
		gap: 5px;
		width: 44px;
		height: 44px;
		background: none;
		border: none;
		cursor: pointer;
		padding: var(--space-2);
		border-radius: var(--space-2);
		transition: background-color 0.2s ease;
	}

	.hamburger-btn:hover {
		background-color: var(--color-bg-secondary);
	}

	.hamburger-btn:focus-visible {
		outline: 2px solid var(--color-primary);
		outline-offset: 2px;
	}

	.hamburger-line {
		display: block;
		width: 22px;
		height: 2px;
		background-color: var(--color-text);
		border-radius: 2px;
		transition: transform 0.3s ease, opacity 0.3s ease;
		transform-origin: center;
	}

	/* Animate hamburger to X when open */
	.hamburger-line:nth-child(1).open {
		transform: translateY(7px) rotate(45deg);
	}

	.hamburger-line:nth-child(2).open {
		opacity: 0;
		transform: scaleX(0);
	}

	.hamburger-line:nth-child(3).open {
		transform: translateY(-7px) rotate(-45deg);
	}

	/* Mobile menu */
	.mobile-menu {
		display: flex;
		flex-direction: column;
		background: var(--color-bg);
		border-top: 1px solid var(--color-border);
		padding: var(--space-4) var(--space-6);
		gap: var(--space-1);
		animation: slide-in-down 0.2s ease-out;
	}

	.mobile-nav-link {
		text-decoration: none;
		color: var(--color-text-muted);
		font-weight: var(--font-weight-medium);
		font-size: var(--font-size-base);
		padding: var(--space-3) var(--space-4);
		border-radius: var(--space-2);
		transition: background-color 0.2s ease, color 0.2s ease;
		min-height: 44px; /* WCAG touch target */
		display: flex;
		align-items: center;
	}

	.mobile-nav-link:hover {
		background-color: var(--color-bg-secondary);
		color: var(--color-primary);
	}

	.mobile-nav-link:focus-visible {
		outline: 2px solid var(--color-primary);
		outline-offset: 2px;
	}

	.mobile-nav-link.active {
		background-color: var(--color-primary-subtle);
		color: var(--color-primary);
		font-weight: var(--font-weight-semibold);
	}

	.mobile-health {
		padding: var(--space-3) var(--space-4);
		border-top: 1px solid var(--color-border-subtle);
		margin-top: var(--space-2);
	}

	main {
		min-height: calc(100vh - 60px);
		background: var(--color-bg);
	}

	/* Responsive: show hamburger, hide desktop links on mobile */
	@media (max-width: 768px) {
		.nav-links {
			display: none;
		}

		.hamburger-btn {
			display: flex;
		}

		.nav-container {
			padding: var(--space-3) var(--space-4);
		}
	}

	/* Tablet: slightly smaller gaps */
	@media (min-width: 769px) and (max-width: 1024px) {
		.nav-links {
			gap: var(--space-4);
		}

		.nav-link {
			font-size: var(--font-size-xs);
		}
	}

	/* Reduced motion: disable menu animation */
	@media (prefers-reduced-motion: reduce) {
		.mobile-menu {
			animation: none;
		}

		.hamburger-line {
			transition: none;
		}
	}
</style>
