import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { watch } from 'vue'

import { api } from '../../dev-api/client'
import { unwrap } from '../../dev-api/problem'
import { fetchedTilesKey } from '../fetched-tiles/api'
import { hasFinishedTiles, hasPendingWork } from './queue'

export const queuedTilesKey = ['tiles', 'queued']
export const pendingWorkKey = ['pending']

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

	// A tile that left the queue is fetched now: the fetched tiles are out of date, and the
	// mapper and the enricher have new work.
	watch(query.data, (after, before) => {
		if (before && after && hasFinishedTiles(before, after)) {
			void queryClient.invalidateQueries({ queryKey: fetchedTilesKey })
			void queryClient.invalidateQueries({ queryKey: pendingWorkKey })
		}
	})

	return query
}

/** What the mapper and the enricher have left to do. */
export function usePendingWork() {
	return useQuery({
		queryKey: pendingWorkKey,
		queryFn: () => unwrap(api.GET('/pending')),
		// Only while work is left; a fetched tile brings more and reloads it.
		refetchInterval: (query) => {
			const pending = query.state.data
			return pending && hasPendingWork(pending) ? REFRESH_EVERY_MS : false
		},
	})
}
