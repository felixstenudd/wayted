import { VueQueryPlugin, type VueQueryPluginOptions } from '@tanstack/vue-query'

export const vueQueryOptions: VueQueryPluginOptions = {
	queryClientConfig: {
		defaultOptions: {
			queries: {
				// Route results and saved routes change rarely within a planning session.
				staleTime: 60_000,
				retry: 1,
			},
		},
	},
}

export { VueQueryPlugin }
