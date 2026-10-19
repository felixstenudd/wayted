import { useQuery } from '@tanstack/vue-query'

import { useAuthStore } from '@/features/auth'

import type { RouteAttribute } from './types'

export function useRouteAttributes() {
	const auth = useAuthStore()
	return useQuery({
		queryKey: ['routing', 'attributes'],
		queryFn: () => auth.authedRequest<RouteAttribute[]>('/routing/attributes'),
		// The list changes with a backend release, not during a session.
		staleTime: Infinity,
	})
}
