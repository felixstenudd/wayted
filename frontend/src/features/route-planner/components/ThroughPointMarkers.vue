<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { MapMarker } from '@/features/map'
import { CourseSymbol } from '@/shared/ui/course-symbol'

import { useFoundRoute } from '../api'
import { usePlannerStore } from '../store'
import { throughPointNumbers } from '../throughPoints'

const { t } = useI18n()
const planner = usePlannerStore()
const state = useFoundRoute()

// Numbered once a route says the order the planner chose; any change drops the route again.
const numbers = computed(() =>
	throughPointNumbers(
		state.value.status === 'found'
			? (state.value.routes[0]?.properties.waypoint_order ?? null)
			: null,
		planner.throughPoints.length,
	),
)

function label(number: number | undefined): string {
	return number === undefined
		? t('planner.points.through.marker')
		: t('planner.points.through.numberedMarker', { n: number })
}
</script>

<template>
	<MapMarker
		v-for="(point, index) in planner.throughPoints"
		:key="point.id"
		:lon-lat="point.lonLat"
		:label="label(numbers[index])"
		draggable
		@move="planner.moveThroughPoint(point.id, $event)"
	>
		<CourseSymbol
			kind="control"
			:control-number="numbers[index]"
			class="size-6 cursor-grab sm:size-7"
		/>
	</MapMarker>
</template>
