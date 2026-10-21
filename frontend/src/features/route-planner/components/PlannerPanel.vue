<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useShownRoute } from '../composables/useShownRoute'
import { usePlannerStore } from '../store'
import DistanceField from './DistanceField.vue'
import FindRoutes from './FindRoutes.vue'
import PlanAgainNotice from './PlanAgainNotice.vue'
import PreferenceSection from './PreferenceSection.vue'
import RouteKindFields from './RouteKindFields.vue'
import RoutePoints from './RoutePoints.vue'
import RouteView from './RouteView.vue'
import SaveRoute from './SaveRoute.vue'
import SettingsLine from './SettingsLine.vue'
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
const { shown } = useShownRoute()

// Two phases: setting up, then the routes found with their settings folded into one line.
const isShowingRoute = computed(() => shown.value !== null && !planner.isChangingSettings)
const plannedWith = computed(() => (shown.value ? (planner.search?.request ?? null) : null))

// On a phone a through point's settings take the sheet over; on a desktop they open on the map.
const editingPoint = computed(() =>
	planner.throughPoints.find((point) => point.id === planner.editingThroughPointId),
)
</script>

<template>
	<div v-if="layout === 'panel'" class="flex flex-col">
		<div class="px-5 pt-5 empty:hidden"><PlanAgainNotice /></div>
		<div v-if="isShowingRoute" class="p-5">
			<h1 class="sr-only">{{ t('planner.title') }}</h1>
			<RouteView layout="panel" />
		</div>
		<div v-else class="flex flex-col gap-5 p-5">
			<SettingsLine
				v-if="plannedWith"
				:request="plannedWith"
				:action="t('planner.settingsLine.done')"
				@action="planner.changeSettings(false)"
			/>
			<h1 :class="plannedWith ? 'sr-only' : 'text-heading'">{{ t('planner.title') }}</h1>
			<RouteKindFields />
			<RoutePoints />
			<DistanceField />
			<PreferenceSection />
		</div>
		<!-- The phase's one main action: find routes while setting up, then save the one shown. -->
		<div class="sticky bottom-0 border-t border-line bg-paper px-5 pt-4 pb-5">
			<SaveRoute v-if="isShowingRoute" />
			<FindRoutes v-else />
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
	<div v-else-if="isShowingRoute" class="border-t border-line pt-4">
		<h1 class="sr-only">{{ t('planner.title') }}</h1>
		<RouteView layout="sheet" />
	</div>
	<div v-else class="flex flex-col gap-5 border-t border-line pt-4">
		<h1 class="sr-only">{{ t('planner.title') }}</h1>
		<SettingsLine
			v-if="plannedWith"
			:request="plannedWith"
			:action="t('planner.settingsLine.done')"
			@action="planner.changeSettings(false)"
		/>
		<RouteKindFields />
		<RoutePoints />
		<PreferenceSection />
	</div>
</template>
