<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import {
	EMPTY,
	MapMarker,
	tokenColor,
	useMapClickAt,
	useMapSource,
	type LonLat,
	type MapData,
} from '@/features/map'

import { useStretchPick } from '../composables/useStretchPick'
import { useSavedRoutesStore } from '../store'

const props = defineProps<{ routeId: number }>()

const { t } = useI18n()
const pick = useStretchPick(() => props.routeId)
const store = useSavedRoutesStore()
// Once the review is being written, the stretch stays put.
const canMove = computed(() => store.stretchStage === 'pick')

const stretchLine = computed<MapData>(() =>
	pick.line.value.length > 1
		? {
				type: 'Feature',
				geometry: { type: 'LineString', coordinates: pick.line.value.map((p) => [...p]) },
				properties: {},
			}
		: EMPTY,
)
const fromPoint = computed(() =>
	pick.stretch.value ? pick.pointOf(pick.stretch.value.from) : null,
)
const toPoint = computed(() => (pick.stretch.value ? pick.pointOf(pick.stretch.value.to) : null))

// A dropped handle has to come back to its junction even when the junction is the same one,
// so each drop draws the handles anew.
const drops = ref(0)
function drop(which: 'from' | 'to', at: LonLat): void {
	pick.moveEnd(which, at)
	drops.value++
}

const round = { 'line-cap': 'round', 'line-join': 'round' } as const
// The stretch stays bright over the dimmed course, and a heavy bracket runs beside it: a pencil
// mark next to the course line, not on it.
useMapSource('saved-route-stretch', stretchLine, [
	{
		id: 'saved-route-stretch-casing',
		type: 'line',
		layout: round,
		paint: { 'line-color': tokenColor('--overprint-contrast'), 'line-width': 8 },
	},
	{
		id: 'saved-route-stretch',
		type: 'line',
		layout: round,
		paint: { 'line-color': tokenColor('--overprint'), 'line-width': 5 },
	},
	{
		id: 'saved-route-stretch-bracket',
		type: 'line',
		layout: round,
		paint: {
			'line-color': tokenColor('--overprint-contrast'),
			'line-width': 4,
			'line-offset': 11,
		},
	},
])
useMapClickAt((at) => {
	if (canMove.value) pick.placeAt(at)
})
</script>

<template>
	<MapMarker
		v-if="pick.lonePoint.value"
		:lon-lat="pick.lonePoint.value"
		:label="t('savedRoutes.stretch.startHere')"
	>
		<span
			class="block size-3.5 rounded-full border-[2.5px] border-overprint-contrast bg-overprint"
		/>
	</MapMarker>
	<template v-if="canMove && fromPoint && toPoint">
		<MapMarker
			:key="`from-${drops}`"
			:lon-lat="fromPoint"
			:label="t('savedRoutes.stretch.fromHandle')"
			draggable
			@move="drop('from', $event)"
		>
			<span class="grid size-11 cursor-grab place-items-center">
				<span
					class="block size-3.5 rounded-full border-[2.5px] border-overprint-contrast bg-overprint"
				/>
			</span>
		</MapMarker>
		<MapMarker
			:key="`to-${drops}`"
			:lon-lat="toPoint"
			:label="t('savedRoutes.stretch.toHandle')"
			draggable
			@move="drop('to', $event)"
		>
			<span class="grid size-11 cursor-grab place-items-center">
				<span
					class="block size-3.5 rounded-full border-[2.5px] border-overprint-contrast bg-overprint"
				/>
			</span>
		</MapMarker>
	</template>
</template>
