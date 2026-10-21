<script setup lang="ts">
import { Crosshair, X } from '@lucide/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useMapView } from '@/features/map'
import { useMediaQuery } from '@/shared/composables/useMediaQuery'
import { Button } from '@/shared/ui/button'

import { useShownRoute } from '../composables/useShownRoute'
import { usePlannerStore } from '../store'
import PointRow from './PointRow.vue'

const { t } = useI18n()
const planner = usePlannerStore()
const { shown } = useShownRoute()
const { center } = useMapView()
const isTouch = useMediaQuery('(pointer: coarse)')

const count = computed(() => planner.throughPoints.length)
const hint = computed(() => {
	if (count.value > 0)
		return t(
			isTouch.value
				? 'planner.points.through.addedTapHint'
				: 'planner.points.through.addedHint',
			{ n: count.value },
			count.value,
		)
	if (planner.missingPoint === 'start') return t('planner.points.through.afterStartHint')
	if (planner.missingPoint === 'finish') return t('planner.points.through.afterFinishHint')
	// While a route is shown a map click adds nothing; the button still does.
	if (shown.value !== null) return t('planner.points.through.routeShownHint')
	return t(isTouch.value ? 'planner.points.through.tapHint' : 'planner.points.through.clickHint')
})

function addAtCenter(): void {
	const at = center()
	if (at) planner.addThroughPoint(at)
}
</script>

<template>
	<PointRow kind="control" :label="t('planner.points.through.label')" :hint="hint">
		<template #actions>
			<Button
				variant="ghost"
				size="icon"
				:aria-label="t('planner.points.through.addAtCenter')"
				:title="t('planner.points.through.addAtCenter')"
				@click="addAtCenter"
			>
				<Crosshair />
			</Button>
			<Button
				v-if="count > 0"
				variant="ghost"
				size="icon"
				:aria-label="t('planner.points.through.removeAll')"
				:title="t('planner.points.through.removeAll')"
				@click="planner.clearThroughPoints()"
			>
				<X />
			</Button>
		</template>
	</PointRow>
</template>
