import { useQuery } from '@tanstack/vue-query'

import type { Bounds } from '@/features/map'

import { api } from '../../dev-api/client'
import { unwrap } from '../../dev-api/problem'

/** The graph, areas and lines last loaded, with their bounds. A load that fails keeps the one before. */
export function useGraph() {
	let requested: Bounds | null = null

	const { data, error, isFetching, refetch } = useQuery({
		// One key for every area, so an error leaves the last answer in place.
		queryKey: ['graph'],
		queryFn: async () => {
			if (!requested) throw new Error('No bounds requested.')
			const bounds = requested
			const graph = await unwrap(api.GET('/graph', { params: { query: bounds } }))
			// Only after the graph: its edge limit is what keeps the view small enough for areas.
			const areas = await unwrap(api.GET('/areas', { params: { query: bounds } }))
			const lines = await unwrap(api.GET('/lines', { params: { query: bounds } }))
			return { bounds, graph, areas, lines }
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
