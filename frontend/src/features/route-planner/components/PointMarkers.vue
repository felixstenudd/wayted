<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { MapMarker, useMapClickAt } from '@/features/map'
import { CourseSymbol } from '@/shared/ui/course-symbol'

import { useShownRoute } from '../composables/useShownRoute'
import { usePlannerStore } from '../store'

const { t } = useI18n()
const planner = usePlannerStore()
const { shown } = useShownRoute()

// A click beside an open through point's settings closes them, and places nothing.
useMapClickAt((at) => {
	if (planner.editingThroughPointId !== null) planner.editThroughPoint(null)
	else planner.placeNextPoint(at, shown.value !== null)
})
</script>

<template>
	<MapMarker
		v-if="planner.start"
		:lon-lat="planner.start"
		:label="t('planner.points.start')"
		draggable
		@move="planner.start = $event"
	>
		<CourseSymbol kind="start" class="size-6 cursor-grab sm:size-7" />
	</MapMarker>
	<MapMarker
		v-if="planner.shape === 'point_to_point' && planner.finish"
		:lon-lat="planner.finish"
		:label="t('planner.points.finish')"
		draggable
		@move="planner.finish = $event"
	>
		<CourseSymbol kind="finish" class="size-6 cursor-grab sm:size-7" />
	</MapMarker>
</template>
