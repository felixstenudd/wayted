import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import { useAuthStore } from '@/features/auth'

import type { Answer } from './review'
import type { RouteSummary, SavedRoute, SavedRouteReview } from './types'

export const savedRoutesKey = ['logbook', 'routes'] as const
const savedRouteKey = (id: number) => [...savedRoutesKey, id] as const
// The user's default weights, which a route review nudges.
const preferencesKey = ['logbook', 'preferences'] as const

/** The user's saved routes, newest first. */
export function useSavedRoutes() {
	const auth = useAuthStore()
	return useQuery({
		queryKey: savedRoutesKey,
		queryFn: () => auth.authedRequest<RouteSummary[]>('/logbook/routes'),
	})
}

export function useSavedRoute(id: MaybeRefOrGetter<number>) {
	const auth = useAuthStore()
	return useQuery({
		queryKey: computed(() => savedRouteKey(toValue(id))),
		queryFn: () => auth.authedRequest<SavedRoute>(`/logbook/routes/${toValue(id)}`),
	})
}

export function useRenameRoute(id: MaybeRefOrGetter<number>) {
	const auth = useAuthStore()
	const queryClient = useQueryClient()
	return useMutation({
		mutationFn: (name: string) =>
			auth.authedRequest<RouteSummary>(`/logbook/routes/${toValue(id)}`, {
				method: 'PATCH',
				body: { name },
			}),
		onSuccess: (renamed) => {
			queryClient.setQueryData<SavedRoute>(savedRouteKey(renamed.id), (route) =>
				route ? { ...route, name: renamed.name } : route,
			)
			void queryClient.invalidateQueries({ queryKey: savedRoutesKey, exact: true })
		},
	})
}

export function useDeleteRoute(id: MaybeRefOrGetter<number>) {
	const auth = useAuthStore()
	const queryClient = useQueryClient()
	return useMutation({
		mutationFn: () =>
			auth.authedRequest<void>(`/logbook/routes/${toValue(id)}`, { method: 'DELETE' }),
		onSuccess: () => {
			queryClient.removeQueries({ queryKey: savedRouteKey(toValue(id)) })
			void queryClient.invalidateQueries({ queryKey: savedRoutesKey, exact: true })
		},
	})
}

export interface RouteReviewInput {
	answers: Record<string, Answer>
	comment: string | null
}

/** Creates or replaces the review; the answer says which of the user's weights moved. */
export function useSaveRouteReview(id: MaybeRefOrGetter<number>) {
	const auth = useAuthStore()
	const queryClient = useQueryClient()
	return useMutation({
		mutationFn: (review: RouteReviewInput) =>
			auth.authedRequest<SavedRouteReview>(`/logbook/routes/${toValue(id)}/review`, {
				method: 'PUT',
				body: review,
			}),
		onSuccess: (saved) => {
			queryClient.setQueryData<SavedRoute>(savedRouteKey(toValue(id)), (route) =>
				route ? { ...route, review: saved.review } : route,
			)
			void queryClient.invalidateQueries({ queryKey: preferencesKey })
		},
	})
}
