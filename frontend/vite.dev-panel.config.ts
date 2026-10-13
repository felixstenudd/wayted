import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

const fromHere = (path: string) => fileURLToPath(new URL(path, import.meta.url))

export default defineConfig({
	root: fromHere('./src/dev-panel'),
	// VITE_ variables sit in the repository's .env, next to the compose files.
	envDir: fromHere('..'),
	plugins: [vue(), tailwindcss()],
	resolve: {
		alias: {
			'@': fromHere('./src'),
		},
	},
	build: {
		outDir: fromHere('./dist-dev-panel'),
		emptyOutDir: true,
		// MapLibre alone is larger than Vite's default limit.
		chunkSizeWarningLimit: 1500,
	},
	server: {
		port: 5174,
		strictPort: true,
		proxy: {
			'/api': {
				target: process.env.DEV_API_PROXY_TARGET ?? 'http://localhost:8001',
				changeOrigin: true,
				rewrite: (path) => path.replace(/^\/api/, ''),
			},
		},
	},
})
