import { useQuery } from '@tanstack/vue-query'

import { useAuthStore } from '@/features/auth'

import type { RouteSummary } from './types'

export const savedRoutesKey = ['logbook', 'routes'] as const

/** The user's saved routes, newest first. */
export function useSavedRoutes() {
	const auth = useAuthStore()
	return useQuery({
		queryKey: savedRoutesKey,
		queryFn: () => auth.authedRequest<RouteSummary[]>('/logbook/routes'),
	})
}
