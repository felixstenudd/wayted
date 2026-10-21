import { computed, type ComputedRef } from 'vue'

import { usePlannerStore } from '../store'
import { skippedPoints } from '../throughPoints'
import { useShownRoute } from './useShownRoute'

/** The ids of the through points the user's edits took the shown route away from. */
export function useSkippedThroughPoints(): ComputedRef<number[]> {
	const planner = usePlannerStore()
	const { routes, shown } = useShownRoute()
	return computed(() => {
		const planned = routes.value[planner.selectedOption]
		// Out of date, the points may no longer be the ones the route was planned through.
		if (planner.isStale || planner.edit?.option !== planner.selectedOption) return []
		if (!planned || !shown.value) return []
		const skipped = skippedPoints(
			planner.throughPoints.map((point) => point.lonLat),
			planned.geometry.coordinates,
			shown.value.geometry.coordinates,
		)
		return planner.throughPoints.filter((_, index) => skipped[index]).map((point) => point.id)
	})
}
