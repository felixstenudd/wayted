import { computed, defineComponent, watch } from 'vue'

import { EMPTY, ringBounds, tokenColor, useMapSource, useMapView } from '@/features/map'

import { useFoundRoute } from '../api'

/** Draws the found route on the map and fits the map to it. Renders nothing in the page. */
export default defineComponent({
	name: 'RouteLine',
	setup() {
		const state = useFoundRoute()
		const route = computed(() =>
			state.value.status === 'found' ? (state.value.routes[0] ?? null) : null,
		)
		const { showBounds } = useMapView()

		// The course is drawn in overprint over an overprint-contrast edge, so it shows on both
		// themes.
		useMapSource('route', () => route.value ?? EMPTY, [
			{
				id: 'route-edge',
				type: 'line',
				layout: { 'line-cap': 'round', 'line-join': 'round' },
				paint: { 'line-color': tokenColor('--overprint-contrast'), 'line-width': 7 },
			},
			{
				id: 'route-line',
				type: 'line',
				layout: { 'line-cap': 'round', 'line-join': 'round' },
				paint: { 'line-color': tokenColor('--overprint'), 'line-width': 4 },
			},
		])

		watch(route, (found) => {
			if (found) showBounds(ringBounds(found.geometry.coordinates))
		})

		return () => null
	},
})
