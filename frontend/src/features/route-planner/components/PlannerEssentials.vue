<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { Button } from '@/shared/ui/button'

import { useShownRoute } from '../composables/useShownRoute'
import { useThroughPointNumbers } from '../composables/useThroughPointNumbers'
import { usePlannerStore } from '../store'
import DistanceField from './DistanceField.vue'
import FindRoutes from './FindRoutes.vue'
import PlanAgainNotice from './PlanAgainNotice.vue'
import EditedBar from './EditedBar.vue'
import RouteHead from './RouteHead.vue'
import RouteOptions from './RouteOptions.vue'
import SaveRoute from './SaveRoute.vue'

const { t } = useI18n()
const planner = usePlannerStore()
const { nameOf } = useThroughPointNumbers()

const { shown } = useShownRoute()

const MISSING_ID = 'sheet-missing-point'

const editingId = computed(() => planner.editingThroughPointId)
const isShowingRoute = computed(() => shown.value !== null && !planner.isChangingSettings)
</script>

<template>
	<!-- While a through point's settings fill the sheet, its name and the way back head it. -->
	<div v-if="editingId !== null" class="flex items-baseline justify-between gap-3">
		<h2 id="through-point-sheet-title" class="text-title">{{ nameOf(editingId) }}</h2>
		<Button variant="ghost" class="-my-2 -mr-3 h-11" @click="planner.editThroughPoint(null)">
			{{ t('planner.points.through.done') }}
		</Button>
	</div>
	<!-- What a phone shows at the sheet's lowest stop: enough to go. -->
	<div v-else class="flex flex-col gap-3">
		<PlanAgainNotice />
		<template v-if="isShowingRoute">
			<RouteOptions />
			<EditedBar />
			<RouteHead />
			<template v-if="planner.isStale">
				<FindRoutes />
				<SaveRoute quiet />
			</template>
			<SaveRoute v-else />
		</template>
		<template v-else>
			<!-- The first thing to do. -->
			<p v-if="planner.missingPoint" :id="MISSING_ID">
				{{ t(`planner.sheet.missing.${planner.missingPoint}`) }}
			</p>
			<DistanceField />
			<FindRoutes :missing-hint-id="MISSING_ID" />
		</template>
	</div>
</template>
