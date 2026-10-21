<script setup lang="ts">
import type { FilterSpecification } from 'maplibre-gl'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import {
	EMPTY,
	MapMarker,
	ringBounds,
	tokenColor,
	useMapClick,
	useMapFilter,
	useMapLayerCursor,
	useMapLineDrag,
	useMapPaint,
	useMapSource,
	useMapView,
	type LonLat,
	type MapData,
} from '@/features/map'
import { useMediaQuery } from '@/shared/composables/useMediaQuery'

import { useRouteEditing } from '../composables/useRouteEditing'
import { useShownRoute } from '../composables/useShownRoute'
import { formatKm } from '../distance'
import { labelPoints } from '../labels'
import { optionLetter } from '../options'
import { usePlannerStore } from '../store'
import EditHandles from './EditHandles.vue'

const { t } = useI18n()
const planner = usePlannerStore()
const { routes, shown } = useShownRoute()
const { showBounds } = useMapView()
const editing = useRouteEditing()
// A finger hides the line it is on, so on touch a tap places a handle that is then dragged.
const isTouch = useMediaQuery('(pointer: coarse)')

// The shown option is drawn as it is now: edited, when the user has edited it.
const lines = computed<MapData>(() => ({
	type: 'FeatureCollection',
	// Once one is saved the others are let go.
	features: routes.value.flatMap((route, index) =>
		planner.isChosen && index !== planner.selectedOption
			? []
			: [
					{
						type: 'Feature' as const,
						geometry:
							index === planner.selectedOption && shown.value
								? shown.value.geometry
								: route.geometry,
						properties: { index },
					},
				],
	),
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
	// Wider than the line and not drawn, so the line is easy to grab.
	{
		id: 'route-hit',
		type: 'line',
		layout: round,
		filter: isShown(),
		paint: { 'line-color': tokenColor('--overprint'), 'line-width': 22, 'line-opacity': 0 },
	},
])
useMapFilter('route-options', isOther)
useMapFilter('route-edge', isShown)
useMapFilter('route-line', isShown)
useMapFilter('route-hit', isShown)
useMapLayerCursor('route-options', 'pointer')

// While an edit is on its way, or the route is out of date, the course dims; the drag that made an
// edit stays drawn until it answers.
const dropped = ref<{ grab: LonLat; drop: LonLat } | null>(null)
const tapped = ref<LonLat | null>(null)
const { grab, pointer, hover } = useMapLineDrag('route-hit', (from, to) => {
	if (isTouch.value) return
	dropped.value = { grab: from, drop: to }
	editing.dragLine(from, to)
})
watch(editing.isPending, (pending) => {
	if (!pending) dropped.value = null
})
const courseOpacity = () => (editing.isPending.value || planner.isStale ? 0.45 : 1)
useMapPaint('route-line', 'line-opacity', courseOpacity)
useMapPaint('route-edge', 'line-opacity', courseOpacity)

const band = computed<MapData>(() => {
	const from = dropped.value?.grab ?? grab.value
	const to = dropped.value?.drop ?? pointer.value
	if (!from || !to) return EMPTY
	return {
		type: 'Feature',
		geometry: {
			type: 'LineString',
			coordinates: [
				[from.lon, from.lat],
				[to.lon, to.lat],
			],
		},
		properties: {},
	}
})
useMapSource('route-band', band, [
	{
		id: 'route-band',
		type: 'line',
		layout: round,
		paint: {
			'line-color': tokenColor('--overprint-contrast'),
			'line-width': 2,
			'line-dasharray': [2, 2],
		},
	},
])
// The handle under the pointer, on a mouse: where a drag would take the line from.
const ghost = computed(() => (!isTouch.value && !grab.value && hover.value) || null)

useMapClick(['route-options', 'route-hit'], (feature, at) => {
	if (feature?.layerId === 'route-options') planner.selectOption(Number(feature.properties.index))
	tapped.value = isTouch.value && feature?.layerId === 'route-hit' ? at : null
})

function dragTapped(to: LonLat): void {
	if (tapped.value) editing.dragLine(tapped.value, to)
	tapped.value = null
}

// A new search fits every option in view; stepping between them leaves the map be.
watch(routes, (found) => {
	if (found.length > 0)
		showBounds(ringBounds(found.flatMap((route) => route.geometry.coordinates)))
})

// One route is not a choice, so it goes unlabelled. The shown one is labelled as it is now.
const labels = computed(() => {
	if (routes.value.length < 2 || planner.isChosen || planner.isStale) return []
	const drawn = routes.value.map((route, index) =>
		index === planner.selectedOption && shown.value ? shown.value : route,
	)
	const points = labelPoints(drawn.map((route) => route.geometry.coordinates))
	return drawn.flatMap((route, index) => {
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
	<MapMarker v-if="ghost" :lon-lat="ghost" class="pointer-events-none">
		<span class="block size-3.5 rounded-full border-2 border-overprint-contrast bg-paper" />
	</MapMarker>
	<EditHandles
		:handles="planner.editHandles"
		:tapped="tapped"
		@move="editing.moveHandle"
		@remove="editing.removeHandle"
		@drag-tapped="dragTapped"
	/>
</template>
