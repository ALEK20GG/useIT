<script lang="ts">
	import { onMount } from 'svelte';
	import { PUBLIC_BACKEND_URL } from '$env/static/public';
	import { sanitizeHtml } from '$lib/sanitize';

	const BACKEND_URL = PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

	// Upload state
	let selectedFile: File | null = null;
	let isDragging = false;
	let uploadLoading = false;
	let uploadMessage = '';
	let uploadError = '';

	// Search state
	interface PDFSearchResult {
		filename: string;
		relative_url: string;
		score: number;
		preview_text: string;
		page_number: number | null;
	}

	interface PDFSearchResponse {
		results: PDFSearchResult[];
		total: number;
		offset: number;
		limit: number;
	}

	let searchQuery = '';
	let searchLoading = false;
	let searchError = '';
	let searchResults: PDFSearchResult[] = [];
	let searchTotal = 0;
	let searchOffset = 0;
	let searchLimit = 20;
	let filenameFilter = '';
	let deletingResultFiles = new Set<string>();

	// Index all state
	let indexLoading = false;
	let indexMessage = '';
	let indexError = '';

	// Preview state
	let previewPdf: string | null = null;
	let showPreview = false;

	// Tab state
	let currentTab = 'upload';

	// Library state
	interface IndexedPDF {
		filename: string;
		relative_url: string;
		chunk_count: number;
		indexed_at: string;
	}

	let libraryPdfs: IndexedPDF[] = [];
	let libraryLoading = false;
	let libraryError = '';
	let reindexingFiles = new Set<string>();
	let deletingFiles = new Set<string>();

	async function loadLibrary() {
		libraryLoading = true;
		libraryError = '';
		try {
			const res = await fetch(`${BACKEND_URL}/pdf/list`);
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			libraryPdfs = await res.json();
		} catch (err) {
			libraryError = err instanceof Error ? err.message : 'Errore nel caricamento della libreria.';
		} finally {
			libraryLoading = false;
		}
	}

	async function reindexPdf(filename: string) {
		reindexingFiles = new Set([...reindexingFiles, filename]);
		try {
			const res = await fetch(`${BACKEND_URL}/pdf/reindex/${encodeURIComponent(filename)}`, { method: 'POST' });
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			await loadLibrary();
		} catch (err) {
			libraryError = err instanceof Error ? err.message : 'Errore durante la re-indicizzazione.';
		} finally {
			reindexingFiles = new Set([...reindexingFiles].filter(f => f !== filename));
		}
	}

	async function deleteFromLibrary(filename: string) {
		deletingFiles = new Set([...deletingFiles, filename]);
		try {
			const res = await fetch(`${BACKEND_URL}/pdf/${encodeURIComponent(filename)}`, { method: 'DELETE' });
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			libraryPdfs = libraryPdfs.filter(p => p.filename !== filename);
		} catch (err) {
			libraryError = err instanceof Error ? err.message : "Errore durante l'eliminazione.";
		} finally {
			deletingFiles = new Set([...deletingFiles].filter(f => f !== filename));
		}
	}

	function switchTab(tab: string) {
		currentTab = tab;
		if (tab === 'library') loadLibrary();
	}

	function onFileChange(event: Event) {
		const target = event.target as HTMLInputElement;
		const file = target.files?.[0];
		handleNewFile(file ?? null);
	}

	function handleNewFile(file: File | null) {
		uploadError = '';
		uploadMessage = '';

		if (!file) {
			selectedFile = null;
			return;
		}

		if (!file.name.toLowerCase().endsWith('.pdf')) {
			uploadError = 'Per favore seleziona un file PDF.';
			return;
		}

		selectedFile = file;
	}

	function onDragOver(event: DragEvent) {
		event.preventDefault();
		isDragging = true;
	}

	function onDragLeave(event: DragEvent) {
		event.preventDefault();
		isDragging = false;
	}

	function onDrop(event: DragEvent) {
		event.preventDefault();
		isDragging = false;
		const file = event.dataTransfer?.files?.[0];
		handleNewFile(file ?? null);
	}

	async function uploadPDF() {
		uploadError = '';
		uploadMessage = '';

		if (!selectedFile) {
			uploadError = 'Prima seleziona un file PDF da caricare.';
			return;
		}

		uploadLoading = true;
		try {
			const formData = new FormData();
			formData.append('file', selectedFile);

			const res = await fetch(`${BACKEND_URL}/pdf/upload`, {
				method: 'POST',
				body: formData
			});

			if (!res.ok) {
				const data = await res.json().catch(() => ({}));
				throw new Error(data.detail ?? `Errore durante il caricamento (status ${res.status})`);
			}

			const data = await res.json();
			uploadMessage = data.message ?? 'PDF caricato e indicizzato con successo!';

			// Reset del file selezionato dopo il caricamento
			selectedFile = null;

			// Reset del file input
			const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
			if (fileInput) {
				fileInput.value = '';
			}
		} catch (err) {
			uploadError = err instanceof Error ? err.message : 'Si è verificato un errore durante il caricamento.';
		} finally {
			uploadLoading = false;
		}
	}

	async function indexAllPDFs() {
		indexError = '';
		indexMessage = '';

		indexLoading = true;
		try {
			console.log(`Calling ${BACKEND_URL}/pdf/index-all`);
			const res = await fetch(`${BACKEND_URL}/pdf/index-all`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				}
			});

			console.log(`Response status: ${res.status}`);

			if (!res.ok) {
				const data = await res.json().catch(() => {
					// If JSON parsing fails, get text instead
					return res.text().then(text => ({ detail: text || `Errore HTTP ${res.status}` }));
				});
				const errorMsg = data.detail ?? data.message ?? `Errore durante l'indicizzazione (status ${res.status})`;
				throw new Error(errorMsg);
			}

			const data = await res.json();
			console.log('Response data:', data);
			indexMessage = data.message ?? `Indicizzati ${data.indexed} PDF su ${data.total}`;
			if (data.errors && data.errors.length > 0) {
				indexMessage += `. Errori: ${data.errors.join(', ')}`;
			}
			if (data.directory) {
				indexMessage += ` (directory: ${data.directory})`;
			}
		} catch (err) {
			console.error('Error indexing PDFs:', err);
			if (err instanceof TypeError && err.message.includes('fetch')) {
				indexError = `Errore di connessione: il backend potrebbe non essere in esecuzione. Assicurati che il backend sia avviato su ${BACKEND_URL}`;
			} else {
				indexError = err instanceof Error ? err.message : 'Si è verificato un errore durante l\'indicizzazione.';
			}
		} finally {
			indexLoading = false;
		}
	}


	function highlightQuery(text: string, query: string): string {
		const sanitized = sanitizeHtml(text);
		if (!query.trim()) return sanitized;
		const words = query.trim().split(/\s+/).filter(Boolean);
		let result = sanitized;
		for (const word of words) {
			const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
			result = result.replace(new RegExp(escaped, 'gi'), (match) => `<mark>${match}</mark>`);
		}
		return result;
	}

	async function searchPDFs(newOffset = 0) {
		searchError = '';
		searchResults = [];
		searchOffset = newOffset;

		if (!searchQuery.trim()) {
			searchError = 'Per favore inserisci una query di ricerca.';
			return;
		}

		searchLoading = true;
		try {
			const body: Record<string, unknown> = {
				query: searchQuery,
				collection_name: 'pdfs',
				limit: searchLimit,
				offset: searchOffset
			};
			if (filenameFilter) body.filename_filter = filenameFilter;

			const res = await fetch(`${BACKEND_URL}/pdf/search`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(body)
			});

			if (!res.ok) {
				const data = await res.json().catch(() => ({}));
				throw new Error(data.detail ?? `Errore durante la ricerca (status ${res.status})`);
			}

			const data: PDFSearchResponse = await res.json();
			searchResults = data.results;
			searchTotal = data.total;

			if (data.results.length === 0) {
				searchError = 'Nessun PDF trovato per questa query.';
			}
		} catch (err) {
			searchError = err instanceof Error ? err.message : 'Si è verificato un errore durante la ricerca.';
		} finally {
			searchLoading = false;
		}
	}

	async function deleteSearchResult(filename: string) {
		deletingResultFiles = new Set([...deletingResultFiles, filename]);
		try {
			const res = await fetch(`${BACKEND_URL}/pdf/${encodeURIComponent(filename)}`, { method: 'DELETE' });
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			searchResults = searchResults.filter((r) => r.filename !== filename);
			searchTotal = Math.max(0, searchTotal - 1);
		} catch (err) {
			searchError = err instanceof Error ? err.message : "Errore durante l'eliminazione.";
		} finally {
			deletingResultFiles = new Set([...deletingResultFiles].filter((f) => f !== filename));
		}
	}

	function openPreview(url: string) {
		previewPdf = url;
		showPreview = true;
	}

	function closePreview() {
		showPreview = false;
		previewPdf = null;
	}

	function openPdfInNewTab(url: string) {
		window.open(url, '_blank');
	}

	onMount(() => {
		// Auto-index PDFs on mount
		// indexAllPDFs();
	});
