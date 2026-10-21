<script setup lang="ts">
import type { FilterSpecification } from 'maplibre-gl'
import { computed, onScopeDispose, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import {
	distanceM,
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

import { useDragPreview } from '../composables/useDragPreview'
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

// Where the line was let go, until the edit that makes answers.
const dropped = ref<LonLat | null>(null)
const tapped = ref<LonLat | null>(null)
// One edit at a time: while one is on its way the line cannot be taken.
const { grab, pointer, hover } = useMapLineDrag(
	'route-hit',
	(from, to) => {
		if (isTouch.value) return
		const previewed = preview.answerFor(to)
		if (!previewed) dropped.value = to
		editing.dragLine(from, to, previewed)
	},
	() => !editing.isPending.value,
)
// While dragging, what letting go would make, where it has been previewed.
const preview = useDragPreview(grab, pointer, editing.previewDrag)

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

watch(editing.isPending, (pending) => {
	if (!pending) dropped.value = null
})

// How the course is printed. Faded: it no longer holds, because the settings changed or because a
// drag is previewing what replaces it. Updating: an edit of it is on its way.
const look = computed<'printed' | 'faded' | 'updating'>(() => {
	if (editing.isPending.value) return 'updating'
	return planner.isStale || preview.answer.value ? 'faded' : 'printed'
})
const DASHED = [1.5, 1]
const SOLID = [1, 0]
useMapPaint('route-line', 'line-color', () =>
	tokenColor(look.value === 'faded' ? '--overprint-faded' : '--overprint'),
)
useMapPaint('route-edge', 'line-color', () =>
	tokenColor(look.value === 'faded' ? '--line-strong' : '--overprint-contrast'),
)
useMapPaint('route-line', 'line-dasharray', () => (look.value === 'updating' ? DASHED : SOLID))
// Out of date, the other options step back further, below the faded course.
useMapPaint('route-options', 'line-opacity', () => (planner.isStale ? 0.35 : 0.75))

// The preview is printed as the course, over the faded one it would replace.
const previewLine = computed<MapData>(() => {
	const previewed = preview.answer.value
	return previewed ? { ...previewed.answer.route, properties: {} } : EMPTY
})
useMapSource('route-preview', previewLine, [
	{
		id: 'route-preview-edge',
		type: 'line',
		layout: round,
		paint: { 'line-color': tokenColor('--overprint-contrast'), 'line-width': 7 },
	},
	{
		id: 'route-preview',
		type: 'line',
		layout: round,
		paint: { 'line-color': tokenColor('--overprint'), 'line-width': 4 },
	},
])
// The held handle: at the pointer while dragging, then at the drop until the edit answers.
const held = computed(() => pointer.value ?? grab.value ?? dropped.value)
watch(grab, (from) => planner.setDraggingLine(from !== null))
onScopeDispose(() => planner.setDraggingLine(false))

const handlePoints = computed(() =>
	shown.value && planner.edit?.option === planner.selectedOption
		? planner.editHandles.map((handle) => handle.at)
		: [],
)

// The handle under the pointer, on a mouse: where a drag would take the line from.
const ghost = computed(() => (!isTouch.value && !grab.value && hover.value) || null)

useMapClick(['route-options', 'route-hit'], (feature, at) => {
	if (feature?.layerId === 'route-options') planner.selectOption(Number(feature.properties.index))
	tapped.value = isTouch.value && feature?.layerId === 'route-hit' ? at : null
})

// Dropped back where it was tapped, a touch drag is called off.
const TAP_CANCEL_M = 10

function dragTapped(to: LonLat): void {
	if (tapped.value && distanceM(tapped.value, to) > TAP_CANCEL_M && !editing.isPending.value) {
		editing.dragLine(tapped.value, to)
	}
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
		<span class="block size-3 rounded-full border-2 border-overprint-contrast bg-paper" />
	</MapMarker>
	<MapMarker v-if="held" :lon-lat="held" class="pointer-events-none">
		<span class="block size-5 rounded-full border-2 border-overprint-contrast bg-overprint" />
	</MapMarker>
	<EditHandles
		:handles="handlePoints"
		:tapped="tapped"
		:locked="editing.isPending.value"
		@move="editing.moveHandle"
		@remove="editing.removeHandle"
		@drag-tapped="dragTapped"
	/>
</template>
