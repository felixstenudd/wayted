import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { watch } from 'vue'

import { api } from '../../dev-api/client'
import { unwrap } from '../../dev-api/problem'
import { fetchedTilesKey } from '../fetched-tiles/api'
import { hasFinishedTiles } from './queue'

export const queuedTilesKey = ['tiles', 'queued']

const REFRESH_EVERY_MS = 5_000

export function useQueuedTiles() {
	const queryClient = useQueryClient()
	const query = useQuery({
		queryKey: queuedTilesKey,
		queryFn: () => unwrap(api.GET('/tiles/queued')),
		// Only while something is queued; an area request reloads it once.
		refetchInterval: (query) => (query.state.data?.features.length ? REFRESH_EVERY_MS : false),
		shallow: true,
	})

	// A tile that left the queue is fetched now, so the fetched tiles are out of date.
	watch(query.data, (after, before) => {
		if (before && after && hasFinishedTiles(before, after)) {
			void queryClient.invalidateQueries({ queryKey: fetchedTilesKey })
		}
	})

	return query
}
