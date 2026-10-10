import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { watch } from 'vue'

import { api } from './client'
import { unwrap } from './problem'

const CHECK_EVERY_MS = 10_000

export function useHealth() {
	const queryClient = useQueryClient()
	const query = useQuery({
		queryKey: ['health'],
		queryFn: () => unwrap(api.GET('/health')),
		refetchInterval: CHECK_EVERY_MS,
	})

	// The dev API answers again: what failed to load while it was away can be loaded now.
	watch(query.isSuccess, (isUp) => {
		if (isUp) {
			void queryClient.refetchQueries({
				predicate: (other) => other.state.status === 'error',
			})
		}
	})

	return query
}