</script>

<svelte:head>
	<title>Gestione PDF – UseIt</title>
</svelte:head>

<main class="page page-transition">
	<section class="hero">
		<div class="hero-text">
			<h1>Gestione PDF</h1>
			<p>Carica PDF nella cartella pdf-source e cercali semanticamente usando Qdrant.</p>
		</div>
	</section>

	<section class="tabs-section">
		<div class="tabs">
			<button class="tab-button" class:active={currentTab === 'upload'} on:click={() => switchTab('upload')}>Carica PDF</button>
			<button class="tab-button" class:active={currentTab === 'search'} on:click={() => switchTab('search')}>Cerca PDF</button>
			<button class="tab-button" class:active={currentTab === 'library'} on:click={() => switchTab('library')}>Libreria</button>
		</div>
	</section>

	{#if currentTab === 'upload'}
		<section class="upload-section">
			<div class="layout">
				<div
					class="dropzone"
					class:is-dragging={isDragging}
					role="button"
					tabindex="0"
					aria-label="Area di caricamento PDF - trascina qui i file o clicca per selezionare"
					on:dragover|preventDefault={onDragOver}
					on:dragleave={onDragLeave}
					on:drop={onDrop}
					on:keydown={(e) => {
						if (e.key === 'Enter' || e.key === ' ') {
							e.preventDefault();
							const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
							fileInput?.click();
						}
					}}
					on:click={() => {
						const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
						fileInput?.click();
					}}
				>
					<div class="dropzone-inner">
						{#if selectedFile}
							<div class="file-info">
								<div class="file-icon">📄</div>
								<p class="file-name">{selectedFile.name}</p>
								<p class="file-size">{(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
							</div>
						{:else}
							<div class="placeholder-icon">📄</div>
						{/if}

						<div class="instructions">
							<p>
								<strong>Trascina qui</strong> un file PDF<br />
								oppure
							</p>

							<label class="btn btn-secondary">
								Scegli file
								<input type="file" accept=".pdf,application/pdf" on:change={onFileChange} />
							</label>
						</div>
					</div>
				</div>

				<div class="side-card">
					<h2>Caricamento</h2>
					<button
						class="btn btn-primary"
						on:click|preventDefault={uploadPDF}
						disabled={uploadLoading || !selectedFile}
					>
						{#if uploadLoading}
							<span class="spinner spinner-sm"></span>
							<span>Caricamento...</span>
						{:else}
							Carica PDF
						{/if}
					</button>

					{#if uploadMessage}
						<p class="status success">{uploadMessage}</p>
					{/if}
					{#if uploadError}
						<p class="status error">{uploadError}</p>
					{/if}

					<div class="divider"></div>

					<h3>Indicizza PDF esistenti</h3>
					<p class="muted">Indicizza tutti i PDF già presenti nella cartella pdf-source</p>
					<button
						class="btn btn-secondary"
						on:click|preventDefault={indexAllPDFs}
						disabled={indexLoading}
					>
						{#if indexLoading}
							<span class="spinner spinner-sm"></span>
							<span>Indicizzazione...</span>
						{:else}
							Indicizza tutti i PDF
						{/if}
					</button>

					{#if indexMessage}
						<p class="status success">{indexMessage}</p>
					{/if}
					{#if indexError}
						<p class="status error">{indexError}</p>
					{/if}
				</div>
			</div>
		</section>
	{:else if currentTab === 'search'}
		<section class="search-section">
			<div class="search-form-container">
				<div class="search-form">
					<label>
						<span>Query di ricerca</span>
						<input
							type="text"
							bind:value={searchQuery}
							placeholder="es: 'concetti di algebra' o 'calcoli matematici'"
							on:keydown={(e) => e.key === 'Enter' && searchPDFs(0)}
						/>
					</label>

					<label>
						<span>Filtra per nome file</span>
						<input
							type="text"
							bind:value={filenameFilter}
							placeholder="es: 'algebra.pdf'"
							on:keydown={(e) => e.key === 'Enter' && searchPDFs(0)}
						/>
					</label>

					<button
						class="btn btn-primary"
						on:click|preventDefault={() => searchPDFs(0)}
						disabled={searchLoading || !searchQuery.trim()}
					>
						{#if searchLoading}
							<span class="spinner spinner-sm"></span>
							<span>Ricerca...</span>
						{:else}
							Cerca
						{/if}
					</button>
				</div>

				{#if searchError}
					<p class="status error">{searchError}</p>
				{/if}
			</div>

			{#if searchResults.length > 0}
				<div class="results fade-in">
					<h2>Risultati ({searchTotal})</h2>
					<div class="results-grid">
						{#each searchResults as result, index}
							<div class="result-card scale-in" style="animation-delay: {index * 0.05}s;">
								<div class="result-header">
									<h3>{result.filename}</h3>
									<span class="score">{(result.score * 100).toFixed(1)}%</span>
								</div>
								{#if result.page_number !== null && result.page_number !== undefined}
									<p class="page-number">Pagina {result.page_number}</p>
								{/if}
								<p class="preview-text">{@html highlightQuery(result.preview_text, searchQuery)}...</p>
								<div class="result-actions">
									<button class="btn btn-sm" on:click={() => openPreview(result.relative_url)}>
										👁️ Preview
									</button>
									<button class="btn btn-secondary btn-sm" on:click={() => openPdfInNewTab(result.relative_url)}>
										📄 Apri in nuova scheda
									</button>
									<button
										class="btn btn-error btn-sm"
										on:click={() => deleteSearchResult(result.filename)}
										disabled={deletingResultFiles.has(result.filename)}
									>
										{#if deletingResultFiles.has(result.filename)}
											<span class="spinner spinner-sm"></span>
										{:else}
											🗑️
										{/if}
									</button>
								</div>
							</div>
						{/each}
					</div>
					<div class="pagination">
						<button
							class="btn btn-secondary btn-sm"
							on:click={() => searchPDFs(searchOffset - searchLimit)}
							disabled={searchOffset === 0 || searchLoading}
						>
							← Precedente
						</button>
						<span class="pagination-info">
							{searchOffset + 1}–{Math.min(searchOffset + searchLimit, searchTotal)} di {searchTotal}
						</span>
						<button
							class="btn btn-secondary btn-sm"
							on:click={() => searchPDFs(searchOffset + searchLimit)}
							disabled={searchOffset + searchLimit >= searchTotal || searchLoading}
						>
							Successivo →
						</button>
					</div>
				</div>
			{/if}
		</section>
	{:else if currentTab === 'library'}
		<section class="library-section">
			{#if libraryLoading}
				<div class="loading-container">
					<span class="spinner spinner-lg"></span>
					<p class="muted">Caricamento libreria...</p>
				</div>
			{:else if libraryError}
				<p class="status error">{libraryError}</p>
			{:else if libraryPdfs.length === 0}
				<p class="muted">Nessun PDF indicizzato.</p>
			{:else}
				<div class="library-list fade-in">
					{#each libraryPdfs as pdf, index}
						<div class="library-item scale-in" style="animation-delay: {index * 0.05}s;">
							<div class="library-info">
								<strong>{pdf.filename}</strong>
								<span class="muted">{pdf.chunk_count} chunk · {new Date(pdf.indexed_at).toLocaleDateString('it-IT')}</span>
							</div>
							<div class="library-actions">
								<button
									class="btn btn-secondary btn-sm"
									on:click={() => reindexPdf(pdf.filename)}
									disabled={reindexingFiles.has(pdf.filename)}
								>
									{#if reindexingFiles.has(pdf.filename)}
										<span class="spinner spinner-sm"></span>
										<span>Re-indicizzazione...</span>
									{:else}
										Re-indicizza
									{/if}
								</button>
								<button
									class="btn btn-error btn-sm"
									on:click={() => deleteFromLibrary(pdf.filename)}
									disabled={deletingFiles.has(pdf.filename)}
								>
									{#if deletingFiles.has(pdf.filename)}
										<span class="spinner spinner-sm"></span>
									{:else}
										🗑️ Elimina
									{/if}
								</button>
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</section>
	{/if}
</main>

{#if showPreview && previewPdf}
	<div 
		class="modal-overlay fade-in" 
		role="dialog" 
		aria-modal="true" 
		aria-label="Anteprima PDF"
		tabindex="-1"
		on:click={closePreview} 
		on:keydown={(e) => {
			if (e.key === 'Escape') {
				closePreview();
			} else if (e.key === 'Enter' || e.key === ' ') {
				e.preventDefault();
				closePreview();
			}
		}}
	>
		<div class="modal-content slide-in-up" role="document">
			<div class="modal-header">
				<h2>Anteprima PDF</h2>
				<button 
					class="close-button" 
					on:click={closePreview}
					on:keydown={(e) => {
						if (e.key === 'Enter' || e.key === ' ') {
							e.preventDefault();
							closePreview();
						}
					}}
					aria-label="Chiudi anteprima PDF"
				>✕</button>
			</div>
			<div class="modal-body">
				<iframe 
					src={previewPdf} 
					class="pdf-preview" 
					title="Anteprima del documento PDF - {previewPdf ? previewPdf.split('/').pop()?.replace('.pdf', '') || 'documento' : 'documento'}"
				></iframe>
				<div class="modal-actions">
					<button class="btn btn-primary" on:click={() => openPdfInNewTab(previewPdf!)}>
						Apri in nuova scheda
					</button>
					<button class="btn btn-secondary" on:click={closePreview}>Chiudi</button>
				</div>
			</div>
		</div>
	</div>
{/if}

<style>
	:global(.page) {
		max-width: 1200px;
		margin: 0 auto;
		padding: var(--space-8) var(--space-6);
	}

	.hero {
		margin-bottom: var(--space-12);
	}

	.hero-text {
		text-align: center;
	}

	.hero-text h1 {
		font-size: var(--font-size-5xl);
		font-weight: var(--font-weight-bold);
		line-height: var(--line-height-tight);
		letter-spacing: var(--letter-spacing-tight);
		margin-bottom: var(--space-4);
		color: var(--color-text);
	}

	.hero-text p {
		font-size: var(--font-size-lg);
		line-height: var(--line-height-relaxed);
		color: var(--color-text-muted);
	}

	.tabs-section {
		margin-bottom: var(--space-8);
		border-bottom: 2px solid var(--color-border);
	}

	.tabs {
		display: flex;
		gap: var(--space-4);
		max-width: 1200px;
		margin: 0 auto;
		padding: 0 var(--space-6);
	}

	.tab-button {
		padding: var(--space-3) var(--space-6);
		border: none;
		background: transparent;
		color: var(--color-text-muted);
		font-weight: var(--font-weight-medium);
		font-size: var(--font-size-base);
		line-height: var(--line-height-normal);
		cursor: pointer;
		border-bottom: 2px solid transparent;
		margin-bottom: -2px;
		transition: all 0.2s;
	}

	.tab-button:hover {
		color: #4f46e5;
	}

	.tab-button.active {
		color: #4f46e5;
		border-bottom-color: #4f46e5;
	}

	.layout {
		display: grid;
		grid-template-columns: 1fr 400px;
		gap: var(--space-8);
		margin-top: var(--space-8);
	}

	.dropzone {
		border: 2px dashed var(--color-border);
		border-radius: var(--space-3);
		padding: var(--space-12) var(--space-8);
		text-align: center;
		transition: all 0.3s ease;
		background: var(--color-bg-secondary);
		cursor: pointer;
	}

	.dropzone:focus {
		outline: 2px solid #4f46e5;
		outline-offset: var(--space-1);
	}

	.dropzone.is-dragging {
		border-color: #4f46e5;
		background-color: #eef2ff;
	}

	.dropzone-inner {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--space-6);
	}

	.placeholder-icon {
		font-size: var(--font-size-5xl);
		margin-bottom: var(--space-2);
	}

	.file-info {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--space-2);
	}

	.file-icon {
		font-size: var(--font-size-4xl);
	}

	.file-name {
		font-weight: var(--font-weight-semibold);
		color: var(--color-text);
		margin: 0;
	}

	.file-size {
		color: var(--color-text-muted);
		font-size: var(--font-size-sm);
		margin: 0;
	}

	.instructions {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--space-4);
	}

	.instructions p {
		margin: 0;
		color: var(--color-text-muted);
		line-height: var(--line-height-relaxed);
	}

	input[type='file'] {
		display: none;
	}

	.side-card {
		background: var(--color-card-bg);
		padding: var(--space-6);
		border-radius: var(--space-3);
		box-shadow: 0 1px var(--space-1) var(--color-shadow);
		height: fit-content;
	}

	.side-card h2,
	.side-card h3 {
		margin-top: 0;
		margin-bottom: var(--space-4);
		color: var(--color-text);
		font-size: var(--font-size-xl);
		font-weight: var(--font-weight-semibold);
		line-height: var(--line-height-snug);
	}

	.side-card .btn {
		width: 100%;
		margin-bottom: var(--space-4);
	}

	.divider {
		height: 1px;
		background: var(--color-border);
		margin: var(--space-6) 0;
	}

	.muted {
		color: var(--color-text-muted);
		font-size: var(--font-size-sm);
		line-height: var(--line-height-relaxed);
		margin-bottom: var(--space-4);
	}

	.status {
		padding: var(--space-3);
		border-radius: var(--space-2);
		margin-top: var(--space-4);
	}

	.status.success {
		background-color: var(--color-success-bg);
		color: var(--color-success-text);
		border: 1px solid var(--color-success-border);
	}

	.status.error {
		background-color: var(--color-error-bg);
		color: var(--color-error-text);
		border: 1px solid var(--color-error-border);
	}

	/* Search Section */
	.search-section {
		margin-top: var(--space-8);
	}

	.search-form-container {
		margin-bottom: var(--space-8);
	}

	.search-form {
		display: flex;
		gap: var(--space-4);
		align-items: flex-end;
	}

	.search-form label {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
	}

	.search-form label span {
		font-weight: var(--font-weight-medium);
		color: var(--color-text);
		font-size: var(--font-size-sm);
		line-height: var(--line-height-normal);
	}

	.search-form input[type='text'] {
		padding: var(--space-3);
		border: 1px solid var(--color-border);
		border-radius: var(--space-2);
		font-size: var(--font-size-base);
		line-height: var(--line-height-normal);
		background: var(--color-input-bg);
		color: var(--color-text);
		transition: border-color 0.2s;
	}

	.search-form input[type='text']:focus {
		outline: none;
		border-color: #4f46e5;
		box-shadow: 0 0 0 var(--space-1) rgba(79, 70, 229, 0.1);
	}

	.results {
		margin-top: var(--space-8);
	}

	.results h2 {
		margin-bottom: var(--space-6);
		color: var(--color-text);
		font-size: var(--font-size-2xl);
		font-weight: var(--font-weight-semibold);
		line-height: var(--line-height-snug);
	}

	.results-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
		gap: var(--space-6);
	}

	.result-card {
		background: var(--color-card-bg);
		padding: var(--space-6);
		border-radius: var(--space-3);
		box-shadow: 0 1px var(--space-1) var(--color-shadow);
		transition: transform 0.2s, box-shadow 0.2s;
	}

	.result-card:hover {
		transform: translateY(-2px);
		box-shadow: 0 var(--space-1) var(--space-3) rgba(0, 0, 0, 0.15);
	}

	.result-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: var(--space-4);
		gap: var(--space-4);
	}

	.result-header h3 {
		margin: 0;
		font-size: var(--font-size-base);
		color: #4f46e5;
		font-weight: var(--font-weight-semibold);
		line-height: var(--line-height-snug);
		flex: 1;
		word-break: break-word;
	}

	.score {
		background: linear-gradient(135deg, #4f46e5, #6366f1);
		color: white;
		padding: var(--space-1) var(--space-3);
		border-radius: var(--space-3);
		font-size: var(--font-size-xs);
		font-weight: var(--font-weight-semibold);
		line-height: var(--line-height-tight);
		white-space: nowrap;
	}

	.preview-text {
		color: var(--color-text-muted);
		margin: 0 0 var(--space-4) 0;
		line-height: var(--line-height-relaxed);
		font-size: var(--font-size-sm);
	}

	.result-actions {
		display: flex;
		gap: var(--space-2);
		flex-wrap: wrap;
	}

	.result-actions .btn {
		flex: 1;
		min-width: 120px;
	}

	/* Modal */
	.modal-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.75);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
		padding: var(--space-8);
	}

	.modal-content {
		background: var(--color-card-bg);
		border-radius: var(--space-3);
		width: 100%;
		max-width: 900px;
		max-height: 90vh;
		display: flex;
		flex-direction: column;
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: var(--space-6);
		border-bottom: 1px solid var(--color-border);
	}

	.modal-header h2 {
		margin: 0;
		color: var(--color-text);
		font-size: var(--font-size-xl);
		font-weight: var(--font-weight-semibold);
		line-height: var(--line-height-snug);
	}

	.close-button {
		background: none;
		border: none;
		font-size: var(--font-size-xl);
		cursor: pointer;
		color: var(--color-text-muted);
		padding: 0;
		width: 32px;
		height: 32px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: var(--space-1);
		transition: background-color 0.2s;
	}

	.close-button:hover {
		background-color: var(--color-bg-secondary);
	}

	.modal-body {
		padding: var(--space-6);
		flex: 1;
		overflow: auto;
		display: flex;
		flex-direction: column;
	}

	.pdf-preview {
		width: 100%;
		height: 600px;
		border: 1px solid var(--color-border);
		border-radius: var(--space-2);
		margin-bottom: var(--space-4);
	}

	.modal-actions {
		display: flex;
		gap: var(--space-4);
		justify-content: flex-end;
	}

	@media (max-width: 768px) {
		:global(.page) {
			padding: var(--space-6) var(--space-4);
		}

		.hero {
			margin-bottom: var(--space-8);
		}

		.hero-text h1 {
			font-size: var(--font-size-3xl);
		}

		.tabs {
			padding: 0 var(--space-4);
			gap: var(--space-2);
		}

		.tab-button {
			padding: var(--space-2) var(--space-4);
			font-size: var(--font-size-sm);
		}

		.layout {
			grid-template-columns: 1fr;
			gap: var(--space-6);
		}

		.dropzone {
			padding: var(--space-8) var(--space-4);
		}

		.search-form {
			flex-direction: column;
			gap: var(--space-4);
		}

		.results-grid {
			grid-template-columns: 1fr;
			gap: var(--space-4);
		}

		.modal-overlay {
			padding: var(--space-4);
		}

		.modal-content {
			max-width: 100%;
			max-height: 100%;
			margin: 0;
			border-radius: 0;
		}

		.modal-header,
		.modal-body {
			padding: var(--space-4);
		}

		.pdf-preview {
			height: 400px;
		}

		.library-item {
			flex-direction: column;
			align-items: flex-start;
			padding: var(--space-4);
		}

		.library-actions {
			width: 100%;
			justify-content: flex-end;
		}

		.pagination {
			flex-wrap: wrap;
			gap: var(--space-2);
		}

		.btn,
		:global(button),
		:global(input[type='text']),
		:global(input[type='file']) {
			min-height: 44px;
		}
	}

	/* Library Section */
	.library-section {
		margin-top: var(--space-8);
	}

	.loading-container {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: var(--space-4);
		padding: var(--space-12);
	}

	.library-list {
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
	}

	.library-item {
		background: var(--color-card-bg);
		padding: var(--space-4) var(--space-6);
		border-radius: var(--space-2);
		box-shadow: 0 1px var(--space-1) var(--color-shadow);
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: var(--space-4);
	}

	.library-info {
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
	}

	.library-actions {
		display: flex;
		gap: var(--space-2);
		flex-shrink: 0;
	}

	.page-number {
		font-size: var(--font-size-xs);
		color: var(--color-primary);
		font-weight: var(--font-weight-medium);
		line-height: var(--line-height-tight);
		margin: 0 0 var(--space-2) 0;
	}

	.pagination {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: var(--space-4);
		margin-top: var(--space-8);
	}

	.pagination-info {
		color: var(--color-text-muted);
		font-size: var(--font-size-sm);
		line-height: var(--line-height-normal);
	}

	:global(mark) {
		background-color: var(--color-warning-subtle);
		color: var(--color-warning-active);
		border-radius: 2px;
		padding: 0 1px;
	}
</style>

