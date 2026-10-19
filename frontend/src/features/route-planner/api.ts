import { useMutation, useQuery } from '@tanstack/vue-query'

import { useAuthStore } from '@/features/auth'

import type { RouteAttribute, RouteRequest } from './types'

export function useRouteAttributes() {
	const auth = useAuthStore()
	return useQuery({
		queryKey: ['routing', 'attributes'],
		queryFn: () => auth.authedRequest<RouteAttribute[]>('/routing/attributes'),
		// The list changes with a backend release, not during a session.
		staleTime: Infinity,
	})
}

/** Asks the backend for routes. Generation is not built yet, so for now it answers 501. */
export function useFindRoutes() {
	const auth = useAuthStore()
	return useMutation({
		mutationFn: (request: RouteRequest) =>
			auth.authedRequest<unknown>('/routing/routes', { method: 'POST', body: request }),
	})
}
