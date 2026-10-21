<script setup lang="ts">
import { CircleAlert, Crosshair, LoaderCircle, Navigation, X } from '@lucide/vue'
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useMapView, type LonLat } from '@/features/map'
import { Button } from '@/shared/ui/button'

import { useCurrentLocation } from '../composables/useCurrentLocation'
import { usePlannerStore } from '../store'
import PointRow from './PointRow.vue'
import ThroughPointRow from './ThroughPointRow.vue'

type Point = 'start' | 'finish'

const { t } = useI18n()
const planner = usePlannerStore()
const { center, showPoint } = useMapView()
const location = useCurrentLocation()

const points = computed<Point[]>(() =>
	planner.shape === 'point_to_point' ? ['start', 'finish'] : ['start'],
)

// A start placed some other way makes a failed lookup old news.
watch(
	() => planner.start,
	() => {
		location.error.value = null
	},
)

function hint(point: Point): string {
	if (planner[point] !== null) return t('planner.points.placedHint')
	return planner.missingPoint === point
		? t('planner.points.clickHint')
		: t('planner.points.afterStartHint')
}

function place(point: Point, at: LonLat | null): void {
	if (at) planner[point] = at
}

async function useMyLocation(): Promise<void> {
	const at = await location.locate()
	if (!at) return
	planner.start = at
	showPoint(at)
}
</script>

<template>
	<section :aria-label="t('planner.points.label')" class="flex flex-col gap-3">
		<PointRow
			v-for="point in points"
			:key="point"
			:kind="point"
			:label="t(`planner.points.${point}`)"
			:hint="hint(point)"
		>
			<template #actions>
				<Button
					v-if="point === 'start'"
					variant="ghost"
					size="icon"
					:aria-label="
						location.isLocating.value
							? t('planner.points.locating')
							: t('planner.points.useMyLocation')
					"
					:title="t('planner.points.useMyLocation')"
					:aria-busy="location.isLocating.value"
					:disabled="location.isLocating.value"
					@click="useMyLocation"
				>
					<LoaderCircle v-if="location.isLocating.value" class="animate-spin" />
					<Navigation v-else />
				</Button>
				<Button
					variant="ghost"
					size="icon"
					:aria-label="t(`planner.points.placeAtCenter.${point}`)"
					:title="t(`planner.points.placeAtCenter.${point}`)"
					@click="place(point, center())"
				>
					<Crosshair />
				</Button>
				<Button
					v-if="planner[point] !== null"
					variant="ghost"
					size="icon"
					:aria-label="t(`planner.points.remove.${point}`)"
					:title="t(`planner.points.remove.${point}`)"
					@click="planner[point] = null"
				>
					<X />
				</Button>
			</template>
		</PointRow>
		<ThroughPointRow />
		<p
			v-if="location.error.value"
			role="alert"
			class="flex items-start gap-1.5 text-small text-contour"
		>
			<CircleAlert class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
			{{ t(`planner.points.locationErrors.${location.error.value}`) }}
		</p>
	</section>
</template>
