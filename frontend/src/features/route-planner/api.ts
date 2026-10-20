import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'

import { useAuthStore } from '@/features/auth'

import type { RouteAttribute, RouteRequest, StoredPreferences } from './types'

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

// Exported for route reviews, which nudge these weights and mark them stale.
export const storedPreferencesKey = ['logbook', 'preferences'] as const

/** The user's stored weights, which the planner starts from. */
export function useStoredPreferences() {
	const auth = useAuthStore()
	return useQuery({
		queryKey: storedPreferencesKey,
		queryFn: () => auth.authedRequest<StoredPreferences>('/logbook/preferences'),
	})
}

export function useSaveDefaults() {
	const auth = useAuthStore()
	const queryClient = useQueryClient()
	return useMutation({
		mutationFn: (weights: Record<string, number>) =>
			auth.authedRequest<StoredPreferences>('/logbook/preferences', {
				method: 'PUT',
				body: { weights },
			}),
		onSuccess: (saved) => queryClient.setQueryData(storedPreferencesKey, saved),
	})
}
