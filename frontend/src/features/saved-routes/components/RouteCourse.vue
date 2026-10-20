<script setup lang="ts">
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import {
	distanceM,
	EMPTY,
	MapMarker,
	ringBounds,
	tokenColor,
	useMapPaint,
	useMapSource,
	useMapView,
	type LonLat,
	type MapData,
} from '@/features/map'
import { CourseSymbol } from '@/shared/ui/course-symbol'

import { useSavedRoute } from '../api'
import { chevronsAlong } from '../chevrons'
import { useSavedRoutesStore } from '../store'
import StretchLayers from './StretchLayers.vue'

const props = defineProps<{ routeId: number }>()

// About a dozen direction marks, but never closer than this.
const MIN_CHEVRON_SPACING_M = 250
const CHEVRON_COUNT = 12
// A finish this close to the start is the same place: one symbol is enough there.
const SAME_PLACE_M = 30

const { t } = useI18n()
const saved = useSavedRoute(() => props.routeId)
const store = useSavedRoutesStore()
const { bounds, showBounds } = useMapView()

const coordinates = computed(() => saved.data.value?.geometry.coordinates ?? [])
const line = computed<MapData>(() =>
	saved.data.value
		? { type: 'Feature', geometry: saved.data.value.geometry, properties: {} }
		: EMPTY,
)

const toLonLat = (point: readonly number[] | undefined): LonLat | null => {
	const [lon, lat] = point ?? []
	return lon === undefined || lat === undefined ? null : { lon, lat }
}
const start = computed(() => toLonLat(coordinates.value[0]))
const finish = computed(() => {
	const end = toLonLat(coordinates.value.at(-1))
	if (!end || !start.value) return end
	return distanceM(start.value, end) < SAME_PLACE_M ? null : end
})
const chevrons = computed(() => {
	const distance = saved.data.value?.distance_m ?? 0
	const spacing = Math.max(MIN_CHEVRON_SPACING_M, distance / CHEVRON_COUNT)
	return chevronsAlong(coordinates.value, spacing)
})

const round = { 'line-cap': 'round', 'line-join': 'round' } as const
useMapSource('saved-route-course', line, [
	{
		id: 'saved-route-course-casing',
		type: 'line',
		layout: round,
		paint: { 'line-color': tokenColor('--overprint-contrast'), 'line-width': 8 },
	},
	{
		id: 'saved-route-course',
		type: 'line',
		layout: round,
		paint: { 'line-color': tokenColor('--overprint'), 'line-width': 5 },
	},
])

// While a stretch is picked, the rest of the course steps back: a pale line without its edge.
useMapPaint('saved-route-course-casing', 'line-opacity', () => (store.isPickingStretch ? 0 : 1))
useMapPaint('saved-route-course', 'line-opacity', () => (store.isPickingStretch ? 0.45 : 1))

// Fit each route once, when it and the map are both there; after that the map is the user's.
let fittedId: number | null = null
watch(
	[() => saved.data.value, bounds],
	([route, view]) => {
		if (!route || !view || fittedId === route.id) return
		fittedId = route.id
		showBounds(ringBounds(route.geometry.coordinates))
	},
	{ immediate: true },
)
</script>

<template>
	<StretchLayers v-if="store.isPickingStretch" :route-id="routeId" />
	<MapMarker
		v-for="(chevron, index) in chevrons"
		:key="`${routeId}-${index}`"
		:lon-lat="chevron.at"
	>
		<svg
			viewBox="0 0 12 12"
			class="size-3"
			:style="{ transform: `rotate(${chevron.bearingDeg - 90}deg)` }"
		>
			<path
				d="M4 2.5 7.5 6 4 9.5"
				class="fill-none stroke-overprint-contrast"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
			/>
		</svg>
	</MapMarker>
	<MapMarker
		v-if="finish"
		:key="`${routeId}-finish`"
		:lon-lat="finish"
		:label="t('savedRoutes.finish')"
	>
		<CourseSymbol kind="finish" class="size-6 sm:size-7" />
	</MapMarker>
	<MapMarker
		v-if="start"
		:key="`${routeId}-start`"
		:lon-lat="start"
		:label="t('savedRoutes.start')"
	>
		<CourseSymbol kind="start" class="size-6 sm:size-7" />
	</MapMarker>
</template>
