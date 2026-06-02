import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	// Consult https://svelte.dev/docs/kit/integrations
	// for more information about preprocessors
	preprocess: vitePreprocess(),

	kit: {
		// adapter-node produces a standalone Node.js server — required for Docker deployments.
		// For local dev, `npm run dev` still works without building.
		adapter: adapter()
	}
};

export default config;
