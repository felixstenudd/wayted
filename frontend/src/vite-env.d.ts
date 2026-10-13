/// <reference types="vite/client" />

interface ImportMetaEnv {
	// a MapLibre style document; see .env.example
	readonly VITE_MAP_STYLE_URL: string | undefined
}

interface ImportMeta {
	readonly env: ImportMetaEnv
}
