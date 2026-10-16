import { useQuery } from '@tanstack/vue-query'

import type { Bounds } from '@/features/map'

import { api } from '../../dev-api/client'
import { unwrap } from '../../dev-api/problem'

/** The graph last loaded, with its bounds. A load that fails keeps the one before. */
export function useGraph() {
	let requested: Bounds | null = null

	const { data, error, isFetching, refetch } = useQuery({
		// One key for every area, so an error leaves the last answer in place.
		queryKey: ['graph'],
		queryFn: async () => {
			if (!requested) throw new Error('No bounds requested.')
			const bounds = requested
			const graph = await unwrap(api.GET('/graph', { params: { query: bounds } }))
			return { bounds, graph }
		},
		// Runs only when load is called. One answer can be 13 MB, so none is cached.
		enabled: false,
		gcTime: 0,
		shallow: true,
	})

	function load(bounds: Bounds) {
		requested = bounds
		void refetch()
	}

	return { loaded: data, error, isFetching, load }
}
