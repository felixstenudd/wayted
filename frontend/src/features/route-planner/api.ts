import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, type ComputedRef } from 'vue'

import { useAuthStore } from '@/features/auth'
import type { LonLat } from '@/features/map'
import { storedPreferencesKey } from '@/features/route'

import { PREPARING_POLL_MS, routeState, shouldPoll, type RouteState } from './route'
import { usePlannerStore } from './store'
import type { RerouteAnswer, Route, RouteAnswer, StoredPreferences } from './types'

/**
 * The route for the planner's current search. The backend answers 202 until the map data around
 * the route is ready, so it is asked again every few seconds until it answers with the route.
 */
export function useFoundRoute(): ComputedRef<RouteState> {
	const auth = useAuthStore()
	const planner = usePlannerStore()
	const query = useQuery({
		queryKey: computed(() => ['routing', 'route', planner.search] as const),
		queryFn: ({ queryKey: [, , search] }) =>
			auth.authedRequest<RouteAnswer>('/routing/routes', {
				method: 'POST',
				body: search?.request,
			}),
		enabled: computed(() => planner.search !== null),
		// Each search is planned once; asking again is up to the user.
		staleTime: Infinity,
		refetchOnWindowFocus: false,
		// A failure is the answer: no route, or one that took the backend too long.
		retry: false,
		refetchInterval: ({ queryKey: [, , search], state }) =>
			search && shouldPoll(state.data, search.startedAt, state.dataUpdatedAt)
				? PREPARING_POLL_MS
				: false,
	})
	return computed(() =>
		routeState({
			isSearching: planner.search !== null,
			answer: query.data.value,
			error: query.error.value,
			isFetching: query.isFetching.value,
			startedAt: planner.search?.startedAt ?? 0,
			answeredAt: query.dataUpdatedAt.value,
		}),
	)
}

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

export const rerouteKey = ['routing', 'reroute'] as const

/** Moves the part of route around grab onto the road nearest drop; without drop, tidies it. */
export function useReroute() {
	const auth = useAuthStore()
	const planner = usePlannerStore()
	return useMutation({
		mutationKey: rerouteKey,
		mutationFn: ({
			route,
			grab,
			drop,
		}: {
			route: Route
			grab: LonLat
			drop: LonLat | null
		}) => {
			const request = planner.search?.request
			if (!request) throw new Error('There is no search whose route could be edited.')
			return auth.authedRequest<RerouteAnswer>('/routing/routes/reroute', {
				method: 'POST',
				body: {
					activity: request.activity,
					edges: route.properties.edges,
					grab,
					drop,
					...(request.target_distance_m
						? { target_distance_m: request.target_distance_m }
						: {}),
				},
			})
		},
	})
}
