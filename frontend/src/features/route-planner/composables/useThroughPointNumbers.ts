import { computed, type ComputedRef } from 'vue'
import { useI18n } from 'vue-i18n'

import { useFoundRoute } from '../api'
import { usePlannerStore } from '../store'
import { throughPointNumbers } from '../throughPoints'

/**
 * Each through point's control number once a route says the order the planner chose (any change
 * to the points drops the route again), and its name: "Through point 2", or "Through point".
 */
export function useThroughPointNumbers(): {
	numbers: ComputedRef<(number | undefined)[]>
	nameOf: (id: number) => string
} {
	const { t } = useI18n()
	const planner = usePlannerStore()
	const state = useFoundRoute()

	const numbers = computed(() =>
		throughPointNumbers(
			// Out of date, the order may no longer be the points'.
			state.value.status === 'found' && !planner.isStale
				? (state.value.routes[0]?.properties.waypoint_order ?? null)
				: null,
			planner.throughPoints.length,
		),
	)

	function nameOf(id: number): string {
		const number = numbers.value[planner.throughPoints.findIndex((point) => point.id === id)]
		return number === undefined
			? t('planner.points.through.marker')
			: t('planner.points.through.numberedMarker', { n: number })
	}

	return { numbers, nameOf }
}
