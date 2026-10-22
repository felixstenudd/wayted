import { computed, type ComputedRef } from 'vue'

import { useFoundRoute } from '../api'
import { usePlannerStore } from '../store'
import type { Route } from '../types'

/**
 * The routes found for the current search, the best first, and the one the user is looking at:
 * their edited copy of it, when they have edited it.
 */
export function useShownRoute(): {
	routes: ComputedRef<Route[]>
	shown: ComputedRef<Route | null>
} {
	const planner = usePlannerStore()
	const state = useFoundRoute()
	const routes = computed(() => (state.value.status === 'found' ? state.value.routes : []))
	// Nothing is shown until the routes are there, edits included: they are of one of them.
	const shown = computed(() => {
		if (routes.value.length === 0) return null
		return planner.edit?.option === planner.selectedOption
			? planner.editedRoute
			: (routes.value[Math.min(planner.selectedOption, routes.value.length - 1)] ?? null)
	})
	return { routes, shown }
}
