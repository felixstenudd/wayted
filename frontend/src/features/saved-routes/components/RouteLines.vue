<script setup lang="ts">
import type { FilterSpecification } from 'maplibre-gl'
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import {
	MapMarker,
	ringBounds,
	tokenColor,
	useMapFilter,
	useMapSource,
	useMapView,
	type LonLat,
	type MapData,
} from '@/features/map'
import { CourseSymbol } from '@/shared/ui/course-symbol'

import { useSavedRoutes } from '../api'
import { useSavedRoutesStore } from '../store'

const NO_ROUTE = -1

const { t } = useI18n()
const routes = useSavedRoutes()
const store = useSavedRoutesStore()
const { bounds, showBounds } = useMapView()

const lines = computed<MapData>(() => ({
	type: 'FeatureCollection',
	features: (routes.data.value ?? []).map((route) => ({
		type: 'Feature',
		geometry: route.geometry,
		properties: { id: route.id },
	})),
}))

const round = { 'line-cap': 'round', 'line-join': 'round' } as const
const highlighted = (): FilterSpecification => [
	'==',
	['get', 'id'],
	store.highlightedId ?? NO_ROUTE,
]

// Every route in faint graphite; the one the list points at is lifted into the course style.
useMapSource('saved-routes', lines, [
	{
		id: 'saved-routes',
		type: 'line',
		layout: round,
		paint: { 'line-color': tokenColor('--graphite'), 'line-width': 3, 'line-opacity': 0.6 },
	},
	{
		id: 'saved-route-casing',
		type: 'line',
		layout: round,
		filter: ['==', ['get', 'id'], NO_ROUTE],
		paint: { 'line-color': tokenColor('--overprint-contrast'), 'line-width': 8 },
	},
	{
		id: 'saved-route',
		type: 'line',
		layout: round,
		filter: ['==', ['get', 'id'], NO_ROUTE],
		paint: { 'line-color': tokenColor('--overprint'), 'line-width': 5 },
	},
])
useMapFilter('saved-route-casing', highlighted)
useMapFilter('saved-route', highlighted)

const start = computed<LonLat | null>(() => {
	const route = routes.data.value?.find((r) => r.id === store.highlightedId)
	const [lon, lat] = route?.geometry.coordinates[0] ?? []
	return lon === undefined || lat === undefined ? null : { lon, lat }
})

// Show every route once they and the map are both there; after that the map is the user's.
let hasFitted = false
watch(
	[() => routes.data.value, bounds],
	([list, view]) => {
		if (hasFitted || !view || !list?.length) return
		hasFitted = true
		showBounds(ringBounds(list.flatMap((route) => route.geometry.coordinates)))
	},
	{ immediate: true },
)
</script>

<template>
	<MapMarker
		v-if="start"
		:key="store.highlightedId ?? NO_ROUTE"
		:lon-lat="start"
		:label="t('savedRoutes.start')"
	>
		<CourseSymbol kind="start" class="size-6 sm:size-7" />
	</MapMarker>
</template>
