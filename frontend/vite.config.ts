import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		// In dev mode, Vite proxies /api to the local backend
		proxy: { '/api': process.env.BUDGIE_API_URL ?? 'http://localhost:8000' }
	}
});
