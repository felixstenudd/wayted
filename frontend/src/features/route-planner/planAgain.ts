import type { SavedRoute } from '@/features/saved-routes'

import type { SavedPlan } from './types'

/** What a saved route was planned from: its settings, and the ends of its line for its points. */
export function planOf(
	route: Pick<
		SavedRoute,
		'activity' | 'shape' | 'target_distance_m' | 'preferences' | 'waypoints' | 'geometry'
	>,
): SavedPlan | null {
	const first = route.geometry.coordinates[0]
	const last = route.geometry.coordinates.at(-1)
	if (!first || !last) return null
	return {
		activity: route.activity,
		shape: route.shape,
		start: { lon: first[0], lat: first[1] },
		finish: { lon: last[0], lat: last[1] },
		targetDistanceM: route.target_distance_m,
		preferences: route.preferences,
		waypoints: route.waypoints,
	}
}
