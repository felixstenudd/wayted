import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import { useAuthStore } from '@/features/auth'
import { storedPreferencesKey } from '@/features/route'

import type { ReviewReason } from './reasons'
import type {
	NewStretchReview,
	RouteReviewInput,
	RouteSummary,
	SavedRoute,
	SavedRouteReview,
	SegmentReview,
	StretchReviewChange,
} from './types'

export const savedRoutesKey = ['logbook', 'routes'] as const
const savedRouteKey = (id: number) => [...savedRoutesKey, id] as const

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
			// The review nudged the user's default weights, which the planner starts from.
			void queryClient.invalidateQueries({ queryKey: storedPreferencesKey })
		},
	})
}

/** What a stretch review can say. */
export function useReviewReasons() {
	const auth = useAuthStore()
	return useQuery({
		queryKey: ['logbook', 'review-reasons'],
		queryFn: () => auth.authedRequest<ReviewReason[]>('/logbook/review-reasons'),
		// The list changes with a backend release, not during a session.
		staleTime: Infinity,
	})
}

const segmentReviewsKey = (routeId: number) =>
	[...savedRouteKey(routeId), 'segment-reviews'] as const

/** The user's stretch reviews on one route, in route order. */
export function useSegmentReviews(routeId: MaybeRefOrGetter<number>) {
	const auth = useAuthStore()
	return useQuery({
		queryKey: computed(() => segmentReviewsKey(toValue(routeId))),
		queryFn: () =>
			auth.authedRequest<SegmentReview[]>(
				`/logbook/routes/${toValue(routeId)}/segment-reviews`,
			),
	})
}

/** Creates a stretch review, or changes one when given its id; the stretch of one never changes. */
export function useSaveSegmentReview(routeId: MaybeRefOrGetter<number>) {
	const auth = useAuthStore()
	const queryClient = useQueryClient()
	return useMutation({
		mutationFn: (
			input:
				| ({ reviewId: null } & NewStretchReview)
				| ({ reviewId: number } & StretchReviewChange),
		) => {
			const { reviewId, ...body } = input
			return reviewId === null
				? auth.authedRequest<SegmentReview>(
						`/logbook/routes/${toValue(routeId)}/segment-reviews`,
						{ method: 'POST', body },
					)
				: auth.authedRequest<SegmentReview>(`/logbook/segment-reviews/${reviewId}`, {
						method: 'PATCH',
						body,
					})
		},
		onSuccess: () =>
			queryClient.invalidateQueries({ queryKey: segmentReviewsKey(toValue(routeId)) }),
	})
}

export function useDeleteSegmentReview(routeId: MaybeRefOrGetter<number>) {
	const auth = useAuthStore()
	const queryClient = useQueryClient()
	return useMutation({
		mutationFn: (reviewId: number) =>
			auth.authedRequest<void>(`/logbook/segment-reviews/${reviewId}`, { method: 'DELETE' }),
		onSuccess: () =>
			queryClient.invalidateQueries({ queryKey: segmentReviewsKey(toValue(routeId)) }),
	})
}
