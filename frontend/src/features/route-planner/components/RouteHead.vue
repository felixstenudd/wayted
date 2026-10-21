<script setup lang="ts">
import { CircleAlert, TriangleAlert } from '@lucide/vue'
import { useIsMutating } from '@tanstack/vue-query'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { rerouteKey } from '../api'
import { useShownRoute } from '../composables/useShownRoute'
import { useSkippedThroughPoints } from '../composables/useSkippedThroughPoints'
import { useThroughPointNumbers } from '../composables/useThroughPointNumbers'
import { formatKm } from '../distance'
import { optionLetter, routeFit } from '../options'
import { usePlannerStore } from '../store'

const { t } = useI18n()
const planner = usePlannerStore()
const { routes, shown } = useShownRoute()
const skipped = useSkippedThroughPoints()
const { nameOf } = useThroughPointNumbers()
const rerouting = useIsMutating({ mutationKey: rerouteKey })
const isRerouting = computed(() => rerouting.value > 0)

const targetKm = computed(() => formatKm((planner.search?.request.target_distance_m ?? 0) / 1000))
// The planner's warnings explain what it found; an edited route is the user's own, so it is only
// said how far off the target it is.
const isEdited = computed(() => planner.edit?.option === planner.selectedOption)
// With options to choose from, their cards say the length and letter; the head only updates.
const hasCards = computed(() => routes.value.length > 1 && !planner.isChosen)
const editedFit = computed(() => {
	if (!isEdited.value || !shown.value || shown.value.properties.warnings.length === 0) return null
	const fit = routeFit(shown.value.properties.length_m, planner.search?.request.target_distance_m)
	return fit && fit.kind !== 'close' ? fit : null
})
const plannerWarnings = computed(() =>
	isEdited.value ? [] : (shown.value?.properties.warnings ?? []),
)
</script>

<template>
	<!-- The shown route's length, which option it is, and why it misses the target if it does. -->
	<div v-if="shown" role="status" class="flex flex-col gap-1 empty:hidden">
		<div v-if="!hasCards || isRerouting" class="flex items-baseline justify-between gap-3">
			<p class="text-heading" :class="{ 'text-graphite': isRerouting }">
				{{
					isRerouting
						? t('planner.edit.updating')
						: t('planner.route.length', {
								km: formatKm(shown.properties.length_m / 1000),
							})
				}}
			</p>
			<p v-if="hasCards" class="text-small text-graphite">
				{{ t('planner.options.name', { letter: optionLetter(planner.selectedOption) }) }}
			</p>
		</div>
		<p v-if="editedFit" class="flex gap-1.5 text-small text-graphite">
			<TriangleAlert class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
			{{
				t(editedFit.kind === 'long' ? 'planner.edit.longer' : 'planner.edit.shorter', {
					km: formatKm(editedFit.km),
					target: targetKm,
				})
			}}
		</p>
		<p
			v-for="warning in plannerWarnings"
			:key="warning"
			class="flex gap-1.5 text-small text-graphite"
		>
			<TriangleAlert class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
			{{ t(`planner.route.warnings.${warning}`, { km: targetKm }) }}
		</p>
		<p v-for="id in skipped" :key="id" class="flex gap-1.5 text-small text-graphite">
			<TriangleAlert class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
			{{ t('planner.edit.skips', { name: nameOf(id) }) }}
		</p>
		<p v-if="planner.isDraggingLine" role="status" class="text-small text-graphite">
			{{ t('planner.edit.dragging') }}
		</p>
		<p v-if="planner.editError" role="alert" class="flex gap-1.5 text-small text-contour">
			<CircleAlert class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
			{{
				planner.editError === 'dropOffRoad'
					? t(
							`planner.edit.errors.dropOffRoad.${planner.search?.request.activity ?? 'running'}`,
						)
					: t(`planner.edit.errors.${planner.editError}`)
			}}
		</p>
	</div>
</template>
