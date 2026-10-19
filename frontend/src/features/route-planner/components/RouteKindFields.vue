<script setup lang="ts">
import { ArrowRight, Bike, Footprints, Repeat } from '@lucide/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { SegmentedControl } from '@/shared/ui/segmented-control'

import { usePlannerStore } from '../store'
import type { Activity } from '../types'

const { t } = useI18n()
const planner = usePlannerStore()

// Through the store's setter, so the distance follows the activity's range.
const activity = computed({
	get: () => planner.activity,
	set: (next: Activity) => planner.setActivity(next),
})

const activities = computed(() => [
	{ value: 'running' as const, label: t('planner.activity.running'), icon: Footprints },
	{ value: 'cycling' as const, label: t('planner.activity.cycling'), icon: Bike },
])
const shapes = computed(() => [
	{ value: 'loop' as const, label: t('planner.shape.loop'), icon: Repeat },
	{ value: 'point_to_point' as const, label: t('planner.shape.pointToPoint'), icon: ArrowRight },
])
</script>

<template>
	<div class="grid grid-cols-2 gap-2">
		<SegmentedControl
			v-model="activity"
			:label="t('planner.activity.label')"
			:options="activities"
		/>
		<SegmentedControl
			v-model="planner.shape"
			:label="t('planner.shape.label')"
			:options="shapes"
		/>
	</div>
</template>
