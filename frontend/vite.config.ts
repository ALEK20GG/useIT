import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		// So redirects to both http://127.0.0.1:5173 and http://localhost:5173 work during SSO testing
		host: true
	}
});
