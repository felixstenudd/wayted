import { useQuery } from '@tanstack/vue-query'

import { api } from './client'
import { unwrap } from './problem'

const CHECK_EVERY_MS = 10_000

export function useHealth() {
	return useQuery({
		queryKey: ['health'],
		queryFn: () => unwrap(api.GET('/health')),
		refetchInterval: CHECK_EVERY_MS,
	})
}
