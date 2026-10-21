<script setup lang="ts">
import type { FilterSpecification } from 'maplibre-gl'
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import {
	MapMarker,
	ringBounds,
	tokenColor,
	useMapClick,
	useMapFilter,
	useMapSource,
	useMapView,
	type MapData,
} from '@/features/map'

import { useShownRoute } from '../composables/useShownRoute'
import { formatKm } from '../distance'
import { labelPoints } from '../labels'
import { optionLetter } from '../options'
import { usePlannerStore } from '../store'

const { t } = useI18n()
const planner = usePlannerStore()
const { routes } = useShownRoute()
const { showBounds } = useMapView()

const lines = computed<MapData>(() => ({
	type: 'FeatureCollection',
	features: routes.value.map((route, index) => ({
		type: 'Feature',
		geometry: route.geometry,
		properties: { index },
	})),
}))

const round = { 'line-cap': 'round', 'line-join': 'round' } as const
const isShown = (): FilterSpecification => ['==', ['get', 'index'], planner.selectedOption]
const isOther = (): FilterSpecification => ['!=', ['get', 'index'], planner.selectedOption]

// The other options in graphite underneath; the shown one is the course, in overprint over an
// overprint-contrast edge so it reads on both themes.
useMapSource('route', lines, [
	{
		id: 'route-options',
		type: 'line',
		layout: round,
		filter: isOther(),
		paint: {
			'line-color': tokenColor('--graphite'),
			'line-width': 3.5,
			'line-opacity': 0.75,
		},
	},
	{
		id: 'route-edge',
		type: 'line',
		layout: round,
		filter: isShown(),
		paint: { 'line-color': tokenColor('--overprint-contrast'), 'line-width': 7 },
	},
	{
		id: 'route-line',
		type: 'line',
		layout: round,
		filter: isShown(),
		paint: { 'line-color': tokenColor('--overprint'), 'line-width': 4 },
	},
])
useMapFilter('route-options', isOther)
useMapFilter('route-edge', isShown)
useMapFilter('route-line', isShown)

useMapClick(['route-options'], (feature) => {
	if (feature) planner.selectOption(Number(feature.properties.index))
})

// A new search fits every option in view; stepping between them leaves the map be.
watch(routes, (found) => {
	if (found.length > 0)
		showBounds(ringBounds(found.flatMap((route) => route.geometry.coordinates)))
})

// One route is not a choice, so it goes unlabelled.
const labels = computed(() => {
	if (routes.value.length < 2) return []
	const points = labelPoints(routes.value.map((route) => route.geometry.coordinates))
	return routes.value.flatMap((route, index) => {
		const at = points[index]
		if (!at) return []
		const name = t('planner.options.label', {
			letter: optionLetter(index),
			km: formatKm(route.properties.length_m / 1000),
		})
		return [{ index, name, lonLat: { lon: at[0], lat: at[1] } }]
	})
})
</script>

<template>
	<MapMarker v-for="label in labels" :key="label.index" :lon-lat="label.lonLat" control>
		<button
			type="button"
			class="rounded-full border px-2 py-0.5 text-caption whitespace-nowrap transition-[color,background-color,border-color] duration-150 ease-out"
			:class="
				label.index === planner.selectedOption
					? 'border-overprint-contrast bg-overprint font-semibold text-overprint-contrast'
					: 'border-line bg-paper text-graphite hover:border-line-strong hover:text-ink'
			"
			:aria-pressed="label.index === planner.selectedOption"
			:aria-label="t('planner.options.show', { name: label.name })"
			@click="planner.selectOption(label.index)"
		>
			{{ label.name }}
		</button>
	</MapMarker>
</template>
