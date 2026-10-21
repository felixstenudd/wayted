<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { usePlannerStore } from '../store'
import DistanceField from './DistanceField.vue'
import FindRoutes from './FindRoutes.vue'
import PreferenceSection from './PreferenceSection.vue'
import RouteKindFields from './RouteKindFields.vue'
import RoutePoints from './RoutePoints.vue'
import ThroughPointSettings from './ThroughPointSettings.vue'

defineProps<{
	/**
	 * panel: floating beside the map, Find routes pinned at the bottom.
	 * sheet: the rest of a bottom sheet whose header holds PlannerEssentials.
	 */
	layout: 'panel' | 'sheet'
}>()

const { t } = useI18n()
const planner = usePlannerStore()

// On a phone a through point's settings take the sheet over; on a desktop they open on the map.
const editingPoint = computed(() =>
	planner.throughPoints.find((point) => point.id === planner.editingThroughPointId),
)
</script>

<template>
	<div v-if="layout === 'panel'" class="flex flex-col">
		<div class="flex flex-col gap-5 p-5">
			<h1 class="text-heading">{{ t('planner.title') }}</h1>
			<RouteKindFields />
			<RoutePoints />
			<DistanceField />
			<PreferenceSection />
		</div>
		<div class="sticky bottom-0 border-t border-line bg-paper px-5 pt-4 pb-5">
			<FindRoutes />
		</div>
	</div>
	<div v-else-if="editingPoint" class="border-t border-line pt-4">
		<h1 class="sr-only">{{ t('planner.title') }}</h1>
		<ThroughPointSettings
			:point="editingPoint"
			title-id="through-point-sheet-title"
			id-prefix="through-point-sheet"
		/>
	</div>
	<div v-else class="flex flex-col gap-5 border-t border-line pt-4">
		<h1 class="sr-only">{{ t('planner.title') }}</h1>
		<RouteKindFields />
		<RoutePoints />
		<PreferenceSection />
	</div>
</template>
