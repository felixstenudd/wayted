import { useQuery } from '@tanstack/vue-query'

import { api } from '../../dev-api/client'
import { unwrap } from '../../dev-api/problem'

export const queuedTilesKey = ['tiles', 'queued']

const REFRESH_EVERY_MS = 5_000

export function useQueuedTiles() {
	return useQuery({
		queryKey: queuedTilesKey,
		queryFn: () => unwrap(api.GET('/tiles/queued')),
		// Only while something is queued; an area request reloads it once.
		refetchInterval: (query) => (query.state.data?.features.length ? REFRESH_EVERY_MS : false),
		shallow: true,
	})
}
