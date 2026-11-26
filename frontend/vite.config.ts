import adapter from '@sveltejs/adapter-node';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [sveltekit({ adapter: adapter() })],
	server: {
		// In dev mode, Vite proxies /api to the local backend
		proxy: { '/api': process.env.BUDGIE_API_URL ?? 'http://localhost:8000' }
	},
	test: {
		include: ['src/**/*.{test,spec}.ts'],
		coverage: {
			provider: 'v8',
			reporter: ['text', 'json-summary', 'lcov'],
			include: ['src/lib/**/*.ts'],
			exclude: ['src/**/*.test.ts', 'src/lib/types.ts']
		}
	}
});
