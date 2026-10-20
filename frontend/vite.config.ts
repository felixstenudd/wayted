import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

export default defineConfig({
	// VITE_ variables sit in the repository's .env, next to the compose files.
	envDir: fileURLToPath(new URL('..', import.meta.url)),
	plugins: [vue(), tailwindcss()],
	resolve: {
		alias: {
			'@': fileURLToPath(new URL('./src', import.meta.url)),
		},
	},
	server: {
		proxy: {
			'/api': {
				target: process.env.API_PROXY_TARGET ?? 'http://localhost:8000',
				changeOrigin: true,
				rewrite: (path) => path.replace(/^\/api/, ''),
			},
		},
	},
	test: {
		environment: 'jsdom',
		include: ['src/**/*.{test,spec}.ts'],
	},
})
